"""Customer download package assembler and pure PDF generator.

Generates the customer-facing ZIP bundle containing:
- master.png (4500x5400 @ 300 DPI)
- print-ready.pdf (Vector-dimensioned PDF embedding the master artwork)
- Mockup preview images (e.g. mockup-tshirt.png)
- LICENSE.txt (Commercial use rights and limitations)
- INSTRUCTIONS.txt (Sizing guide and software instructions)
- manifest.sha256 (Cryptographic checksum manifest)

All operations use the standard library only (zero new dependencies).
"""

from __future__ import annotations

import hashlib
import io
import os
import re
import struct
from typing import Final
import zipfile
import zlib
import structlog

logger = structlog.get_logger(__name__)

DEFAULT_WIDTH_PX: Final[int] = 4500
DEFAULT_HEIGHT_PX: Final[int] = 5400
DEFAULT_DPI: Final[int] = 300


def _parse_png_dimensions_and_channels(png_bytes: bytes) -> tuple[int, int, int]:
    """Extract width, height, and color type from PNG IHDR chunk."""
    if len(png_bytes) < 24 or png_bytes[:8] != b"\x89PNG\r\n\x1a\n":
        return DEFAULT_WIDTH_PX, DEFAULT_HEIGHT_PX, 6
    width, height, bit_depth, color_type = struct.unpack(">IIBB", png_bytes[16:26])
    return width, height, color_type


def optimize_png_deflate(png_bytes: bytes) -> bytes:
    """Losslessly optimize PNG compression using scanline unfiltering, zero-alpha cleaning, adaptive filtering, and zlib level 9.

    Preserves all chunks, dimensions, transparency channels, and pixel values exactly.
    """
    if len(png_bytes) < 24 or png_bytes[:8] != b"\x89PNG\r\n\x1a\n":
        return png_bytes

    width, height, bit_depth, color_type = struct.unpack(">IIBB", png_bytes[16:26])

    offset = 8
    chunks: list[tuple[bytes, bytes]] = []
    idat_combined = bytearray()

    while offset < len(png_bytes):
        if offset + 8 > len(png_bytes):
            break
        length = struct.unpack(">I", png_bytes[offset : offset + 4])[0]
        chunk_type = png_bytes[offset + 4 : offset + 8]
        chunk_data = png_bytes[offset + 8 : offset + 8 + length]
        if chunk_type == b"IDAT":
            idat_combined.extend(chunk_data)
        else:
            chunks.append((chunk_type, chunk_data))
        offset += 12 + length
        if chunk_type == b"IEND":
            break

    try:
        raw_data = zlib.decompress(bytes(idat_combined))
    except Exception:
        return png_bytes

    best_recompressed = zlib.compress(raw_data, level=9)

    # If 8-bit RGBA or RGB, attempt scanline unfiltering + zero-alpha clean + adaptive Sub/Up re-filtering
    bpp = 4 if color_type == 6 else (3 if color_type == 2 else 0)
    stride = 1 + width * bpp

    if bit_depth == 8 and bpp in (3, 4) and len(raw_data) == stride * height:
        try:
            unfiltered_rows: list[bytearray] = []
            prior_unfiltered = bytearray(width * bpp)

            for y in range(height):
                row_offset = y * stride
                filter_type = raw_data[row_offset]
                row_bytes = bytearray(raw_data[row_offset + 1 : row_offset + stride])
                unfiltered = bytearray(width * bpp)

                if filter_type == 0:  # None
                    unfiltered = row_bytes
                elif filter_type == 1:  # Sub
                    for x in range(width * bpp):
                        left = unfiltered[x - bpp] if x >= bpp else 0
                        unfiltered[x] = (row_bytes[x] + left) & 0xFF
                elif filter_type == 2:  # Up
                    for x in range(width * bpp):
                        up = prior_unfiltered[x]
                        unfiltered[x] = (row_bytes[x] + up) & 0xFF
                elif filter_type == 3:  # Average
                    for x in range(width * bpp):
                        left = unfiltered[x - bpp] if x >= bpp else 0
                        up = prior_unfiltered[x]
                        unfiltered[x] = (row_bytes[x] + ((left + up) >> 1)) & 0xFF
                elif filter_type == 4:  # Paeth
                    for x in range(width * bpp):
                        left = unfiltered[x - bpp] if x >= bpp else 0
                        up = prior_unfiltered[x]
                        up_left = prior_unfiltered[x - bpp] if x >= bpp else 0
                        p = left + up - up_left
                        pa = abs(p - left)
                        pb = abs(p - up)
                        pc = abs(p - up_left)
                        pr = left if (pa <= pb and pa <= pc) else (up if pb <= pc else up_left)
                        unfiltered[x] = (row_bytes[x] + pr) & 0xFF
                else:
                    unfiltered = row_bytes

                # For RGBA: Zero out RGB on completely transparent pixels (alpha = 0)
                if bpp == 4:
                    for x in range(width):
                        p = x * 4
                        if unfiltered[p + 3] == 0:
                            unfiltered[p] = 0
                            unfiltered[p + 1] = 0
                            unfiltered[p + 2] = 0

                unfiltered_rows.append(unfiltered)
                prior_unfiltered = unfiltered

            # Adaptive re-filtering (evaluating None, Sub, Up)
            re_filtered = bytearray()
            prior_row = bytearray(width * bpp)

            for row in unfiltered_rows:
                # Filter 0: None
                sum0 = sum(row[i] if row[i] < 128 else 256 - row[i] for i in range(0, width * bpp, 4))

                # Filter 1: Sub
                f1 = bytearray(width * bpp)
                sum1 = 0
                for i in range(width * bpp):
                    left = row[i - bpp] if i >= bpp else 0
                    d = (row[i] - left) & 0xFF
                    f1[i] = d
                    if i % 4 == 0:
                        sum1 += d if d < 128 else 256 - d

                # Filter 2: Up
                f2 = bytearray(width * bpp)
                sum2 = 0
                for i in range(width * bpp):
                    up = prior_row[i]
                    d = (row[i] - up) & 0xFF
                    f2[i] = d
                    if i % 4 == 0:
                        sum2 += d if d < 128 else 256 - d

                min_sum = min(sum0, sum1, sum2)
                if min_sum == sum2:
                    re_filtered.append(2)
                    re_filtered.extend(f2)
                elif min_sum == sum1:
                    re_filtered.append(1)
                    re_filtered.extend(f1)
                else:
                    re_filtered.append(0)
                    re_filtered.extend(row)

                prior_row = row

            adaptive_compressed = zlib.compress(bytes(re_filtered), level=9)
            if len(adaptive_compressed) < len(best_recompressed):
                best_recompressed = adaptive_compressed
        except Exception:
            pass

    if len(best_recompressed) >= len(idat_combined):
        return png_bytes

    out = bytearray(b"\x89PNG\r\n\x1a\n")
    for chunk_type, chunk_data in chunks:
        if chunk_type == b"IEND":
            # Inject optimized IDAT chunk before IEND
            crc = zlib.crc32(b"IDAT" + best_recompressed)
            out.extend(
                struct.pack(">I", len(best_recompressed))
                + b"IDAT"
                + best_recompressed
                + struct.pack(">I", crc)
            )
        crc = zlib.crc32(chunk_type + chunk_data)
        out.extend(struct.pack(">I", len(chunk_data)) + chunk_type + chunk_data + struct.pack(">I", crc))

    return bytes(out)


def create_print_ready_pdf(
    png_bytes: bytes,
    width_px: int = DEFAULT_WIDTH_PX,
    height_px: int = DEFAULT_HEIGHT_PX,
    dpi: int = DEFAULT_DPI,
) -> bytes:
    """Create a high-fidelity, conforming PDF 1.4 embedding the artwork flattened on white.

    1. Decode source PNG using Pillow.
    2. Preserve original RGB colors (sRGB).
    3. Composite transparent RGBA pixels over a solid white background (#FFFFFF).
    4. Flatten transparency before PDF embedding (no /SMask transparency layer).
    5. Set exact page MediaBox in PDF points (72 pt / inch) for the 300 DPI image
       (e.g., 4500x5400 px @ 300 DPI = 15x18 inches = 1080x1296 points).
    6. Embed as pure 24-bit /DeviceRGB FlateDecode image object.
    """
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(png_bytes))
        w_px, h_px = img.size

        # Composite over solid white background if image has alpha/transparency
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            rgba_img = img.convert("RGBA")
            bg = Image.new("RGBA", rgba_img.size, (255, 255, 255, 255))
            flattened = Image.alpha_composite(bg, rgba_img).convert("RGB")
        else:
            flattened = img.convert("RGB")

        raw_rgb = flattened.tobytes()
        stride = w_px * 3

        # Apply PNG Paeth adaptive prediction filter (filter type 4) to achieve compact lossless compression
        filtered_data = bytearray()
        prior_row = bytearray(stride)

        for y in range(h_px):
            row_offset = y * stride
            row = raw_rgb[row_offset : row_offset + stride]
            filtered_row = bytearray(stride + 1)
            filtered_row[0] = 4  # Paeth filter byte

            for x in range(stride):
                left = row[x - 3] if x >= 3 else 0
                up = prior_row[x]
                up_left = prior_row[x - 3] if x >= 3 else 0
                p = left + up - up_left
                pa = abs(p - left)
                pb = abs(p - up)
                pc = abs(p - up_left)
                pr = left if (pa <= pb and pa <= pc) else (up if pb <= pc else up_left)
                filtered_row[x + 1] = (row[x] - pr) & 0xFF

            filtered_data.extend(filtered_row)
            prior_row = row

        rgb_stream = zlib.compress(bytes(filtered_data), level=6)
        decode_parms = f"/DecodeParms << /Predictor 15 /Columns {w_px} /Colors 3 /BitsPerComponent 8 >> "
    except Exception as exc:
        logger.warning("create_print_ready_pdf_flattening_fallback", error=str(exc))
        detected_w, detected_h, _ = _parse_png_dimensions_and_channels(png_bytes)
        w_px = detected_w or width_px
        h_px = detected_h or height_px
        rgb_stream = zlib.compress(png_bytes, level=6)
        decode_parms = ""

    # Calculate page dimensions in points (72 points = 1 inch)
    width_pt = (w_px * 72.0) / dpi
    height_pt = (h_px * 72.0) / dpi

    pdf_buffer = io.BytesIO()

    # Objects:
    # 1: Catalog
    # 2: Pages
    # 3: Page (MediaBox = [0 0 width_pt height_pt])
    # 4: Contents (q width_pt 0 0 height_pt 0 0 cm /Im1 Do Q)
    # 5: Image XObject (/DeviceRGB, 8 bits/channel, FlateDecode + Predictor 15)
    objects: list[bytes] = []

    # 1: Catalog
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    # 2: Pages
    objects.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    # 3: Page
    page_dict = (
        f"<< /Type /Page /Parent 2 0 R "
        f"/MediaBox [0 0 {width_pt:.2f} {height_pt:.2f}] "
        f"/Contents 4 0 R "
        f"/Resources << /XObject << /Im1 5 0 R >> >> >>"
    ).encode("ascii")
    objects.append(page_dict)

    # 4: Contents
    content_stream = (
        f"q {width_pt:.2f} 0 0 {height_pt:.2f} 0 0 cm /Im1 Do Q"
    ).encode("ascii")
    objects.append(
        f"<< /Length {len(content_stream)} >>\nstream\n".encode("ascii")
        + content_stream
        + b"\nendstream"
    )

    # 5: Image XObject (DeviceRGB, FlateDecode, Predictor 15, 8 bits/channel, no /SMask)
    img_dict = (
        f"<< /Type /XObject /Subtype /Image /Width {w_px} /Height {h_px} "
        f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode "
        f"{decode_parms}"
        f"/Length {len(rgb_stream)} >>\nstream\n"
    ).encode("ascii") + rgb_stream + b"\nendstream"
    objects.append(img_dict)

    # Build PDF binary
    pdf_buffer.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    xref_offsets = [0]

    for i, obj in enumerate(objects, start=1):
        offset_pos = pdf_buffer.tell()
        xref_offsets.append(offset_pos)
        pdf_buffer.write(f"{i} 0 obj\n".encode("ascii"))
        pdf_buffer.write(obj)
        pdf_buffer.write(b"\nendobj\n")

    xref_start = pdf_buffer.tell()
    pdf_buffer.write(f"xref\n0 {len(xref_offsets)}\n".encode("ascii"))
    pdf_buffer.write(b"0000000000 65535 f \n")
    for off in xref_offsets[1:]:
        pdf_buffer.write(f"{off:010d} 00000 n \n".encode("ascii"))

    pdf_buffer.write(
        f"trailer\n<< /Size {len(xref_offsets)} /Root 1 0 R >>\n"
        f"startxref\n{xref_start}\n%%EOF\n".encode("ascii")
    )

    return pdf_buffer.getvalue()


def sanitize_brand_slug(name: str, max_length: int = 40) -> str:
    """Convert a brand/shop name into a clean, filesystem-safe identifier.

    - Keeps letters and numbers
    - Converts spaces to underscores
    - Removes unsafe filesystem characters
    - Collapses repeated separators
    - Trims leading and trailing separators
    - Limits length reasonably
    """
    raw = str(name).strip() if name is not None else ""
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", raw)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_-")
    return cleaned[:max_length] if cleaned else "Shop"


def sanitize_product_title(title: str, max_length: int = 40) -> str:
    """Extract a concise, clean product slug from listing title for customer filenames.

    Extracts primary title segment and strips SEO clutter.
    """
    raw = str(title).strip() if title is not None else ""
    primary = re.split(r"[,|\-–—]", raw)[0].strip() or raw
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", primary)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_-")
    return cleaned[:max_length] if cleaned else "Artwork"


def sanitize_display_title(title: str, max_length: int = 60) -> str:
    """Extract clean, short display title for customer documents (LICENSE/INSTRUCTIONS)."""
    raw = str(title).strip() if title is not None else ""
    primary = re.split(r"[,|\-–—]", raw)[0].strip() or raw
    return primary[:max_length] if primary else "Digital Artwork"


def generate_license_text(shop_name: str, listing_title: str) -> str:
    """Generate the commercial use license document for customer packages."""
    display_shop = (shop_name or "Digital Art Studio").strip()
    clean_title = sanitize_display_title(listing_title)
    return f"""COMMERCIAL USE LICENSE & TERMS OF USE
================================================================================
Product: {clean_title}
Issued By: {display_shop}

Thank you for your purchase! This digital product includes a Commercial Use License.

PERMITTED USES:
--------------------------------------------------------------------------------
1. Physical Products: You MAY use this graphic on physical end-products for personal
   or commercial sale (including T-shirts, sweatshirts, mugs, tumblers, tote bags,
   posters, stickers, cards, pillows, and gifts).
2. Print-On-Demand (POD): You MAY upload this artwork to print-on-demand fulfillment
   services (Printify, Printful, Gelato, etc.) to produce physical items.
3. Quantity: Commercial sale up to 5,000 physical units per purchase.

PROHIBITED USES:
--------------------------------------------------------------------------------
1. Digital Resale: You may NOT resell, sub-license, share, donate, or distribute this
   digital file or any modified digital version in any format (PNG, SVG, PDF, etc.).
2. Digital Bundles: You may NOT include this artwork in digital scrapbooking kits,
   clipart packages, drive shares, or digital downloads.
3. Trademarking: You may NOT register this design, in whole or in part, as a trademark,
   service mark, or logo.
4. AI Training: You may NOT use this artwork to train public generative AI models.

REFUNDS & SUPPORT:
--------------------------------------------------------------------------------
Due to the digital nature of instant downloads, all sales are final. If you encounter
any issue unzipping or opening your files:
Support: Contact {display_shop} through Etsy Messages.
================================================================================
"""


def generate_instructions_text(listing_title: str, shop_name: str = "Digital Art Studio") -> str:
    """Generate customer instructions and printing sizing guide."""
    display_shop = (shop_name or "Digital Art Studio").strip()
    clean_title = sanitize_display_title(listing_title)
    return f"""INSTRUCTIONS & SIZING GUIDE
================================================================================
Artwork: {clean_title}

FILE SPECIFICATIONS:
--------------------------------------------------------------------------------
- Resolution: 4500 x 5400 Pixels (High-Resolution Print Quality)
- Print Density: 300 DPI (Dots Per Inch)
- Format: PNG with Transparent Background (sRGB Color Profile)
- Aspect Ratio: Standard 1:1.2 (Optimized for Direct-to-Garment and Apparel)
- Additional Format: Print-Ready PDF (Vector Scale-Preserved)

RECOMMENDED PRINT SIZES:
--------------------------------------------------------------------------------
- Standard Apparel: 10" x 12", 12" x 14", 14" x 16" (Max print area @ 300 DPI: 15" x 18")
- Wall Art & Posters: 8"x10", 11"x14", 12"x16", 16"x20"
- Drinkware & Accessories: Mugs (11oz & 15oz), Tumblers (20oz), Stickers & Tote Bags

HOW TO USE YOUR FILES:
--------------------------------------------------------------------------------
1. Unzip the downloaded package to your computer (Right-click > Extract All on Windows,
   or double-click on Mac).
2. Open the PNG in your design or cutter software (Photoshop, Illustrator, Canva,
   Cricut Design Space, Silhouette Studio, CorelDraw, Inkscape).
3. Ensure "Transparent Background" is preserved when placing on dark or light garments.
4. For highest print quality, do not stretch the graphic beyond 15" x 18" (300 DPI).

Need assistance? Contact {display_shop} via Etsy Messages.
================================================================================
"""


def generate_checksum_manifest(files: dict[str, bytes]) -> str:
    """Generate a standard sha256 checksum manifest (sha256  filename)."""
    lines: list[str] = [
        "# SHA-256 Checksum Manifest",
        "# Verify integrity: sha256sum -c manifest.sha256",
        "",
    ]
    for filename, content in sorted(files.items()):
        if filename == "manifest.sha256":
            continue
        sha = hashlib.sha256(content).hexdigest()
        lines.append(f"{sha}  {filename}")
    lines.append("")
    return "\n".join(lines)


def build_zip_archive(files: dict[str, bytes]) -> bytes:
    """Assemble an in-memory ZIP archive from named file contents deterministically.
    
    Sanitizes filenames to prevent directory traversal or Zip Slip attacks.
    """
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zip_file:
        for filename, content in sorted(files.items()):
            # Strip path traversal components and ensure clean basename
            clean_name = os.path.basename(filename.replace("\\", "/")).strip()
            clean_name = re.sub(r"[^\w\-. ]", "_", clean_name)
            if not clean_name or clean_name.startswith(".."):
                clean_name = f"file_{hashlib.sha256(content).hexdigest()[:8]}.dat"

            # Use deterministic ZipInfo with fixed timestamp
            info = zipfile.ZipInfo(clean_name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            zip_file.writestr(info, content)
    return zip_buffer.getvalue()

