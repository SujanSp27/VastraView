"""The exported update never stops an active worker or resets a runtime."""
import ast
import base64
import json
import socket
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts import export_colab_update as update


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    monkeypatch.setattr(socket, "gethostname", lambda: "runtime-a")
    monkeypatch.setattr(update, "gpu_available", lambda: True)
    monkeypatch.setattr(update, "installation_complete", lambda _: True)
    monkeypatch.setattr(update, "running", lambda _: False)
    monkeypatch.setitem(sys.modules, "fcntl", SimpleNamespace(LOCK_EX=2, LOCK_NB=4, flock=Mock()))
    launch = Mock(return_value={"state": "loading"})
    monkeypatch.setattr(update, "_recover_pinned", launch)
    source = tmp_path / "scripts/online_worker.py"
    source.parent.mkdir()
    source.write_bytes(b"# old worker\n")
    for name in ("worker-token.txt", "worker-config.json", "completed-result.png"):
        (tmp_path / name).write_bytes(b"preserve")
    payload = {"scripts/online_worker.py": base64.b64encode(b"# new worker\n").decode()}
    return tmp_path, payload, launch


@pytest.mark.parametrize("busy", ["inference", "worker", "setup"])
def test_update_refuses_active_worker_and_keeps_sources(runtime, monkeypatch, busy):
    root, payload, launch = runtime
    if busy == "inference":
        (root / "active-generation.json").write_text("{}")
    else:
        monkeypatch.setattr(update, "running", lambda p: p.name == (
            "online_worker.py" if busy == "worker" else "setup_online_worker.py"))
    reply = update.update_stopped_worker(root, payload, "runtime-a")
    assert reply["state"] == "update_pending"
    assert (root / "scripts/online_worker.py").read_bytes() == b"# old worker\n"
    assert not (root / "source-backups").exists()
    launch.assert_not_called()


def test_update_backs_up_sources_before_using_bounded_recovery(runtime):
    root, payload, launch = runtime
    reply = update.update_stopped_worker(root, payload, "runtime-a")
    assert reply["state"] == "loading" and reply["updatedFiles"] == 1
    backup = next((root / "source-backups").iterdir())
    assert (backup / "scripts/online_worker.py").read_bytes() == b"# old worker\n"
    assert json.loads((backup / "manifest.json").read_text())["scripts\\online_worker.py" if sys.platform == "win32" else "scripts/online_worker.py"]["previousSha256"]
    for name in ("worker-token.txt", "worker-config.json", "completed-result.png"):
        assert (root / name).read_bytes() == b"preserve"
    launch.assert_called_once_with(root, payload)


def test_update_wrong_runtime_or_installation_never_launches(runtime, monkeypatch):
    root, payload, launch = runtime
    assert update.update_stopped_worker(root, payload, "runtime-b")["state"] == "runtime_changed"
    monkeypatch.setattr(update, "installation_complete", lambda _: False)
    assert update.update_stopped_worker(root, payload, "runtime-a")["state"] == "existing_installation_required"
    assert not (root / ".recovery.lock").exists()
    launch.assert_not_called()


def test_export_embeds_real_category_and_compositor_sources_without_executing_them():
    source = update.update_source("runtime-a")
    tree = ast.parse(source)
    invocation = tree.body[-1].value.args[0].args[0]
    assert invocation.func.id == "update_stopped_worker"
    payload = ast.literal_eval(invocation.args[1])
    assert "ml/vton/categories.py" in payload
    composite = base64.b64decode(payload["ml/vton/online_composite.py"])
    assert b"semantic-category-preservation-v11" in composite
    assert ast.literal_eval(invocation.args[2]) == "runtime-a"
