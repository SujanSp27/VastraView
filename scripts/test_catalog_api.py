import urllib.request
import json

brands = ["zara", "only", "marks-and-spencer", "vero-moda", "h-m", "levi-s", "westside"]
total_items = 0
for b in brands:
    url = f"http://127.0.0.1:8000/api/v1/products?brand_id={b}&limit=48"
    resp = json.loads(urllib.request.urlopen(url).read())
    count = resp.get("total", 0)
    total_items += count
    print(f"Brand {b:20}: {count:2} products (returned {len(resp.get('items', []))})")

print(f"Total across all 7 brands: {total_items}")

# Also test anthropometry size recommendation for Zara
recommend_req = urllib.request.Request(
    "http://127.0.0.1:8000/api/v1/anthropometry/recommend",
    data=json.dumps({
        "brand_id": "zara",
        "category": "shirt",
        "gender": "women",
        "measurements": {
            "chest_circumference": 88.0,
            "waist_circumference": 68.0,
            "hip_circumference": 95.0
        }
    }).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)

try:
    rec_resp = json.loads(urllib.request.urlopen(recommend_req).read())
    print(f"Zara recommendation test: Recommended size -> {rec_resp.get('recommended_size')}")
except Exception as e:
    print(f"Sizing recommendation note: {e}")
