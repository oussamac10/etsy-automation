"""Tests for pure Python customer download package builder and PDF generator."""

import zipfile
import io
import hashlib

from app.domain.package_builder import (
    build_zip_archive,
    create_print_ready_pdf,
    generate_checksum_manifest,
    generate_instructions_text,
    generate_license_text,
)


class TestPackageBuilder:
    def test_create_print_ready_pdf_valid_header_and_structure(self) -> None:
        # Minimal 1x1 PNG
        png_bytes = bytes.fromhex(
            "89504e470d0a1a0a0000000d494844520000000100000001080600000"
            "01f15c4890000000a49444154789c6360000002000100ffff03000006"
            "000557bfabd40000000049454e44ae426082"
        )

        pdf_bytes = create_print_ready_pdf(png_bytes, width_px=4500, height_px=5400)
        assert pdf_bytes.startswith(b"%PDF-1.4")
        assert b"%%EOF" in pdf_bytes
        assert b"/MediaBox [0 0 " in pdf_bytes
        assert b"/Type /XObject" in pdf_bytes
        assert b"/Subtype /Image" in pdf_bytes

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

        # Verify reading with Python standard zipfile
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            namelist = zf.namelist()
            assert "master.png" in namelist
            assert "print-ready.pdf" in namelist
            assert "LICENSE.txt" in namelist
            assert "INSTRUCTIONS.txt" in namelist
            assert "manifest.sha256" in namelist
            assert zf.read("master.png") == b"png data here"
            assert zf.read("print-ready.pdf") == b"%PDF-1.4 test"
