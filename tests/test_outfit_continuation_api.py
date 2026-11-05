import time
from uuid import uuid4

import pytest

from backend.app import outfit_continuation
from tests import test_single_garment
from tests.test_single_garment import photo


@pytest.fixture
def single_api(tmp_path, monkeypatch):
    yield from test_single_garment.single_api.__wrapped__(tmp_path, monkeypatch)


def test_continuation_schedules_one_owned_input_and_deduplicates(single_api, monkeypatch):
    client, jobs, _ = single_api
    calls = []
    original = photo("green")
    monkeypatch.setattr(outfit_continuation, "continuation_input", lambda *args: original)
    monkeypatch.setattr(outfit_continuation, "apply_garment", lambda *args, **kw:
                        calls.append((args, kw)) or {"status": "success"})
    key, source = str(uuid4()), str(uuid4())
    options = dict(files={"garmentImage": ("pants.png", photo("blue"))},
                   data={"sourceRunId": source, "garmentCategory": "jeans", "garmentPhotoType": "flat-lay"},
                   headers={"Idempotency-Key": key})
    assert client.post("/api/tryon/apply", **options).status_code == 202
    deadline = time.monotonic() + 4
    while jobs.get(key)["status"] not in {"success", "failed"} and time.monotonic() < deadline:
        time.sleep(.01)
    assert jobs.get(key)["status"] == "success"
    assert client.post("/api/tryon/apply", **options).status_code == 202
    assert len(calls) == 1 and calls[0][0][2] == original
    assert calls[0][1]["source_run_id"] == source
    assert calls[0][1]["category"] == "jeans"


def test_continuation_rejects_client_person_and_duplicate_garments(single_api):
    client, _, calls = single_api
    for extra in ["personImage", "garmentImage", "topwearImage"]:
        response = client.post("/api/tryon/apply", files=[
            ("garmentImage", ("pants.png", photo("blue"))), (extra, ("extra.png", photo("red")))],
            data={"sourceRunId": str(uuid4()), "garmentCategory": "jeans"})
        assert response.status_code == 422
        assert "outfit_inputs" in response.text
    assert calls == []
