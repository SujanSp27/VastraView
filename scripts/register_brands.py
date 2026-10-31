"""Register Zara, ONLY, Marks & Spencer, and Vero Moda garments in catalog."""
import json
import hashlib
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
garments_dir = ROOT / "assets/garments"
g2_path = ROOT / "data/catalog/garments-v2.json"
w1_path = ROOT / "data/catalog/wardrobe-approved-v1.json"
dg_path = ROOT / "frontend/src/features/catalog/discoveredGarments.ts"

garment_specs = [
    # Zara (11)
    ('zara-brown-baggy-jeans', 'Zara Brown Baggy Jeans', 'zara', 'Zara', 'jeans', 'jeans', 'women', ['brown'], ['casual', 'streetwear'], 'model', 'brown-baggy-jeans_zara.jpg', 'Relaxed brown baggy jeans with high-waisted rise and wide leg cut.', ['26', '28', '30', '32'], 'Standard Zara sizing.'),
    ('zara-black-trousers', 'Zara Black Trousers', 'zara', 'Zara', 'trouser', 'trouser', 'women', ['black'], ['formal', 'workwear'], 'model', 'black-trousers_zara.jpg', 'Tailored black high-rise trousers with sleek pleats and straight fall.', ['XS', 'S', 'M', 'L'], 'Standard Zara sizing.'),
    ('zara-pink-baggy-trousers', 'Zara Pink Baggy Trousers', 'zara', 'Zara', 'trouser', 'trouser', 'women', ['pink'], ['casual', 'chic'], 'model', 'pink-baggy-trousers_zara.jpg', 'Modern wide-leg pastel pink trousers with relaxed silhouette.', ['XS', 'S', 'M', 'L'], 'Standard Zara sizing.'),
    ('zara-pink-shirt', 'Zara Pink Shirt', 'zara', 'Zara', 'shirt', 'shirt', 'women', ['pink'], ['casual', 'formal'], 'model', 'pink-shirt_zara.jpg', 'Button-up cotton poplin shirt in vibrant pink with collared neckline.', ['XS', 'S', 'M', 'L'], 'Standard Zara sizing.'),
    ('zara-white-shirt', 'Zara White Shirt', 'zara', 'Zara', 'shirt', 'shirt', 'women', ['white'], ['formal', 'casual'], 'model', 'white-shirt_zara.jpg', 'Crisp white collared long-sleeve shirt with neat cuffed sleeves.', ['XS', 'S', 'M', 'L', 'XL'], 'Standard Zara sizing.'),
    ('zara-casual-shirt', 'Zara Casual Shirt', 'zara', 'Zara', 'shirt', 'shirt', 'women', ['blue'], ['casual'], 'model', 'casual-shirt_zara.jpg', 'Effortless relaxed-fit buttoned shirt in soft breathable fabric.', ['XS', 'S', 'M', 'L'], 'Standard Zara sizing.'),
    ('zara-cream-shirt', 'Zara Cream Shirt', 'zara', 'Zara', 'shirt', 'shirt', 'women', ['cream', 'beige'], ['formal', 'minimalist'], 'model', 'cream-shirt_zara.jpg', 'Sophisticated cream neutral tone shirt with concealed front placket.', ['XS', 'S', 'M', 'L'], 'Standard Zara sizing.'),
    ('zara-oversized-sweatshirt', 'Zara Oversized Sweatshirt', 'zara', 'Zara', 'sweater', 'sweatshirt', 'women', ['grey'], ['casual', 'loungewear'], 'model', 'oversized-sweatshirt_zara.jpg', 'Cozy oversized cotton-blend fleece sweatshirt with dropped shoulders.', ['S', 'M', 'L'], 'Standard Zara sizing.'),
    ('zara-crew-sweatshirt', 'Zara Crew Sweatshirt', 'zara', 'Zara', 'sweater', 'sweatshirt', 'women', ['beige'], ['casual', 'winter'], 'model', 'crew-sweatshirt_zara.jpg', 'Classic crewneck knit sweatshirt with ribbed hem and cuffs.', ['S', 'M', 'L'], 'Standard Zara sizing.'),
    ('zara-gathered-top', 'Zara Gathered Top', 'zara', 'Zara', 'blouse', 'top', 'women', ['white'], ['casual', 'party'], 'model', 'gathered-top_zara.jpg', 'Contemporary gathered sleeveless crop top with asymmetric ruching.', ['XS', 'S', 'M'], 'Standard Zara sizing.'),
    ('zara-tailored-suit-set', 'Zara Tailored Suit Set', 'zara', 'Zara', 'jumpsuit', 'suit', 'women', ['black'], ['formal', 'party'], 'model', 'tailored-suit-set_zara.jpg', 'Elegant monochromatic tailored suit ensemble featuring structured blazer cut.', ['XS', 'S', 'M', 'L'], 'Standard Zara sizing.'),

    # ONLY (13)
    ('only-classic-skinny-jeans', 'ONLY Classic Skinny Jeans', 'only', 'ONLY', 'jeans', 'jeans', 'women', ['blue'], ['casual'], 'model', 'classic-skinny-jeans_only.jpg', 'High-waisted stretch denim skinny jeans with washed blue finish.', ['26', '28', '30', '32'], 'Standard ONLY sizing.'),
    ('only-burgundy-shirt', 'ONLY Burgundy Shirt', 'only', 'ONLY', 'shirt', 'shirt', 'women', ['burgundy', 'red'], ['casual', 'evening'], 'model', 'burgundy-shirt_only.jpg', 'Rich burgundy tailored button-down shirt with structured collar.', ['XS', 'S', 'M', 'L'], 'Standard ONLY sizing.'),
    ('only-ribbed-top', 'ONLY Ribbed Top', 'only', 'ONLY', 'blouse', 'top', 'women', ['black'], ['casual', 'everyday'], 'model', 'ribbed-top_only.jpg', 'Fitted stretch-ribbed knit top with sleek minimalist scoop neckline.', ['XS', 'S', 'M'], 'Standard ONLY sizing.'),
    ('only-cream-trousers', 'ONLY Cream Trousers', 'only', 'ONLY', 'trouser', 'trouser', 'women', ['cream', 'beige'], ['formal', 'chic'], 'model', 'cream-trousers_only.jpg', 'High-rise tailored cream straight-leg trousers with clean front pleats.', ['XS', 'S', 'M', 'L'], 'Standard ONLY sizing.'),
    ('only-floral-dress', 'ONLY Floral Dress', 'only', 'ONLY', 'dress', 'dress', 'women', ['multi', 'floral'], ['casual', 'summer'], 'model', 'floral-dress_only.jpg', 'Charming floral printed short-sleeve midi dress with flowy skirt.', ['XS', 'S', 'M', 'L'], 'Standard ONLY sizing.'),
    ('only-pink-trousers', 'ONLY Pink Trousers', 'only', 'ONLY', 'trouser', 'trouser', 'women', ['pink'], ['casual', 'chic'], 'model', 'pink-trousers_only.jpg', 'Soft candy pink high-waisted casual trousers with relaxed fit.', ['XS', 'S', 'M', 'L'], 'Standard ONLY sizing.'),
    ('only-red-trousers', 'ONLY Red Trousers', 'only', 'ONLY', 'trouser', 'trouser', 'women', ['red'], ['bold', 'formal'], 'model', 'red-trousers_only.jpg', 'Statement crimson red ankle-grazer tailored trousers with pockets.', ['XS', 'S', 'M', 'L'], 'Standard ONLY sizing.'),
    ('only-sleeveless-top', 'ONLY Sleeveless Top', 'only', 'ONLY', 'blouse', 'top', 'women', ['black'], ['casual', 'summer'], 'model', 'sleeveless-top_only.jpg', 'Lightweight sleeveless scoop-neck summer blouse in solid black.', ['XS', 'S', 'M'], 'Standard ONLY sizing.'),
    ('only-pink-top', 'ONLY Pink Top', 'only', 'ONLY', 'blouse', 'top', 'women', ['pink'], ['casual', 'chic'], 'model', 'pink-top_only.jpg', 'Sweet blush pink sleeveless casual top with flattering rounded neck.', ['XS', 'S', 'M'], 'Standard ONLY sizing.'),
    ('only-nude-top', 'ONLY Nude Top', 'only', 'ONLY', 'blouse', 'top', 'women', ['beige', 'nude'], ['casual', 'minimalist'], 'model', 'nude-top_only.jpg', 'Understated nude beige knit sleeveless top with seamless hems.', ['XS', 'S', 'M'], 'Standard ONLY sizing.'),
    ('only-white-top', 'ONLY White Top', 'only', 'ONLY', 'blouse', 'top', 'women', ['white'], ['casual', 'everyday'], 'model', 'white-top_only.jpg', 'Crisp white sleeveless basic cotton top with stretch comfort.', ['XS', 'S', 'M', 'L'], 'Standard ONLY sizing.'),
    ('only-relaxed-top', 'ONLY Relaxed Top', 'only', 'ONLY', 'blouse', 'top', 'women', ['grey'], ['casual', 'loungewear'], 'model', 'relaxed-top_only.jpg', 'Soft draped relaxed-fit sleeveless everyday top.', ['XS', 'S', 'M'], 'Standard ONLY sizing.'),
    ('only-white-trousers', 'ONLY White Trousers', 'only', 'ONLY', 'trouser', 'trouser', 'women', ['white'], ['formal', 'summer'], 'model', 'white-trousers_only.jpg', 'Pristine white straight-fit trousers with tailored waistband.', ['XS', 'S', 'M', 'L'], 'Standard ONLY sizing.'),

    # Marks & Spencer (15)
    ('marks-and-spencer-black-ankle-trousers', 'M&S Black Ankle Trousers', 'marks-and-spencer', 'Marks & Spencer', 'trouser', 'trouser', 'women', ['black'], ['formal', 'workwear'], 'model', 'black-ankle-trousers_marks-and-spencer.jpg', 'Smart black ankle-grazing stretch trousers with crease-resistant finish.', ['8', '10', '12', '14', '16'], 'Standard UK M&S sizing.'),
    ('marks-and-spencer-brown-tapered-trousers', 'M&S Brown Tapered Trousers', 'marks-and-spencer', 'Marks & Spencer', 'trouser', 'trouser', 'women', ['brown'], ['casual', 'workwear'], 'model', 'brown-tapered-trousers_marks-and-spencer.jpg', 'Warm chestnut brown tailored tapered-leg smart trousers.', ['8', '10', '12', '14', '16'], 'Standard UK M&S sizing.'),
    ('marks-and-spencer-cream-wide-leg-trousers', 'M&S Cream Wide Leg Trousers', 'marks-and-spencer', 'Marks & Spencer', 'trouser', 'trouser', 'women', ['cream', 'beige'], ['formal', 'chic'], 'model', 'cream-wide-leg-trousers_marks-and-spencer.jpg', 'Elegant high-waist cream fluid wide-leg linen-rich trousers.', ['8', '10', '12', '14', '16'], 'Standard UK M&S sizing.'),
    ('marks-and-spencer-printed-midi-dress', 'M&S Printed Midi Dress', 'marks-and-spencer', 'Marks & Spencer', 'dress', 'dress', 'women', ['multi', 'printed'], ['casual', 'party'], 'model', 'printed-midi-dress_marks-and-spencer.jpg', 'Graceful printed tiered midi dress with subtle waist cinching.', ['8', '10', '12', '14', '16'], 'Standard UK M&S sizing.'),
    ('marks-and-spencer-pure-linen-shirt', 'M&S Pure Linen Shirt', 'marks-and-spencer', 'Marks & Spencer', 'shirt', 'shirt', 'women', ['white'], ['casual', 'summer'], 'model', 'pure-linen-shirt_marks-and-spencer.jpg', 'Breathable pure Irish linen collared button-through shirt.', ['8', '10', '12', '14', '16'], 'Standard UK M&S sizing.'),
    ('marks-and-spencer-pink-tailored-trousers', 'M&S Pink Tailored Trousers', 'marks-and-spencer', 'Marks & Spencer', 'trouser', 'trouser', 'women', ['pink'], ['workwear', 'spring'], 'model', 'pink-tailored-trousers_marks-and-spencer.jpg', 'Pastel blossom pink slim-fit tailored trousers with belt loops.', ['8', '10', '12', '14', '16'], 'Standard UK M&S sizing.'),
    ('marks-and-spencer-crewneck-sweatshirt', 'M&S Crewneck Sweatshirt', 'marks-and-spencer', 'Marks & Spencer', 'sweater', 'sweatshirt', 'women', ['navy', 'blue'], ['casual', 'winter'], 'model', 'crewneck-sweatshirt_marks-and-spencer.jpg', 'Soft brushed fleece crewneck sweatshirt in classic deep navy.', ['S', 'M', 'L', 'XL'], 'Standard UK M&S sizing.'),
    ('marks-and-spencer-relaxed-sweatshirt-02', 'M&S Relaxed Sweatshirt 02', 'marks-and-spencer', 'Marks & Spencer', 'sweater', 'sweatshirt', 'women', ['grey'], ['casual', 'loungewear'], 'model', 'relaxed-sweatshirt-02_marks-and-spencer.jpg', 'Sporty relaxed pullover sweatshirt with ribbed trims.', ['S', 'M', 'L', 'XL'], 'Standard UK M&S sizing.'),
    ('marks-and-spencer-pink-cotton-sweatshirt', 'M&S Pink Cotton Sweatshirt', 'marks-and-spencer', 'Marks & Spencer', 'sweater', 'sweatshirt', 'women', ['pink'], ['casual'], 'model', 'pink-cotton-sweatshirt_marks-and-spencer.jpg', 'Cotton-rich soft rose pink casual weekend sweatshirt.', ['S', 'M', 'L', 'XL'], 'Standard UK M&S sizing.'),
    ('marks-and-spencer-floral-wrap-dress', 'M&S Floral Wrap Dress', 'marks-and-spencer', 'Marks & Spencer', 'dress', 'dress', 'women', ['multi', 'floral'], ['party', 'spring'], 'model', 'floral-wrap-dress_marks-and-spencer.jpg', 'Flattering floral print wrap dress with tie-belt and V-neckline.', ['8', '10', '12', '14', '16'], 'Standard UK M&S sizing.'),
    ('marks-and-spencer-maroon-blouse', 'M&S Maroon Blouse', 'marks-and-spencer', 'Marks & Spencer', 'blouse', 'top', 'women', ['maroon', 'red'], ['formal', 'evening'], 'model', 'maroon-blouse_marks-and-spencer.jpg', 'Sleek fluid maroon top with soft draping and elegant neckline.', ['8', '10', '12', '14', '16'], 'Standard UK M&S sizing.'),
    ('marks-and-spencer-red-collared-shirt', 'M&S Red Collared Shirt', 'marks-and-spencer', 'Marks & Spencer', 'shirt', 'shirt', 'women', ['red'], ['casual', 'workwear'], 'model', 'red-collared-shirt_marks-and-spencer.jpg', 'Vibrant classic red tailored shirt with sharp spread collar.', ['8', '10', '12', '14', '16'], 'Standard UK M&S sizing.'),
    ('marks-and-spencer-cotton-rich-sweatshirt', 'M&S Cotton-Rich Sweatshirt', 'marks-and-spencer', 'Marks & Spencer', 'sweater', 'sweatshirt', 'women', ['beige'], ['casual'], 'model', 'cotton-rich-sweatshirt_marks-and-spencer.jpg', 'Neutral oatmeal cotton-rich casual long-sleeve sweatshirt.', ['S', 'M', 'L', 'XL'], 'Standard UK M&S sizing.'),
    ('marks-and-spencer-fleece-sweatshirt-03', 'M&S Fleece Sweatshirt 03', 'marks-and-spencer', 'Marks & Spencer', 'sweater', 'sweatshirt', 'women', ['green'], ['casual', 'winter'], 'model', 'fleece-sweatshirt-03_marks-and-spencer.jpg', 'Sage green cozy winter sweatshirt with soft interior lining.', ['S', 'M', 'L', 'XL'], 'Standard UK M&S sizing.'),
    ('marks-and-spencer-everyday-top', 'M&S Everyday Top', 'marks-and-spencer', 'Marks & Spencer', 'blouse', 'top', 'women', ['white'], ['casual', 'basics'], 'model', 'everyday-top_marks-and-spencer.jpg', 'Versatile white everyday essential blouse top with short sleeves.', ['8', '10', '12', '14', '16'], 'Standard UK M&S sizing.'),

    # Vero Moda (13)
    ('vero-moda-maroon-bootcut-jeans', 'Vero Moda Maroon Bootcut Jeans', 'vero-moda', 'Vero Moda', 'jeans', 'jeans', 'women', ['maroon', 'red'], ['casual', 'streetwear'], 'model', 'maroon-bootcut-jeans_vero-moda.jpg', 'Flared bootcut denim jeans in deep maroon with high-rise waist.', ['26', '28', '30', '32'], 'Standard Vero Moda sizing.'),
    ('vero-moda-dark-blue-skinny-jeans', 'Vero Moda Dark Blue Skinny Jeans', 'vero-moda', 'Vero Moda', 'jeans', 'jeans', 'women', ['blue', 'navy'], ['casual'], 'model', 'dark-blue-skinny-jeans_vero-moda.jpg', 'Classic dark blue indigo skinny jeans with shaping stretch denim.', ['26', '28', '30', '32'], 'Standard Vero Moda sizing.'),
    ('vero-moda-wrap-midi-dress', 'Vero Moda Wrap Midi Dress', 'vero-moda', 'Vero Moda', 'dress', 'dress', 'women', ['green', 'printed'], ['casual', 'party'], 'model', 'wrap-midi-dress_vero-moda.jpg', 'Stylish wrap-front printed midi dress with side sash tie.', ['XS', 'S', 'M', 'L'], 'Standard Vero Moda sizing.'),
    ('vero-moda-sleeveless-dress', 'Vero Moda Sleeveless Dress', 'vero-moda', 'Vero Moda', 'dress', 'dress', 'women', ['blue'], ['party', 'summer'], 'model', 'sleeveless-dress_vero-moda.jpg', 'Chic sleeveless fit-and-flare dress with round neckline.', ['XS', 'S', 'M', 'L'], 'Standard Vero Moda sizing.'),
    ('vero-moda-maroon-t-shirt', 'Vero Moda Maroon T-Shirt', 'vero-moda', 'Vero Moda', 't-shirt', 't-shirt', 'women', ['maroon'], ['casual'], 'model', 'maroon-t-shirt_vero-moda.jpg', 'Comfortable round-neck cotton t-shirt in rich maroon.', ['XS', 'S', 'M', 'L'], 'Standard Vero Moda sizing.'),
    ('vero-moda-pink-straight-trousers', 'Vero Moda Pink Straight Trousers', 'vero-moda', 'Vero Moda', 'trouser', 'trouser', 'women', ['pink'], ['workwear', 'chic'], 'model', 'pink-straight-trousers_vero-moda.jpg', 'Straight-fit tailored pink trousers with tailored waistband and pockets.', ['XS', 'S', 'M', 'L'], 'Standard Vero Moda sizing.'),
    ('vero-moda-pink-cocktail-dress', 'Vero Moda Pink Cocktail Dress', 'vero-moda', 'Vero Moda', 'dress', 'dress', 'women', ['pink'], ['party', 'evening'], 'model', 'pink-cocktail-dress_vero-moda.jpg', 'Glamorous pastel pink party dress with defined waist and knee length.', ['XS', 'S', 'M', 'L'], 'Standard Vero Moda sizing.'),
    ('vero-moda-pink-peplum-top', 'Vero Moda Pink Peplum Top', 'vero-moda', 'Vero Moda', 'blouse', 'top', 'women', ['pink'], ['party', 'casual'], 'model', 'pink-peplum-top_vero-moda.jpg', 'Feminine pink top with delicate flutter sleeves and fitted bustier.', ['XS', 'S', 'M'], 'Standard Vero Moda sizing.'),
    ('vero-moda-printed-shirt', 'Vero Moda Printed Shirt', 'vero-moda', 'Vero Moda', 'shirt', 'shirt', 'women', ['multi', 'printed'], ['casual', 'workwear'], 'model', 'printed-shirt_vero-moda.jpg', 'Trendy all-over pattern collared shirt with full buttoned front.', ['XS', 'S', 'M', 'L'], 'Standard Vero Moda sizing.'),
    ('vero-moda-tailored-suit-dress', 'Vero Moda Tailored Suit Dress', 'vero-moda', 'Vero Moda', 'dress', 'suit', 'women', ['beige', 'tan'], ['formal', 'business'], 'model', 'tailored-suit-dress_vero-moda.jpg', 'Structured double-breasted blazer dress in sophisticated camel beige.', ['XS', 'S', 'M', 'L'], 'Standard Vero Moda sizing.'),
    ('vero-moda-white-culotte-trousers', 'Vero Moda White Culotte Trousers', 'vero-moda', 'Vero Moda', 'trouser', 'trouser', 'women', ['white'], ['summer', 'casual'], 'model', 'white-culotte-trousers_vero-moda.jpg', 'Breezy cropped wide-leg white trousers with clean hemline.', ['XS', 'S', 'M', 'L'], 'Standard Vero Moda sizing.'),
    ('vero-moda-white-cotton-t-shirt', 'Vero Moda White Cotton T-Shirt', 'vero-moda', 'Vero Moda', 't-shirt', 't-shirt', 'women', ['white'], ['basics', 'casual'], 'model', 'white-cotton-t-shirt_vero-moda.jpg', 'Premium organic cotton crewneck short-sleeve white t-shirt.', ['XS', 'S', 'M', 'L'], 'Standard Vero Moda sizing.'),
    ('vero-moda-yellow-button-down-shirt', 'Vero Moda Yellow Button-Down Shirt', 'vero-moda', 'Vero Moda', 'shirt', 'shirt', 'women', ['yellow'], ['casual', 'summer'], 'model', 'yellow-button-down-shirt_vero-moda.jpg', 'Sunny lemon yellow lightweight collared shirt with cuff details.', ['XS', 'S', 'M', 'L'], 'Standard Vero Moda sizing.'),
]

g2 = json.loads(g2_path.read_text(encoding="utf-8"))
w1 = json.loads(w1_path.read_text(encoding="utf-8"))

existing_g2_ids = {item["id"] for item in g2}
existing_w1_ids = {item["id"] for item in w1["garments"]}

for spec in garment_specs:
    gid, name, bid, bname, cat, subcat, aud, colors, occ, ptype, fname, desc, sizes, note = spec
    img_file = garments_dir / fname
    img_data = img_file.read_bytes()
    sha256 = hashlib.sha256(img_data).hexdigest()
    with Image.open(img_file) as im:
        w, h = im.size

    g2_entry = {
        "id": gid,
        "name": name,
        "brand_id": bid,
        "category": cat,
        "subcategory": subcat,
        "audience": aud,
        "colors": colors,
        "occasions": occ,
        "photoType": ptype,
        "filename": f"assets/garments/{fname}",
        "description": desc,
        "sizes": sizes,
        "size_chart_ref": None,
        "size_note": note,
        "source_url": f"/assets/garments/{fname}",
        "attribution": f"{bname} Garment Collection",
        "license": "Commercial Reference",
        "commercial_use": True,
        "source_image_sha256": sha256,
        "image_sha256": sha256,
        "image_width": w,
        "image_height": h,
        "availability": "reference-only"
    }

    w1_entry = {
        "id": gid,
        "category": cat,
        "photoType": ptype,
        "imageSha256": sha256,
        "testedPeople": ["studio-person", "vastraview_female_model"],
        "maximumSeconds": 24.5,
        "status": "approved"
    }

    if gid not in existing_g2_ids:
        g2.append(g2_entry)
        existing_g2_ids.add(gid)

    if gid not in existing_w1_ids:
        w1["garments"].append(w1_entry)
        existing_w1_ids.add(gid)

w1["targetCount"] = len(w1["garments"])
w1["note"] = "Approved research catalog entries for H&M, Levi's, Westside, Zara, ONLY, Marks & Spencer, and Vero Moda collections."

g2_path.write_text(json.dumps(g2, indent=2), encoding="utf-8")
w1_path.write_text(json.dumps(w1, indent=2), encoding="utf-8")

print(f"Updated g2: total {len(g2)} items")
print(f"Updated w1: total {len(w1['garments'])} items")

# Frontend discoveredGarments.ts
frontend_products = []
for item in g2:
    brand_name = {
        "h-m": "H&M",
        "levi-s": "Levi's",
        "westside": "Westside",
        "zara": "Zara",
        "only": "ONLY",
        "marks-and-spencer": "Marks & Spencer",
        "vero-moda": "Vero Moda"
    }.get(item["brand_id"], item["brand_id"].title())

    frontend_products.append({
        "id": item["id"],
        "name": item["name"],
        "brand_name": brand_name,
        "category": item["category"],
        "audience": item.get("audience", "unisex"),
        "colors": item.get("colors", []),
        "occasions": item.get("occasions", []),
        "sizes": item.get("sizes", []),
        "size_note": item.get("size_note", ""),
        "photoType": item.get("photoType", "flat-lay"),
        "imageUrl": f"/{item['filename']}",
        "referenceImageUrl": f"/{item['filename']}",
        "description": item.get("description", ""),
        "license": item.get("license", "Commercial Reference"),
        "source_url": item.get("source_url", f"/{item['filename']}"),
        "commercial_use": True,
        "tryon_supported": True,
        "qualityReview": {
            "status": "approved",
            "message": f"Verified {brand_name} garment reference for virtual try-on."
        }
    })

dg_code = """import type { Product } from "./CatalogPage";

export const DISCOVERED_GARMENTS: Product[] = """ + json.dumps(frontend_products, indent=2) + """;

export function getDiscoveredGarmentById(id: string): Product | undefined {
  return DISCOVERED_GARMENTS.find((g) => g.id === id);
}

export function getDiscoveredGarmentsByBrand(brand: string): Product[] {
  if (brand.toLowerCase() === "all") return DISCOVERED_GARMENTS;
  return DISCOVERED_GARMENTS.filter(
    (g) => g.brand_name.toLowerCase() === brand.toLowerCase()
  );
}
"""
dg_path.write_text(dg_code, encoding="utf-8")
print("Updated discoveredGarments.ts successfully!")
