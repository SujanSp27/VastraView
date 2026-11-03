"""Experimental, parser-bounded person conditioning for the pinned FASHN model.

This is not enabled in the production worker. GPU visual validation is required
before adopting it. Unlike upstream's bounded mask, it removes only observed
upper-clothing pixels, retaining all other evidence and the original pose input.
"""
from __future__ import annotations

import numpy as np


def upper_clothing_conditioning(image: np.ndarray, labels: np.ndarray) -> np.ndarray:
    """Neutralize FASHN parser label 3 without dilation or invented boundaries.

127 is the pinned model's official neutral mask value, prior to its normal
resize/pad and [-1, 1] normalization. This function cannot correct parser errors
or guarantee garment fidelity; empty/invalid parsing fails explicitly.
"""
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Conditioning requires a uint8 RGB image.")
    if labels.ndim != 2 or labels.shape != image.shape[:2]:
        raise ValueError("Parsing and image dimensions must match before conditioning.")
    if not np.issubdtype(labels.dtype, np.integer) or np.any((labels < 0) | (labels > 17)):
        raise ValueError("Expected the pinned FASHN parser's integer labels 0–17.")
    target = labels == 3
    if not target.any():
        raise ValueError("No upper clothing was identified; do not invent a mask.")
    conditioned = image.copy()
    conditioned[target] = 127
    return conditioned
