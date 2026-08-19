"""Tests for customer download package builder and print-ready PDF generator."""

from __future__ import annotations

import hashlib
import io
import struct
import zipfile
import zlib
import pytest
from PIL import Image

from app.domain.package_builder import (
    build_zip_archive,
    create_print_ready_pdf,
    generate_checksum_manifest,
    generate_instructions_text,
    generate_license_text,
    optimize_png_deflate,
    sanitize_brand_slug,
    sanitize_product_title,
)


def _make_test_rgba_png(
    width: int = 200,
    height: int = 200,
) -> tuple[bytes, dict[str, tuple[int, int, int]]]:
    """Create a test RGBA PNG with distinctive vibrant colors, semi-transparency, and transparent background."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    w4 = max(1, width // 4)
    w2 = max(2, width // 2)
    h4 = max(1, height // 4)
    h2 = max(2, height // 2)

    # Color quadrants:
    # Top-Left: Solid Vibrant Red
    for x in range(w4):
        for y in range(h4):
            img.putpixel((x, y), (255, 0, 0, 255))

    # Top-Right: Solid Gingerbread Brown
    for x in range(w4, w2):
        for y in range(h4):
            img.putpixel((x, y), (180, 100, 50, 255))

    # Center-Left: Solid Vibrant Green
    for x in range(w4):
        for y in range(h4, h2):
            img.putpixel((x, y), (0, 200, 50, 255))

    # Center-Right: 50% Semi-transparent Festive Red (alpha=128)
    # Expected on white: R = round(200 * (128/255) + 255 * (1 - 128/255)) = 227
    #                   G = round(0 * (128/255) + 255 * (1 - 128/255)) = 127
    #                   B = round(0 * (128/255) + 255 * (1 - 128/255)) = 127
    for x in range(w4, w2):
        for y in range(h4, h2):
            img.putpixel((x, y), (200, 0, 0, 128))

    # Bottom half is left fully transparent: (0, 0, 0, 0) -> should flatten to white (255, 255, 255)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    expected_pixels = {
        "red": (255, 0, 0),
        "gingerbread_brown": (180, 100, 50),
        "green": (0, 200, 50),
        "semi_red_on_white": (227, 127, 127),
        "transparent_to_white": (255, 255, 255),
    }
    return png_bytes, expected_pixels


class TestPackageBuilder:
    def test_create_print_ready_pdf_valid_header_and_structure(self) -> None:
        png_bytes, _ = _make_test_rgba_png(width=100, height=100)

        pdf_bytes = create_print_ready_pdf(png_bytes, width_px=4500, height_px=5400, dpi=300)
        assert pdf_bytes.startswith(b"%PDF-1.4")
        assert b"%%EOF" in pdf_bytes
        assert b"/MediaBox [0 0 " in pdf_bytes
        assert b"/Type /XObject" in pdf_bytes
        assert b"/Subtype /Image" in pdf_bytes
        assert b"/ColorSpace /DeviceRGB" in pdf_bytes
        assert b"/BitsPerComponent 8" in pdf_bytes
        # Crucial requirement: No /SMask transparency layer in flattened print PDF
        assert b"/SMask" not in pdf_bytes

    def test_print_ready_pdf_exact_dimensions_4500x5400(self) -> None:
        """4500x5400 at 300 DPI corresponds to 15x18 inches (1080x1296 PDF points)."""
        img = Image.new("RGBA", (4500, 5400), (255, 100, 50, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        pdf_bytes = create_print_ready_pdf(png_bytes, dpi=300)
        # Expected MediaBox [0 0 1080.00 1296.00]
        assert b"/MediaBox [0 0 1080.00 1296.00]" in pdf_bytes
        assert b"q 1080.00 0 0 1296.00 0 0 cm /Im1 Do Q" in pdf_bytes

    def test_pdf_full_color_preservation_and_visual_regression(self) -> None:
        """Visual regression test verifying that colors are preserved accurately and transparent areas become solid white."""
        import fitz

        png_bytes, expected_colors = _make_test_rgba_png(width=200, height=200)
        # Verify source PNG has not changed and retains alpha
        original_img = Image.open(io.BytesIO(png_bytes))
        assert original_img.mode == "RGBA"
        assert original_img.getpixel((150, 150)) == (0, 0, 0, 0)

        # Generate print-ready PDF
        pdf_bytes = create_print_ready_pdf(png_bytes, width_px=200, height_px=200, dpi=300)

        # Render PDF back to image at 300 DPI
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        assert len(doc) == 1
        page = doc[0]
        pix = page.get_pixmap(dpi=300)
        rendered_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # Sample pixel coordinates (scale 1:1 on 200x200 canvas)
        red_sample = rendered_img.getpixel((25, 25))
        brown_sample = rendered_img.getpixel((75, 25))
        green_sample = rendered_img.getpixel((25, 75))
        semi_red_sample = rendered_img.getpixel((75, 75))
        white_sample = rendered_img.getpixel((150, 150))

        # Check tolerances (within 2 values out of 255 for color fidelity)
        assert abs(red_sample[0] - expected_colors["red"][0]) <= 2
        assert abs(red_sample[1] - expected_colors["red"][1]) <= 2
        assert abs(red_sample[2] - expected_colors["red"][2]) <= 2

        assert abs(brown_sample[0] - expected_colors["gingerbread_brown"][0]) <= 2
        assert abs(brown_sample[1] - expected_colors["gingerbread_brown"][1]) <= 2
        assert abs(brown_sample[2] - expected_colors["gingerbread_brown"][2]) <= 2

        assert abs(green_sample[0] - expected_colors["green"][0]) <= 2
        assert abs(green_sample[1] - expected_colors["green"][1]) <= 2
        assert abs(green_sample[2] - expected_colors["green"][2]) <= 2

        assert abs(semi_red_sample[0] - expected_colors["semi_red_on_white"][0]) <= 2
        assert abs(semi_red_sample[1] - expected_colors["semi_red_on_white"][1]) <= 2
        assert abs(semi_red_sample[2] - expected_colors["semi_red_on_white"][2]) <= 2

        assert abs(white_sample[0] - expected_colors["transparent_to_white"][0]) <= 2
        assert abs(white_sample[1] - expected_colors["transparent_to_white"][1]) <= 2
        assert abs(white_sample[2] - expected_colors["transparent_to_white"][2]) <= 2

        # Source PNG must remain transparent and untouched
        recheck_img = Image.open(io.BytesIO(png_bytes))
        assert recheck_img.getpixel((150, 150))[3] == 0

    def test_retro_christmas_baking_style_artwork_color_fidelity(self) -> None:
        """Test on representative multi-color Christmas artwork (red, green, gingerbread brown, candy cane)."""
        import fitz

        # Create multi-color artwork:
        # - Brown gingerbread body (160, 90, 44)
        # - Red icing / Santa hat (220, 20, 30)
        # - Green pine branches (34, 139, 34)
        # - White icing (255, 255, 255)
        # - Transparent background
        w, h = 300, 300
        art = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        for x in range(50, 150):
            for y in range(50, 150):
                art.putpixel((x, y), (160, 90, 44, 255))  # Gingerbread brown
        for x in range(150, 250):
            for y in range(50, 150):
                art.putpixel((x, y), (220, 20, 30, 255))  # Christmas red
        for x in range(50, 150):
            for y in range(150, 250):
                art.putpixel((x, y), (34, 139, 34, 255))  # Pine green

        buf = io.BytesIO()
        art.save(buf, format="PNG")
        art_bytes = buf.getvalue()

        pdf_bytes = create_print_ready_pdf(art_bytes, width_px=w, height_px=h, dpi=300)

        # Render PDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pix = doc[0].get_pixmap(dpi=300)
        rendered = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # Brown region
        brown_px = rendered.getpixel((100, 100))
        assert brown_px == (160, 90, 44)

        # Red region
        red_px = rendered.getpixel((200, 100))
        assert red_px == (220, 20, 30)

        # Green region
        green_px = rendered.getpixel((100, 200))
        assert green_px == (34, 139, 34)

        # Background region (originally transparent, now solid white)
        bg_px = rendered.getpixel((20, 20))
        assert bg_px == (255, 255, 255)

    def test_generate_license_text(self) -> None:
        lic = generate_license_text("Forest Studio", "Cute Mushroom PNG")
        assert "Forest Studio" in lic
        assert "Cute Mushroom PNG" in lic
        assert "COMMERCIAL USE LICENSE" in lic
        assert "PERMITTED USES:" in lic
        assert "PROHIBITED USES:" in lic

    def test_generate_instructions_text(self) -> None:
        inst = generate_instructions_text("Cute Mushroom PNG")
        assert "Cute Mushroom PNG" in inst
        assert "INSTRUCTIONS & SIZING GUIDE" in inst
        assert "4500 x 5400" in inst
        assert "Direct-to-Garment" in inst

    def test_generate_checksum_manifest(self) -> None:
        files = {
            "master.png": b"fake master png bytes",
            "LICENSE.txt": b"fake license text",
        }
        manifest = generate_checksum_manifest(files)
        assert "master.png" in manifest
        assert "LICENSE.txt" in manifest

        expected_sha = hashlib.sha256(b"fake master png bytes").hexdigest()
        assert f"{expected_sha}  master.png" in manifest

    def test_build_zip_archive_is_valid_and_readable(self) -> None:
        files = {
            "master.png": b"png data here",
            "print-ready.pdf": b"%PDF-1.4 test",
            "LICENSE.txt": b"license text",
            "INSTRUCTIONS.txt": b"instruction text",
            "manifest.sha256": b"manifest text",
        }

        zip_bytes = build_zip_archive(files)
        assert zip_bytes.startswith(b"PK")

    def test_optimize_png_deflate(self) -> None:
        png_bytes, _ = _make_test_rgba_png(width=50, height=50)
        opt = optimize_png_deflate(png_bytes)
        assert opt.startswith(b"\x89PNG\r\n\x1a\n")
        assert opt.endswith(b"IEND\xaeB`\x82")

