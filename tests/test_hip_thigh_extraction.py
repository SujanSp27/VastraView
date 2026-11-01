"""Integration tests verifying M4 (Hip circumference) and M5 (Thigh circumference)

extraction across male and female sample models in VastraView.
"""
from pathlib import Path
import mongomock
import pytest
from fastapi.testclient import TestClient

from backend.app.config import ROOT, settings
from backend.app.main import app
from backend.app.anthropometry.repository import MeasurementRepository, get_repository
from backend.app.anthropometry.measurement_service import REASON_MESSAGES


FEMALE_MODEL = ROOT / "assets/Model/vastraview_female_model.png"
MALE_MODEL = ROOT / "assets/Model/studio-person.jpg"


@pytest.fixture
def repository():
    repo = MeasurementRepository(mongomock.MongoClient(tz_aware=True), "test_hip_thigh")
    repo.db.command = lambda *args, **kwargs: {"ok": 1}
    repo.initialize()
    yield repo
    repo.close()


@pytest.fixture
def api_client(repository):
    app.dependency_overrides[get_repository] = lambda: repository
    client = TestClient(app, raise_server_exceptions=True)
    try:
        yield client
    finally:
        client.close()
        app.dependency_overrides.clear()


def test_female_sample_model_extracts_all_six_measurements(api_client):
    """Verify female sample model extracts all 6 measurements (M1-M6)

    with valid numerical values (no Unavailable for M4 Hip or M5 Thigh).
    """
    assert FEMALE_MODEL.is_file(), f"Missing female model image at {FEMALE_MODEL}"

    with open(FEMALE_MODEL, "rb") as f:
        response = api_client.post(
            "/api/v1/measurements/extract",
            data={"height_cm": 170.0, "gender": "female"},
            files={"image": ("vastraview_female_model.png", f, "image/png")},
        )

    assert response.status_code == 200, response.text
    data = response.json()
    measurements = data["measurements"]
    quality = data["quality"]["metrics"]

    # Verify all 6 measurements are present and numerical
    for key in (
        "shoulder_width",
        "chest_circumference",
        "waist_circumference",
        "hip_circumference",
        "thigh_circumference",
        "inseam_length",
    ):
        val = measurements.get(key)
        assert val is not None, f"Expected numerical value for {key}, got None"
        assert isinstance(val, (int, float)) and val > 0, f"Expected positive number for {key}, got {val}"
        metric_q = quality.get(key, {})
        assert metric_q.get("status") != "unavailable", f"{key} marked unavailable: {metric_q}"

    # Specific bounds for female sample model at 170 cm
    assert 30.0 < measurements["shoulder_width"] < 45.0
    assert 65.0 < measurements["chest_circumference"] < 95.0
    assert 55.0 < measurements["waist_circumference"] < 80.0
    assert 85.0 < measurements["hip_circumference"] < 125.0
    assert 40.0 < measurements["thigh_circumference"] < 65.0
    assert 70.0 < measurements["inseam_length"] < 95.0


def test_male_sample_model_extracts_all_six_measurements(api_client):
    """Verify male sample model extracts all 6 measurements (M1-M6)

    with valid numerical values.
    """
    assert MALE_MODEL.is_file(), f"Missing male model image at {MALE_MODEL}"

    with open(MALE_MODEL, "rb") as f:
        response = api_client.post(
            "/api/v1/measurements/extract",
            data={"height_cm": 178.0, "gender": "male"},
            files={"image": ("studio-person.jpg", f, "image/jpeg")},
        )

    assert response.status_code == 200, response.text
    data = response.json()
    measurements = data["measurements"]
    quality = data["quality"]["metrics"]

    # Verify all 6 measurements are present and numerical
    for key in (
        "shoulder_width",
        "chest_circumference",
        "waist_circumference",
        "hip_circumference",
        "thigh_circumference",
        "inseam_length",
    ):
        val = measurements.get(key)
        assert val is not None, f"Expected numerical value for {key}, got None"
        assert isinstance(val, (int, float)) and val > 0, f"Expected positive number for {key}, got {val}"
        metric_q = quality.get(key, {})
        assert metric_q.get("status") != "unavailable", f"{key} marked unavailable: {metric_q}"

    # Specific bounds for male sample model at 178 cm
    assert 38.0 < measurements["shoulder_width"] < 55.0
    assert 80.0 < measurements["chest_circumference"] < 115.0
    assert 70.0 < measurements["waist_circumference"] < 100.0
    assert 85.0 < measurements["hip_circumference"] < 115.0
    assert 45.0 < measurements["thigh_circumference"] < 70.0
    assert 75.0 < measurements["inseam_length"] < 95.0


def test_guidance_messages_on_unavailable_hip_and_thigh():
    """Verify user-friendly guidance messages when hip or thigh is unavailable."""
    hip_msg = REASON_MESSAGES["hip_outline_unavailable"]
    assert "The outer hip outline is obscured or incomplete" in hip_msg
    assert "Keep your full hip outline visible" in hip_msg
    assert "Avoid loose clothing covering your hip area" in hip_msg

    thigh_touch_msg = REASON_MESSAGES["hand_overlaps_thigh"]
    assert "A hand or arm touches the upper-thigh outline" in thigh_touch_msg
    assert "Keep your hands away from your thighs and leave a small gap between your legs." in thigh_touch_msg

    thigh_overlap_msg = REASON_MESSAGES["ambiguous_thigh"]
    assert "Both upper-thigh boundaries cannot be distinguished reliably" in thigh_overlap_msg
    assert "Keep your hands away from your thighs and leave a small gap between your legs." in thigh_overlap_msg
