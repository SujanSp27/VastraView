"""Benchmark requests must exercise the same category gate as app requests."""
import base64
import io
import json

import httpx
import pytest
from PIL import Image

from backend.app.config import settings
from backend.app.online_vton import OnlineTryOn
from ml.errors import PipelineError
from scripts.benchmark_online_vton import render_trial


@pytest.mark.parametrize("category", ["shirt", "dress", "jumpsuit"])
def test_benchmark_discovers_and_sends_exact_garment_kind(tmp_path, monkeypatch, category):
    monkeypatch.setattr(settings, "online_vton_input_encoding", "lossless")
    buffer = io.BytesIO()
    Image.new("RGB", (128, 160), "blue").save(buffer, format="PNG")
    pixels = buffer.getvalue()
    paths = []

    def respond(request):
        paths.append(request.url.path)
        if request.url.path.endswith("/status"):
            return httpx.Response(200, json={"data": [{"ready": True, "device": "cuda",
                "modelRevision": "7720683168567eb5a2a4c67f15116c6e29c83ded",
                "garmentCategories": [category]}]})
        if request.method == "POST":
            assert json.loads(request.content)["data"][3:5] == [category, "model"]
            return httpx.Response(200, json={"event_id": "benchmark"})
        result = {"model": "FASHN VTON 1.5", "device": "cuda",
                  "image": base64.b64encode(pixels).decode()}
        return httpx.Response(200, text="event: complete\ndata: " + json.dumps([result]) + "\n\n")

    worker = OnlineTryOn("https://benchmark.gradio.live", "b" * 32,
                        transport=httpx.MockTransport(respond))
    render_trial(worker, pixels, pixels, category, "model", tmp_path)
    assert paths == ["/gradio_api/run/status", "/gradio_api/call/generate",
                     "/gradio_api/call/generate/benchmark"]
    assert (tmp_path / "tryon-2d.png").read_bytes() == pixels


def test_offline_benchmark_never_submits_images(tmp_path):
    def respond(request):
        assert request.url.path.endswith("/status")
        return httpx.Response(503)

    worker = OnlineTryOn("https://offline.gradio.live", "b" * 32,
                        transport=httpx.MockTransport(respond))
    with pytest.raises(PipelineError) as exc:
        render_trial(worker, b"private person", b"garment", "shirt", "model", tmp_path)
    assert exc.value.code == "online_gpu_unavailable"
    assert not list(tmp_path.iterdir())
