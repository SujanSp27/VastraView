"""Validate Virtual Try-On inference with garments from H&M, Levi's, and Westside."""
import os
from pathlib import Path

import pytest

from backend.app.config import ROOT
from backend.app.online_vton import OnlineTryOn
from scripts.evaluate_garments import evaluate_trial

EVAL_OUTPUT = ROOT / "experiments/brand-vton-verification"
EVAL_OUTPUT.mkdir(parents=True, exist_ok=True)


@pytest.mark.skipif(os.environ.get("VASTRAVIEW_LIVE") != "1", reason="Opt in to real private Colab inference")
def test_brands_vton_pipeline():
    person_path = ROOT / "data/raw/fashn-samples/person1.png"
    assert person_path.is_file(), "Reference person image must exist"

    test_garments = [
        # 1. H&M
        ("hm-formal-pant-1", "H&M", ROOT / "assets/garments/formal-pant1_hm.jpg", "trouser"),
        # 2. Levi's
        ("levis-shirt-1", "Levi's", ROOT / "assets/garments/levi's-shirt_levis.jpeg", "shirt"),
        # 3. Westside
        ("westside-t-shirt-1", "Westside", ROOT / "assets/garments/t-shirt_westside.jpeg", "t-shirt"),
    ]

    worker = OnlineTryOn()
    assert worker.availability(check_connection=True)["available"], "Live Colab worker is required"

    import json
    rows = {row["id"]: row for row in json.loads((ROOT / "data/catalog/garments-v2.json").read_text())}
    for gid, brand, gpath, cat in test_garments:
        assert gpath.is_file(), f"Garment image {gpath} must exist"
        
        metrics = evaluate_trial(
            trial_name=f"verify-{gid}",
            person_path=person_path,
            garment_path=gpath,
            category=rows[gid]["category"],
            photo_type=rows[gid]["photoType"],
            worker=worker
        )
        
        trial_folder = Path(metrics["outputDirectory"])
        assert metrics["status"] == "completed", f"Trial for {gid} failed: {metrics.get('error')}"
        assert (trial_folder / "tryon-2d.png").is_file(), f"Output image for {gid} was not generated"
        assert (trial_folder / "comparison-board.jpg").is_file(), f"Comparison board for {gid} was not generated"
        print(f"Generated, visual review pending: {brand} ({gid}): status={metrics['status']}, timing={metrics['timingSeconds']}s")
