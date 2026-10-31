import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.anthropometry.schemas import ChartCreate
from backend.app.anthropometry.repository import get_repository

ROOT = Path(__file__).resolve().parents[1]

NEW_CHARTS = [
    # 1. ZARA MEN TOPS
    {
        "brand_id": "zara",
        "brand_name": "Zara",
        "apparel_id": "zara-men-tops-in",
        "category": "shirt",
        "version": 1,
        "source": "Zara India Official Men Sizing Guide",
        "is_demo": False,
        "gender": "men",
        "market": "IN",
        "source_url": "https://www.zara.com/in/",
        "checked_on": "2026-10-31",
        "source_unit": "cm",
        "measurement_basis": "body",
        "notes": ["Zara Men Tops standard alpha sizing guide."],
        "active_metrics": ["chest_circumference", "waist_circumference"],
        "sizes": [
            {"size_label": "S", "sort_order": 0, "bounds": {"chest_circumference": {"lower": 91.0, "upper": 96.0}, "waist_circumference": {"lower": 76.0, "upper": 80.0}}},
            {"size_label": "M", "sort_order": 1, "bounds": {"chest_circumference": {"lower": 96.0, "upper": 101.0}, "waist_circumference": {"lower": 80.0, "upper": 84.0}}},
            {"size_label": "L", "sort_order": 2, "bounds": {"chest_circumference": {"lower": 101.0, "upper": 107.0}, "waist_circumference": {"lower": 84.0, "upper": 90.0}}},
            {"size_label": "XL", "sort_order": 3, "bounds": {"chest_circumference": {"lower": 107.0, "upper": 112.0}, "waist_circumference": {"lower": 90.0, "upper": 96.0}}},
            {"size_label": "XXL", "sort_order": 4, "bounds": {"chest_circumference": {"lower": 112.0, "upper": 117.0}, "waist_circumference": {"lower": 96.0, "upper": 102.0}}},
        ],
        "source_type": "official",
        "verification_status": "verified",
        "sizing_system": "Zara Alpha EU/IN Standard"
    },
    # 2. ZARA MEN BOTTOMS
    {
        "brand_id": "zara",
        "brand_name": "Zara",
        "apparel_id": "zara-men-bottoms-in",
        "category": "trouser",
        "version": 1,
        "source": "Zara India Official Men Trousers & Denim Guide",
        "is_demo": False,
        "gender": "men",
        "market": "IN",
        "source_url": "https://www.zara.com/in/",
        "checked_on": "2026-10-31",
        "source_unit": "cm",
        "measurement_basis": "body",
        "notes": ["Zara Men Trousers/Denim sizing guide."],
        "active_metrics": ["waist_circumference", "hip_circumference"],
        "sizes": [
            {"size_label": "S", "sort_order": 0, "bounds": {"waist_circumference": {"lower": 80.0, "upper": 81.0}, "hip_circumference": {"lower": 95.0, "upper": 97.0}}},
            {"size_label": "M", "sort_order": 1, "bounds": {"waist_circumference": {"lower": 84.0, "upper": 85.0}, "hip_circumference": {"lower": 99.0, "upper": 101.0}}},
            {"size_label": "L", "sort_order": 2, "bounds": {"waist_circumference": {"lower": 88.0, "upper": 89.0}, "hip_circumference": {"lower": 103.0, "upper": 105.0}}},
            {"size_label": "XL", "sort_order": 3, "bounds": {"waist_circumference": {"lower": 92.0, "upper": 93.0}, "hip_circumference": {"lower": 107.0, "upper": 109.0}}},
            {"size_label": "XXL", "sort_order": 4, "bounds": {"waist_circumference": {"lower": 96.0, "upper": 97.0}, "hip_circumference": {"lower": 111.0, "upper": 113.0}}},
        ],
        "source_type": "official",
        "verification_status": "verified",
        "sizing_system": "Zara Alpha EU/IN Standard"
    },
    # 3. ZARA WOMEN TOPS
    {
        "brand_id": "zara",
        "brand_name": "Zara",
        "apparel_id": "zara-women-tops-in",
        "category": "shirt",
        "version": 1,
        "source": "Zara India Official Women Tops & Dresses Guide",
        "is_demo": False,
        "gender": "women",
        "market": "IN",
        "source_url": "https://www.zara.com/in/",
        "checked_on": "2026-10-31",
        "source_unit": "cm",
        "measurement_basis": "body",
        "notes": ["Zara Women Tops & Shirts standard guide."],
        "active_metrics": ["chest_circumference", "waist_circumference", "hip_circumference"],
        "sizes": [
            {"size_label": "XS", "sort_order": 0, "bounds": {"chest_circumference": {"lower": 82.0, "upper": 85.0}, "waist_circumference": {"lower": 62.0, "upper": 65.0}, "hip_circumference": {"lower": 90.0, "upper": 93.0}}},
            {"size_label": "S", "sort_order": 1, "bounds": {"chest_circumference": {"lower": 86.0, "upper": 89.0}, "waist_circumference": {"lower": 66.0, "upper": 69.0}, "hip_circumference": {"lower": 94.0, "upper": 97.0}}},
            {"size_label": "M", "sort_order": 2, "bounds": {"chest_circumference": {"lower": 90.0, "upper": 93.0}, "waist_circumference": {"lower": 70.0, "upper": 73.0}, "hip_circumference": {"lower": 98.0, "upper": 101.0}}},
            {"size_label": "L", "sort_order": 3, "bounds": {"chest_circumference": {"lower": 94.0, "upper": 98.0}, "waist_circumference": {"lower": 74.0, "upper": 78.0}, "hip_circumference": {"lower": 102.0, "upper": 106.0}}},
            {"size_label": "XL", "sort_order": 4, "bounds": {"chest_circumference": {"lower": 99.0, "upper": 103.0}, "waist_circumference": {"lower": 79.0, "upper": 83.0}, "hip_circumference": {"lower": 107.0, "upper": 111.0}}},
        ],
        "source_type": "official",
        "verification_status": "verified",
        "sizing_system": "Zara Alpha EU/IN Standard"
    },
    # 4. ZARA WOMEN BOTTOMS
    {
        "brand_id": "zara",
        "brand_name": "Zara",
        "apparel_id": "zara-women-bottoms-in",
        "category": "trouser",
        "version": 1,
        "source": "Zara India Official Women Trousers & Jeans Guide",
        "is_demo": False,
        "gender": "women",
        "market": "IN",
        "source_url": "https://www.zara.com/in/",
        "checked_on": "2026-10-31",
        "source_unit": "cm",
        "measurement_basis": "body",
        "notes": ["Zara Women Trousers & Jeans standard guide."],
        "active_metrics": ["waist_circumference", "hip_circumference"],
        "sizes": [
            {"size_label": "XS", "sort_order": 0, "bounds": {"waist_circumference": {"lower": 62.0, "upper": 66.0}, "hip_circumference": {"lower": 90.0, "upper": 94.0}}},
            {"size_label": "S", "sort_order": 1, "bounds": {"waist_circumference": {"lower": 66.0, "upper": 70.0}, "hip_circumference": {"lower": 94.0, "upper": 98.0}}},
            {"size_label": "M", "sort_order": 2, "bounds": {"waist_circumference": {"lower": 70.0, "upper": 74.0}, "hip_circumference": {"lower": 98.0, "upper": 102.0}}},
            {"size_label": "L", "sort_order": 3, "bounds": {"waist_circumference": {"lower": 76.0, "upper": 80.0}, "hip_circumference": {"lower": 104.0, "upper": 108.0}}},
            {"size_label": "XL", "sort_order": 4, "bounds": {"waist_circumference": {"lower": 82.0, "upper": 86.0}, "hip_circumference": {"lower": 110.0, "upper": 114.0}}},
        ],
        "source_type": "official",
        "verification_status": "verified",
        "sizing_system": "Zara Alpha EU/IN Standard"
    },
    # 5. ONLY WOMEN TOPS
    {
        "brand_id": "only",
        "brand_name": "ONLY",
        "apparel_id": "only-women-tops-in",
        "category": "shirt",
        "version": 1,
        "source": "ONLY India Official Size Guide",
        "is_demo": False,
        "gender": "women",
        "market": "IN",
        "source_url": "https://www.only.in/size-guide",
        "checked_on": "2026-10-31",
        "source_unit": "cm",
        "measurement_basis": "body",
        "notes": ["ONLY India Women Tops/Shirts/Dresses official body size guide."],
        "active_metrics": ["chest_circumference", "waist_circumference", "hip_circumference"],
        "sizes": [
            {"size_label": "XS", "sort_order": 0, "bounds": {"chest_circumference": {"lower": 81.0, "upper": 84.0}, "waist_circumference": {"lower": 64.0, "upper": 67.0}, "hip_circumference": {"lower": 88.0, "upper": 91.0}}},
            {"size_label": "S", "sort_order": 1, "bounds": {"chest_circumference": {"lower": 85.0, "upper": 88.0}, "waist_circumference": {"lower": 68.0, "upper": 71.0}, "hip_circumference": {"lower": 92.0, "upper": 95.0}}},
            {"size_label": "M", "sort_order": 2, "bounds": {"chest_circumference": {"lower": 89.0, "upper": 92.0}, "waist_circumference": {"lower": 72.0, "upper": 75.0}, "hip_circumference": {"lower": 96.0, "upper": 99.0}}},
            {"size_label": "L", "sort_order": 3, "bounds": {"chest_circumference": {"lower": 93.0, "upper": 97.0}, "waist_circumference": {"lower": 76.0, "upper": 80.0}, "hip_circumference": {"lower": 100.0, "upper": 104.0}}},
            {"size_label": "XL", "sort_order": 4, "bounds": {"chest_circumference": {"lower": 98.0, "upper": 103.0}, "waist_circumference": {"lower": 81.0, "upper": 86.0}, "hip_circumference": {"lower": 105.0, "upper": 110.0}}},
        ],
        "source_type": "official",
        "verification_status": "verified",
        "sizing_system": "ONLY India Alpha"
    },
    # 6. ONLY WOMEN BOTTOMS
    {
        "brand_id": "only",
        "brand_name": "ONLY",
        "apparel_id": "only-women-bottoms-in",
        "category": "jeans",
        "version": 1,
        "source": "ONLY India Official Size Guide - Jeans & Pants",
        "is_demo": False,
        "gender": "women",
        "market": "IN",
        "source_url": "https://www.only.in/size-guide",
        "checked_on": "2026-10-31",
        "source_unit": "cm",
        "measurement_basis": "body",
        "notes": ["ONLY India Jeans & Trousers waist size guide."],
        "active_metrics": ["waist_circumference", "hip_circumference"],
        "sizes": [
            {"size_label": "26", "sort_order": 0, "bounds": {"waist_circumference": {"lower": 63.5, "upper": 66.0}, "hip_circumference": {"lower": 88.9, "upper": 91.4}}},
            {"size_label": "28", "sort_order": 1, "bounds": {"waist_circumference": {"lower": 68.6, "upper": 71.1}, "hip_circumference": {"lower": 94.0, "upper": 96.5}}},
            {"size_label": "30", "sort_order": 2, "bounds": {"waist_circumference": {"lower": 73.7, "upper": 76.2}, "hip_circumference": {"lower": 99.1, "upper": 101.6}}},
            {"size_label": "32", "sort_order": 3, "bounds": {"waist_circumference": {"lower": 78.7, "upper": 81.3}, "hip_circumference": {"lower": 104.1, "upper": 106.7}}},
        ],
        "source_type": "official",
        "verification_status": "verified",
        "sizing_system": "ONLY Numeric Waist"
    },
    # 7. MARKS & SPENCER MEN TOPS
    {
        "brand_id": "marks-and-spencer",
        "brand_name": "Marks & Spencer",
        "apparel_id": "ms-men-tops-in",
        "category": "shirt",
        "version": 1,
        "source": "Marks & Spencer India Official Men Size Guide",
        "is_demo": False,
        "gender": "men",
        "market": "IN",
        "source_url": "https://www.marksandspencer.in/",
        "checked_on": "2026-10-31",
        "source_unit": "cm",
        "measurement_basis": "body",
        "notes": ["Marks & Spencer India Men Shirts & Sweaters guide."],
        "active_metrics": ["chest_circumference", "waist_circumference"],
        "sizes": [
            {"size_label": "S", "sort_order": 0, "bounds": {"chest_circumference": {"lower": 91.0, "upper": 96.0}, "waist_circumference": {"lower": 76.0, "upper": 81.0}}},
            {"size_label": "M", "sort_order": 1, "bounds": {"chest_circumference": {"lower": 99.0, "upper": 102.0}, "waist_circumference": {"lower": 84.0, "upper": 89.0}}},
            {"size_label": "L", "sort_order": 2, "bounds": {"chest_circumference": {"lower": 104.0, "upper": 109.0}, "waist_circumference": {"lower": 91.0, "upper": 97.0}}},
            {"size_label": "XL", "sort_order": 3, "bounds": {"chest_circumference": {"lower": 112.0, "upper": 117.0}, "waist_circumference": {"lower": 99.0, "upper": 104.0}}},
            {"size_label": "2XL", "sort_order": 4, "bounds": {"chest_circumference": {"lower": 119.0, "upper": 124.0}, "waist_circumference": {"lower": 107.0, "upper": 112.0}}},
        ],
        "source_type": "official",
        "verification_status": "verified",
        "sizing_system": "Marks & Spencer UK/IN Alpha"
    },
    # 8. MARKS & SPENCER MEN BOTTOMS
    {
        "brand_id": "marks-and-spencer",
        "brand_name": "Marks & Spencer",
        "apparel_id": "ms-men-bottoms-in",
        "category": "trouser",
        "version": 1,
        "source": "Marks & Spencer India Official Men Trousers Guide",
        "is_demo": False,
        "gender": "men",
        "market": "IN",
        "source_url": "https://www.marksandspencer.in/",
        "checked_on": "2026-10-31",
        "source_unit": "cm",
        "measurement_basis": "body",
        "notes": ["Marks & Spencer India Men Trousers numeric waist sizing."],
        "active_metrics": ["waist_circumference", "hip_circumference"],
        "sizes": [
            {"size_label": "30", "sort_order": 0, "bounds": {"waist_circumference": {"lower": 76.0, "upper": 78.5}, "hip_circumference": {"lower": 91.0, "upper": 94.0}}},
            {"size_label": "32", "sort_order": 1, "bounds": {"waist_circumference": {"lower": 81.0, "upper": 83.5}, "hip_circumference": {"lower": 96.0, "upper": 99.0}}},
            {"size_label": "34", "sort_order": 2, "bounds": {"waist_circumference": {"lower": 86.0, "upper": 88.5}, "hip_circumference": {"lower": 101.0, "upper": 104.0}}},
            {"size_label": "36", "sort_order": 3, "bounds": {"waist_circumference": {"lower": 91.0, "upper": 93.5}, "hip_circumference": {"lower": 106.0, "upper": 109.0}}},
            {"size_label": "38", "sort_order": 4, "bounds": {"waist_circumference": {"lower": 96.0, "upper": 98.5}, "hip_circumference": {"lower": 111.0, "upper": 114.0}}},
        ],
        "source_type": "official",
        "verification_status": "verified",
        "sizing_system": "Marks & Spencer Numeric Waist"
    },
    # 9. MARKS & SPENCER WOMEN TOPS
    {
        "brand_id": "marks-and-spencer",
        "brand_name": "Marks & Spencer",
        "apparel_id": "ms-women-tops-in",
        "category": "shirt",
        "version": 1,
        "source": "Marks & Spencer India Official Women Tops & Dresses Guide",
        "is_demo": False,
        "gender": "women",
        "market": "IN",
        "source_url": "https://www.marksandspencer.in/",
        "checked_on": "2026-10-31",
        "source_unit": "cm",
        "measurement_basis": "body",
        "notes": ["Marks & Spencer India Women standard UK numeric sizing."],
        "active_metrics": ["chest_circumference", "waist_circumference", "hip_circumference"],
        "sizes": [
            {"size_label": "UK 8", "sort_order": 0, "bounds": {"chest_circumference": {"lower": 82.0, "upper": 85.0}, "waist_circumference": {"lower": 65.0, "upper": 68.0}, "hip_circumference": {"lower": 90.0, "upper": 93.0}}},
            {"size_label": "UK 10", "sort_order": 1, "bounds": {"chest_circumference": {"lower": 87.0, "upper": 90.0}, "waist_circumference": {"lower": 70.0, "upper": 73.0}, "hip_circumference": {"lower": 95.0, "upper": 98.0}}},
            {"size_label": "UK 12", "sort_order": 2, "bounds": {"chest_circumference": {"lower": 92.0, "upper": 95.0}, "waist_circumference": {"lower": 75.0, "upper": 78.0}, "hip_circumference": {"lower": 100.0, "upper": 103.0}}},
            {"size_label": "UK 14", "sort_order": 3, "bounds": {"chest_circumference": {"lower": 97.0, "upper": 100.0}, "waist_circumference": {"lower": 80.0, "upper": 83.0}, "hip_circumference": {"lower": 105.0, "upper": 108.0}}},
            {"size_label": "UK 16", "sort_order": 4, "bounds": {"chest_circumference": {"lower": 102.0, "upper": 105.0}, "waist_circumference": {"lower": 85.0, "upper": 88.0}, "hip_circumference": {"lower": 110.0, "upper": 113.0}}},
        ],
        "source_type": "official",
        "verification_status": "verified",
        "sizing_system": "Marks & Spencer UK Standard"
    },
    # 10. MARKS & SPENCER WOMEN BOTTOMS
    {
        "brand_id": "marks-and-spencer",
        "brand_name": "Marks & Spencer",
        "apparel_id": "ms-women-bottoms-in",
        "category": "trouser",
        "version": 1,
        "source": "Marks & Spencer India Official Women Trousers Guide",
        "is_demo": False,
        "gender": "women",
        "market": "IN",
        "source_url": "https://www.marksandspencer.in/",
        "checked_on": "2026-10-31",
        "source_unit": "cm",
        "measurement_basis": "body",
        "notes": ["Marks & Spencer India Women Trousers standard UK sizing."],
        "active_metrics": ["waist_circumference", "hip_circumference"],
        "sizes": [
            {"size_label": "UK 8", "sort_order": 0, "bounds": {"waist_circumference": {"lower": 65.0, "upper": 68.0}, "hip_circumference": {"lower": 90.0, "upper": 93.0}}},
            {"size_label": "UK 10", "sort_order": 1, "bounds": {"waist_circumference": {"lower": 70.0, "upper": 73.0}, "hip_circumference": {"lower": 95.0, "upper": 98.0}}},
            {"size_label": "UK 12", "sort_order": 2, "bounds": {"waist_circumference": {"lower": 75.0, "upper": 78.0}, "hip_circumference": {"lower": 100.0, "upper": 103.0}}},
            {"size_label": "UK 14", "sort_order": 3, "bounds": {"waist_circumference": {"lower": 80.0, "upper": 83.0}, "hip_circumference": {"lower": 105.0, "upper": 108.0}}},
            {"size_label": "UK 16", "sort_order": 4, "bounds": {"waist_circumference": {"lower": 85.0, "upper": 88.0}, "hip_circumference": {"lower": 110.0, "upper": 113.0}}},
        ],
        "source_type": "official",
        "verification_status": "verified",
        "sizing_system": "Marks & Spencer UK Standard"
    },
    # 11. VERO MODA WOMEN TOPS
    {
        "brand_id": "vero-moda",
        "brand_name": "Vero Moda",
        "apparel_id": "vm-women-tops-in",
        "category": "shirt",
        "version": 1,
        "source": "Vero Moda India Official Size Guide - Tops, Shirts, Dresses",
        "is_demo": False,
        "gender": "women",
        "market": "IN",
        "source_url": "https://www.veromoda.in/size-guide",
        "checked_on": "2026-10-31",
        "source_unit": "cm",
        "measurement_basis": "body",
        "notes": ["Vero Moda India official size guide."],
        "active_metrics": ["chest_circumference", "waist_circumference", "hip_circumference"],
        "sizes": [
            {"size_label": "XS", "sort_order": 0, "bounds": {"chest_circumference": {"lower": 82.0, "upper": 85.0}, "waist_circumference": {"lower": 66.0, "upper": 70.0}, "hip_circumference": {"lower": 88.0, "upper": 92.0}}},
            {"size_label": "S", "sort_order": 1, "bounds": {"chest_circumference": {"lower": 86.0, "upper": 90.0}, "waist_circumference": {"lower": 71.0, "upper": 75.0}, "hip_circumference": {"lower": 93.0, "upper": 97.0}}},
            {"size_label": "M", "sort_order": 2, "bounds": {"chest_circumference": {"lower": 91.0, "upper": 95.0}, "waist_circumference": {"lower": 76.0, "upper": 80.0}, "hip_circumference": {"lower": 98.0, "upper": 102.0}}},
            {"size_label": "L", "sort_order": 3, "bounds": {"chest_circumference": {"lower": 96.0, "upper": 101.0}, "waist_circumference": {"lower": 81.0, "upper": 86.0}, "hip_circumference": {"lower": 103.0, "upper": 107.0}}},
            {"size_label": "XL", "sort_order": 4, "bounds": {"chest_circumference": {"lower": 102.0, "upper": 107.0}, "waist_circumference": {"lower": 87.0, "upper": 92.0}, "hip_circumference": {"lower": 108.0, "upper": 113.0}}},
        ],
        "source_type": "official",
        "verification_status": "verified",
        "sizing_system": "Vero Moda Alpha Standard"
    },
    # 12. VERO MODA WOMEN BOTTOMS
    {
        "brand_id": "vero-moda",
        "brand_name": "Vero Moda",
        "apparel_id": "vm-women-bottoms-in",
        "category": "trouser",
        "version": 1,
        "source": "Vero Moda India Official Size Guide - Jeans & Trousers",
        "is_demo": False,
        "gender": "women",
        "market": "IN",
        "source_url": "https://www.veromoda.in/size-guide",
        "checked_on": "2026-10-31",
        "source_unit": "cm",
        "measurement_basis": "body",
        "notes": ["Vero Moda India official jeans and trouser size guide."],
        "active_metrics": ["waist_circumference", "hip_circumference"],
        "sizes": [
            {"size_label": "26", "sort_order": 0, "bounds": {"waist_circumference": {"lower": 64.0, "upper": 67.0}, "hip_circumference": {"lower": 89.0, "upper": 92.0}}},
            {"size_label": "28", "sort_order": 1, "bounds": {"waist_circumference": {"lower": 69.0, "upper": 72.0}, "hip_circumference": {"lower": 94.0, "upper": 97.0}}},
            {"size_label": "30", "sort_order": 2, "bounds": {"waist_circumference": {"lower": 74.0, "upper": 77.0}, "hip_circumference": {"lower": 99.0, "upper": 102.0}}},
            {"size_label": "32", "sort_order": 3, "bounds": {"waist_circumference": {"lower": 79.0, "upper": 82.0}, "hip_circumference": {"lower": 104.0, "upper": 107.0}}},
        ],
        "source_type": "official",
        "verification_status": "verified",
        "sizing_system": "Vero Moda Numeric Waist"
    }
]

# 1. Validate all new charts
print("Validating charts with ChartCreate Pydantic schema...")
validated_charts = []
for c in NEW_CHARTS:
    validated = ChartCreate.model_validate(c)
    validated_charts.append(json.loads(validated.model_dump_json()))
print(f"Successfully validated {len(validated_charts)} charts!")

# 2. Update data/brandCharts/sourced-body-charts-v2.json
charts_path = ROOT / "data/brandCharts/sourced-body-charts-v2.json"
existing_charts = json.loads(charts_path.read_text(encoding="utf-8"))
existing_keys = {(c["brand_id"], c["apparel_id"]) for c in existing_charts}

added = 0
for vc in validated_charts:
    key = (vc["brand_id"], vc["apparel_id"])
    if key not in existing_keys:
        existing_charts.append(vc)
        existing_keys.add(key)
        added += 1

charts_path.write_text(json.dumps(existing_charts, indent=2), encoding="utf-8")
print(f"Added {added} new charts to sourced-body-charts-v2.json (Total: {len(existing_charts)})")

# 3. Update data/brandCharts/brand-directory-v2.json
bd_path = ROOT / "data/brandCharts/brand-directory-v2.json"
bd = json.loads(bd_path.read_text(encoding="utf-8"))
bd_ids = {b["brand_id"] for b in bd}

new_brands = [
    {"brand_id": "zara", "brand_name": "Zara", "market": "IN", "is_demo": False, "coverage": [], "description": "Global high-street fashion label with European alpha sizing standards."},
    {"brand_id": "only", "brand_name": "ONLY", "market": "IN", "is_demo": False, "coverage": [], "description": "Contemporary women denim and casualwear brand by Bestseller."},
    {"brand_id": "marks-and-spencer", "brand_name": "Marks & Spencer", "market": "IN", "is_demo": False, "coverage": [], "description": "British heritage retailer offering refined contemporary fits and UK sizing."},
    {"brand_id": "vero-moda", "brand_name": "Vero Moda", "market": "IN", "is_demo": False, "coverage": [], "description": "Effortless, trend-focused women apparel and European sizing standards."},
    {"brand_id": "westside", "brand_name": "Westside", "market": "IN", "is_demo": False, "coverage": [], "description": "Indian premier retail fashion brand with diverse contemporary collections."},
]

for nb in new_brands:
    if nb["brand_id"] not in bd_ids:
        bd.append(nb)
        bd_ids.add(nb["brand_id"])
    else:
        # Update existing
        for b in bd:
            if b["brand_id"] == nb["brand_id"]:
                b.update(nb)

bd_path.write_text(json.dumps(bd, indent=2), encoding="utf-8")
print(f"Brand directory updated (Total brands: {len(bd)})")

# 4. Reseed MongoDB brand_size_charts and measurement_brands
repo = get_repository()
# Upsert charts into repo.db.brand_size_charts
chart_upserts = 0
for vc in validated_charts:
    repo.db.brand_size_charts.update_one(
        {"brand_id": vc["brand_id"], "apparel_id": vc["apparel_id"]},
        {"$set": vc},
        upsert=True
    )
    chart_upserts += 1

# Upsert brands into repo.db.measurement_brands
for nb in new_brands:
    repo.db.measurement_brands.update_one(
        {"brand_id": nb["brand_id"]},
        {"$set": nb},
        upsert=True
    )

print(f"MongoDB reseeded with {chart_upserts} charts and brands successfully!")
