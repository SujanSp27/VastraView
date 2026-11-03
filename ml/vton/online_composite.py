"""Category-aware preservation for the cloud model's complete generated image."""
import cv2
import numpy as np

from ml.errors import PipelineError

LABELS = {"tops": (3,), "bottoms": (5, 6), "one-pieces": (3, 4, 5, 6)}
GENERATED_LABELS = {"tops": (3,), "bottoms": (5, 6), "one-pieces": (4, 3, 5, 6)}


def _top_hem_extension(old, new, source, feather, clothing_extension):
    """Allow a generated shirt to cover a small, connected part of a waistband.

    Keeping every source trouser pixel clips a longer generated top to the old
    shirt's hem. Only generated top pixels near a downward-facing source hem
    may replace pants, skirt or belt pixels. This is deliberately narrower than
    the general clothing extension radius used for nearby skin/background.
    """
    rows = np.nonzero(old)[0]
    height = int(rows.max() - rows.min() + 1)
    baseline_limit = max(feather * 2, round(height * .12))
    maximum_limit = max(baseline_limit, round(height * .40))
    # Lower-facing edges in the bottom 30% exclude sleeve ends and the collar.
    below = np.zeros_like(old)
    below[:-1] = old[1:]
    hem = old & ~below
    hem[:int(rows.min() + height * .70)] = False
    proximity = cv2.distanceTransform((~hem).astype(np.uint8), cv2.DIST_L2, 5)
    _, components = cv2.connectedComponents(new.astype(np.uint8), connectivity=8)
    touching = np.unique(components[old & new])
    touching = touching[touching != 0]
    connected_top = np.isin(components, touching)
    waistband = new & connected_top & np.isin(source, (5, 6, 7))
    # Follow the complete generated hem when it is modestly longer than the
    # original. Cutting it at an arbitrary 12% depth leaves jagged jean wedges.
    # An implausibly long or misparsed top must fail rather than be clipped into
    # an apparently successful result or overwrite most of the trouser legs.
    required_depth = float(proximity[waistband].max()) if waistband.any() else 0.
    if required_depth > maximum_limit:
        raise PipelineError("garment_length_changed",
                            "The generated top extends too far over the lower body. "
                            "Use a person photo wearing a top with similar coverage; this result was rejected.")
    limit = max(baseline_limit, int(np.ceil(required_depth)))
    extension = (
        waistband
        & (proximity <= limit)
    )
    # A target component can connect through pixels outside the allowed edit
    # area. Do not retain an isolated trouser patch after imposing the bound.
    support = old | clothing_extension | extension
    _, supported = cv2.connectedComponents(support.astype(np.uint8), connectivity=8)
    attached = np.unique(supported[old])
    extension &= np.isin(supported, attached[attached != 0])
    return extension, limit


def _align_shoulder_edge(generated, source, target, clothing, feather):
    """Project tiny neural-clothing boundary gaps onto the original arm outline.

    A model can shrink a sleeve edge by a few pixels, leaving an exposed strip
    of the original upper arm after identity preservation. Only complete, narrow
    source-arm / generated-background components adjacent to generated clothing
    qualify. Broader limb changes, bare-skin predictions and hands never qualify.
    Colours come from the nearest interior of the generated garment, not from
    the uploaded flat-lay or a fabricated skin colour.
    """
    radius = max(2, round(min(source.shape) * .008))
    distance = cv2.distanceTransform((~clothing).astype(np.uint8), cv2.DIST_L2, 5)
    gaps = (source == 12) & (target == 0)
    count, components, stats, _ = cv2.connectedComponentsWithStats(gaps.astype(np.uint8))
    projected = np.zeros_like(clothing)
    area_limit = max(16, round(np.count_nonzero(clothing) * .015))
    for component in range(1, count):
        if stats[component, cv2.CC_STAT_AREA] > area_limit:
            continue
        region = components == component
        if distance[region].max() <= radius and distance[region].min() <= 1.5:
            projected |= region
    if not projected.any():
        return generated, projected
    # Parsing can leave one-pixel background gaps between the arm contour and
    # shirt. Join only this narrow boundary band; never retain isolated dots.
    joined = cv2.morphologyEx(
        (clothing | projected).astype(np.uint8), cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius * 2 + 1,) * 2),
    ).astype(bool)
    projected |= joined & ~clothing & np.isin(source, (0, 12)) & (target == 0) & (distance <= radius)
    # Avoid sampling the anti-aliased clothing/background boundary itself.
    interior = cv2.distanceTransform(clothing.astype(np.uint8), cv2.DIST_L2, 5) > feather
    if not interior.any():
        return generated, np.zeros_like(clothing)
    _, nearest = cv2.distanceTransformWithLabels(
        (~interior).astype(np.uint8), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL,
    )
    coordinates = np.argwhere(interior)
    y, x = coordinates[nearest[projected] - 1].T
    aligned = generated.copy()
    aligned[projected] = generated[y, x]
    return aligned, projected


def _revealed_region_transitions(alpha, old, source, target, category):
    """Blend newly exposed background into adjacent agreeing background.

    Existing skin and non-target clothing retain their actual pixels. Semantic
    agreement alone is not evidence that generated skin or fabric has the same
    colour. Never blend through a disconnected region, the face or hands.
    """
    rows = np.nonzero(old)[0]
    radius = min(max(4, round(min(source.shape) * .04)),
                 max(4, round((rows.max() - rows.min() + 1) * .10)))
    core = max(1, radius * .16)
    # Shorter sleeves also uncover background. Without a transition into the
    # adjacent agreeing background, the old sleeve outline remains as a hard
    # polygon even when all of its fabric has been replaced by model output.
    # Semantic agreement does not imply colour/texture agreement. Blending a
    # generated trouser label into real jeans recolours the non-target garment.
    # Only newly covered clothing in _top_hem_extension may edit a waistband.
    labels = (0,)
    adjusted = np.zeros_like(old)
    for label in labels:
        revealed = old & (target == label)
        if not revealed.any():
            continue
        agreement = (source == label) & (target == label)
        _, components = cv2.connectedComponents((revealed | agreement).astype(np.uint8))
        touching = np.unique(components[revealed])
        connected = np.isin(components, touching[touching != 0])
        distance = cv2.distanceTransform((~revealed).astype(np.uint8), cv2.DIST_L2, 5)
        band = agreement & connected & (distance < radius)
        fade = np.clip((radius - distance) / (radius - core), 0., 1.)
        fade = fade * fade * (3. - 2. * fade)
        adjusted |= band & (fade > alpha)
        alpha[band] = np.maximum(alpha[band], fade[band])
    return adjusted


def _is_cropped_reference(reference_labels):
    """Recognize a short flat-lay bodice from already validated reference labels.

    Callers supply labels only after validating a complete flat-lay reference.
    Sleeve span alone cannot establish a crop: the central bodice must also be
    short relative to its hem width. This is a conservative geometric heuristic,
    not a body measurement or guarantee about hidden anatomy.
    """
    if reference_labels is None:
        return False
    fabric = reference_labels == 3
    if fabric.ndim != 2 or np.count_nonzero(fabric) < 256:
        return False
    y, x = np.where(fabric)
    height, width = np.ptp(y) + 1, np.ptp(x) + 1
    if height / width > .85:
        return False
    center = int((x.min() + x.max()) // 2)
    half = max(1, round(width * .05))
    spans = [np.ptp(rows) + 1 for c in range(center - half, center + half + 1)
             if (rows := np.flatnonzero(fabric[:, c])).size]
    hem_width = float(np.median(fabric[y.max() - round(height * .25):y.max()].sum(axis=1)))
    if len(spans) < half or hem_width <= 0 or not .35 <= np.median(spans) / hem_width <= .85:
        return False
    return True


def _cropped_reference_hem(old, target, reference_labels):
    if not _is_cropped_reference(reference_labels):
        return np.zeros_like(old)
    old_rows = np.nonzero(old)[0]
    old_height = int(np.ptp(old_rows)) + 1
    # Only torso skin in the lower 40% qualifies. Neck, arms and legs retain
    # the original exposure limit, regardless of the reference's shape.
    hem = old & (target == 16)
    hem[:int(old_rows.min() + old_height * .60)] = False
    return hem


def _validate_dress(old, source, target):
    """Reject parsed separates left in a requested dress; never paint them out.

    Parser speckles below 0.5% of original clothing (at least 16 pixels) are
    diagnostic noise, not proof of leakage. This conservative gate still needs
    visual review: labels cannot verify a neckline, print, or intended hem.
    """
    tolerance = max(16, round(np.count_nonzero(old) * .005))
    leaked = old & np.isin(target, (3, 5, 6))
    dress = target == 4
    if np.count_nonzero(leaked) > tolerance or np.count_nonzero(dress & old) <= tolerance:
        raise PipelineError("dress_transfer_incomplete",
                            "The generated dress retained separate clothing or was not identified as a complete dress. "
                            "This result was rejected. Try a clearer dress reference and similar clothing coverage.")
    _, components = cv2.connectedComponents(dress.astype(np.uint8), connectivity=8)
    regions = [components[dress & (source == 3)],
               components[dress & np.isin(source, (5, 6))]]
    # A tiny detached skirt touching a few old-shirt pixels does not establish
    # continuity. The dominant dress component in each original region must agree.
    if all(region.size for region in regions) and len({int(np.bincount(region).argmax()) for region in regions}) != 1:
        raise PipelineError("dress_transfer_incomplete", "The generated dress is split into disconnected clothing regions. This result was rejected.")
    return int(np.count_nonzero(leaked))


def _validate_skirt(old, target):
    """Do not accept retained trousers merely because both are model bottoms.

    Reuse the dress gate's parser-noise allowance. This validates a semantic
    mismatch only, not fabric fidelity or a particular skirt length.
    """
    tolerance = max(16, round(np.count_nonzero(old) * .005))
    if (np.count_nonzero(old & (target == 6)) > tolerance
            or np.count_nonzero(old & (target == 5)) <= tolerance):
        raise PipelineError(
            "skirt_transfer_incomplete",
            "The generated skirt retained trousers or could not be identified as a skirt. "
            "This result was rejected. Try a clearer skirt reference and a person photo with similar coverage.",
        )


def preserve_regions(original, generated, source, target, category, *, reference_labels=None, garment_kind=None):
    if category not in LABELS:
        raise ValueError("Unknown garment category")
    if original.shape != generated.shape or source.shape != original.shape[:2] or target.shape != source.shape:
        raise ValueError("Images and label maps must have matching dimensions")
    old = np.isin(source, LABELS[category])
    new = np.isin(target, GENERATED_LABELS[category])
    if garment_kind in {"dress", "jumpsuit"} and category != "one-pieces":
        raise ValueError("Full-body garment requires one-pieces model routing")
    dress_leakage = None
    if garment_kind == "dress":
        dress_leakage = _validate_dress(old, source, target)
        new = target == 4
    if garment_kind == "skirt":
        if category != "bottoms":
            raise ValueError("Skirt requires bottoms model routing")
        _validate_skirt(old, target)
        new = target == 5
    head = np.isin(source, (1, 2, 9, 11))
    if np.count_nonzero(head) < source.size * .001:
        raise PipelineError("face_not_visible", "Use a clear photo with the person's face and hair visible.")
    if np.count_nonzero(old) < source.size * .003 or np.count_nonzero(new) < source.size * .003:
        raise PipelineError("clothing_not_visible", "The selected clothing region is not clearly visible in the input or generated image.")
    # A lower-body replacement must not introduce a second shirt hem inside
    # the old trousers. Preserving the real shirt cannot repair this invented
    # extension: the two hems produce a visible seam/double layer.
    retained_top = old & (target == 3) if category == "bottoms" else np.zeros_like(old)
    if np.count_nonzero(retained_top) > max(16, round(np.count_nonzero(old) * .005)):
        raise PipelineError("non_target_garment_changed",
                            "The generated lower garment introduced an extra upper-body clothing layer. "
                            "This result was rejected; try a photo with a clearly visible waistband.")
    # Hidden anatomy is estimated, never recovered from the photograph. A
    # validated cropped reference can reveal a bounded midriff, but cannot
    # waive the limit for arms, legs or a radically different silhouette.
    revealed_skin = old & np.isin(target, (12, 14, 16))
    crop_hem = _cropped_reference_hem(old, target, reference_labels) if category == 'tops' else np.zeros_like(old)
    old_count = np.count_nonzero(old)
    if (np.count_nonzero(revealed_skin & ~crop_hem) > old_count * .20
            or np.count_nonzero(crop_hem) > old_count * .30
            or np.count_nonzero(revealed_skin) > old_count * .40):
        raise PipelineError(
            "coverage_change_too_large",
            "This outfit would expose too much skin hidden by the original clothing. "
            "Use a person photo with similar sleeve and hem coverage; the generated result was rejected.",
        )
    # Model clothing may cover bare arms/legs and surrounding background.
    # A dress may replace both top and bottom. A top may overlap only a bounded
    # waistband area; the rest of the lower-body clothing stays unchanged.
    feather = max(2, round(min(source.shape) * .003))
    projected = np.zeros_like(old)
    if category == "tops":
        _, components = cv2.connectedComponents(new.astype(np.uint8), connectivity=8)
        touching = np.unique(components[new & old])
        connected_top = new & np.isin(components, touching[touching != 0])
        generated, projected = _align_shoulder_edge(generated, source, target, connected_top, feather)
        new |= projected
    eligible = np.isin(source, (0, 12, 14, 16))
    distance = cv2.distanceTransform((~old).astype(np.uint8), cv2.DIST_L2, 5)
    extension = new & eligible & (distance < min(source.shape) * .30)
    hem_extension = np.zeros_like(old)
    hem_limit = 0
    if category == "tops":
        hem_extension, hem_limit = _top_hem_extension(old, new, source, feather, extension)
        if _is_cropped_reference(reference_labels) and hem_extension.any():
            # The generic longer-shirt allowance must not conceal crop-top
            # length drift by overwriting original shorts or trousers.
            raise PipelineError(
                "garment_length_changed",
                "The generated crop top overlaps the original lower garment. "
                "Its cropped hem was not preserved; this result was rejected. Retry with similar clothing coverage.",
            )
        extension |= hem_extension
    support = old | extension
    edge = cv2.dilate(support.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (feather * 2 + 1,) * 2)).astype(bool)
    support |= edge & eligible & (distance <= feather)
    protected = head | np.isin(source, (13, 15, 8, 17))
    # Keep already visible skin unless the new garment actually covers it.
    # Fading model skin into a real forearm creates a colour seam at protected
    # hands (reproduced with the mirror-person polo baseline).
    visible_skin = np.isin(source, (12, 14, 16)) & ~new
    protected |= visible_skin
    # Shrinking a real limb is not fixed by deleting skin or accepting a white gap.
    skin = np.isin(source, (12, 14))
    interior = cv2.distanceTransform(skin.astype(np.uint8), cv2.DIST_L2, 5) > feather * 2
    missing_skin = interior & (target == 0) & (distance < min(source.shape) * .06)
    if np.count_nonzero(missing_skin) > max(96, np.count_nonzero(skin) * .04):
        raise PipelineError("body_shape_changed", "The generated outfit distorted an exposed arm or leg. Try a clearer frontal photo; this result was rejected.")
    alpha = np.minimum(cv2.distanceTransform(support.astype(np.uint8), cv2.DIST_L2, 5) / feather, 1.)
    alpha[old] = 1.
    alpha[projected] = 1.
    transitions = _revealed_region_transitions(alpha, old, source, target, category)
    alpha[protected] = 0.
    non_target = (np.isin(source, (5, 6, 7)) & ~hem_extension if category == "tops"
                  else source == 3 if category == "bottoms" else np.zeros_like(old))
    alpha[non_target] = 0.
    output = np.rint(generated * alpha[..., None] + original * (1 - alpha[..., None])).clip(0, 255).astype(np.uint8)
    return output, alpha, {
        "identityPreservedExactly": bool(np.array_equal(output[protected], original[protected])),
        "nonTargetClothingPreservedExactly": bool(np.array_equal(output[non_target], original[non_target])),
        "visibleSkinPreservedExactly": bool(np.array_equal(output[visible_skin], original[visible_skin])),
        "garmentKind": garment_kind,
        "dressSeparateClothingPixels": dress_leakage,
        "changedNonTargetClothingPixels": int(np.count_nonzero(np.any(output != original, axis=2) & non_target)),
        "changedPixelsOutsideEditMask": int(np.count_nonzero(np.any(output != original, axis=2) & (alpha == 0))),
        "oldClothingMinimumAlpha": float(alpha[old & ~protected].min()),
        "editedPixels": int(np.count_nonzero(alpha)),
        "hemExtensionPixels": int(np.count_nonzero(hem_extension)),
        "hemExtensionLimitPixels": hem_limit,
        "shoulderProjectionPixels": int(np.count_nonzero(projected)),
        "revealedRegionTransitionPixels": int(np.count_nonzero(transitions & ~protected)),
        "referenceCropHemPixels": int(np.count_nonzero(crop_hem)),
        "estimatedPreviouslyHiddenSkinPixels": int(np.count_nonzero(revealed_skin & ~protected)),
        "compositor": "semantic-category-preservation-v11",
        "limitations": "Semantic parsing can mislabel seams and skin. Newly exposed skin is generated, not observed anatomy. Visual review is still required.",
    }
