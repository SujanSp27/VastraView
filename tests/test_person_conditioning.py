"""Geometry/ownership tests, not evidence of generated-image quality."""
import numpy as np
import pytest

from ml.vton.person_conditioning import upper_clothing_conditioning


def test_only_observed_shirt_pixels_change_and_inputs_are_not_mutated():
    labels = np.arange(18, dtype=np.uint8).reshape(3, 6)
    # Nonrectangular disconnected shirt regions and intervening hands/background.
    labels[0, 0] = labels[2, 5] = 3
    image = np.arange(54, dtype=np.uint8).reshape(3, 6, 3)
    original, original_labels = image.copy(), labels.copy()
    result = upper_clothing_conditioning(image, labels)
    assert np.all(result[labels == 3] == 127)
    assert np.array_equal(result[labels != 3], original[labels != 3])
    assert np.array_equal(image, original)
    assert np.array_equal(labels, original_labels)
    assert not np.shares_memory(result, image)


@pytest.mark.parametrize("shape", [(24, 16), (48, 32), (15, 23)])
def test_independent_of_resolution_or_body_position(shape):
    labels = np.zeros(shape, dtype=np.uint8)
    labels[1::3, 2::4] = 3
    image = np.full((*shape, 3), 220, dtype=np.uint8)
    result = upper_clothing_conditioning(image, labels)
    assert np.array_equal(np.any(result != image, axis=2), labels == 3)


@pytest.mark.parametrize("issue", ["size", "float_labels", "invalid_label", "empty", "float_rgb", "gray"])
def test_invalid_inputs_do_not_silently_produce_agnostic_images(issue):
    image = np.zeros((6, 4, 3), dtype=np.uint8)
    labels = np.full((6, 4), 3, dtype=np.uint8)
    if issue == "size":
        labels = labels[:3]
    elif issue == "float_labels":
        labels = labels.astype(float)
    elif issue == "invalid_label":
        labels[0, 0] = 255
    elif issue == "empty":
        labels[:] = 0
    elif issue == "float_rgb":
        image = image.astype(float)
    elif issue == "gray":
        image = image[:, :, 0]
    with pytest.raises(ValueError):
        upper_clothing_conditioning(image, labels)
