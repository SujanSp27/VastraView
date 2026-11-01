"""Deterministic single-view estimates. These are not measured body circumferences."""

import hashlib
import json
import math
from dataclasses import replace
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import numpy as np
from PIL import Image, ImageDraw

from backend.app.anthropometry.diagnostics import diagnostic
from backend.app.anthropometry.measurement_evidence import (
    VISIBILITY_THRESHOLD,
    annotate_evidence,
    calibrate,
    quality,
    uncertain_arm_is_separate,
)
from backend.app.anthropometry.measurement_evidence import (
    usable as usable_landmarks,
)
from backend.app.anthropometry.measurement_refinement import (
    MASK_SUFFIXES,
    RECOVERABLE_REASONS,
    guard_refined_mask,
    merge_recovered,
    needs_refinement,
)
from backend.app.anthropometry.pose_adapter import (
    MediaPipePose,
    PoseObservation,
    decode_person,
    refine_mask,
)
from backend.app.anthropometry.schemas import ExtractionResponse, PhotoMeasurements
from backend.app.anthropometry.semantic_measurement import (
    TARGETS,
    boundary_evidence,
    folded_forearm_at_section,
    region_mask,
)
from ml.errors import PipelineError

KEY_LANDMARKS = {
    0: "nose", 11: "left shoulder", 12: "right shoulder",
    23: "left hip", 24: "right hip", 25: "left knee", 26: "right knee",
    27: "left ankle", 28: "right ankle", 29: "left heel", 30: "right heel",
}
KAPPA = {"chest": 2.45, "waist": 2.30, "hip": 2.40, "thigh": 2.50}
KAPPA_MALE = {"chest": 2.40, "waist": 2.30, "hip": 2.35, "thigh": 2.50}
KAPPA_FEMALE = {"chest": 2.50, "waist": 2.30, "hip": 2.45, "thigh": 2.50}
THIGH_FRACTION = 0.40  # Hip joints sit above the crotch; 25% often spans both legs.
CHEST_FRACTIONS = (0.25, 0.30, 0.35, 0.40, 0.45)
CHEST_FRACTIONS_MALE = (0.25, 0.28, 0.32, 0.36, 0.40)
CHEST_FRACTIONS_FEMALE = (0.30, 0.33, 0.36, 0.40, 0.44)
WAIST_FRACTIONS_MALE = (0.50, 0.54, 0.58, 0.62)
WAIST_FRACTIONS_FEMALE = (0.46, 0.49, 0.52, 0.56)

REASON_MESSAGES = {
    "shoulder_landmarks_uncertain": "Shoulder position or viewing angle is uncertain. Face forward or enter this tape measurement.",
    "torso_landmarks_uncertain": "Shoulders or hips cannot locate this torso region reliably. Retry a clear front view or enter a tape measurement.",
    "hip_outline_unavailable": "The outer hip outline is obscured or incomplete. Keep your full hip outline visible. Avoid loose clothing covering your hip area.",
    "ambiguous_thigh": "Both upper-thigh boundaries cannot be distinguished reliably. Keep your hands away from your thighs and leave a small gap between your legs.",
    "hand_overlaps_thigh": "A hand or arm touches the upper-thigh outline, so its width cannot be isolated reliably. Keep your hands away from your thighs and leave a small gap between your legs.",
    "leg_geometry_uncertain": "Leg landmarks, overlap or a bent stance prevent this estimate. Enter a tape measurement or stand upright with uncrossed legs.",
    "implausible_geometry": "This region is inconsistent with the entered height. Confirm the height or enter a tape measurement.",
    "arms_overlap_torso": "Arms overlap the visible torso outline; no body boundary was invented. Move arms slightly away or enter this tape measurement.",
    "arm_landmarks_uncertain": "Elbows or wrists are unclear or outside the frame; arm separation cannot be verified. Keep both arms visible or enter this tape measurement.",
    "wide_clothing_outline": "The visible outline is wide relative to the shoulders. Loose/layered clothing or body shape may explain it; confirm with a tape measure.",
    "asymmetric_outline": "The two torso sides disagree. Clothing, an accessory or occlusion may affect the outline; confirm with a tape measure.",
    "torso_segmentation_failed": "No reliable torso edge was found here. Try a contrasting background or enter this tape measurement.",
}
WAIST_FRACTIONS = (0.50, 0.48, 0.52)  # Local band only; do not substitute hips for waist.


def validate_pose(observation: PoseObservation) -> np.ndarray:
    if observation.image.ndim != 3 or observation.image.shape[2] != 3 or min(observation.image.shape[:2]) < 4:
        raise PipelineError("invalid_image", "Expected a valid RGB image for measurement.")
    landmarks = observation.landmarks
    if (landmarks.shape != (33, 4) or not np.isfinite(landmarks).all()
            or np.any((landmarks[:, 3] < 0) | (landmarks[:, 3] > 1))):
        raise PipelineError("invalid_pose", "Expected 33 finite MediaPipe landmarks.")
    h, w = observation.image.shape[:2]
    if observation.mask.shape != (h, w):
        raise PipelineError("invalid_mask", "Person mask dimensions do not match the image.")
    if not np.isfinite(observation.mask).all() or not np.isin(observation.mask, (0, 1)).all():
        raise PipelineError("invalid_mask", "Expected a binary person mask aligned with the processed image.")
    if not observation.mask.any():
        raise PipelineError("segmentation_missing", "No person outline was found. Use a contrasting background and retry.")
    if observation.presence is not None and (
        observation.presence.shape != (33,) or not np.isfinite(observation.presence).all()
        or np.any((observation.presence < 0) | (observation.presence > 1))
    ):
        raise PipelineError("invalid_pose", "Expected valid landmark presence probabilities.")
    valid = usable_landmarks(observation)
    diagnostic("pose_validation", key_visibility={name: round(float(landmarks[i, 3]), 4)
               for i, name in KEY_LANDMARKS.items()}, unusable_indices=np.flatnonzero(~valid).tolist())
    points = landmarks[:, :2] * [w, h]
    return points


def silhouette_width(mask: np.ndarray, center: np.ndarray, direction: np.ndarray):
    """Connected foreground span through the anatomical anchor; never a whole-row bbox."""
    direction = direction / np.linalg.norm(direction)
    radius = int(math.hypot(*mask.shape))
    offsets = np.arange(-radius, radius + 1)
    coordinates = np.rint(center + offsets[:, None] * direction).astype(int)
    x, y = coordinates.T
    inside = (x >= 0) & (x < mask.shape[1]) & (y >= 0) & (y < mask.shape[0])
    foreground = np.zeros(len(offsets), dtype=bool)
    foreground[inside] = mask[y[inside], x[inside]] > 0
    if not foreground[radius]:
        raise PipelineError("ambiguous_silhouette", "Body landmarks are outside the person mask; use a clear contrasting background.")
    left = right = radius
    while left > 0 and foreground[left - 1]:
        left -= 1
    while right + 1 < len(offsets) and foreground[right + 1]:
        right += 1
    endpoints = coordinates[[left, right]]
    if (not inside[left] or not inside[right] or left == 0 or right == len(offsets) - 1
            or np.any(endpoints <= 0)
            or np.any(endpoints >= np.array([mask.shape[1] - 1, mask.shape[0] - 1]))):
        raise PipelineError("partial_body", "Body outline reaches the image boundary.")
    width = float(offsets[right] - offsets[left] + 1)
    if width < 4:
        raise PipelineError("ambiguous_silhouette", "Body outline is too small to measure reliably.")
    return width, (center + offsets[left] * direction, center + offsets[right] * direction)


def band_width(mask, center, direction, axis):
    # Median over five adjacent sections limits isolated segmentation speckles.
    samples = [silhouette_width(mask, center + shift * axis, direction) for shift in (-2, -1, 0, 1, 2)]
    return sorted(samples, key=lambda item: item[0])[2]


def intersects_arm(segment, points, visibility) -> bool:
    """Reject a torso section that includes a confidently detected arm centerline."""
    start, end = segment
    line = end - start
    for a, b in ((11, 13), (13, 15), (12, 14), (14, 16)):
        if min(visibility[[a, b]]) <= VISIBILITY_THRESHOLD:
            continue
        limb = points[b] - points[a]
        matrix = np.column_stack((line, -limb))
        if abs(np.linalg.det(matrix)) < 1e-6:
            # A forearm lying along the section is an overlap, not a safe skip.
            length = np.linalg.norm(line)
            if length and abs(float(np.linalg.det(np.column_stack((line, points[a] - start))))) / length < 1:
                projections = sorted(float(np.dot(points[i] - start, line) / (length * length)) for i in (a, b))
                if projections[0] <= 1 and projections[1] >= 0:
                    return True
            continue
        along_section, along_arm = np.linalg.solve(matrix, points[a] - start)
        if 0 <= along_section <= 1 and 0 <= along_arm <= 1:
            return True
    return False


def connected_hand_near_section(observation, points, valid, segment):
    """Flag a visible hand joined to a measured span, without cutting a body edge.

    Pose's sparse finger landmarks do not describe the fingertips/hand contour.
    Half the observed wrist-to-finger span is a conservative uncertainty margin,
    not an inferred hand mask. Require a foreground path as well as proximity so
    an adjacent hand separated by a real background gap does not reject a leg.
    """
    start, end = segment
    line = end - start
    squared_length = float(np.dot(line, line))
    if squared_length <= 0:
        return False
    for wrist, fingers in ((15, (17, 19, 21)), (16, (18, 20, 22))):
        visible = [index for index in fingers if valid[index]]
        if not valid[wrist] or len(visible) < 2:
            continue
        margin = .5 * max(float(np.linalg.norm(points[index] - points[wrist])) for index in visible)
        for index in visible:
            point = points[index]
            projected = start + np.clip(np.dot(point - start, line) / squared_length, 0, 1) * line
            distance = float(np.linalg.norm(point - projected))
            if distance > margin:
                continue
            path = np.rint(np.linspace(point, projected, max(2, math.ceil(distance) + 1))).astype(int)
            if observation.mask[path[:, 1], path[:, 0]].all():
                return True
    return False


def torso_sections(observation: PoseObservation, points: np.ndarray, region_labels=None, gender: str | None = None):
    """Use observed central spans only; never cut an arm off at an invented body edge."""
    shoulder, hip = points[[11, 12]].mean(0), points[[23, 24]].mean(0)
    axis = (hip - shoulder) / np.linalg.norm(hip - shoulder)
    direction = np.array([axis[1], -axis[0]])
    shoulder_width = float(np.linalg.norm(points[11] - points[12]))
    valid = usable_landmarks(observation)
    arms_known = bool(valid[[11, 12, 13, 14, 15, 16]].all())
    widths, fractions, quality, sections = {}, {}, {}, []
    if gender == "male":
        chest_candidates = CHEST_FRACTIONS_MALE
        waist_candidates = WAIST_FRACTIONS_MALE if region_labels is None else (.48, .52, .56, .60, .64, .68)
    elif gender == "female":
        chest_candidates = CHEST_FRACTIONS_FEMALE
        waist_candidates = WAIST_FRACTIONS_FEMALE if region_labels is None else (.44, .48, .50, .54, .58, .62, .66)
    else:
        chest_candidates = CHEST_FRACTIONS
        waist_candidates = WAIST_FRACTIONS if region_labels is None else (.50, .48, .52, .56, .60, .64, .68, .72)
    for name, candidates in (("chest", chest_candidates), ("waist", waist_candidates)):
        samples, usable = [], []
        for fraction in candidates:
            center = shoulder * (1 - fraction) + hip * fraction
            try:
                width, segment = band_width(observation.mask, center, direction, axis)
            except PipelineError as exc:
                samples.append({"fraction": fraction, "rejected": "torso_segmentation_failed", "code": exc.code})
                continue
            left, right = (float(np.linalg.norm(end - center)) for end in segment)
            edge = boundary_evidence(observation.image, region_labels, segment, axis) if region_labels is not None else None
            crossing = intersects_arm(segment, points, np.where(valid, observation.landmarks[:, 3], 0))
            if region_labels is not None:
                crossing |= folded_forearm_at_section(points, valid, segment, edge)
            arm_evidence = arms_known or uncertain_arm_is_separate(observation, points, center, valid)
            sample = {"fraction": fraction, "width_pixels": width,
                      "left_pixels": round(left, 2), "right_pixels": round(right, 2),
                      "arm_overlap": crossing, "arm_evidence": arm_evidence}
            samples.append(sample)
            if edge is not None:
                sample["boundary_evidence"] = edge
            if not crossing and arm_evidence and (edge is None or edge["accepted"]):
                usable.append((fraction, width, segment, left, right))
        metric = name + "_circumference"
        if not usable:
            reason = ("arm_landmarks_uncertain" if not arms_known else
                      "arms_overlap_torso" if any(s.get("arm_overlap") for s in samples) else
                      "torso_segmentation_failed")
            quality[metric] = {"status": "unavailable", "reason": reason, "requires_manual_review": True}
            widths[name], fractions[name] = None, None
        else:
            # Prefer a non-wide, symmetric natural silhouette at the intended level.
            # The old width ratio remains a review heuristic, never an anatomical verdict.
            def suspicious(item):
                return item[1] > 1.65 * shoulder_width or abs(item[3] - item[4]) / item[1] > .35
            selected = next((item for item in usable if not suspicious(item)), usable[0])
            if region_labels is not None:
                eligible = [item for item in usable if not suspicious(item)] or usable
                selected = (min if name == "waist" else max)(eligible, key=lambda item: item[1])
            fraction, width, segment, left, right = selected
            wide = width > 1.65 * shoulder_width
            asymmetric = abs(left - right) / width > .35
            widths[name], fractions[name] = width, fraction
            sections.append((name, segment))
            quality[metric] = {
                "status": "review_required" if wide or asymmetric else "estimated",
                "reason": "wide_clothing_outline" if wide else "asymmetric_outline" if asymmetric else "observed_arm_free_span",
                "requires_manual_review": wide or asymmetric,
                "sample_fraction": fraction,
            }
            if region_labels is not None:
                quality[metric]["boundary_evidence"] = boundary_evidence(observation.image, region_labels, segment, axis)
        diagnostic("torso_sections", region=name, mask_size=list(observation.mask.shape[::-1]),
                   arm_landmarks_usable=arms_known, samples=samples, decision=quality[metric])
    return widths, fractions, quality, sections


def thigh_sections(observation, points, scale, *, region_labels=None, gender: str | None = None):
    valid = usable_landmarks(observation)
    widths, sections, sides = [], [], []
    for side, (hip, knee, other_hip, other_knee) in enumerate(((23, 25, 24, 26), (24, 26, 23, 25))):
        record = {"side": "left" if side == 0 else "right", "status": "unavailable", "samples": []}
        sides.append(record)
        # Both axes are needed to rule out a span containing the other leg.
        if not valid[[hip, knee, other_hip, other_knee]].all():
            record["reason"] = "leg_geometry_uncertain"
            continue
        axis = points[knee] - points[hip]
        if np.linalg.norm(axis) < 10 or axis[1] <= 0:
            continue
        axis /= np.linalg.norm(axis)
        direction = np.array([axis[1], -axis[0]])
        other_axis = points[other_knee] - points[other_hip]
        fractions = ((THIGH_FRACTION, .38, .42, .45, .48, .50, .52)
                     if region_labels is not None else (THIGH_FRACTION, .38, .42))
        for fraction in fractions:
            center = points[hip] * (1 - fraction) + points[knee] * fraction
            try:
                width, segment = band_width(observation.mask, center, direction, axis)
                # Intersect with the actual opposite leg axis at this section.
                # Projecting its unrelated center gave false overlaps in rotated poses.
                matrix = np.column_stack((direction, -other_axis))
                if abs(np.linalg.det(matrix)) < 1e-6:
                    continue
                offset, along_other = np.linalg.solve(matrix, points[other_hip] - center)
                low, high = sorted(float(np.dot(end - center, direction)) for end in segment)
                joined = 0 <= along_other <= 1 and low <= offset <= high
                arm_overlap = intersects_arm(segment, points, np.where(valid, observation.landmarks[:, 3], 0))
                hand_overlap = connected_hand_near_section(observation, points, valid, segment)
                record["samples"].append({"fraction": fraction, "width_pixels": width, "contains_other_leg": bool(joined),
                                          "arm_overlap": arm_overlap, "connected_hand_nearby": hand_overlap})
                if arm_overlap or hand_overlap:
                    record["reason"] = "hand_overlaps_thigh"
                    continue
                if joined:
                    continue
                widths.append(width)
                sections.append((f"thigh_{side + 1}", segment))
                record.update(status="estimated", fraction=fraction, width_pixels=width)
                break
            except PipelineError as exc:
                record["samples"].append({"fraction": fraction, "rejected": exc.code})
        if record["status"] == "unavailable" and "reason" not in record:
            record["reason"] = "ambiguous_thigh"
    hand_or_arm = any(sample.get("arm_overlap") or sample.get("connected_hand_nearby")
                      for side in sides for sample in side["samples"])
    reason = ("leg_geometry_uncertain" if not valid[[23, 24, 25, 26]].all() else
              "hand_overlaps_thigh" if hand_or_arm else "ambiguous_thigh")
    info = quality(observation, [23, 24, 25, 26], "individual_thigh_silhouette_projection_multiplier",
                   None if widths else reason, sides=sides)
    if len(widths) == 1:
        info.update(status="review_required", reason=reason, requires_manual_review=True,
                    message="Only one thigh outline is visible. This single-side estimate needs a tape measurement before sizing.")
    diagnostic("thigh_sections", sides=sides, measured_sides=len(widths))
    kappa_thigh = (KAPPA_FEMALE if gender == "female" else KAPPA_MALE if gender == "male" else KAPPA)["thigh"]
    return (float(np.mean(widths) * scale * kappa_thigh) if widths else None), info, sections


def estimate(observation: PoseObservation, height_cm: float, *, region_labels=None, gender: str | None = None) -> tuple[dict, list]:
    if not math.isfinite(height_cm) or not 80 <= height_cm <= 250:
        raise PipelineError("invalid_height", "Self-reported height must be between 80 and 250 cm.")
    p = validate_pose(observation)
    kappa = KAPPA_FEMALE if gender == "female" else KAPPA_MALE if gender == "male" else KAPPA
    valid = usable_landmarks(observation)
    scale, head_y, ankle_y, head_indices, feet = calibrate(observation, p, height_cm)
    height_px = ankle_y - head_y
    diagnostic("scale_calibration", image_size=list(observation.image.shape[1::-1]),
               height_pixels=height_px, scale_factor=scale, foot_evidence=feet)
    values = dict.fromkeys(("shoulder_width", "chest_circumference", "waist_circumference",
                           "hip_circumference", "thigh_circumference", "inseam_length"))
    metric_quality, sections = {}, []
    shoulder_ok = bool(valid[[11, 12]].all())
    hips_ok = bool(valid[[23, 24]].all())
    if shoulder_ok:
        width = float(np.linalg.norm(p[11] - p[12]))
        shoulder_ok = width >= 10 and abs(p[11, 1] - p[12, 1]) <= .3 * width
        world = observation.world_landmarks
        if world.shape == (33, 3) and np.isfinite(world).all():
            span = world[11] - world[12]
            shoulder_ok &= abs(span[2]) <= max(abs(span[0]) * .65, .08)
    metric_quality["shoulder_width"] = quality(observation, [11, 12], "projected_shoulder_distance",
        None if shoulder_ok else "shoulder_landmarks_uncertain")
    if shoulder_ok:
        values["shoulder_width"] = width * scale
    torso_ok = shoulder_ok and hips_ok and head_y < p[[11, 12], 1].mean() < p[[23, 24], 1].mean() < ankle_y
    fractions = {"chest": None, "waist": None}
    if torso_ok:
        widths, fractions, torso_quality, torso_lines = torso_sections(observation, p, region_labels, gender=gender)
        sections.extend(torso_lines)
        for name in ("chest", "waist"):
            key = name + "_circumference"
            metric_quality[key] = {**quality(observation, [11, 12, 23, 24], "silhouette_projection_multiplier"), **torso_quality[key]}
            if widths[name] is not None:
                values[key] = widths[name] * scale * kappa[name]
    else:
        for name in ("chest", "waist"):
            metric_quality[name + "_circumference"] = quality(observation, [11, 12, 23, 24],
                "silhouette_projection_multiplier", "torso_landmarks_uncertain")
    metric_quality["hip_circumference"] = quality(observation, [23, 24],
        "hip_silhouette_projection_multiplier", "hip_outline_unavailable")
    if hips_ok:
        center = p[[23, 24]].mean(0)
        axis = np.array([0., 1.])
        try:
            span = center - p[[11, 12]].mean(0)
            hip_fractions = ((0., .04, .08, .12, .16, .20, .24) if gender == "female"
                             else (0., .04, .08, .12, .16) if gender == "male"
                             else (0., .04, .08, .12, .16, .20))
            if region_labels is not None:
                candidates = []
                # Search visible outer hip levels near/below the joint level;
                # joints locate the region but never supply its circumference.
                for fraction in hip_fractions:
                    anchor = center + span * fraction
                    try:
                        width, line = band_width(observation.mask, anchor, np.array([1., 0.]), axis)
                    except PipelineError:
                        continue
                    edge = boundary_evidence(observation.image, region_labels, line, axis)
                    if (edge["accepted"] and not folded_forearm_at_section(p, valid, line, edge)
                            and not intersects_arm(line, p, np.where(valid, observation.landmarks[:, 3], 0))
                            and not connected_hand_near_section(observation, p, valid, line)):
                        candidates.append((width, line, anchor, edge, fraction))
                if not candidates:
                    raise PipelineError("hip_outline_unavailable", "No bilateral hip boundary is visible.")
                hip_width, segment, center, hip_edge, hip_fraction = max(candidates, key=lambda item: item[0])
            else:
                hip_width, segment = band_width(observation.mask, center, np.array([1., 0.]), axis)
            if (region_labels is None and (intersects_arm(segment, p, np.where(valid, observation.landmarks[:, 3], 0))
                    or not (valid[[11, 12, 13, 14, 15, 16]].all()
                            or uncertain_arm_is_separate(observation, p, center, valid)))):
                raise PipelineError("hip_outline_unavailable", "Arms obscure the hip outline.")
            values["hip_circumference"] = hip_width * scale * kappa["hip"]
            info = quality(observation, [23, 24], "hip_silhouette_projection_multiplier")
            if region_labels is not None:
                info.update(boundary_evidence=hip_edge, sample_fraction=hip_fraction)
            left, right = (float(np.linalg.norm(end - center)) for end in segment)
            max_hip_mult = 2.8 if gender == "female" else 2.4 if gender == "male" else 2.5
            if hip_width > max_hip_mult * np.linalg.norm(p[23] - p[24]) or abs(left - right) / hip_width > .35:
                info.update(status="review_required", reason="wide_clothing_outline", requires_manual_review=True,
                            message="The hip outline is wide or asymmetric relative to the visible joints. Clothing or body shape may explain it; confirm with a tape measure.")
            metric_quality["hip_circumference"] = info
            sections.append(("hip", segment))
            diagnostic("hip_section", width_pixels=hip_width, left_pixels=left, right_pixels=right, decision=info["status"])
        except PipelineError as exc:
            diagnostic("hip_section", decision="unavailable", reason=exc.code)
    thigh_value, thigh_info, thigh_lines = thigh_sections(observation, p, scale, region_labels=region_labels, gender=gender)
    values["thigh_circumference"] = thigh_value
    metric_quality["thigh_circumference"] = thigh_info
    sections.extend(thigh_lines)
    leg_ids = [23, 24, 25, 26, 27, 28]
    legs_ok = bool(valid[leg_ids].all())
    if legs_ok:
        legs_ok = (p[23, 0] - p[24, 0]) * (p[25, 0] - p[26, 0]) > 0
        for hip, knee, ankle in ((23, 25, 27), (24, 26, 28)):
            length = np.linalg.norm(p[knee] - p[hip]) + np.linalg.norm(p[ankle] - p[knee])
            legs_ok &= p[hip, 1] < p[knee, 1] < p[ankle, 1] and length > 0 and (p[ankle, 1] - p[hip, 1]) / length >= .9
    metric_quality["inseam_length"] = quality(observation, leg_ids, "hip_midpoint_to_ankles_proxy",
        None if legs_ok else "leg_geometry_uncertain")
    if legs_ok:
        center = p[[23, 24]].mean(0)
        values["inseam_length"] = float(np.mean([np.linalg.norm(p[i] - center) for i in (27, 28)]) * scale)
    for key, value in values.items():
        limit = 100 if key == "shoulder_width" else 200 if key == "inseam_length" else 400
        if value is not None and not 0 < value <= limit:
            values[key] = None
            metric_quality[key].update(status="unavailable", reason="implausible_geometry", requires_manual_review=True)
    review = [name for name, info in metric_quality.items() if info["requires_manual_review"]]
    reasons = REASON_MESSAGES
    for name, info in metric_quality.items():
        if info["requires_manual_review"]:
            info.setdefault("message", reasons[info["reason"]])
    annotate_evidence(values, metric_quality)
    return {
        "scale_factor": scale,
        "measurements": {name: round(value, 2) if value is not None else None for name, value in values.items()},
        "quality": {"estimates_only": True,
                    "status": "review_required" if review else "estimated",
                    "requires_manual_review": review, "metrics": metric_quality,
                    "minimum_key_landmark_visibility": float(observation.landmarks[list(KEY_LANDMARKS), 3].min()),
                    "visibility_threshold_exclusive": VISIBILITY_THRESHOLD,
                    "statistical_uncertainty": "Not calibrated; landmark visibility is not measurement accuracy."},
        "geometry": {"height_cm": height_cm, "height_pixels": height_px,
                     "head_y": head_y, "ankle_y": ankle_y,
                     "head_reference": "minimum y of visible MediaPipe face landmarks 0-10",
                     "head_landmark_indices": head_indices, "foot_evidence": feet,
                     "image_size": list(observation.image.shape[1::-1]),
                     "gender": gender,
                     "projection_multipliers": kappa,
                     "chest_torso_fraction": fractions["chest"], "waist_torso_fraction": fractions["waist"],
                     "thigh_leg_fraction": THIGH_FRACTION,
                     "inseam_reference": "mean Euclidean distance from hip midpoint to ankles 27/28"},
        "warnings": measurement_warnings(metric_quality, fractions),
    }, sections


def measurement_warnings(metric_quality, fractions):
    return [
            "Single-view estimates depend on self-reported height, perspective, clothing and segmentation.",
            "MediaPipe has no crown or crotch landmark. Face-to-ankle scale and hip-midpoint inseam are biased anatomical proxies.",
            "Circumference multipliers are specified heuristics, not calibrated tape measurements. Hip circumference uses the observed outer silhouette; clothing can obscure the body.",
            (f"Chest uses an observed arm-free section at {fractions['chest']:.0%} of shoulder-to-hip distance; it may miss the fullest chest/bust."
             if fractions["chest"] is not None else "Chest circumference is unavailable. " + metric_quality["chest_circumference"]["message"]),
            "Confirm important dimensions with a tape measure before choosing a size.",
        ] + [name.replace("_", " ") + ": " + info["message"]
             for name, info in metric_quality.items() if info["requires_manual_review"]]


class MeasurementService:
    def __init__(self, detector: MediaPipePose, output_root: Path, semantic_parser=None):
        self.detector = detector
        self.output_root = output_root
        self.semantic_parser = semantic_parser

    def extract(self, data: bytes, height_cm: float, gender: str | None = None) -> ExtractionResponse:
        started = perf_counter()
        try:
            response = self._extract(data, height_cm, gender=gender)
        except PipelineError as exc:
            diagnostic("measurement_failed", code=exc.code, duration_seconds=round(perf_counter() - started, 3))
            raise
        diagnostic("measurement_completed", quality=response.quality["status"],
                   duration_seconds=round(perf_counter() - started, 3))
        return response

    def _extract(self, data: bytes, height_cm: float, gender: str | None = None) -> ExtractionResponse:
        image = decode_person(data)
        observation = self.detector.detect(image)
        if observation.image.shape != image.shape:
            raise PipelineError("invalid_pose_frame", "The pose and photo use different image dimensions. Retry extraction.")
        result, sections = estimate(observation, height_cm, gender=gender)
        refined_masks = {}
        if observation.probabilities is not None:
            # Bounded retries, including small images and hip/thigh-only failures.
            # The first keeps confident foreground; the second can reopen real
            # gaps even where the pose prior confidently bridged an arm.
            modes = (["native"] if max(image.shape[:2]) > 800 else []) + ["image_guided"]
            for mode in modes:
                if not needs_refinement(result):
                    break
                started = perf_counter()
                attempt = {"method": mode, "recovered": []}
                try:
                    options = {"max_edge": 1600}
                    if mode == "image_guided":
                        options["reconsider_foreground"] = True
                    mask = guard_refined_mask(observation, refine_mask(image, observation.probabilities, **options))
                    next_result, next_sections = estimate(replace(observation, mask=mask), height_cm, gender=gender)
                    result, sections, recovered = merge_recovered(result, sections, next_result, next_sections, mode)
                    attempt["recovered"] = recovered
                    if recovered:
                        refined_masks[f"_{mode}_mask.png"] = mask
                except PipelineError as exc:
                    attempt["code"] = exc.code
                attempt["duration_seconds"] = round(perf_counter() - started, 3)
                result["geometry"].setdefault("refinement_attempts", []).append(attempt)
                diagnostic("measurement_refinement", **attempt)
            result["warnings"] = measurement_warnings(result["quality"]["metrics"], {
                key: result["geometry"][key + "_torso_fraction"] for key in ("chest", "waist")})
        semantic_labels = None
        if self.semantic_parser is not None and any(
            result["measurements"][key] is None and result["quality"]["metrics"][key]["reason"] in RECOVERABLE_REASONS
            for key in TARGETS
        ):
            started = perf_counter()
            attempt = {"method": "semantic_regions", "recovered": []}
            try:
                parsed = self.semantic_parser.predict(image)
                mask = region_mask(observation, parsed.labels)
                candidate, candidate_lines = estimate(replace(observation, mask=mask), height_cm, region_labels=parsed.labels, gender=gender)
                # Do not let the measurement-only region mask alter any limb metric.
                for key in candidate["measurements"]:
                    if key not in TARGETS:
                        candidate["measurements"][key] = None
                result, sections, recovered = merge_recovered(result, sections, candidate, candidate_lines, "semantic_regions")
                attempt["recovered"] = recovered
                if recovered:
                    semantic_labels = parsed.labels
                    refined_masks["_semantic_mask.png"] = mask
                    result["geometry"]["semantic_parser"] = parsed.diagnostics
                    for key in recovered:
                        info = result["quality"]["metrics"][key]
                        previous_message = info.get("message", "")
                        info.update(method="semantic_visible_contour_projection_multiplier",
                                    message="Estimated from visible clothing/body-region edges, excluding parsed arms and hands. Depth and clothing fit are not calibrated; confirm with a tape measure before sizing.",
                                    refinement_warning=previous_message)
            except (PipelineError, ImportError, OSError, RuntimeError) as exc:
                attempt["code"] = exc.code if isinstance(exc, PipelineError) else "semantic_parser_unavailable"
            attempt["duration_seconds"] = round(perf_counter() - started, 3)
            result["geometry"].setdefault("refinement_attempts", []).append(attempt)
            diagnostic("measurement_refinement", **attempt)
        annotate_evidence(result["measurements"], result["quality"]["metrics"])
        result["warnings"] = measurement_warnings(result["quality"]["metrics"], {
            key: result["geometry"][key + "_torso_fraction"] for key in ("chest", "waist")})
        filename = f"pose_{uuid4().hex}"
        canvas = Image.fromarray(image)
        draw = ImageDraw.Draw(canvas)
        points = observation.landmarks[:, :2] * [image.shape[1], image.shape[0]]
        valid = usable_landmarks(observation)
        for a, b in ((11, 12), (11, 23), (12, 24), (23, 24), (11, 13), (13, 15),
                     (12, 14), (14, 16), (23, 25), (25, 27), (24, 26), (26, 28), (27, 29), (28, 30)):
            if valid[[a, b]].all():
                draw.line([tuple(points[a]), tuple(points[b])], fill="#34bd68", width=2)
        for index, point in enumerate(points):
            if valid[index]:
                x, y = point
                draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill="#ffd34d")
                draw.text((x + 4, y), str(index), fill="#193c28")
        for name, segment in sections:
            draw.line([tuple(end) for end in segment], fill="#00b0ff", width=3)
            draw.text(tuple(segment[0]), name, fill="#005085")
        prov = {"model": "MediaPipe Pose Landmarker Full", "landmarks": 33,
                "model_sha256": self.detector.model_sha256, "device": "cpu",
                "local_gpu_used": False, "input_sha256": hashlib.sha256(data).hexdigest(),
                "method": "landmark-silhouette-projection-v6",
                "segmentation": "MediaPipe probabilities with CPU GrabCut and optional CPU semantic-region edge validation"}
        if gender:
            prov["model_type"] = gender
        response = ExtractionResponse(
            gender=gender,
            **result, measurement_id=filename, annotated_image_url=f"/static/annotated/{filename}.png",
            landmarks_normalized=observation.landmarks.tolist(),
            landmark_presence=observation.presence.tolist() if observation.presence is not None else None,
            provenance=prov,





        )
        # Validate all geometry before creating successful artifacts.
        PhotoMeasurements.model_validate(result["measurements"])
        try:
            self.output_root.mkdir(parents=True, exist_ok=True)
            canvas.save(self.output_root / f"{filename}.png")
            Image.fromarray(observation.mask.astype(np.uint8) * 255).save(self.output_root / f"{filename}_mask.png")
            for suffix, mask in refined_masks.items():
                Image.fromarray(mask.astype(np.uint8) * 255).save(self.output_root / f"{filename}{suffix}")
            if semantic_labels is not None:
                Image.fromarray(semantic_labels.astype(np.uint8)).save(self.output_root / f"{filename}_semantic_labels.png")
            (self.output_root / f"{filename}.json").write_text(json.dumps({
                **response.model_dump(), "landmarks_normalized": observation.landmarks.tolist(),
                "landmarks_world_meters": observation.world_landmarks.tolist(),
                "landmark_presence": observation.presence.tolist() if observation.presence is not None else None,
            }, indent=2, allow_nan=False), encoding="utf-8")
        except OSError as exc:
            self.remove_artifacts(filename)
            raise PipelineError("measurement_storage_unavailable", "Measurement output could not be saved. Check available storage.", 503) from exc
        return response

    def artifact_path(self, measurement_id: str, suffix: str = ".png") -> Path:
        import re
        if not re.fullmatch(r"pose_[0-9a-f]{32}", measurement_id) or suffix not in (".png", "_mask.png", ".json", *MASK_SUFFIXES):
            raise PipelineError("measurement_missing", "This measurement artifact was not found.", 404)
        root = self.output_root.resolve()
        path = root / f"{measurement_id}{suffix}"
        if path.resolve().parent != root:
            raise PipelineError("measurement_missing", "This measurement artifact was not found.", 404)
        return path

    def remove_artifacts(self, measurement_id: str):
        try:
            for suffix in (".png", "_mask.png", ".json", *MASK_SUFFIXES):
                self.artifact_path(measurement_id, suffix).unlink(missing_ok=True)
        except OSError as exc:
            raise PipelineError("measurement_storage_unavailable", "Measurement artifacts could not be removed; retry when storage is writable.", 503) from exc
