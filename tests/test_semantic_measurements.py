"""Torso/hip recovery requires actual image edges and region evidence on both sides."""
import io
from dataclasses import replace

import numpy as np
import pytest
from PIL import Image

from backend.app.anthropometry.measurement_service import MeasurementService, estimate
from backend.app.anthropometry.semantic_measurement import (
    boundary_evidence,
    folded_forearm_at_section,
    region_mask,
)
from ml.errors import PipelineError
from ml.vton.parsing import HumanParse

pytest_plugins = ["test_anthropometry"]


def fixture(observation):
    # Torso is visibly dark, arms are light, while the person mask joins both.
    labels = np.zeros(observation.mask.shape, np.uint8)
    labels[observation.mask] = 6
    labels[250:490, 200:400] = 3
    labels[300:530, 140:200] = 12
    labels[300:530, 400:470] = 12
    observation.mask |= labels == 12
    observation.image[:] = 245
    observation.image[np.isin(labels, (3, 6))] = 40
    observation.image[labels == 12] = [210, 150, 110]
    observation.landmarks[17:23, 3] = 0  # No finger geometry in this fixture.
    return observation, labels


def run(observation, labels, tmp_path, *, fail=False):
    class Detector:
        model_sha256 = "synthetic"
        def detect(self, image):
            return replace(observation, image=image)
    class Parser:
        def predict(self, image):
            assert np.array_equal(image, observation.image)
            if fail:
                raise PipelineError("parser_unavailable", "Missing local assets", 503)
            return HumanParse(labels, {"device": "cpu", "modelVersion": "fixture"})
    encoded = io.BytesIO()
    Image.fromarray(observation.image).save(encoded, format="PNG")
    service = MeasurementService(Detector(), tmp_path, semantic_parser=Parser())
    return service, service.extract(encoded.getvalue(), 160)


def test_all_three_missing_dimensions_recover_without_changing_limbs(observation, tmp_path):
    observation, labels = fixture(observation)
    before, _ = estimate(observation, 160)
    assert all(before["measurements"][key] is None for key in ("chest_circumference", "waist_circumference", "hip_circumference"))
    service, scan = run(observation, labels, tmp_path)
    for key, expected in (("chest_circumference", 98), ("waist_circumference", 92), ("hip_circumference", 96)):
        assert getattr(scan.measurements, key) == expected
        info = scan.quality["metrics"][key]
        assert info["requires_manual_review"] and info["source"] == "image_estimated"
        assert 0 < info["evidence_confidence"] <= 1 and info["confidence"] is None
        assert info["boundary_evidence"]["accepted"]
    for key in ("shoulder_width", "thigh_circumference", "inseam_length"):
        assert getattr(scan.measurements, key) == before["measurements"][key]
    assert service.artifact_path(scan.measurement_id, "_semantic_labels.png").is_file()
    assert service.artifact_path(scan.measurement_id, "_semantic_mask.png").is_file()
    service.remove_artifacts(scan.measurement_id)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("condition", ["no_contrast", "hair", "bag", "crossed_arm", "folded_forearm"])
def test_labels_alone_cannot_create_a_hidden_boundary(observation, tmp_path, condition):
    observation, labels = fixture(observation)
    if condition == "no_contrast":
        observation.image[300:530, 140:470] = 40
    elif condition in ("hair", "bag"):
        labels[300:530, 190:200] = 2 if condition == "hair" else 8
    elif condition == "crossed_arm":
        observation.landmarks[13, :2] = [220 / 600, 280 / 1000]
        observation.landmarks[15, :2] = [380 / 600, 490 / 1000]
    else:
        # Outside the clipped visible fabric span, but occluding its real side.
        observation.landmarks[13, :2] = [180 / 600, 470 / 1000]
        observation.landmarks[15, :2] = [190 / 600, 280 / 1000]
    _, scan = run(observation, labels, tmp_path)
    assert scan.measurements.chest_circumference is None
    assert scan.measurements.waist_circumference is None
    assert scan.measurements.shoulder_width == 40


def test_unavailable_parser_retains_partial_results(observation, tmp_path):
    observation, labels = fixture(observation)
    before, _ = estimate(observation, 160)
    _, scan = run(observation, labels, tmp_path, fail=True)
    assert scan.measurements.model_dump() == before["measurements"]
    assert scan.geometry["refinement_attempts"][-1]["code"] == "parser_unavailable"


@pytest.mark.parametrize("bad", ["shape", "float", "unknown"])
def test_invalid_semantic_maps_are_not_used(observation, bad):
    labels = np.zeros(observation.mask.shape, np.uint8)
    if bad == "shape":
        labels = labels[:100]
    elif bad == "float":
        labels = labels.astype(float)
    else:
        labels[:] = 18
    with pytest.raises(PipelineError, match="aligned"):
        region_mask(observation, labels)


def test_local_waist_minimum_and_hip_maximum_use_visible_contours(observation):
    observation, labels = fixture(observation)
    # A real narrower waist at 64% of shoulder-to-hip length.
    labels[405:416, 200:225] = 12
    labels[405:416, 375:400] = 12
    observation.image[labels == 12] = [210, 150, 110]
    # Hip expands below joint level, independently of joint spacing.
    labels[525:545, 190:410] = 6
    labels[525:545, 175:190] = 12
    labels[525:545, 410:425] = 12
    observation.mask[525:545, 175:425] = True
    observation.image[labels == 6] = 40
    observation.image[labels == 12] = [210, 150, 110]
    result, _ = estimate(replace(observation, mask=region_mask(observation, labels)), 160, region_labels=labels)
    assert result["measurements"]["waist_circumference"] == 69
    assert result["geometry"]["waist_torso_fraction"] == .64
    assert result["measurements"]["hip_circumference"] == 105.6
    larger, _ = estimate(replace(observation, mask=region_mask(observation, labels)), 200, region_labels=labels)
    for key in ("chest_circumference", "waist_circumference", "hip_circumference"):
        assert larger["measurements"][key] == pytest.approx(result["measurements"][key] * 1.25, abs=.02)


def test_outside_image_cannot_supply_edge_evidence():
    image = np.zeros((20, 20, 3), np.uint8)
    labels = np.full((20, 20), 3, np.uint8)
    evidence = boundary_evidence(image, labels, (np.array([0., 10.]), np.array([19., 10.])), np.array([0., 1.]))
    assert not evidence["accepted"]


def test_folded_elbow_skin_below_joint_is_not_a_torso_edge(observation):
    points = observation.landmarks[:, :2] * [600, 1000]
    points[13], points[15] = [180, 470], [190, 280]
    section = (np.array([200., 480.]), np.array([400., 480.]))
    valid = np.ones(33, dtype=bool)
    assert folded_forearm_at_section(points, valid, section, {"adjacent_label_ids": [[12], [0]]})
    assert not folded_forearm_at_section(points, valid, section, {"adjacent_label_ids": [[0], [0]]})


@pytest.mark.integration
def test_real_male_and_female_photos_use_existing_cpu_parser(tmp_path):
    from backend.app.anthropometry.pose_adapter import MediaPipePose, decode_person
    from backend.app.config import ROOT, settings
    from ml.vton.parsing import FashnHumanParser

    photos = [ROOT / "data/raw/studio-person.jpg",
              ROOT / "data/processed/1fbe7846-eb2d-4b22-a8ef-0f79e94c48c0/original-person.png",
              ROOT / "data/processed/5c554801-c873-4633-a35b-7df508b6d58d/original-person.png",
              ROOT / "data/raw/fashn-samples/person5.png"]
    parser = FashnHumanParser()
    if not parser.available() or not settings.measurement_model_path.is_file() or not all(p.is_file() for p in photos):
        pytest.skip("Local pinned CPU checkpoints and permitted private regression photos required")
    detector = MediaPipePose(settings.measurement_model_path)
    service = MeasurementService(detector, tmp_path, semantic_parser=parser)
    try:
        for index, path in enumerate(photos):
            data = path.read_bytes()
            baseline, _ = estimate(detector.detect(decode_person(data)), 172)
            scan = service.extract(data, 172)
            if index == 3:
                assert scan.measurements.chest_circumference is None
                # Visual review: upper sections end on raised forearms. Only
                # the lower shirt boundary below both elbows remains visible.
                # It is clothing evidence, not an accurate anatomical waist.
                assert scan.measurements.waist_circumference is not None
                assert scan.geometry["waist_torso_fraction"] == .72
                waist = scan.quality["metrics"]["waist_circumference"]
                assert waist["requires_manual_review"]
                assert not any(label in (12, 13) for side in waist["boundary_evidence"]["adjacent_label_ids"] for label in side)
                assert scan.measurements.hip_circumference == baseline["measurements"]["hip_circumference"]
            for key in (() if index == 3 else ("chest_circumference", "waist_circumference", "hip_circumference")):
                assert getattr(scan.measurements, key) is not None
                if baseline["measurements"][key] is None:
                    assert scan.quality["metrics"][key]["requires_manual_review"]
                    assert scan.quality["metrics"][key]["boundary_evidence"]["accepted"]
            if index == 3:
                assert scan.measurements.thigh_circumference is not None
                if baseline["measurements"]["thigh_circumference"] is None:
                    assert scan.quality["metrics"]["thigh_circumference"]["requires_manual_review"]
            for key in ("shoulder_width", "inseam_length"):
                assert getattr(scan.measurements, key) == baseline["measurements"][key]
            assert scan.provenance["local_gpu_used"] is False
            if index == 0:
                assert "semantic_parser" not in scan.geometry  # No extra model work for complete scans.
    finally:
        detector.close()
