"""Offline replays exercise the same category gate without approving saved output."""
import json

import numpy as np
import pytest
from PIL import Image

from ml.errors import PipelineError
from scripts import replay_preservation as replay


def test_replay_passes_exact_dress_kind_and_records_rejection(tmp_path, monkeypatch):
    source = tmp_path / "saved"
    source.mkdir()
    for name in ("person-input.png", "raw.png", "source-labels.png", "target-labels.png"):
        Image.fromarray(np.zeros((32, 24, 3) if name in {"person-input.png", "raw.png"}
                                 else (32, 24), dtype=np.uint8)).save(source / name)
    before = {p.name: p.read_bytes() for p in source.iterdir()}

    def reject(**kwargs):
        assert kwargs["garment_kind"] == "dress" and kwargs["category"] == "one-pieces"
        raise PipelineError("dress_transfer_incomplete", "Original trousers remain")

    monkeypatch.setattr(replay, "preserve_regions", reject)
    destination = tmp_path / "replayed"
    report = replay.replay(source, destination, "one-pieces", garment_kind="dress")
    assert report["status"] == "rejected" and report["code"] == "dress_transfer_incomplete"
    assert report["newInference"] is False and report["approval"] == "not_evaluated"
    assert json.loads((destination / "report.json").read_text())["garmentKind"] == "dress"
    assert not (destination / "result.png").exists()
    assert before == {p.name: p.read_bytes() for p in source.iterdir()}


def test_replay_rejects_mismatched_kind_before_creating_files(tmp_path):
    destination = tmp_path / "replayed"
    with pytest.raises(ValueError, match="does not match"):
        replay.replay(tmp_path / "source", destination, "tops", garment_kind="dress")
    assert not destination.exists()


def test_replay_never_overwrites_saved_evidence(tmp_path):
    with pytest.raises(ValueError, match="separate replay"):
        replay.replay(tmp_path, tmp_path / "nested", "tops")
    destination = tmp_path / "previous"
    destination.mkdir()
    with pytest.raises(FileExistsError):
        replay.replay(tmp_path / "source", destination, "tops")
