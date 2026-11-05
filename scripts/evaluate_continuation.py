"""Resume one real, authenticated saved-render continuation; no quality auto-approval."""
import argparse
import json
import time
from pathlib import Path
from uuid import uuid4

import httpx

from backend.app.config import ROOT
from scripts.evaluate_wardrobe import authenticate, catalog_rows, digest, reference_path, save, sheet
from scripts.worker_audits import retrieve_http


def run(folder, source, product_id, session):
    row = next(row for row in catalog_rows() if row["id"] == product_id)
    garment_path = reference_path(row)
    garment = garment_path.read_bytes()
    inputs = {"sourceRunId": source, "productId": product_id, "garmentSha256": digest(garment)}
    path = folder / "trial.json"
    state = json.loads(path.read_text()) if path.exists() else {
        "jobId": str(uuid4()), "inputs": inputs, "status": "prepared", "visualStatus": "not_reviewed"}
    if state["inputs"] != inputs:
        raise ValueError("Inputs changed; use a new evidence directory")
    save(path, state)
    if state["status"] in {"generated", "failed"}:
        return state
    with httpx.Client(base_url="http://127.0.0.1:8000", trust_env=False, timeout=30) as client:
        authenticate(client, session)
        if state["status"] == "prepared":
            state.update(status="submitting", startedAt=time.time())
            save(path, state)
            response = client.post("/api/tryon/apply", files={"garmentImage": (garment_path.name, garment)},
                                   data={"sourceRunId": source, "garmentCategory": row["category"],
                                         "garmentPhotoType": row["photoType"], "productId": product_id},
                                   headers={"Idempotency-Key": state["jobId"]})
            if response.status_code != 202:
                state.update(status="failed", error=response.json())
                save(path, state)
                return state
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            response = client.get("/api/tryon/jobs/" + state["jobId"])
            response.raise_for_status()
            job = response.json()
            if job["status"] in {"success", "failed"}:
                break
            time.sleep(2)
        else:
            return state
        save(folder / "job.json", job)
        if job["status"] == "failed":
            state.update(status="failed", error=job.get("error"))
        else:
            result = job["result"]
            for name, url in [("before.png", result["originalUrl"]), ("after.png", result["previewUrl"])]:
                response = client.get(url)
                response.raise_for_status()
                (folder / name).write_bytes(response.content)
            state.update(status="generated", runId=result["runId"], timingSeconds=result["timingSeconds"],
                         observedEndToEndSeconds=round(time.time()-state["startedAt"], 3),
                         diagnostics=result["provenance"]["weights"], continuation=result["continuation"])
            sheet([folder / "before.png", garment_path, folder / "after.png"],
                  ["Previous actual render", row["name"], "Actual continuation"], folder / "comparison.jpg", 3, (400, 640))
        save(path, state)
        if state["status"] == "generated":
            retrieve_http(folder, state, ROOT / ".runtime/online-connection.json")
        return state


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", type=Path, required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--product", required=True)
    parser.add_argument("--session", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.folder, args.source, args.product, args.session)
    print(json.dumps({key: result.get(key) for key in ("status", "runId", "timingSeconds", "error")}))
