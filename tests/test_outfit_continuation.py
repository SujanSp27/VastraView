"""One additional generation, ownership and preservation checks; not visual approval."""
import pytest
from fastapi import HTTPException

from backend.app.outfit_continuation import apply_garment, continuation_input
from ml.errors import PipelineError
from tests import test_outfits
from tests.test_outfits import photo


@pytest.fixture
def setup(tmp_path):
    yield from test_outfits.setup.__wrapped__(tmp_path)


def first(db, pipeline):
    return pipeline.run(db, photo("white"), photo("red"), None, "shirt", owner="alice")


def test_complementary_garment_uses_exact_owned_result_once(setup):
    db, pipeline, worker = setup
    previous = first(db, pipeline)
    person = continuation_input(db, pipeline, previous["runId"], "alice", "trouser")
    final = apply_garment(pipeline, db, person, photo("blue"), source_run_id=previous["runId"],
                          category="trouser", photo_type="flat-lay", owner="alice")
    assert len(worker.calls) == 2
    assert worker.calls[1][0] == person == photo("green")
    assert final["continuation"]["sourceRunId"] == previous["runId"]
    assert (pipeline.store.folder(previous["runId"]) / "tryon-2d.png").read_bytes() == person


@pytest.mark.parametrize("category", ["shirt", "dress", "jumpsuit", "shoes"])
def test_wrong_region_does_not_generate(setup, category):
    db, pipeline, worker = setup
    previous = first(db, pipeline)
    with pytest.raises(PipelineError, match="other|lower-body"):
        continuation_input(db, pipeline, previous["runId"], "alice", category)
    assert len(worker.calls) == 1


def test_other_user_cannot_continue_saved_render(setup):
    db, pipeline, worker = setup
    previous = first(db, pipeline)
    with pytest.raises(HTTPException) as error:
        continuation_input(db, pipeline, previous["runId"], "bob", "jeans")
    assert error.value.status_code == 404 and len(worker.calls) == 1


def test_no_preservation_proof_does_not_publish_result(setup):
    db, pipeline, worker = setup
    previous = first(db, pipeline)
    person = continuation_input(db, pipeline, previous["runId"], "alice", "jeans")
    worker.proof["changedNonTargetClothingPixels"] = 7
    with pytest.raises(PipelineError, match="preserved reliably"):
        apply_garment(pipeline, db, person, photo("blue"), source_run_id=previous["runId"],
                      category="jeans", photo_type="flat-lay", owner="alice")
    assert (pipeline.store.folder(previous["runId"]) / "tryon-2d.png").read_bytes() == person
