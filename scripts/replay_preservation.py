"""Replay saved GPU output through preservation on CPU, without rerunning inference.

This checks compositing only. It never approves garment fidelity or overwrites
the original run. Use raw output and its exact source/target parsing maps.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
from PIL import Image

from ml.errors import PipelineError
from ml.vton import online_composite
from ml.vton.categories import MODEL_CATEGORIES
from ml.vton.online_composite import preserve_regions


def replay(source: Path, destination: Path, category: str, person_name="person-input.png", *, garment_kind=None):
    destination = destination.resolve()
    source = source.resolve()
    if person_name not in {"person-input.png", "original-person.png"}:
        raise ValueError("Choose a saved unannotated person image")
    if category not in {"tops", "bottoms", "one-pieces"}:
        raise ValueError("Unsupported model category")
    if garment_kind is not None and MODEL_CATEGORIES.get(garment_kind) != category:
        raise ValueError("Garment kind does not match the model category")
    if destination == source or destination.is_relative_to(source):
        raise ValueError("Use a separate replay directory to preserve saved evidence")
    destination.mkdir(parents=True, exist_ok=False)
    files = {key: source / name for key, name in {
        "original": person_name, "generated": "raw.png",
        "source": "source-labels.png", "target": "target-labels.png",
    }.items()}
    report = {"sourceRun": str(source), "personFile": person_name, "category": category,
              "garmentKind": garment_kind, "newInference": False,
              "approval": "not_evaluated", "inputHashes": {},
              "compositorSourceSha256": hashlib.sha256(Path(online_composite.__file__).read_bytes()).hexdigest()}
    try:
        arrays = {}
        for key, path in files.items():
            report["inputHashes"][key] = hashlib.sha256(path.read_bytes()).hexdigest()
            with Image.open(path) as image:
                arrays[key] = np.array(image.convert("RGB") if key in {"original", "generated"} else image)
        reference = None
        prep = source / "reference-preparation.json"
        if prep.is_file() and json.loads(prep.read_text()).get("applied"):
            path = source / "garment-labels.png"
            with Image.open(path) as image:
                reference = np.array(image)
            report["inputHashes"]["reference"] = hashlib.sha256(path.read_bytes()).hexdigest()
        start = time.perf_counter()
        output, alpha, diagnostics = preserve_regions(**arrays, category=category,
                                                     reference_labels=reference, garment_kind=garment_kind)
        report.update(status="composited", cpuSeconds=time.perf_counter() - start, diagnostics=diagnostics)
        Image.fromarray(output).save(destination / "result.png")
        Image.fromarray(np.rint(alpha * 255).astype(np.uint8)).save(destination / "edit-mask.png")
        previous = source / "result.png"
        if previous.is_file():
            with Image.open(previous) as image:
                prior = np.array(image.convert("RGB"))
            if prior.shape == output.shape:
                report["pixelsDifferentFromSavedComposite"] = int(np.count_nonzero(np.any(prior != output, axis=2)))
        report["limitations"] = "Saved model output; no new GPU timing or visual approval. Parsing errors remain possible."
    except (OSError, ValueError, PipelineError) as exc:
        report.update(status="rejected", code=getattr(exc, "code", type(exc).__name__), reason=str(exc))
    (destination / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--category", required=True, choices=("tops", "bottoms", "one-pieces"))
    parser.add_argument("--person-name", default="person-input.png", choices=("person-input.png", "original-person.png"))
    parser.add_argument("--garment-kind", choices=sorted(MODEL_CATEGORIES),
                        help="Exact catalog category, needed to exercise the dress-specific gate")
    args = parser.parse_args()
    result = replay(args.source, args.destination, args.category, args.person_name, garment_kind=args.garment_kind)
    print(json.dumps({k: result[k] for k in ("status", "newInference", "approval")}))
