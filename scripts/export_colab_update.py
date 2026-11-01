"""Export a private, pinned update cell when the notebook helper is unavailable.

This deliberately never terminates a worker. A running legacy worker cannot be
drained atomically through its inference API; the cell reports update_pending
until it has stopped. It retains weights, runs, configuration and credentials.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path

from scripts.auto_connect_colab import recovery_source, valid_hostname
from scripts.colab_control import ROOT
from scripts.colab_worker_recovery import (
    _recover_pinned,
    gpu_available,
    installation_complete,
    running,
    validated_sources,
)


def update_stopped_worker(root, payload, expected_hostname):
    # Imported by the generated cell, independently of the local application.
    import hashlib
    import json
    import socket
    import time

    if socket.gethostname() != expected_hostname:
        return {"state": "runtime_changed"}
    if not gpu_available() or not installation_complete(root):
        return {"state": "existing_installation_required"}
    sources = validated_sources(root, payload)
    for target, data in sources.items():
        compile(data, str(target), "exec")
    import fcntl
    with (root / ".recovery.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"state": "notebook_busy"}
        if ((root / "active-generation.json").exists()
                or running(root / "scripts/online_worker.py")
                or running(root / "scripts/setup_online_worker.py")):
            return {"state": "update_pending", "reason": "Existing worker/setup is running; no files changed or processes stopped."}
        changed = {target: data for target, data in sources.items()
                   if not target.is_file() or target.read_bytes() != data}
        backup = root / "source-backups" / str(time.time_ns())
        if changed:
            backup.mkdir(parents=True, exist_ok=False)
            manifest = {}
            for target, data in changed.items():
                name = str(target.relative_to(root))
                previous = target.read_bytes() if target.is_file() else None
                manifest[name] = {"previousSha256": hashlib.sha256(previous).hexdigest() if previous is not None else None,
                                  "newSha256": hashlib.sha256(data).hexdigest()}
                if previous is not None:
                    saved = backup / name
                    saved.parent.mkdir(parents=True, exist_ok=True)
                    saved.write_bytes(previous)
            (backup / "manifest.json").write_text(json.dumps(manifest, indent=2))
        # The existing bounded launch policy applies; no profile override,
        # package installation or model download is requested by this updater.
        reply = _recover_pinned(root, payload)
        reply.pop("connection", None)
        return {**reply, "updatedFiles": len(changed),
                "backup": str(backup) if changed else None}


def update_source(hostname):
    import inspect
    if not valid_hostname(hostname):
        raise ValueError("Verify and pin the existing runtime hostname first")
    tree = ast.parse(recovery_source(expected_hostname=hostname))
    # Reuse the real worker payload and recovery definitions, not a second list
    # of dependencies that can drift away from production recovery.
    invocation = tree.body[-1].value.args[0].args[0]
    payload = ast.literal_eval(invocation.args[1])
    definitions = ast.unparse(ast.Module(body=tree.body[:-1], type_ignores=[]))
    source = ("# VastraView preservation update; existing stopped worker only\n"
              + definitions + "\n" + inspect.getsource(update_stopped_worker)
              + "\nprint(json.dumps(update_stopped_worker(Path('/content/formfit-online'), "
              + repr(payload) + ", " + repr(hostname) + ")))\n")
    compile(source, "<colab-update>", "exec")
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    state = json.loads((ROOT / ".runtime/colab-autoconnect.json").read_text())
    source = update_source(state.get("expectedHostname"))
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    with args.destination.open("x", encoding="utf-8") as output:
        output.write(source)
    print(json.dumps({"state": "exported_not_deployed", "path": str(args.destination),
                      "sha256": hashlib.sha256(source.encode()).hexdigest()}))


if __name__ == "__main__":
    main()
