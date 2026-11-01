"""Unit and regression tests for the automated garment evaluation system."""

import numpy as np
import pytest
from PIL import Image

from backend.app.config import ROOT
from scripts import evaluate_garments
from scripts.evaluate_garments import (
    compute_color_histogram_correlation,
    compute_edge_density_similarity,
    create_side_by_side,
    evaluate_trial,
)


def test_color_histogram_correlation_identical_and_distinct():
    # Identical image and mask should yield correlation close to 1.0
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[:, :] = [180, 50, 40]
    mask = np.ones((100, 100), dtype=bool)
    
    corr_self = compute_color_histogram_correlation(img, mask, img, mask)
    assert corr_self > 0.95
    
    # Very different color
    other = np.zeros((100, 100, 3), dtype=np.uint8)
    other[:, :] = [20, 240, 220]
    corr_diff = compute_color_histogram_correlation(img, mask, other, mask)
    assert corr_diff < corr_self


def test_edge_density_similarity():
    # Both smooth regions
    smooth1 = np.ones((50, 50, 3), dtype=np.uint8) * 128
    smooth2 = np.ones((50, 50, 3), dtype=np.uint8) * 200
    mask = np.ones((50, 50), dtype=bool)
    sim = compute_edge_density_similarity(smooth1, mask, smooth2, mask)
    assert sim == 1.0


def test_side_by_side_board_dimensions():
    before = np.ones((600, 400, 3), dtype=np.uint8) * 100
    after = np.ones((600, 400, 3), dtype=np.uint8) * 200
    garment = np.ones((800, 600, 3), dtype=np.uint8) * 150
    
    board = create_side_by_side(before, after, garment)
    assert isinstance(board, Image.Image)
    assert board.height == 800
    assert board.width > 800


def test_evaluate_trial_baseline(tmp_path, monkeypatch):
    person_path = ROOT / "data/raw/studio-person.jpg"
    garment_path = ROOT / "assets/garments/shirt_hm.jpg"
    
    if not person_path.is_file() or not garment_path.is_file():
        pytest.skip("Test sample assets unavailable.")
        
    monkeypatch.setattr(evaluate_garments, "OUTPUT_DIR", tmp_path)
    class Offline:
        def availability(self, **kwargs):
            return {"available": False}
        def render(self, *args):
            pytest.fail("An offline worker must not be called")
    res = evaluate_trial(
        trial_name="test-trial-offline", person_path=person_path,
        garment_path=garment_path, category="shirt", worker=Offline(),
    )
    assert res["status"] == "blocked"
    assert "preservationScore" not in res and "comparisonBoardUrl" not in res
    assert not (tmp_path / "test-trial-offline/tryon-2d.png").exists()
    assert res["visualApproval"] == "not_reviewed"


@pytest.mark.parametrize("mode", ["unchanged", "mismatch", "failure"])
def test_generated_file_does_not_prove_transfer(tmp_path, monkeypatch, mode):
    monkeypatch.setattr(evaluate_garments, "OUTPUT_DIR", tmp_path)
    person_path = ROOT / "data/raw/studio-person.jpg"
    garment_path = ROOT / "assets/garments/shirt_hm.jpg"

    class Worker:
        def availability(self, **kwargs):
            return {"available": True}

        def render(self, person, garment, category, photo_type, folder):
            if mode == "failure":
                raise RuntimeError("Disconnected")
            if mode == "unchanged":
                (folder / "tryon-2d.png").write_bytes(evaluate_garments.normalized_image(person))
            else:
                Image.new("RGB", (128, 128)).save(folder / "tryon-2d.png")
            return {"testOnly": True}

    res = evaluate_trial("failure-case", person_path, garment_path, "shirt", worker=Worker())
    assert res["status"] == "failed"
    assert res["visualApproval"] == "not_reviewed"
    assert res.get("preservationScore", 0) == 0
    first = (tmp_path / "failure-case/evaluation-result.json").read_bytes()
    second = evaluate_trial("failure-case", person_path, garment_path, "shirt", worker=Worker())
    assert second["outputDirectory"] != res["outputDirectory"]
    assert (tmp_path / "failure-case/evaluation-result.json").read_bytes() == first
