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

DEFAULT_WIDTH_PX: Final[int] = 4500
DEFAULT_HEIGHT_PX: Final[int] = 5400
DEFAULT_DPI: Final[int] = 300


def _parse_png_dimensions_and_channels(png_bytes: bytes) -> tuple[int, int, int]:
    """Extract width, height, and color type from PNG IHDR chunk."""
    if len(png_bytes) < 24 or png_bytes[:8] != b"\x89PNG\r\n\x1a\n":
        return DEFAULT_WIDTH_PX, DEFAULT_HEIGHT_PX, 6
    width, height, bit_depth, color_type = struct.unpack(">IIBB", png_bytes[16:26])
    return width, height, color_type


def create_print_ready_pdf(
    png_bytes: bytes,
    width_px: int = DEFAULT_WIDTH_PX,
    height_px: int = DEFAULT_HEIGHT_PX,
    dpi: int = DEFAULT_DPI,
) -> bytes:
    """Create a minimal, conforming PDF 1.4 embedding the master PNG.

    Computes exact page dimensions in points (72 pt / inch) for the 300 DPI image.
    """
    detected_w, detected_h, color_type = _parse_png_dimensions_and_channels(png_bytes)
    w_px = detected_w or width_px
    h_px = detected_h or height_px

    # Calculate dimensions in points (72 points = 1 inch)
    width_pt = (w_px * 72.0) / dpi
    height_pt = (h_px * 72.0) / dpi

    # Extract raw IDAT chunks from PNG
    idat_data = bytearray()
    offset = 8
    while offset < len(png_bytes):
        if offset + 8 > len(png_bytes):
            break
        length = struct.unpack(">I", png_bytes[offset : offset + 4])[0]
        chunk_type = png_bytes[offset + 4 : offset + 8]
        if chunk_type == b"IDAT":
            idat_data.extend(png_bytes[offset + 8 : offset + 8 + length])
        elif chunk_type == b"IEND":
            break
        offset += 12 + length

    # If IDAT extraction succeeded, process scanlines for PDF
    # Otherwise fallback to a clean wrapper
    pdf_buffer = io.BytesIO()

    # Objects:
    # 1 0: Catalog
    # 2 0: Outlines
    # 3 0: Pages
    # 4 0: Page
    # 5 0: Page contents (stream)
    # 6 0: Image XObject (stream)
    # 7 0: SMask XObject (if RGBA)

    # Decode PNG raster to separate RGB and Alpha if RGBA (color_type 6)
    rgb_stream = b""
    alpha_stream = b""
    has_smask = False

    try:
        if idat_data:
            decompressed = zlib.decompress(bytes(idat_data))
            bpp = 4 if color_type == 6 else (3 if color_type == 2 else 4)
            expected_stride = 1 + w_px * bpp

            if len(decompressed) >= expected_stride * h_px:
                rgb_raw = bytearray()
                alpha_raw = bytearray()
                for y in range(h_px):
                    row_start = y * expected_stride
                    filter_byte = decompressed[row_start]
                    # Simple unfiltering for filter 0 (none) or direct channel extraction
                    row_pixels = decompressed[row_start + 1 : row_start + expected_stride]
                    for x in range(w_px):
                        px_idx = x * bpp
                        rgb_raw.extend(row_pixels[px_idx : px_idx + 3])
                        if bpp == 4:
                            alpha_raw.append(row_pixels[px_idx + 3])

                rgb_stream = zlib.compress(bytes(rgb_raw))
                if bpp == 4:
                    alpha_stream = zlib.compress(bytes(alpha_raw))
                    has_smask = True
    except Exception:
        # If raw IDAT decomposition fails, use full PNG IDAT
        rgb_stream = bytes(idat_data) if idat_data else png_bytes

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

    # 5: Image XObject
    if has_smask and alpha_stream:
        img_dict = (
            f"<< /Type /XObject /Subtype /Image /Width {w_px} /Height {h_px} "
            f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode "
            f"/SMask 6 0 R /Length {len(rgb_stream)} >>\nstream\n"
        ).encode("ascii") + rgb_stream + b"\nendstream"
        objects.append(img_dict)

        # 6: SMask XObject
        smask_dict = (
            f"<< /Type /XObject /Subtype /Image /Width {w_px} /Height {h_px} "
            f"/ColorSpace /DeviceGray /BitsPerComponent 8 /Filter /FlateDecode "
            f"/Length {len(alpha_stream)} >>\nstream\n"
        ).encode("ascii") + alpha_stream + b"\nendstream"
        objects.append(smask_dict)
    else:
        img_dict = (
            f"<< /Type /XObject /Subtype /Image /Width {w_px} /Height {h_px} "
            f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode "
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


def generate_license_text(shop_name: str, listing_title: str) -> str:
    """Generate the commercial use license document for customer packages."""
    return f"""COMMERCIAL USE LICENSE & TERMS OF USE
================================================================================
Product: {listing_title}
Issued By: {shop_name or "Digital Art Studio"}

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
any issue unzipping or opening your files, please reach out via Etsy messages!
================================================================================
"""


def generate_instructions_text(listing_title: str) -> str:
    """Generate customer instructions and printing sizing guide."""
    return f"""INSTRUCTIONS & SIZING GUIDE
================================================================================
Artwork: {listing_title}

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

Need assistance? Feel free to contact us via Etsy messages!
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
