"""Conservative reference framing for controlled experiments, not a model default.

Only empty margins are removed. Pixel values, fabric geometry, orientation and
aspect ratio are unchanged. A parser mask alone is insufficient: visible pixels
outside it must also fit inside the retained canvas. Worn/cropped/ambiguous
references abstain. Visual review and real inference are still required.
"""
import numpy as np
from PIL import Image


def frame_reference(image: Image.Image, labels: np.ndarray, photo_type: str):
    rgb = np.asarray(image.convert("RGB"))
    if labels.shape != rgb.shape[:2]:
        raise ValueError("Reference labels must match image dimensions")
    report = {"version": "reference-framing-experiment-v1", "applied": False}
    if photo_type != "flat-lay":
        return image, {**report, "reason": "worn_reference"}
    if not np.isin(labels, (0, 3, 4, 5, 6)).all():
        return image, {**report, "reason": "ambiguous_reference"}
    foreground = labels != 0
    if not foreground.any():
        return image, {**report, "reason": "empty_foreground"}
    border = np.concatenate((rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1])).astype(float)
    background = np.median(border, axis=0)
    if background.min() < 220 or np.percentile(np.abs(border - background), 95) > 12:
        return image, {**report, "reason": "nonuniform_background"}
    # Include shadows and any visible details omitted by the semantic parser.
    visible = np.max(np.abs(rgb.astype(float) - background), axis=2) > 20
    occupied = foreground | visible
    y, x = np.where(occupied)
    if x.min() == 0 or y.min() == 0 or x.max() == image.width - 1 or y.max() == image.height - 1:
        return image, {**report, "reason": "foreground_touches_frame"}
    margin = max(1, int(np.ceil(max(np.ptp(x) + 1, np.ptp(y) + 1) * .05)))
    box = (max(0, int(x.min()) - margin), max(0, int(y.min()) - margin),
           min(image.width, int(x.max()) + margin + 1), min(image.height, int(y.max()) + margin + 1))
    return image.crop(box), {**report, "applied": True, "box": list(box),
                             "reason": "removed_empty_margins", "fabricPixelsUnchanged": True}
