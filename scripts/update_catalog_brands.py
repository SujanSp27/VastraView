from pathlib import Path

cp = Path("frontend/src/features/catalog/CatalogPage.tsx")
text = cp.read_text(encoding="utf-8")

old_brands_block = """        const hmBrand = { id: "h-m", name: "H&M", product_count: 14 };
        const levisBrand = { id: "levi-s", name: "Levi's", product_count: 11 };
        const westsideBrand = { id: "westside", name: "Westside", product_count: 13 };
        const customIds = new Set(["h-m", "levi-s", "westside"]);
        const bFiltered = b.filter(
          (item) =>
            !customIds.has(item.id) &&
            item.name.toLowerCase() !== "h&m" &&
            item.name.toLowerCase() !== "levi's" &&
            item.name.toLowerCase() !== "westside",
        );
        setBrands([hmBrand, levisBrand, westsideBrand, ...bFiltered]);"""

new_brands_block = """        const featuredBrands = [
          { id: "h-m", name: "H&M", product_count: 14 },
          { id: "levi-s", name: "Levi's", product_count: 11 },
          { id: "westside", name: "Westside", product_count: 13 },
          { id: "zara", name: "Zara", product_count: 11 },
          { id: "only", name: "ONLY", product_count: 13 },
          { id: "marks-and-spencer", name: "Marks & Spencer", product_count: 15 },
          { id: "vero-moda", name: "Vero Moda", product_count: 13 },
        ];
        const customIds = new Set(featuredBrands.map((x) => x.id));
        const bFiltered = b.filter((item) => !customIds.has(item.id));
        setBrands([...featuredBrands, ...bFiltered]);"""

old_fallback = """        setBrands([
          { id: "h-m", name: "H&M", product_count: 14 },
          { id: "levi-s", name: "Levi's", product_count: 11 },
          { id: "westside", name: "Westside", product_count: 13 },
        ]);"""

new_fallback = """        setBrands([
          { id: "h-m", name: "H&M", product_count: 14 },
          { id: "levi-s", name: "Levi's", product_count: 11 },
          { id: "westside", name: "Westside", product_count: 13 },
          { id: "zara", name: "Zara", product_count: 11 },
          { id: "only", name: "ONLY", product_count: 13 },
          { id: "marks-and-spencer", name: "Marks & Spencer", product_count: 15 },
          { id: "vero-moda", name: "Vero Moda", product_count: 13 },
        ]);"""

old_desc = """            {brand === "h-m"
              ? "Explore our curated collection of 14 verified H&M garments, compare your size, and preview them with personalized virtual try-on."
              : brand === "levi-s"
              ? "Explore our verified collection of 11 Levi's denim, shirts, and trousers, compare your size, and preview them with personalized virtual try-on."
              : brand === "westside"
              ? "Explore our verified collection of 13 Westside apparel pieces, compare your size, and preview them with personalized virtual try-on."
              : "Explore verified garment collections from H&M, Levi's, and Westside, compare your size, and preview them with personalized virtual try-on."}"""

new_desc = """            {brand === "h-m"
              ? "Explore our curated collection of 14 verified H&M garments, compare your size, and preview them with personalized virtual try-on."
              : brand === "levi-s"
              ? "Explore our verified collection of 11 Levi's denim, shirts, and trousers, compare your size, and preview them with personalized virtual try-on."
              : brand === "westside"
              ? "Explore our verified collection of 13 Westside apparel pieces, compare your size, and preview them with personalized virtual try-on."
              : brand === "zara"
              ? "Explore our verified collection of 11 Zara garments, compare your size, and preview them with personalized virtual try-on."
              : brand === "only"
              ? "Explore our verified collection of 13 ONLY garments, compare your size, and preview them with personalized virtual try-on."
              : brand === "marks-and-spencer"
              ? "Explore our verified collection of 15 Marks & Spencer garments, compare your size, and preview them with personalized virtual try-on."
              : brand === "vero-moda"
              ? "Explore our verified collection of 13 Vero Moda garments, compare your size, and preview them with personalized virtual try-on."
              : "Explore verified garment collections from Zara, H&M, Levi's, Marks & Spencer, ONLY, Vero Moda, and Westside, compare your size, and preview them with personalized virtual try-on."}"""

norm_text = text.replace("\r\n", "\n")
norm_text = norm_text.replace(old_brands_block.replace("\r\n", "\n"), new_brands_block.replace("\r\n", "\n"))
norm_text = norm_text.replace(old_fallback.replace("\r\n", "\n"), new_fallback.replace("\r\n", "\n"))
norm_text = norm_text.replace(old_desc.replace("\r\n", "\n"), new_desc.replace("\r\n", "\n"))

cp.write_text(norm_text, encoding="utf-8")
print("Successfully updated CatalogPage.tsx with 7 featured brands!")
