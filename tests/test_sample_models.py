"""Test Male and Female Sample Models endpoints and assets."""
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app import main
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
    with Image.open(io.BytesIO(response.content)) as image:
        image.load()
        assert image.format in {"PNG", "JPEG"}
        assert response.headers["content-type"] == Image.MIME[image.format]
        assert min(image.size) >= 128
        model = next(m for m in client.get("/api/samples/models").json() if m["id"] == "male")
        assert Path(model["filename"]).suffix == (".png" if image.format == "PNG" else ".jpg")
    assert len(response.content) > 10000

def test_female_model_endpoint():
    response = client.get("/api/samples/person-female")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert len(response.content) > 10000

def test_legacy_person_endpoint_preserved():
    response = client.get("/api/samples/person")
    assert response.status_code == 200
    current = client.get("/api/samples/person-male")
    assert response.content == current.content
    assert response.headers["content-type"] == current.headers["content-type"]


@pytest.mark.parametrize("filename,gender", [
    ("assets/Model/studio-person.png", "male"),
    ("assets/Model/studio-person.jpg", "male"),
    ("data/raw/studio-person.jpg", "male"),
    ("assets/Model/vastraview_female_model.png", "female"),
])
def test_sample_discovery_matches_available_asset(tmp_path, monkeypatch, filename, gender):
    monkeypatch.setattr(main, "ROOT", tmp_path)
    monkeypatch.setattr(main.settings, "environment", "development")
    assert client.get("/api/samples/models").json() == []
    assert not client.get("/api/v1/public-config").json()["sample_photos"]
    target = tmp_path / filename
    target.parent.mkdir(parents=True)
    Image.new("RGB", (128, 256), "navy").save(target)
    models = client.get("/api/samples/models").json()
    assert len(models) == 1
    assert models[0]["id"] == gender
    assert models[0]["filename"] == target.name
    assert client.get(models[0]["url"]).content == target.read_bytes()
    assert client.get("/api/v1/public-config").json()["sample_photos"]
    monkeypatch.setattr(main.settings, "environment", "production")
    assert client.get("/api/samples/models").json() == []
    assert not client.get("/api/v1/public-config").json()["sample_photos"]
    assert client.get(models[0]["url"]).status_code == 404
