"""Image audit corrections are reproducible and never overwrite user data."""
import hashlib
import json

import mongomock
import pytest

from backend.app import catalog
from scripts import evaluate_wardrobe


def test_review_matches_every_current_reference_without_claiming_inference():
    rows = json.loads((catalog.ROOT / "data/catalog/garments-v2.json").read_text())
    review = json.loads((catalog.ROOT / "data/catalog/classification-review-v1.json").read_text())
    indexed = {r["id"]: r for r in review["garments"]}
    assert len(rows) == len(indexed) == 90
    for row in rows:
        entry = indexed[row["id"]]
        assert entry["imageSha256"] == hashlib.sha256(evaluate_wardrobe.reference_path(row).read_bytes()).hexdigest()
        assert entry["corrected"] == {k: row[k] for k in ("category", "subcategory", "photoType")}
        assert entry["classification"] == row["classification"]
        assert entry["productionApproval"] == "pending_real_inference_and_visual_review"
        assert row["subcategory"] in {item[0] for item in catalog.TAXONOMY}


def test_migration_preserves_ids_favorites_approvals_and_operator_corrections():
    db = mongomock.MongoClient().catalog
    entries = json.loads((catalog.ROOT / "data/catalog/classification-review-v1.json").read_text())["garments"]
    changed = [r for r in entries if r["changed"]]
    first, edited, replaced = changed[:3]
    for entry in (first, edited, replaced):
        db.products.insert_one({"_id": entry["id"], "filename": entry["filename"], **entry["previous"],
                                "name": "Retained name", "description": "Operator text", "active": False,
                                "qualityReview": {"status": "unreviewed"}})
        db.favorites.insert_one({"user_id": "owner", "product_id": entry["id"]})
    db.products.update_one({"_id": edited["id"]}, {"$set": {"subcategory": "operator-value"}})
    db.products.update_one({"_id": replaced["id"]}, {"$set": {"filename": "assets/garments/replacement.jpg"}})
    result = catalog.apply_classification_review(db)
    assert first["id"] in result["applied"]
    assert edited["id"] in result["skipped"] and replaced["id"] in result["skipped"]
    saved = db.products.find_one({"_id": first["id"]})
    assert all(saved[key] == value for key, value in first["corrected"].items())
    assert saved["name"] == "Retained name" and saved["description"] == "Operator text"
    assert saved["qualityReview"] == {"status": "unreviewed"} and saved["active"] is False
    before = list(db.products.find())
    catalog.apply_classification_review(db)
    assert list(db.products.find()) == before
    assert db.products.count_documents({}) == db.favorites.count_documents({}) == 3


def test_changed_reference_bytes_are_not_migrated(tmp_path, monkeypatch):
    entry = {"id": "example", "filename": "assets/garments/example.png", "imageSha256": "0" * 64}
    (tmp_path / "data/catalog").mkdir(parents=True)
    (tmp_path / "assets/garments").mkdir(parents=True)
    (tmp_path / entry["filename"]).write_bytes(b"changed")
    (tmp_path / "data/catalog/classification-review-v1.json").write_text(json.dumps({"garments": [entry]}))
    monkeypatch.setattr(catalog, "ROOT", tmp_path)
    db = mongomock.MongoClient().catalog
    assert catalog.apply_classification_review(db)["skipped"] == ["example"]
    assert db.products.count_documents({}) == 0


def test_evaluator_resolves_product_assets_and_rejects_private_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(evaluate_wardrobe, "ROOT", tmp_path)
    asset = tmp_path / "assets/garments/product.png"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"image")
    assert evaluate_wardrobe.reference_path({"filename": "assets/garments/product.png"}) == asset
    for filename in ("../../.env", str(tmp_path / ".env"), "../../private/result.png"):
        with pytest.raises(ValueError):
            evaluate_wardrobe.reference_path({"filename": filename})
