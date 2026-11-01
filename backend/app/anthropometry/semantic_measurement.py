"""Optional CPU parsing evidence for visible torso/hip contours, not hidden anatomy."""

import numpy as np

from ml.errors import PipelineError

REGION_IDS = (3, 4, 5, 6, 7, 16)  # Official FASHN top/dress/skirt/pants/belt/torso.
TARGETS = ("chest_circumference", "waist_circumference", "hip_circumference")


def folded_forearm_at_section(points, valid, segment, boundary=None):
    """An inward, raised forearm can hide an edge without crossing its visible span.

    Parser boundaries at that occluder describe exposed fabric, not the outer
    torso. Do not extrapolate a hidden side from the remaining visible fabric.
    """
    axis = points[[23, 24]].mean(0) - points[[11, 12]].mean(0)
    axis /= np.linalg.norm(axis)
    level = float(np.dot((segment[0] + segment[1]) / 2, axis))
    for elbow, wrist in ((13, 15), (14, 16)):
        if not valid[[elbow, wrist]].all():
            continue
        elbow_level, wrist_level = (float(np.dot(points[index], axis)) for index in (elbow, wrist))
        if wrist_level < elbow_level and level >= wrist_level:
            # The elbow landmark is its centre, not its outer skin boundary.
            # Observed arm labels also veto sections just below that centre;
            # do not invent a fixed anatomical radius to trim the elbow.
            touches_arm = boundary is not None and any(
                label in (12, 13) for side in boundary["adjacent_label_ids"] for label in side
            )
            if level <= elbow_level or touches_arm:
                return True
    return False


def region_mask(observation, labels):
    if (labels.shape != observation.mask.shape or not np.issubdtype(labels.dtype, np.integer)
            or np.any((labels < 0) | (labels > 17))):
        raise PipelineError("invalid_region_labels", "Body-region labels are not aligned with the photo.")
    h = labels.shape[0]
    shoulder = observation.landmarks[[11, 12], 1].mean() * h
    hip = observation.landmarks[[23, 24], 1].mean() * h
    if hip <= shoulder:
        raise PipelineError("torso_landmarks_uncertain", "Torso landmarks cannot locate these regions.")
    first = max(0, int(shoulder - .05 * (hip - shoulder)))
    last = min(h, int(hip + .22 * (hip - shoulder)) + 5)
    mask = observation.mask.copy()
    # Keep original scale/foot evidence and original limbs. This mask is only
    # consulted for M2-M4 candidates; it never replaces M1/M5/M6.
    mask[first:last] &= np.isin(labels[first:last], REGION_IDS)
    return mask


def boundary_evidence(image, labels, segment, axis):
    """Require bilateral class transitions with observed colour contrast.

    A parser label alone is not a visible anatomical edge. Inspect five adjacent
    rows on each side, with strips sized to the parser's 576-pixel input. Hair,
    bags, legs and ambiguous labels cannot stand in for a torso boundary.
    Contrast >=8 RGB levels is a conservative image QA threshold, not a measured
    accuracy probability. A manual-review gate always accompanies this fallback.
    """
    left, right = segment
    direction = (right - left) / np.linalg.norm(right - left)
    reach = max(3, round(max(labels.shape) / 576 * 2))
    scores, contacts = [], []
    for endpoint, sign in ((left, -1), (right, 1)):
        supported, side_contacts = [], []
        for shift in (-2, -1, 0, 1, 2):
            center = endpoint + shift * axis
            inside = np.rint(center - sign * direction * np.arange(1, reach + 1)[:, None]).astype(int)
            outside = np.rint(center + sign * direction * np.arange(1, reach + 1)[:, None]).astype(int)
            xy = np.concatenate((inside, outside))
            if np.any(xy < 0) or np.any(xy >= np.array(labels.shape[::-1])):
                supported.append(False)
                continue
            in_labels = labels[inside[:, 1], inside[:, 0]]
            out_labels = labels[outside[:, 1], outside[:, 0]]
            # Majority strips tolerate subpixel/upsampled label boundaries.
            valid = (np.mean(np.isin(in_labels, REGION_IDS)) >= .6
                     and np.mean(np.isin(out_labels, (0, 12, 13))) >= .6
                     and not np.isin(out_labels, (1, 2, 8, 9, 10, 11, 14, 15, 17)).any())
            a = np.median(image[inside[:, 1], inside[:, 0]].astype(float), axis=0)
            b = np.median(image[outside[:, 1], outside[:, 0]].astype(float), axis=0)
            supported.append(bool(valid and np.linalg.norm(a - b) >= 8))
            side_contacts.extend(out_labels.tolist())
        scores.append(float(np.mean(supported)))
        contacts.append(sorted(set(side_contacts)))
    return {"accepted": min(scores) >= .6, "boundary_support": scores,
            "adjacent_label_ids": contacts, "criterion": "bilateral_semantic_transition_and_image_contrast"}
