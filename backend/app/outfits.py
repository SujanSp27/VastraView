"""Two real, private single-garment generations; never synthesize a success.

The pinned FASHN model accepts one reference. Its existing bottomwear compositor
protects parsed source top pixels. Combined jobs require that preservation proof
and retain the independently successful top run if bottomwear fails.
"""
import hashlib
import shutil
import time
from contextlib import contextmanager

from backend.app.models import Run
from backend.app.online_vton import normalized_image
from backend.app.pipeline import TryOnPipeline
from backend.app.private_data import owned_run
from ml.errors import PipelineError
from ml.progress import _callback, observe_progress, report_progress
from ml.vton.categories import MODEL_CATEGORIES


@contextmanager
def stage_progress(stage):
    """Local orchestration labels; leave the shipped GPU progress module intact."""
    parent = _callback.get()
    with observe_progress(lambda detail: parent({**detail, "stage": stage}) if parent else None):
        report_progress(stage)
        yield


class OutfitFailure(PipelineError):
    def __init__(self, error, top):
        super().__init__(getattr(error, "code", "outfit_failed"),
                         f"Bottomwear failed. Your topwear result is saved. {error}",
                         getattr(error, "status_code", 422))
        self.partial_result = top


class PreservingBottomWorker:
    def __init__(self, worker):
        self.worker = worker

    def render(self, *args, **kwargs):
        result = self.worker.render(*args, **kwargs)
        proof = result.get("preservation", {})
        if (result.get("category") != "bottoms"
                or proof.get("nonTargetClothingPreservedExactly") is not True
                or proof.get("changedNonTargetClothingPixels") != 0
                or proof.get("identityPreservedExactly") is not True):
            raise PipelineError("outfit_preservation_failed",
                                "The worker could not verify preservation of the completed topwear and identity.")
        return result


def validate_outfit(top_category, bottom_category):
    if MODEL_CATEGORIES.get(top_category) != "tops" or MODEL_CATEGORIES.get(bottom_category) != "bottoms":
        raise PipelineError("outfit_category", "Choose separate topwear and bottomwear. Dresses and jumpsuits use single-garment try-on.")


def reusable_top(db, pipeline, run_id, owner, person, garment, category, photo_type):
    row = owned_run(db, run_id, owner)
    result = row.metadata_json.get("result", {})
    if (row.status != "success" or result.get("outfit")
            or result.get("garmentCategory") != category
            or row.metadata_json.get("garmentPhotoType") != photo_type):
        raise PipelineError("outfit_top_mismatch", "The saved topwear does not match this selection.", 409)
    folder = pipeline.store.folder(str(run_id))
    for name, data in (("original-person.png", person), ("garment-reference.png", garment)):
        path = folder / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(normalized_image(data)).digest():
            raise PipelineError("outfit_top_mismatch", "The person or topwear changed. Generate a new topwear result first.", 409)
    if not (folder / "tryon-2d.png").is_file():
        raise PipelineError("outfit_top_missing", "The saved topwear image is no longer available.", 404)
    return result


def run_outfit(pipeline, db, person, topwear, bottomwear, *, top_category, bottom_category,
               top_photo_type="flat-lay", bottom_photo_type="flat-lay", owner, top_run_id=None):
    validate_outfit(top_category, bottom_category)
    started = time.perf_counter()
    # Validate both uploads before spending GPU time on either stage.
    for image in (person, topwear, bottomwear):
        normalized_image(image)
    top = reusable_top(db, pipeline, top_run_id, owner, person, topwear, top_category, top_photo_type) if top_run_id else None
    reused = top is not None
    tick = time.perf_counter()
    if top is None:
        with stage_progress("outfit_topwear"):
            top = pipeline.run(db, person, topwear, None, top_category, photo_type=top_photo_type, owner=owner)
    top_seconds = time.perf_counter() - tick
    final = None
    try:
        top_image = (pipeline.store.folder(top["runId"]) / "tryon-2d.png").read_bytes()
        tick = time.perf_counter()
        bottom_pipeline = TryOnPipeline(pipeline.store, PreservingBottomWorker(pipeline.worker))
        with stage_progress("outfit_bottomwear"):
            final = bottom_pipeline.run(db, top_image, bottomwear, None, bottom_category,
                                        photo_type=bottom_photo_type, owner=owner)
        bottom_seconds = time.perf_counter() - tick
        final["outfit"] = {
            "strategy": "sequential-top-then-bottom", "topwear": top,
            "bottomwearCategory": bottom_category, "topwearReused": reused,
            "stageSeconds": {"topwear": round(top_seconds, 3), "bottomwear": round(bottom_seconds, 3)},
            "stageTimings": {"topwear": top.get("timings", {}), "bottomwear": final.get("timings", {})},
            "preservation": final["provenance"]["weights"]["preservation"],
        }
        # The combined result survives deletion of its independent topwear run.
        # Keep original-person.png as the actual second-pass input for audits.
        target = pipeline.store.folder(final["runId"])
        source = pipeline.store.folder(top["runId"])
        for before, after in (("original-person.png", "outfit-original.png"),
                              ("tryon-2d.png", "topwear-preview.png"),
                              ("garment-reference.png", "topwear-reference.png")):
            shutil.copyfile(source / before, target / after)
        final["originalUrl"] = pipeline.store.url(final["runId"], "outfit-original.png")
        final["outfit"]["topwear"] = {
            **top, "originalUrl": final["originalUrl"],
            "previewUrl": pipeline.store.url(final["runId"], "topwear-preview.png"),
            "garmentUrl": pipeline.store.url(final["runId"], "topwear-reference.png"),
        }
        final["timingSeconds"] = round(time.perf_counter() - started, 3)
        final["warnings"] += ["Two sequential generations were used. Inspect the waistband and both garments; visual fidelity is not guaranteed."]
        pipeline.store.write_json(final["runId"], "result.json", final)
        record = db.get(Run, final["runId"])
        record.metadata_json = {**record.metadata_json, "result": final}
        db.commit()
        return final
    except Exception as exc:
        if final is not None:
            # Final packaging must succeed before this run is retrievable as an outfit.
            db.rollback()
            record = db.get(Run, final["runId"])
            record.status = "failed"
            record.metadata_json = {**record.metadata_json, "result": None,
                                    "code": "outfit_finalization_failed"}
            (pipeline.store.folder(final["runId"]) / "result.json").unlink(missing_ok=True)
            db.commit()
        if not isinstance(exc, PipelineError):
            exc = PipelineError("outfit_failed", "The second stage could not be completed. Retry bottomwear.", 500)
        raise OutfitFailure(exc, top) from exc
