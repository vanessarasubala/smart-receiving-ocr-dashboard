from PIL import Image, ImageDraw, ImageFont
import os

os.makedirs("samples", exist_ok=True)


def get_fonts():
    try:
        font_title = ImageFont.truetype("Arial.ttf", 36)
        font_header = ImageFont.truetype("Arial.ttf", 24)
        font_body = ImageFont.truetype("Arial.ttf", 22)
    except:
        font_title = ImageFont.load_default()
        font_header = ImageFont.load_default()
        font_body = ImageFont.load_default()

    return font_title, font_header, font_body


def create_receiving_doc(filename, lines):
    width, height = 900, 620
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)

    font_title, font_header, font_body = get_fonts()

    draw.text((40, 40), "DELIVERY ORDER", fill="black", font=font_title)
    draw.line((40, 95, 860, 95), fill="black", width=2)

    y = 140
    for line in lines:
        draw.text((60, y), line, fill="black", font=font_body)
        y += 45

    draw.rectangle((40, 520, 860, 570), outline="black", width=2)
    draw.text(
        (60, 532),
        "Receiver Signature: __________________",
        fill="black",
        font=font_header
    )

    output_path = f"samples/{filename}"
    image.save(output_path)
    print(f"Created: {output_path}")


# -----------------------------
# 1. Matched document
# Expected PO-1001 quantity = 500
# Received quantity = 500
# -----------------------------
create_receiving_doc(
    "sample_matched.png",
    [
        "Supplier: ABC Electronics",
        "PO Number: PO-1001",
        "Item Code: DRAM-8GB",
        "Quantity: 500",
        "Received Date: 2026-04-01",
        "",
        "Remarks: Full delivery received at warehouse."
    ]
)


# -----------------------------
# 2. Mismatch document
# Expected PO-1002 quantity = 300
# Received quantity = 280
# -----------------------------
create_receiving_doc(
    "sample_mismatch.png",
    [
        "Supplier: Global Components",
        "PO Number: PO-1002",
        "Item Code: NAND-256GB",
        "Quantity: 280",
        "Received Date: 2026-04-02",
        "",
        "Remarks: Partial delivery received at warehouse."
    ]
)


# -----------------------------
# 3. PO not found document
# PO-9999 does not exist in expected_po.csv
# -----------------------------
create_receiving_doc(
    "sample_po_not_found.png",
    [
        "Supplier: Unknown Supplier",
        "PO Number: PO-9999",
        "Item Code: UNKNOWN-ITEM",
        "Quantity: 100",
        "Received Date: 2026-04-06",
        "",
        "Remarks: PO number requires manual review."
    ]
)


# -----------------------------
# 4. Missing quantity document
# Quantity line is intentionally removed
# -----------------------------
create_receiving_doc(
    "sample_missing_quantity.png",
    [
        "Supplier: Semicon Supply Co",
        "PO Number: PO-1003",
        "Item Code: WAFER-A12",
        "Received Date: 2026-04-03",
        "",
        "Remarks: Quantity is missing from the delivery document."
    ]
)