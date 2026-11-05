import numpy as np
import pytest
from PIL import Image

from ml.vton.reference_framing import frame_reference


def reference():
    rgb = np.full((400, 300, 3), 245, dtype=np.uint8)
    rgb[130:270, 60:240] = [100, 60, 70]
    labels = np.zeros((400, 300), dtype=np.uint8)
    labels[130:270, 60:240] = 3
    return rgb, labels


def test_framing_preserves_every_retained_pixel_and_complete_garment():
    rgb, labels = reference()
    image, report = frame_reference(Image.fromarray(rgb), labels, "flat-lay")
    left, top, right, bottom = report["box"]
    assert left < 60 and top < 130 and right > 240 and bottom > 270
    assert np.array_equal(np.asarray(image), rgb[top:bottom, left:right])
    assert image.height < 400


def test_visible_detail_missing_from_parser_is_retained():
    rgb, labels = reference()
    rgb[100:130, 100:105] = 40
    _, report = frame_reference(Image.fromarray(rgb), labels, "flat-lay")
    assert report["box"][1] < 100


@pytest.mark.parametrize("case", ["model", "empty", "cropped", "skin", "background"])
def test_ambiguous_inputs_are_not_modified(case):
    rgb, labels = reference()
    if case == "empty":
        labels[:] = 0
    elif case == "cropped":
        labels[0, 100] = 3
    elif case == "skin":
        labels[150, 100] = 11
    elif case == "background":
        rgb[0] = 0
    original = Image.fromarray(rgb)
    image, report = frame_reference(original, labels, "model" if case == "model" else "flat-lay")
    assert image is original and report["applied"] is False


def test_mask_dimensions_must_match():
    rgb, labels = reference()
    with pytest.raises(ValueError, match="dimensions"):
        frame_reference(Image.fromarray(rgb), labels[:200], "flat-lay")
