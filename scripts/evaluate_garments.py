"""Real Colab evaluation with basic image diagnostics, never automatic approval.

Colour histograms and edge density do not establish garment identity, correct
anatomy, or mask preservation. Use evaluate_wardrobe for resumable authenticated
jobs, retrieved semantic masks and explicit visual review. Offline trials remain
blocked and never produce a substitute photograph or a synthetic quality score.
"""
from __future__ import annotations

import io
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import ROOT as APP_ROOT
from backend.app.online_vton import OnlineTryOn, normalized_image
from ml.vton.categories import MODEL_CATEGORIES

OUTPUT_DIR = APP_ROOT / "experiments/garment-evaluation"


def compute_color_histogram_correlation(img1_rgb: np.ndarray, mask1: np.ndarray,
                                       img2_rgb: np.ndarray, mask2: np.ndarray) -> float:
    """Compute HSV histogram correlation between two masked regions."""
    if not mask1.any() or not mask2.any():
        return 0.0
    hsv1 = cv2.cvtColor(img1_rgb, cv2.COLOR_RGB2HSV)
    hsv2 = cv2.cvtColor(img2_rgb, cv2.COLOR_RGB2HSV)
    
    # 2D histogram on Hue and Saturation
    hist1 = cv2.calcHist([hsv1], [0, 1], mask1.astype(np.uint8), [30, 32], [0, 180, 0, 256])
    hist2 = cv2.calcHist([hsv2], [0, 1], mask2.astype(np.uint8), [30, 32], [0, 180, 0, 256])
    cv2.normalize(hist1, hist1, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
    cv2.normalize(hist2, hist2, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
    correlation = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
    return float(max(0.0, min(1.0, correlation)))


def compute_edge_density_similarity(img1_rgb: np.ndarray, mask1: np.ndarray,
                                   img2_rgb: np.ndarray, mask2: np.ndarray) -> float:
    """Compute edge structure similarity using Sobel gradients."""
    if not mask1.any() or not mask2.any():
        return 0.0
    gray1 = cv2.cvtColor(img1_rgb, cv2.COLOR_RGB2GRAY)
    gray2 = cv2.cvtColor(img2_rgb, cv2.COLOR_RGB2GRAY)
    
    sobel1 = cv2.Sobel(gray1, cv2.CV_64F, 1, 1, ksize=3)
    sobel2 = cv2.Sobel(gray2, cv2.CV_64F, 1, 1, ksize=3)
    
    edge_mag1 = np.sqrt(sobel1**2)
    edge_mag2 = np.sqrt(sobel2**2)
    
    mean_edge1 = float(np.mean(edge_mag1[mask1]))
    mean_edge2 = float(np.mean(edge_mag2[mask2]))
    
    # Ratio between 0 and 1
    if max(mean_edge1, mean_edge2) == 0:
        return 1.0
    similarity = min(mean_edge1, mean_edge2) / max(mean_edge1, mean_edge2)
    return float(similarity)


def create_side_by_side(before_rgb: np.ndarray, after_rgb: np.ndarray,
                        garment_rgb: np.ndarray | None = None) -> Image.Image:
    """Create a high-resolution side-by-side comparison board."""
    h = 800
    w_before = int(before_rgb.shape[1] * (h / before_rgb.shape[0]))
    w_after = int(after_rgb.shape[1] * (h / after_rgb.shape[0]))
    
    resized_before = cv2.resize(before_rgb, (w_before, h), interpolation=cv2.INTER_LANCZOS4)
    resized_after = cv2.resize(after_rgb, (w_after, h), interpolation=cv2.INTER_LANCZOS4)
    
    panels = [resized_before]
    if garment_rgb is not None:
        w_garment = int(garment_rgb.shape[1] * (h / garment_rgb.shape[0]))
        resized_garment = cv2.resize(garment_rgb, (w_garment, h), interpolation=cv2.INTER_LANCZOS4)
        panels.append(resized_garment)
    panels.append(resized_after)
    
    board = np.hstack(panels)
    return Image.fromarray(board)


def evaluate_trial(trial_name: str, person_path: Path, garment_path: Path,
                   category: str, photo_type: str = "flat-lay",
                   worker: OnlineTryOn | None = None) -> dict:
    """Run try-on for a person/garment pair and compute comprehensive evaluation metrics."""
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,159}", trial_name):
        raise ValueError("Invalid trial name")
    if category not in MODEL_CATEGORIES or photo_type not in {"model", "flat-lay"}:
        raise ValueError("Unsupported garment category or photo type")
    trial_folder = OUTPUT_DIR / trial_name
    if trial_folder.exists() and any(trial_folder.iterdir()):
        # Preserve old evidence (including invalid historical simulations).
        trial_folder = OUTPUT_DIR / f"{trial_name}-{uuid4().hex[:12]}"
    trial_folder.mkdir(parents=True, exist_ok=True)
    
    person_bytes = person_path.read_bytes()
    garment_bytes = garment_path.read_bytes()
    
    person_norm = normalized_image(person_bytes)
    garment_norm = normalized_image(garment_bytes)
    
    (trial_folder / "original-person.png").write_bytes(person_norm)
    (trial_folder / "garment-reference.png").write_bytes(garment_norm)
    
    person_img = Image.open(io.BytesIO(person_norm)).convert("RGB")
    garment_img = Image.open(io.BytesIO(garment_norm)).convert("RGB")
    person_np = np.asarray(person_img)
    garment_np = np.asarray(garment_img)
    
    start_time = time.perf_counter()
    status = "pending"
    diagnostics = {}
    error_msg = None
    
    if worker is None:
        worker = OnlineTryOn()
        
    avail = worker.availability(check_connection=True)
    output_img_np = None
    
    if avail.get("available"):
        try:
            diagnostics = worker.render(person_bytes, garment_bytes, category, photo_type, trial_folder)
            status = "completed"
            output_bytes = (trial_folder / "tryon-2d.png").read_bytes()
            output_img = Image.open(io.BytesIO(output_bytes)).convert("RGB")
            output_img_np = np.asarray(output_img)
        except Exception as exc:
            status = "failed"
            error_msg = str(exc)
    else:
        status = "blocked"
        error_msg = "GPU worker unavailable; no inference or substitute result was generated."
        
    duration = time.perf_counter() - start_time
    
    # Quantitative Quality & Preservation Metrics
    metrics = {
        "status": status,
        "timingSeconds": round(duration, 3),
        "error": error_msg,
        "personImage": str(person_path.resolve().relative_to(APP_ROOT.resolve())),
        "garmentImage": str(garment_path.resolve().relative_to(APP_ROOT.resolve())),
        "garmentCategory": category,
        "photoType": photo_type,
        "outputDirectory": str(trial_folder.resolve()),
        "visualApproval": "not_reviewed",
        "diagnostics": diagnostics,
        "limitations": "Whole-image colour and edge statistics are diagnostics, not fit or preservation accuracy.",
    }

    if output_img_np is not None and person_np.shape != output_img_np.shape:
        metrics.update(status="failed", error="Generated dimensions do not match the person image.", dimensionMatch=False)
        output_img_np = None
    
    if output_img_np is not None:
        # 1. Identity & Unaffected Background exactness
        # Check boundary integrity: person image and output must have identical dimensions
        has_matching_dimensions = (person_np.shape == output_img_np.shape)
        metrics["dimensionMatch"] = has_matching_dimensions
        
        # 2. Check for image difference & edit area
        diff = np.abs(output_img_np.astype(float) - person_np.astype(float))
        changed_pixels = int(np.count_nonzero(diff.max(axis=2) > 2))
        total_pixels = person_np.shape[0] * person_np.shape[1]
        changed_percentage = round((changed_pixels / total_pixels) * 100, 2)
        metrics["changedPixelPercentage"] = changed_percentage
        
        # 3. Create side-by-side comparison image
        side_by_side = create_side_by_side(person_np, output_img_np, garment_np)
        side_by_side.save(trial_folder / "comparison-board.jpg", quality=92)
        metrics["comparisonBoardPath"] = str((trial_folder / "comparison-board.jpg").resolve())
        
        # 4. Color & Texture consistency between garment and changed region
        changed_mask = diff.max(axis=2) > 4
        garment_mask = np.ones(garment_np.shape[:2], dtype=bool)
        
        if changed_mask.any():
            color_corr = compute_color_histogram_correlation(garment_np, garment_mask,
                                                            output_img_np, changed_mask)
            edge_sim = compute_edge_density_similarity(garment_np, garment_mask,
                                                       output_img_np, changed_mask)
            metrics["garmentColorCorrelation"] = round(color_corr, 3)
            metrics["garmentEdgeSimilarity"] = round(edge_sim, 3)
            metrics["preservationScore"] = round((color_corr * 0.6 + edge_sim * 0.4) * 100, 1)
        else:
            metrics.update(status="failed", error="The output contains no detectable garment transfer.",
                           garmentColorCorrelation=0., garmentEdgeSimilarity=0., preservationScore=0.)
            
    # Save individual trial metadata
    (trial_folder / "evaluation-result.json").write_text(json.dumps(metrics, indent=2))
    return metrics


def run_full_evaluation_suite() -> dict:
    """Run comprehensive automated garment evaluation across diverse test matrices."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Neutral fixture IDs describe image provenance, not inferred gender.
    subjects = [
        {"id": "studio", "path": APP_ROOT / "data/raw/studio-person.jpg"},
        {"id": "sample-5", "path": APP_ROOT / "data/raw/fashn-samples/person5.png"},
        {"id": "sample-1", "path": APP_ROOT / "data/raw/fashn-samples/person1.png"},
    ]
    from scripts.evaluate_wardrobe import catalog_rows, reference_path
    garment_matrix = [
        {"name": row["id"], "path": reference_path(row), "category": row["category"],
         "photoType": row["photoType"], "expectedType": MODEL_CATEGORIES[row["category"]]}
        for row in catalog_rows() if row["category"] in MODEL_CATEGORIES
    ]

    worker = OnlineTryOn()
    avail = worker.availability(check_connection=True)
    print(f"Starting Automated Garment Evaluation (GPU Worker Available: {avail.get('available')})...")
    
    results = []
    
    for subject in subjects:
        if not subject["path"].is_file():
            continue
        for garment in garment_matrix:
            if not garment["path"].is_file():
                continue
            trial_id = f"{subject['id']}__{garment['name']}"
            print(f"  Evaluating {trial_id} ({garment['category']} -> {garment['expectedType']})...")
            
            res = evaluate_trial(
                trial_name=trial_id,
                person_path=subject["path"],
                garment_path=garment["path"],
                category=garment["category"],
                photo_type=garment["photoType"],
                worker=worker,
            )
            res["subjectId"] = subject["id"]
            res["garmentName"] = garment["name"]
            results.append(res)
            
    # 2. Compile Aggregated Evaluation Report
    total_trials = len(results)
    completed_trials = sum(1 for r in results if r["status"] == "completed")
    failed_trials = sum(1 for r in results if r["status"] == "failed")
    
    completed = [r for r in results if r["status"] == "completed"]
    avg_preservation = float(np.mean([r["preservationScore"] for r in completed])) if completed else None
    avg_timing = float(np.mean([r["timingSeconds"] for r in completed])) if completed else None
    
    summary = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "totalEvaluations": total_trials,
        "successfulEvaluations": completed_trials,
        "failedEvaluations": failed_trials,
        "blockedEvaluations": sum(r["status"] == "blocked" for r in results),
        "meanPreservationScore": round(avg_preservation, 1) if avg_preservation is not None else None,
        "meanEndToEndSeconds": round(avg_timing, 2) if avg_timing is not None else None,
        "gpuWorkerAvailable": avail.get("available"),
        "testedCategories": list({g["category"] for g in garment_matrix}),
        "testedSubjects": [s["id"] for s in subjects if s["path"].is_file()],
        "trials": results,
    }
    
    report_file = APP_ROOT / "experiments/garment-evaluation-report.json"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(summary, indent=2))
    print(f"Evaluation Complete! Summary written to {report_file}")
    return summary


if __name__ == "__main__":
    run_full_evaluation_suite()
