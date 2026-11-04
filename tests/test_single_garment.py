"""Production request contract: exactly one reference and one inference operation."""
import io
import time
from threading import BoundedSemaphore
from uuid import uuid4

import mongomock
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app import main
from backend.app.anthropometry.repository import MeasurementRepository, get_repository
from backend.app.jobs import TryOnJobs


def photo(color):
    buffer = io.BytesIO()
    Image.new("RGB", (320, 480), color).save(buffer, "PNG")
    return buffer.getvalue()


@pytest.fixture
def single_api(tmp_path, monkeypatch):
    repo = MeasurementRepository(mongomock.MongoClient(tz_aware=True), "single_api")
    repo.db.command = lambda *args, **kwargs: {"ok": 1}
    main.app.dependency_overrides[get_repository] = lambda: repo
    jobs = TryOnJobs(tmp_path / "jobs", BoundedSemaphore(1))
    monkeypatch.setattr(main, "jobs", jobs)
    monkeypatch.setattr(main, "require_tryon_ready", lambda: None)
    calls = []

    def run(db, person, garment, *args, **kwargs):
        calls.append((person, garment, args, kwargs))
        return {"status": "success", "runId": "transport-only"}

    monkeypatch.setattr(main.pipeline, "run", run)
    try:
        with TestClient(main.app) as client:
            assert client.post("/api/v1/auth/signup", json={
                "name": "Single Test", "email": "single@example.com",
                "password": "Single!Secure2026", "terms_accepted": True,
            }).status_code == 201
            yield client, jobs, calls
    finally:
        jobs.close()
        main.app.dependency_overrides.clear()


@pytest.mark.parametrize("category", ["t-shirt", "shirt", "blouse", "sweater", "jacket", "dress", "trouser", "jeans", "shorts", "skirt"])
def test_single_request_runs_once_and_idempotent_retry_does_not_repeat(single_api, category):
    client, jobs, calls = single_api
    key = str(uuid4())
    person, garment = photo("white"), photo("red")
    options = dict(files={"personImage": ("p.png", person), "garmentImage": ("g.png", garment)},
                   data={"garmentCategory": category, "garmentPhotoType": "model"},
                   headers={"Prefer": "respond-async", "Idempotency-Key": key})
    assert client.post("/api/tryon", **options).status_code == 202
    deadline = time.monotonic() + 4
    while jobs.get(key)["status"] not in {"success", "failed"} and time.monotonic() < deadline:
        time.sleep(.01)
    assert jobs.get(key)["status"] == "success"
    assert client.post("/api/tryon", **options).status_code == 202
    assert len(calls) == 1
    assert calls[0][0:2] == (person, garment)
    assert calls[0][3]["category"] == category
    assert calls[0][3]["photo_type"] == "model"
    assert "bottomwear" not in str(calls[0][3])


@pytest.mark.parametrize("extra", ["garmentImage", "personImage", "bottomwearImage", "topwearImage", "anotherGarment"])
def test_extra_or_duplicate_files_are_rejected_before_inference(single_api, extra):
    client, _, calls = single_api
    files = [("personImage", ("p.png", photo("white"))),
             ("garmentImage", ("g.png", photo("red"))), (extra, ("extra.png", photo("blue")))]
    response = client.post("/api/tryon", files=files, data={"garmentCategory": "shirt"})
    assert response.status_code == 422
    assert "single_garment_only" in response.text
    assert calls == []


def test_retired_metadata_rejected_and_sync_client_still_runs_once(single_api):
    client, _, calls = single_api
    files = {"personImage": ("p.png", photo("white")), "garmentImage": ("g.png", photo("red"))}
    for field in ["bottomwearCategory", "bottomwearPhotoType", "bottomwearProductId", "topwearRunId"]:
        assert client.post("/api/tryon", files=files, data={"garmentCategory": "shirt", field: "old"}).status_code == 422
    assert calls == []
    assert client.post("/api/tryon", files=files, data={"garmentCategory": "shirt"}).status_code == 200
    assert len(calls) == 1
