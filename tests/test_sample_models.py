"""Test Male and Female Sample Models endpoints and assets."""
from pathlib import Path
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_sample_models_list():
    response = client.get("/api/samples/models")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    ids = [m["id"] for m in data]
    assert "male" in ids
    assert "female" in ids

def test_male_model_endpoint():
    response = client.get("/api/samples/person-male")
    assert response.status_code == 200
    assert response.headers["content-type"] in {"image/jpeg", "image/jpg"}
    assert len(response.content) > 10000

def test_female_model_endpoint():
    response = client.get("/api/samples/person-female")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert len(response.content) > 10000

def test_legacy_person_endpoint_preserved():
    response = client.get("/api/samples/person")
    assert response.status_code == 200
    assert response.headers["content-type"] in {"image/jpeg", "image/jpg"}
