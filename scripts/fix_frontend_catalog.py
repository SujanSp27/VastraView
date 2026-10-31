from pathlib import Path

path = Path("frontend/src/features/catalog/discoveredGarments.ts")
content = path.read_text(encoding="utf-8")

func = """
export function filterDiscoveredGarments(options: {
  query?: string;
  brand?: string;
  category?: string;
  audience?: string;
  color?: string;
  occasion?: string;
  sort?: string;
}): Product[] {
  let list = [...DISCOVERED_GARMENTS];
  if (options.brand) {
    const b = options.brand.toLowerCase().trim();
    list = list.filter((item) => {
      const ib = item.brand_name.toLowerCase();
      if (ib === b) return true;
      if ((b === "h-m" || b === "h&m") && ib === "h&m") return true;
      if ((b === "levi-s" || b === "levis" || b === "levi's") && ib === "levi's") return true;
      if (b === "westside" && ib === "westside") return true;
      if (b === "zara" && ib === "zara") return true;
      if (b === "only" && ib === "only") return true;
      if ((b === "marks-and-spencer" || b === "m&s" || b === "marks & spencer") && (ib === "marks & spencer" || ib === "m&s")) return true;
      if ((b === "vero-moda" || b === "veromoda" || b === "vero moda") && ib === "vero moda") return true;
      return false;
    });
  }
  if (options.query) {
    const q = options.query.toLowerCase().trim();
    list = list.filter(
      (item) =>
        item.name.toLowerCase().includes(q) ||
        item.description.toLowerCase().includes(q) ||
        item.brand_name.toLowerCase().includes(q) ||
        item.category.toLowerCase().includes(q),
    );
  }
  if (options.category) {
    list = list.filter((item) => item.category === options.category);
  }
  if (options.audience) {
    list = list.filter(
      (item) =>
        item.audience === options.audience || item.audience === "unisex",
    );
  }
  if (options.color) {
    list = list.filter((item) =>
      item.colors.some(
        (c) => c.toLowerCase() === options.color?.toLowerCase(),
      ),
    );
  }
  if (options.occasion) {
    list = list.filter((item) =>
      item.occasions?.some(
        (o: string) => o.toLowerCase() === options.occasion?.toLowerCase(),
      ),
    );
  }
  if (options.sort === "name") {
    list.sort((a, b) => a.name.localeCompare(b.name));
  }
  return list;
}
"""

if "export function filterDiscoveredGarments" not in content:
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n" + func.strip() + "\n")
    print("Appended filterDiscoveredGarments successfully.")
else:
    print("Already present.")

# Also fix CatalogPage.tsx line 187 typing
cp_path = Path("frontend/src/features/catalog/CatalogPage.tsx")
cp_content = cp_path.read_text(encoding="utf-8")
if "fallbackList.filter((d) =>" in cp_content:
    cp_content = cp_content.replace(
        "fallbackList.filter((d) => !existingIds.has(d.id));",
        "fallbackList.filter((d: Product) => !existingIds.has(d.id));"
    )
    cp_path.write_text(cp_content, encoding="utf-8")
    print("Fixed CatalogPage.tsx d: Product type annotation.")
