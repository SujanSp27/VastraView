"""Resolve catalog evidence into a shared, auditable inference description.

This is metadata validation, not an image classifier. Unknown construction stays
unknown. FASHN accepts a body family and image, not text prompts for shirt closure.
"""
from ml.vton.categories import MODEL_CATEGORIES
from ml.vton.taxonomy import TAXONOMY

REGIONS = {"tops": "upper-body", "bottoms": "lower-body", "one-pieces": "full-body"}
SUBTYPES = {key: (label, category) for key, label, _, category in TAXONOMY}
DETAILS = ("sleeveType", "sleeveLength", "neckline", "collar", "openingType",
           "wearState", "pattern", "silhouette", "fit")


def describe_garment(row):
    category = row.get("category")
    subtype = row.get("subcategory")
    family = MODEL_CATEGORIES.get(category)
    review = row.get("classification") or {}
    pieces = review.get("pieces")
    issues = []
    if family is None:
        issues.append("unsupported_category")
    if row.get("photoType") is not None and row["photoType"] not in {"model", "flat-lay"}:
        issues.append("unknown_photo_type")
    if subtype in SUBTYPES:
        subtype_family = MODEL_CATEGORIES.get(SUBTYPES[subtype][1])
        # A knitted polo can be a sweater, a cropped tee a t-shirt. Never
        # overwrite a reviewed category just because a subtype has a default.
        if subtype_family != family or subtype_family is None:
            issues.append("subcategory_requires_review")
    elif subtype:
        issues.append("unknown_subcategory")
    if pieces is not None and (type(pieces) is not int or pieces != 1):
        issues.append("multiple_or_unknown_pieces")
    if review.get("coverage") and review["coverage"] != REGIONS.get(family):
        issues.append("coverage_conflict")
    construction = row.get("construction") or {}
    # Only explicit reviewed annotations; product names/descriptions are not
    # sufficient evidence for whether buttons are fastened or a shirt is open.
    evidence = construction.get("evidence") or {}
    reviewed = evidence.get("status") == "image_reviewed" and bool(evidence.get("sourceSha256"))
    return {
        "version": 1, "category": category, "subtype": subtype,
        "displayCategory": review.get("mainCategory") or SUBTYPES.get(subtype, (category, None))[0],
        "modelCategory": family, "targetRegion": REGIONS.get(family),
        "pieces": pieces, "audience": row.get("audience"), "photoType": row.get("photoType"),
        "colors": row.get("colors", []),
        "construction": {key: construction.get(key) if reviewed else None for key in DETAILS},
        "constructionEvidence": evidence if reviewed else None,
        "routingStatus": "needs_review" if issues else "supported",
        "issues": issues,
        "qualityVerified": False,
    }
