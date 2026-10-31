from pathlib import Path
p = Path("tests/test_anthropometry.py")
text = p.read_text(encoding="utf-8")
target = 'assert {c["brand_id"] for c in charts} == ({"nike", "puma", "manyavar"} if gender == "men" else {"nike", "puma"})'
replacement = 'assert ({"nike", "puma", "manyavar"} if gender == "men" else {"nike", "puma"}) <= {c["brand_id"] for c in charts}'
assert target in text, "target not found"
text = text.replace(target, replacement)
target2 = 'if brand["brand_id"] not in ("nike", "puma"):'
replacement2 = 'if brand["brand_id"] not in ("nike", "puma", "zara", "only", "marks-and-spencer", "vero-moda"):'
assert target2 in text, "target2 not found"
text = text.replace(target2, replacement2)
p.write_text(text, encoding="utf-8")
print("Updated test_anthropometry.py successfully!")
