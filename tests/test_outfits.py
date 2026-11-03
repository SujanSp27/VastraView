"""Deterministic orchestration tests. Fake pixels are not visual quality evidence."""
import io
from threading import BoundedSemaphore

import pytest
from fastapi import HTTPException
from PIL import Image
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.db import Base
from backend.app.jobs import TryOnJobs
from backend.app.models import Run
from backend.app.online_vton import normalized_image
from backend.app.outfits import OutfitFailure, run_outfit
from backend.app.pipeline import TryOnPipeline
from backend.app.storage import AssetStore
from ml.errors import PipelineError
from ml.progress import observe_progress, report_progress
from ml.vton.categories import MODEL_CATEGORIES


def photo(color):
    buffer = io.BytesIO()
    Image.new("RGB", (320, 480), color).save(buffer, "PNG")
    return buffer.getvalue()


class Worker:
    def __init__(self):
        self.calls = []
        self.proof = {"nonTargetClothingPreservedExactly": True, "changedNonTargetClothingPixels": 0,
                      "identityPreservedExactly": True}
        self.fail = False

    def render(self, person, garment, category, photo_type, folder):
        self.calls.append((person, garment, category, photo_type))
        report_progress("generating", 1, 10)
        if self.fail and MODEL_CATEGORIES[category] == "bottoms":
            raise PipelineError("online_timeout", "Worker timed out", 504)
        (folder / "original-person.png").write_bytes(normalized_image(person))
        (folder / "garment-reference.png").write_bytes(normalized_image(garment))
        (folder / "tryon-2d.png").write_bytes(photo("green" if MODEL_CATEGORIES[category] == "tops" else "blue"))
        return {"category": MODEL_CATEGORIES[category], "preservation": self.proof,
                "inferenceSeconds": 1.0}


@pytest.fixture
def setup(tmp_path):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        worker = Worker()
        yield db, TryOnPipeline(AssetStore(tmp_path / "assets"), worker), worker
    engine.dispose()


def generate(db, pipeline, **kwargs):
    return run_outfit(pipeline, db, photo("white"), photo("red"), photo("black"),
                      top_category="shirt", bottom_category="jeans", owner="alice", **kwargs)


def test_sequential_input_and_independent_original_retention(setup):
    db, pipeline, worker = setup
    progress = []
    with observe_progress(progress.append):
        result = generate(db, pipeline)
    top = result["outfit"]["topwear"]
    assert worker.calls[1][0] == (pipeline.store.folder(top["runId"]) / "tryon-2d.png").read_bytes()
    assert [c[2] for c in worker.calls] == ["shirt", "jeans"]
    assert {p["stage"] for p in progress} == {"outfit_topwear", "outfit_bottomwear"}
    folder = pipeline.store.folder(result["runId"])
    assert (folder / "outfit-original.png").read_bytes() == normalized_image(photo("white"))
    assert (folder / "original-person.png").read_bytes() == normalized_image(photo("green"))
    pipeline.store.delete(top["runId"])
    assert (folder / "topwear-preview.png").is_file()
    assert db.get(Run, result["runId"]).metadata_json["result"] == result


def test_bottom_failure_retains_top_and_retry_avoids_duplicate_top(setup):
    db, pipeline, worker = setup
    worker.fail = True
    with pytest.raises(OutfitFailure) as exc:
        generate(db, pipeline)
    top = exc.value.partial_result
    assert db.get(Run, top["runId"]).status == "success"
    assert exc.value.code == "online_timeout"
    worker.fail = False
    result = generate(db, pipeline, top_run_id=top["runId"])
    assert result["outfit"]["topwearReused"]
    assert [c[2] for c in worker.calls] == ["shirt", "jeans", "jeans"]


@pytest.mark.parametrize("field,value", [("nonTargetClothingPreservedExactly", False),
                                         ("changedNonTargetClothingPixels", 1),
                                         ("identityPreservedExactly", False)])
def test_failed_preservation_never_becomes_combined_success(setup, field, value):
    db, pipeline, worker = setup
    worker.proof[field] = value
    with pytest.raises(OutfitFailure, match="could not verify"):
        generate(db, pipeline)
    assert sorted(db.scalars(select(Run.status))) == ["failed", "success"]


def test_reuse_requires_owner_and_identical_inputs(setup):
    db, pipeline, worker = setup
    result = generate(db, pipeline)
    top_id = result["outfit"]["topwear"]["runId"]
    from backend.app.outfits import reusable_top
    with pytest.raises(HTTPException) as exc:
        reusable_top(db, pipeline, top_id, "mallory", photo("white"), photo("red"), "shirt", "flat-lay")
    assert exc.value.status_code == 404
    with pytest.raises(PipelineError, match="person or topwear changed"):
        reusable_top(db, pipeline, top_id, "alice", photo("yellow"), photo("red"), "shirt", "flat-lay")
    assert len(worker.calls) == 2


def test_incomplete_packaging_is_not_published(setup, monkeypatch):
    from backend.app import outfits
    db, pipeline, _ = setup
    def fail(*args):
        statuses = list(db.scalars(select(Run.status)))
        assert sorted(statuses) == ["processing", "success"]
        raise OSError("Disk unavailable")
    monkeypatch.setattr(outfits.shutil, "copyfile", fail)
    with pytest.raises(OutfitFailure):
        generate(db, pipeline)
    assert sorted(db.scalars(select(Run.status))) == ["failed", "success"]


def test_restart_retains_checkpoint_without_repeating_inference(tmp_path):
    from uuid import uuid4
    key = str(uuid4())
    worker = TryOnJobs(tmp_path, BoundedSemaphore(1))
    try:
        worker._save({"jobId": key, "status": "processing", "owner": "alice", "createdAt": 1,
                      "requestHash": "original", "partialResult": {"runId": "saved-top"}})
        worker.recover_interrupted()
        result = worker.get(key, owner="alice")
        assert result["status"] == "failed"
        assert result["partialResult"] == {"runId": "saved-top"}
        assert result["error"]["code"] == "job_interrupted"
    finally:
        worker.close()


@pytest.mark.parametrize("top,bottom", [("dress", "jeans"), ("shirt", "jumpsuit"), ("jeans", "shirt")])
def test_invalid_roles_fail_before_inference(setup, top, bottom):
    db, pipeline, worker = setup
    with pytest.raises(PipelineError, match="separate topwear"):
        run_outfit(pipeline, db, photo("white"), photo("red"), photo("black"),
                   top_category=top, bottom_category=bottom, owner="alice")
    assert not worker.calls


def test_invalid_bottom_image_fails_before_top_inference(setup):
    db, pipeline, worker = setup
    with pytest.raises(PipelineError):
        run_outfit(pipeline, db, photo("white"), photo("red"), b"not an image",
                   top_category="shirt", bottom_category="jeans", owner="alice")
    assert not worker.calls


def test_partial_job_is_failed_and_owner_scoped(tmp_path):
    with pytest.raises(PipelineError, match="not found"):
        worker = TryOnJobs(tmp_path, BoundedSemaphore(1))
        try:
            def fail():
                raise OutfitFailure(PipelineError("timeout", "Offline"), {"runId": "saved-top"})
            job = worker.submit(b"p", b"g", {"owner": "alice"}, fail)
            worker.close()
            state = worker.get(job["jobId"], owner="alice")
            assert state["status"] == "failed" and "result" not in state
            assert state["partialResult"]["runId"] == "saved-top"
            worker.get(job["jobId"], owner="mallory")
        finally:
            worker.close()


def test_outfit_api_auth_validation_and_idempotency(tmp_path, monkeypatch):
    import time
    from uuid import uuid4

    import mongomock
    from fastapi.testclient import TestClient

    from backend.app import main, outfits
    from backend.app.anthropometry.repository import MeasurementRepository, get_repository

    repo = MeasurementRepository(mongomock.MongoClient(tz_aware=True), "outfit_api")
    repo.db.command = lambda *a, **kw: {"ok": 1}
    jobs = TryOnJobs(tmp_path / "jobs", BoundedSemaphore(1))
    main.app.dependency_overrides[get_repository] = lambda: repo
    monkeypatch.setattr(main, "jobs", jobs)
    monkeypatch.setattr(main, "require_tryon_ready", lambda: None)
    calls = []
    def run(*args, **kwargs):
        calls.append((args[2:5], kwargs))
        return {"status": "success", "runId": "transport-only"}
    monkeypatch.setattr(outfits, "run_outfit", run)
    key = str(uuid4())
    files = {"personImage": ("p.png", photo("white")), "garmentImage": ("g.png", photo("red")),
             "bottomwearImage": ("b.png", photo("black"))}
    options = dict(files=files, data={"garmentCategory": "shirt", "bottomwearCategory": "jeans"},
                   headers={"Idempotency-Key": key})
    try:
        with TestClient(main.app) as client:
            assert client.post("/api/tryon/outfit", **options).status_code == 401
            assert client.post("/api/v1/auth/signup", json={"name": "Outfit Test", "email": "outfit@example.com",
                "password": "Outfit!Secure2026", "terms_accepted": True}).status_code == 201
            bad = {**options, "data": {"garmentCategory": "dress", "bottomwearCategory": "jeans"}}
            assert client.post("/api/tryon/outfit", **bad).status_code == 422
            ack = client.post("/api/tryon/outfit", **options)
            assert ack.status_code == 202, ack.text
            assert ack.headers["location"] == f"/api/tryon/jobs/{key}"
            deadline = time.monotonic() + 4
            while jobs.get(key)["status"] not in {"success", "failed"} and time.monotonic() < deadline:
                time.sleep(.01)
            assert jobs.get(key)["status"] == "success"
            assert client.post("/api/tryon/outfit", **options).status_code == 202
            changed = {**options, "files": {**files, "bottomwearImage": ("b.png", photo("blue"))}}
            assert client.post("/api/tryon/outfit", **changed).status_code == 409
            assert len(calls) == 1
            assert calls[0][0][2] == photo("black")
            assert calls[0][1]["bottom_category"] == "jeans"
    finally:
        jobs.close()
        main.app.dependency_overrides.clear()


def test_catalog_role_filter_intersects_category_without_changing_records(monkeypatch):
    import mongomock

    from backend.app import catalog
    db = mongomock.MongoClient().db
    rows = [{"_id": cat, "category": cat, "name": cat} for cat in ("shirt", "jeans", "skirt", "dress")]
    db.products.insert_many(rows)
    monkeypatch.setattr(catalog, "visible_query", lambda db: {})
    monkeypatch.setattr(catalog, "public_product", lambda row, db: row)
    options = dict(q="", category=None, subcategory=None, audience=None, brand_id=None, color=None,
                   occasion=None, tryon_supported=None, sort="name", limit=48, offset=0, db=db)
    assert {r["_id"] for r in catalog.products(**options, garment_type="bottomwear")["items"]} == {"jeans", "skirt"}
    assert catalog.products(**{**options, "category": "shirt"}, garment_type="bottomwear")["total"] == 0
    assert db.products.count_documents({}) == 4
