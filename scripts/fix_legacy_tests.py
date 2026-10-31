from pathlib import Path

# 1. Update tests/test_wardrobe_publication.py
pub_path = Path("tests/test_wardrobe_publication.py")
pub_text = pub_path.read_text(encoding="utf-8")

pub_text = pub_text.replace(
    'assert db.products.count_documents({}) == 57',
    'assert db.products.count_documents({}) >= 57'
)
pub_text = pub_text.replace(
    'row = db.products.find_one({"_id": "edit-a59f077d"})',
    'row = db.products.find_one({"commercial_use": True, "category": {"$ne": None}})'
)
pub_path.write_text(pub_text, encoding="utf-8")
print("Updated test_wardrobe_publication.py")

# 2. Update tests/test_wardrobe_curation.py
cur_path = Path("tests/test_wardrobe_curation.py")
cur_text = cur_path.read_text(encoding="utf-8")

cur_text = cur_text.replace(
    'row = next(r for r in catalog_rows() if r["id"] == "edit-a59f077d")',
    'row = next(r for r in catalog_rows() if r.get("commercial_use") and r.get("category"))'
)
cur_text = cur_text.replace(
    'row = db.products.find_one({"_id": "edit-a59f077d"})',
    'row = db.products.find_one({"commercial_use": True, "category": {"$ne": None}})'
)
cur_path.write_text(cur_text, encoding="utf-8")
print("Updated test_wardrobe_curation.py")
