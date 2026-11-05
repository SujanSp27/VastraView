"""Classification evidence must not become invented construction or quality claims."""
import json

import mongomock
import pytest

from backend.app.catalog import supported_routing_query
from backend.app.config import ROOT
from ml.vton.garment_metadata import describe_garment


def test_entire_current_catalog_has_consistent_body_routing():
    rows = json.loads((ROOT / "data/catalog/garments-v2.json").read_text())
    assert len(rows) == 90
    for row in rows:
        result = describe_garment(row)
        assert result["routingStatus"] == "supported", (row["id"], result)
        assert result["targetRegion"] == row["classification"]["coverage"]
        assert result["qualityVerified"] is False
        assert all(value is None for value in result["construction"].values())


@pytest.mark.parametrize("changes,issue", [
    ({"subcategory": "skirt"}, "subcategory_requires_review"),
    ({"subcategory": "saree"}, "subcategory_requires_review"),
    ({"category": "shoes"}, "unsupported_category"),
    ({"subcategory": "unrecognized"}, "unknown_subcategory"),
    ({"classification": {"pieces": 2}}, "multiple_or_unknown_pieces"),
    ({"classification": {"coverage": "lower-body"}}, "coverage_conflict"),
])
def test_conflicts_do_not_route_as_ordinary_shirts(changes, issue):
    result = describe_garment({"category": "shirt", "subcategory": "shirt", **changes})
    assert result["routingStatus"] == "needs_review"
    assert issue in result["issues"]


def test_no_closure_or_gender_inference_from_product_name():
    result = describe_garment({"name": "Closed women's button shirt", "category": "shirt"})
    assert result["construction"]["wearState"] is None
    assert result["audience"] is None


def test_reviewed_knitted_polo_keeps_specific_category():
    result = describe_garment({"category": "sweater", "subcategory": "polo"})
    assert result["routingStatus"] == "supported"
    assert result["category"] == "sweater"


def test_filter_and_total_use_same_body_routing_as_product_response():
    db = mongomock.MongoClient().catalog
    rows = [
        {"_id": "valid", "category": "shirt", "subcategory": "shirt", "photoType": "flat-lay"},
        {"_id": "legacy", "category": "jeans"},
        {"_id": "knit-polo", "category": "sweater", "subcategory": "polo"},
        {"_id": "wrong-region", "category": "shirt", "subcategory": "skirt"},
        {"_id": "set", "category": "shirt", "classification": {"pieces": 2}},
        {"_id": "saree", "category": "dress", "subcategory": "saree"},
        {"_id": "unknown", "category": "unclassified"},
        {"_id": "coverage", "category": "shirt", "classification": {"coverage": "lower-body"}},
    ]
    db.products.insert_many(rows)
    expected = {r["_id"] for r in rows if describe_garment(r)["routingStatus"] == "supported"}
    query = supported_routing_query()
    assert {r["_id"] for r in db.products.find(query)} == expected
    assert db.products.count_documents(query) == len(expected)
    assert db.products.count_documents({"$nor": [query]}) == len(rows) - len(expected)

