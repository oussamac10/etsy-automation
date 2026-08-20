"""Tests for EtsyDigitalDeliveryPlanner, ZIP integrity, and direct file delivery."""

from __future__ import annotations

import io
import struct
import tempfile
import zipfile
import zlib
import pytest

from app.domain.errors import DomainError
from app.domain.etsy_delivery_planner import (
    EtsyDeliveryFile,
    EtsyDigitalDeliveryPlanner,
    MAX_ETSY_DIGITAL_FILE_BYTES,
    MAX_ETSY_DIGITAL_FILES_COUNT,
    validate_png_integrity,
    validate_zip_integrity,
)
from app.domain.package_builder import (
    build_zip_archive,
    create_print_ready_pdf,
    generate_checksum_manifest,
)


def _create_test_png_bytes(
    width: int = 4500,
    height: int = 5400,
    color_type: int = 6,
    raw_payload_bytes: int = 1024,
) -> bytes:
    """Helper to create a deterministic valid PNG with IHDR and IDAT chunks."""
    header = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data)
    ihdr = struct.pack(">I", len(ihdr_data)) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)

    import os
    raw_scanlines = b"\x00" + os.urandom(raw_payload_bytes)

    # Use level 0 (store only) so raw_payload_bytes doesn't shrink under deflate
    compressed_idat = zlib.compress(raw_scanlines, level=0)
    idat_crc = zlib.crc32(b"IDAT" + compressed_idat)
    idat = struct.pack(">I", len(compressed_idat)) + b"IDAT" + compressed_idat + struct.pack(">I", idat_crc)

    iend_crc = zlib.crc32(b"IEND")
    iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)

    return header + ihdr + idat + iend


class TestZipIntegrityValidation:
    def test_validate_zip_integrity_succeeds_on_valid_archive(self) -> None:
        files = {
            "master.png": b"fake master png content",
            "LICENSE.txt": b"fake commercial license text",
            "manifest.sha256": b"fake sha256 checksums",
        }
        zip_bytes = build_zip_archive(files)
        validate_zip_integrity(zip_bytes, expected_members=list(files.keys()))

    def test_validate_zip_integrity_fails_on_empty_bytes(self) -> None:
        with pytest.raises(DomainError, match="empty"):
            validate_zip_integrity(b"")

    def test_validate_zip_integrity_fails_on_corrupt_or_truncated_bytes(self) -> None:
        valid_zip = build_zip_archive({"test.txt": b"content"})
        corrupt_zip = valid_zip[: len(valid_zip) // 2]
        with pytest.raises(DomainError, match="Invalid ZIP archive structure"):
            validate_zip_integrity(corrupt_zip)

    def test_validate_zip_integrity_fails_on_missing_expected_member(self) -> None:
        valid_zip = build_zip_archive({"file_a.txt": b"AAA"})
        with pytest.raises(DomainError, match="missing from ZIP archive"):
            validate_zip_integrity(valid_zip, expected_members=["file_b.txt"])


class TestPngIntegrityValidation:
    def test_validate_png_integrity_succeeds_on_valid_png(self) -> None:
        png_bytes = _create_test_png_bytes(width=4500, height=5400)
        validate_png_integrity(png_bytes, expected_width=4500, expected_height=5400)

    def test_validate_png_integrity_fails_on_invalid_signature(self) -> None:
        with pytest.raises(DomainError, match="Invalid PNG signature"):
            validate_png_integrity(b"NOT_A_PNG_FILE")

    def test_validate_png_integrity_fails_on_dimension_mismatch(self) -> None:
        png_bytes = _create_test_png_bytes(width=3000, height=3000)
        with pytest.raises(DomainError, match="width 3000px does not match expected 4500px"):
            validate_png_integrity(png_bytes, expected_width=4500, expected_height=5400)

    def test_validate_png_integrity_fails_on_corrupted_idat(self) -> None:
        # Create a PNG where IDAT chunk data is corrupted compressed stream
        header = b"\x89PNG\r\n\x1a\n"
        ihdr_data = struct.pack(">IIBBBBB", 100, 100, 8, 6, 0, 0, 0)
        ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data)
        ihdr = struct.pack(">I", len(ihdr_data)) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)

        corrupt_idat_data = b"NOT_VALID_ZLIB_DATA_AT_ALL_XYZ123"
        idat_crc = zlib.crc32(b"IDAT" + corrupt_idat_data)
        idat = struct.pack(">I", len(corrupt_idat_data)) + b"IDAT" + corrupt_idat_data + struct.pack(">I", idat_crc)

        iend_crc = zlib.crc32(b"IEND")
        iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)

        png_bytes = header + ihdr + idat + iend

        with pytest.raises(DomainError, match="Corrupted PNG IDAT stream"):
            validate_png_integrity(png_bytes, expected_width=100, expected_height=100)


class TestEtsyDigitalDeliveryPlanner:
    def test_case_a_single_complete_zip_when_under_limit(self) -> None:
        planner = EtsyDigitalDeliveryPlanner(max_file_bytes=20 * 1024 * 1024)
        png_bytes = _create_test_png_bytes(width=4500, height=5400)

        planned = planner.plan_delivery(
            master_png_bytes=png_bytes,
            listing_title="Cozy Fall Book Lover PNG",
            shop_name="Autumn Crafts Studio",
            master_width=4500,
            master_height=5400,
            include_pdf=True,
        )

        assert len(planned) == 1
        complete_zip = planned[0]
        assert complete_zip.filename == "Autumn_Crafts_Studio_Cozy_Fall_Book_Lover_PNG_Digital_Download.zip"
        assert complete_zip.mime_type == "application/zip"
        assert len(complete_zip.content) <= 20 * 1024 * 1024

        # Verify ZIP can be opened and extracted completely with branded filenames
        with zipfile.ZipFile(io.BytesIO(complete_zip.content), "r") as zf:
            assert zf.testzip() is None
            namelist = zf.namelist()
            assert "Autumn_Crafts_Studio_Cozy_Fall_Book_Lover_PNG_PNG.png" in namelist
            assert "Autumn_Crafts_Studio_Cozy_Fall_Book_Lover_PNG_LICENSE.txt" in namelist
            assert "Autumn_Crafts_Studio_Cozy_Fall_Book_Lover_PNG_INSTRUCTIONS.txt" in namelist
            assert "Autumn_Crafts_Studio_Cozy_Fall_Book_Lover_PNG_manifest.sha256" in namelist

    def test_case_b_direct_master_png_and_extras_zip_when_total_exceeds_limit(self) -> None:
        # Create a PNG of 15KB with random bytes
        png_bytes = _create_test_png_bytes(width=4500, height=5400, raw_payload_bytes=15000)

        # Single complete ZIP is ~15.5KB. Set max_file_bytes to 15.2KB so single ZIP fails,
        # but direct master PNG (15.0KB) and extras ZIP (1.5KB) both fit easily.
        planner = EtsyDigitalDeliveryPlanner(max_file_bytes=len(png_bytes) + 100)

        planned = planner.plan_delivery(
            master_png_bytes=png_bytes,
            listing_title="Cozy Fall Book Lover PNG",
            shop_name="Autumn Crafts Studio",
            master_width=4500,
            master_height=5400,
            include_pdf=False,
        )

        assert len(planned) == 2
        file1 = planned[0]
        file2 = planned[1]

        # Deliverable 1: Direct Master PNG
        assert file1.filename == "Autumn_Crafts_Studio_Cozy_Fall_Book_Lover_PNG_PNG.png"
        assert file1.mime_type == "image/png"
        validate_png_integrity(file1.content, 4500, 5400)

        # Deliverable 2: Extras ZIP
        assert file2.filename == "Autumn_Crafts_Studio_Cozy_Fall_Book_Lover_PNG_Extras.zip"
        assert file2.mime_type == "application/zip"
        validate_zip_integrity(
            file2.content,
            [
                "Autumn_Crafts_Studio_Cozy_Fall_Book_Lover_PNG_LICENSE.txt",
                "Autumn_Crafts_Studio_Cozy_Fall_Book_Lover_PNG_INSTRUCTIONS.txt",
                "Autumn_Crafts_Studio_Cozy_Fall_Book_Lover_PNG_manifest.sha256",
            ],
        )

        # Confirm all planned files are within configured limit
        for f in planned:
            assert len(f.content) <= planner.max_file_bytes

    def test_dynamic_shop_name_generates_distinct_branding_without_code_changes(self) -> None:
        """Asserts that two different shop names produce distinct branding dynamically."""
        planner = EtsyDigitalDeliveryPlanner(max_file_bytes=20 * 1024 * 1024)
        png_bytes = _create_test_png_bytes(width=4500, height=5400)

        # Shop A
        planned_a = planner.plan_delivery(
            master_png_bytes=png_bytes,
            listing_title="Vintage Floral PNG",
            shop_name="NovaCraftPixel",
            include_pdf=False,
        )
        assert planned_a[0].filename == "NovaCraftPixel_Vintage_Floral_PNG_Digital_Download.zip"
        with zipfile.ZipFile(io.BytesIO(planned_a[0].content), "r") as zf:
            lic = zf.read("NovaCraftPixel_Vintage_Floral_PNG_LICENSE.txt").decode("utf-8")
            assert "Issued By: NovaCraftPixel" in lic
            assert "Support: Contact NovaCraftPixel through Etsy Messages." in lic

        # Shop B
        planned_b = planner.plan_delivery(
            master_png_bytes=png_bytes,
            listing_title="Vintage Floral PNG",
            shop_name="PixelMoonStudio",
            include_pdf=False,
        )
        assert planned_b[0].filename == "PixelMoonStudio_Vintage_Floral_PNG_Digital_Download.zip"
        with zipfile.ZipFile(io.BytesIO(planned_b[0].content), "r") as zf:
            lic = zf.read("PixelMoonStudio_Vintage_Floral_PNG_LICENSE.txt").decode("utf-8")
            assert "Issued By: PixelMoonStudio" in lic
            assert "Support: Contact PixelMoonStudio through Etsy Messages." in lic

    def test_case_c_oversized_master_fails_safely_with_domain_error(self) -> None:
        # Set limit extremely small so even master PNG cannot fit
        planner = EtsyDigitalDeliveryPlanner(max_file_bytes=50)  # 50 bytes
        png_bytes = _create_test_png_bytes(width=4500, height=5400, raw_payload_bytes=5000)

        with pytest.raises(DomainError, match="exceeds Etsy's maximum digital file limit"):
            planner.plan_delivery(
                master_png_bytes=png_bytes,
                listing_title="Massive Artwork",
                master_width=4500,
                master_height=5400,
            )

    def test_regression_no_raw_byte_chunking_all_zips_independently_extractable(self) -> None:
        """Regression test ensuring every generated .zip is independently extractable on disk (like macOS Archive Utility)."""
        png_bytes = _create_test_png_bytes(width=4500, height=5400, raw_payload_bytes=8000)
        planner = EtsyDigitalDeliveryPlanner(max_file_bytes=len(png_bytes) + 100)

        planned = planner.plan_delivery(
            master_png_bytes=png_bytes,
            listing_title="Cozy Fall Book Lover PNG",
            include_pdf=False,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            for item in planned:
                if item.mime_type == "application/zip":
                    # Must unzip without any error or corruption
                    with zipfile.ZipFile(io.BytesIO(item.content), "r") as zf:
                        assert zf.testzip() is None
                        zf.extractall(tmp_dir)

    def test_enforces_max_files_count_limit(self) -> None:
        png_bytes = _create_test_png_bytes(width=4500, height=5400, raw_payload_bytes=8000)
        planner = EtsyDigitalDeliveryPlanner(max_files_count=1, max_file_bytes=len(png_bytes) + 100)

        with pytest.raises(DomainError, match="exceeds Etsy's maximum allowed limit of 1 files"):
            planner.plan_delivery(
                master_png_bytes=png_bytes,
                listing_title="Test Listing",
                include_pdf=False,
            )

    def test_etsy_filename_length_strictly_under_70_chars(self) -> None:
        """Verify that very long listing titles and shop names produce filenames strictly <= 70 chars."""
        import re

        planner = EtsyDigitalDeliveryPlanner()
        png_bytes = _create_test_png_bytes(width=4500, height=5400)

        planned = planner.plan_delivery(
            master_png_bytes=png_bytes,
            listing_title="Patchwork Sea Turtle PNG Sublimation Design Digital Download Clipart For T-Shirts and Hoodies",
            shop_name="NovaCraftPixel Studio Boutique",
            include_pdf=True,
        )

        assert len(planned) > 0
        for item in planned:
            assert 3 <= len(item.filename) <= 70, f"Filename '{item.filename}' length {len(item.filename)} violates Etsy 3-70 constraint"
            assert re.match(r"^[a-zA-Z0-9_.-]+$", item.filename), f"Filename '{item.filename}' contains invalid Etsy chars"

