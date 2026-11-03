"""Run real sequential inference in private experiment storage without model overrides."""
import argparse
import hashlib
import io
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.db import Base
from backend.app.online_vton import conditioning_image
from backend.app.outfits import OutfitFailure, run_outfit
from backend.app.pipeline import TryOnPipeline
from backend.app.storage import AssetStore
from ml.errors import PipelineError
from ml.vton.input_audit import image_record
from scripts.worker_audits import retrieve_http


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--person", type=Path, required=True)
    parser.add_argument("--topwear", type=Path, required=True)
    parser.add_argument("--bottomwear", type=Path, required=True)
    parser.add_argument("--top-category", default="t-shirt")
    parser.add_argument("--bottom-category", default="trouser")
    parser.add_argument("--top-photo-type", default="flat-lay", choices=["flat-lay", "model"])
    parser.add_argument("--bottom-photo-type", default="flat-lay", choices=["flat-lay", "model"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reuse-top", help="Run UUID in this private evaluation store")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    report_path = args.output / "evaluation.json"
    if report_path.exists():
        parser.error("Evaluation exists. Choose a new output directory; completed evidence is never overwritten.")
    # Sibling trials share a private DB/store to safely reuse a completed top.
    store = AssetStore(args.output.parent / "runs")
    engine = create_engine("sqlite:///" + str((args.output.parent / "runs.sqlite").resolve()))
    Base.metadata.create_all(engine)
    pipeline = TryOnPipeline(store)
    health = pipeline.worker.availability(check_connection=True)
    if not health["available"]:
        raise SystemExit(health["reason"])
    report = {"status": "running", "visualAcceptance": "pending", "inputs": {
        name: {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        for name, path in (("person", args.person), ("topwear", args.topwear), ("bottomwear", args.bottomwear))},
        "categories": [args.top_category, args.bottom_category]}
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    previous_runs = {p.name for p in store.root.iterdir() if p.is_dir()}
    started = time.perf_counter()
    with Session(engine) as db:
        try:
            result = run_outfit(pipeline, db, args.person.read_bytes(), args.topwear.read_bytes(),
                                args.bottomwear.read_bytes(), top_category=args.top_category,
                                bottom_category=args.bottom_category, top_photo_type=args.top_photo_type,
                                bottom_photo_type=args.bottom_photo_type, owner="private-outfit-evaluation",
                                top_run_id=args.reuse_top)
            report.update(status="generated", result=result)
        except PipelineError as exc:
            report.update(status="failed", code=exc.code, message=str(exc))
            if isinstance(exc, OutfitFailure):
                report["partialResult"] = exc.partial_result
    report["endToEndSeconds"] = round(time.perf_counter() - started, 3)
    report["createdRunIds"] = sorted(p.name for p in store.root.iterdir() if p.is_dir() and p.name not in previous_runs)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    # Export audits only after the evidence is durable. No repeat generation.
    result = report.get("result", report.get("partialResult"))
    if result:
        runs = [result] + ([result["outfit"]["topwear"]] if result.get("outfit") else [])
        for run in runs:
            folder = store.folder(run["runId"])
            diagnostics = run["provenance"]["weights"]
            retrieve_http(folder, {"diagnostics": diagnostics}, settings.online_connection_path)
    for run_id in report["createdRunIds"]:
        folder = store.folder(run_id)
        failure = folder / "remote-failure.json"
        if failure.is_file():
            diagnostics = json.loads(failure.read_text())
            diagnostics["inputAudit"] = {
                name: image_record(Image.open(io.BytesIO(conditioning_image((folder / filename).read_bytes(), settings.online_vton_input_encoding))))
                for name, filename in (("person", "original-person.png"), ("garment", "garment-reference.png"))}
            audit_folder = folder / "worker-audit"
            audit_folder.mkdir(exist_ok=True)
            retrieve_http(audit_folder, {"diagnostics": diagnostics}, settings.online_connection_path)
    print(json.dumps({"status": report["status"], "report": str(report_path),
                      "runId": result["runId"] if result else None}))


if __name__ == "__main__":
    main()
