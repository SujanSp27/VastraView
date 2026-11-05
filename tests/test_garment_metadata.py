"""Classification evidence must not become invented construction or quality claims."""
import json

import pytest

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

