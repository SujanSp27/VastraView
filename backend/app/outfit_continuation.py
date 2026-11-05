"""Apply one complementary garment to an owned, completed render.

One additional model call; the earlier garment is retained as input pixels.
Never infer an identity or trust a client-supplied path/ownership assertion.
"""
from backend.app.pipeline import TryOnPipeline
from backend.app.private_data import owned_run
from ml.errors import PipelineError
from ml.vton.categories import MODEL_CATEGORIES


def continuation_input(db, pipeline, run_id, owner, category):
    row = owned_run(db, run_id, owner)
    result = row.metadata_json.get("result", {})
    previous = MODEL_CATEGORIES.get(result.get("garmentCategory"))
    current = MODEL_CATEGORIES.get(category)
    if row.status != "success" or {previous, current} != {"tops", "bottoms"}:
        raise PipelineError("outfit_region_conflict", "Choose a lower-body garment after a top, or a top after a lower-body garment.", 422)
    path = pipeline.store.folder(str(run_id)) / "tryon-2d.png"
    if not path.is_file():
        raise PipelineError("outfit_source_missing", "The previous render is unavailable. Generate it again before adding a garment.", 404)
    return path.read_bytes()


class PreservingWorker:
    def __init__(self, worker):
        self.worker = worker

    def render(self, person, garment, category, photo_type, folder):
        result = self.worker.render(person, garment, category, photo_type, folder)
        proof = result.get("preservation", {})
        if (result.get("category") != MODEL_CATEGORIES[category]
                or proof.get("nonTargetClothingPreservedExactly") is not True
                or proof.get("changedNonTargetClothingPixels") != 0
                or proof.get("identityPreservedExactly") is not True):
            raise PipelineError("outfit_preservation_failed", "The previous garment could not be preserved reliably. Your earlier render is unchanged.")
        if category == "skirt" and proof.get("skirtTransferValidated") is not True:
            raise PipelineError("outfit_preservation_failed", "Skirt transfer could not be verified. Your earlier render is unchanged.")
        return result


def apply_garment(pipeline, db, person, garment, *, source_run_id, category,
                  photo_type, owner, garment_descriptor=None):
    # Recheck ownership and bytes inside the job, not only during submission.
    source = continuation_input(db, pipeline, source_run_id, owner, category)
    if source != person:
        raise PipelineError("outfit_source_changed", "The previous render changed. Select it again.", 409)
    protected = TryOnPipeline(pipeline.store, PreservingWorker(pipeline.worker))

    def finalize(result):
        result["continuation"] = {"sourceRunId": str(source_run_id), "strategy": "one-complementary-garment",
                                  "preservation": result["provenance"]["weights"]["preservation"]}
        return result

    return protected.run(db, person, garment, None, category, photo_type=photo_type,
                         owner=owner, garment_descriptor=garment_descriptor, finalize=finalize)
