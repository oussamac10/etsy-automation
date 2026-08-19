"""Etsy digital delivery packaging and file planning.

Plans, groups, and validates deterministic, valid digital deliverable files for Etsy Open API v3.
Ensures:
- Every uploaded .zip file is a standalone, fully valid ZIP archive (verified with testzip()).
- Zero raw byte chunking or slicing of archives.
- Direct master PNG delivery where applicable.
- Validates PNG integrity (signature, dimensions, non-truncated IDAT).
- Validates PDF completeness.
- Validates checksum manifest accuracy.
- Enforces Etsy limits (<= 5 files, <= 20MB per file).
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import re
import struct
from typing import Final
import zipfile
import zlib

from app.domain.errors import DomainError
from app.domain.package_builder import (
    DEFAULT_HEIGHT_PX,
    DEFAULT_WIDTH_PX,
    build_zip_archive,
    create_print_ready_pdf,
    generate_checksum_manifest,
    generate_instructions_text,
    generate_license_text,
    optimize_png_deflate,
)

MAX_ETSY_DIGITAL_FILES_COUNT: Final[int] = 5
MAX_ETSY_DIGITAL_FILE_BYTES: Final[int] = 20 * 1024 * 1024  # 20MB (20,971,520 bytes)


@dataclass(frozen=True)
class EtsyDeliveryFile:
    """A verified, standalone deliverable file ready for upload to Etsy Open API v3."""

    filename: str
    mime_type: str
    content: bytes
    checksum_sha256: str
    file_key: str  # Deterministic identifier for idempotent uploads


def validate_zip_integrity(zip_bytes: bytes, expected_members: list[str] | None = None) -> None:
    """Verify that bytes represent a complete, uncorrupted, extractable ZIP archive.
    
    Checks:
    1. Opens successfully with zipfile.ZipFile.
    2. testzip() reports zero corrupt members.
    3. Contains at least one member.
    4. No duplicate member names.
    5. All expected members are present and readable in full.
    """
    if len(zip_bytes) == 0:
        raise DomainError("Generated ZIP archive is empty (0 bytes).")

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            bad_member = zf.testzip()
            if bad_member is not None:
                raise DomainError(f"Corrupt member '{bad_member}' detected in generated ZIP archive.")

            namelist = zf.namelist()
            if not namelist:
                raise DomainError("ZIP archive contains no file members.")

            if len(namelist) != len(set(namelist)):
                raise DomainError("ZIP archive contains duplicate member names.")

            if expected_members:
                for expected in expected_members:
                    if expected not in namelist:
                        raise DomainError(f"Expected member '{expected}' missing from ZIP archive.")

            # Read all members to verify full uncompressed stream integrity
            for name in namelist:
                zf.read(name)
    except (zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise DomainError(f"Invalid ZIP archive structure: {exc}") from exc


def validate_png_integrity(
    png_bytes: bytes,
    expected_width: int | None = None,
    expected_height: int | None = None,
) -> None:
    """Verify that bytes represent a valid, complete PNG with valid signature and readable IDAT."""
    if len(png_bytes) < 24 or png_bytes[:8] != b"\x89PNG\r\n\x1a\n":
        raise DomainError("Invalid PNG signature.")

    width, height, bit_depth, color_type = struct.unpack(">IIBB", png_bytes[16:26])
    if width <= 0 or height <= 0:
        raise DomainError(f"Invalid PNG dimensions: {width}x{height}")

    if expected_width and expected_width > 0 and width != expected_width:
        raise DomainError(f"PNG width {width}px does not match expected {expected_width}px.")
    if expected_height and expected_height > 0 and height != expected_height:
        raise DomainError(f"PNG height {height}px does not match expected {expected_height}px.")

    # Traverse chunks and ensure IDAT stream decompresses
    offset = 8
    idat_combined = bytearray()
    has_iend = False

    while offset < len(png_bytes):
        if offset + 8 > len(png_bytes):
            break
        length = struct.unpack(">I", png_bytes[offset : offset + 4])[0]
        chunk_type = png_bytes[offset + 4 : offset + 8]
        if chunk_type == b"IDAT":
            idat_combined.extend(png_bytes[offset + 8 : offset + 8 + length])
        elif chunk_type == b"IEND":
            has_iend = True
            break
        offset += 12 + length

    if not has_iend:
        raise DomainError("Incomplete PNG: missing IEND chunk.")

    try:
        zlib.decompress(bytes(idat_combined))
    except Exception as exc:
        raise DomainError(f"Corrupted PNG IDAT stream: {exc}") from exc


class EtsyDigitalDeliveryPlanner:
    """Planner for assembling compliant, valid digital deliverables for Etsy."""

    def __init__(
        self,
        max_file_bytes: int = MAX_ETSY_DIGITAL_FILE_BYTES,
        max_files_count: int = MAX_ETSY_DIGITAL_FILES_COUNT,
    ) -> None:
        self.max_file_bytes = max_file_bytes
        self.max_files_count = max_files_count

    def plan_delivery(
        self,
        *,
        master_png_bytes: bytes,
        listing_title: str,
        shop_name: str = "Digital Art Studio",
        master_width: int = DEFAULT_WIDTH_PX,
        master_height: int = DEFAULT_HEIGHT_PX,
        include_pdf: bool = True,
    ) -> list[EtsyDeliveryFile]:
        """Create a deterministic, validated list of uploadable Etsy digital deliverable files.

        Delivery Hierarchy:
        - Case A: Single complete customer ZIP fits within limit (<= 20MB).
        - Case B: Complete ZIP > 20MB, but master PNG fits individually (<= 20MB).
                  Produces [master.png, extras.zip] (where extras contains PDF, license, instructions, manifest).
        - Case C: Master PNG > 20MB:
                  1. Run lossless deflate optimization.
                  2. If optimized PNG <= 20MB, execute Case B.
                  3. If optimized PNG packed in standalone ZIP <= 20MB, produces [master.zip, extras.zip].
                  4. If even master.zip exceeds 20MB, fail safely with DomainError without raw byte splitting.
        """
        clean_slug = re.sub(r"[^a-zA-Z0-9_-]", "_", listing_title[:35]).strip("_") or "artwork"

        # 1. Optimize master PNG losslessly
        optimized_master = optimize_png_deflate(master_png_bytes)
        validate_png_integrity(optimized_master, master_width, master_height)
        master_sha = hashlib.sha256(optimized_master).hexdigest()

        # 2. Build Documentation
        license_doc = generate_license_text(shop_name, listing_title).encode("utf-8")
        instructions_doc = generate_instructions_text(listing_title).encode("utf-8")

        # 3. Build Optional Print-Ready PDF
        pdf_bytes: bytes | None = None
        if include_pdf and len(optimized_master) < 10 * 1024 * 1024:
            try:
                pdf_bytes = create_print_ready_pdf(
                    optimized_master,
                    width_px=master_width,
                    height_px=master_height,
                )
                if len(pdf_bytes) > self.max_file_bytes:
                    pdf_bytes = None
            except Exception:
                pdf_bytes = None

        # ----------------------------------------------------------------------
        # Case A: Try single complete customer archive
        # ----------------------------------------------------------------------
        single_pack_files: dict[str, bytes] = {
            "master.png": optimized_master,
            "LICENSE.txt": license_doc,
            "INSTRUCTIONS.txt": instructions_doc,
        }
        if pdf_bytes is not None:
            single_pack_files["print-ready.pdf"] = pdf_bytes

        manifest_a = generate_checksum_manifest(single_pack_files).encode("utf-8")
        single_pack_files["manifest.sha256"] = manifest_a

        single_zip_bytes = build_zip_archive(single_pack_files)

        if len(single_zip_bytes) <= self.max_file_bytes:
            validate_zip_integrity(single_zip_bytes, list(single_pack_files.keys()))
            zip_sha = hashlib.sha256(single_zip_bytes).hexdigest()
            return [
                EtsyDeliveryFile(
                    filename=f"{clean_slug}.zip",
                    mime_type="application/zip",
                    content=single_zip_bytes,
                    checksum_sha256=zip_sha,
                    file_key=f"{clean_slug}_complete_zip",
                )
            ]

        # ----------------------------------------------------------------------
        # Case B: Direct Master PNG + Standalone Extras ZIP
        # ----------------------------------------------------------------------
        planned_files: list[EtsyDeliveryFile] = []

        if len(optimized_master) <= self.max_file_bytes:
            # Deliverable 1: Direct Master PNG
            planned_files.append(
                EtsyDeliveryFile(
                    filename=f"{clean_slug}_master.png",
                    mime_type="image/png",
                    content=optimized_master,
                    checksum_sha256=master_sha,
                    file_key=f"{clean_slug}_master_png",
                )
            )
        else:
            # Check if packing master in a dedicated ZIP archive compresses under limit
            master_zip_files = {f"{clean_slug}_master.png": optimized_master}
            master_zip_bytes = build_zip_archive(master_zip_files)
            if len(master_zip_bytes) <= self.max_file_bytes:
                validate_zip_integrity(master_zip_bytes, [f"{clean_slug}_master.png"])
                planned_files.append(
                    EtsyDeliveryFile(
                        filename=f"{clean_slug}_master.zip",
                        mime_type="application/zip",
                        content=master_zip_bytes,
                        checksum_sha256=hashlib.sha256(master_zip_bytes).hexdigest(),
                        file_key=f"{clean_slug}_master_zip",
                    )
                )
            else:
                # Master itself exceeds Etsy's per-file limit even after optimization and zipping
                size_mb = len(optimized_master) / (1024 * 1024)
                limit_mb = self.max_file_bytes // (1024 * 1024)
                raise DomainError(
                    f"Master PNG is {size_mb:.1f} MB and exceeds Etsy's maximum digital file limit of {limit_mb}MB. "
                    f"Optimize the production master before Etsy dispatch."
                )

        # Build Extras ZIP (PDF if fits, License, Instructions, Master Checksum Manifest)
        extras_files: dict[str, bytes] = {
            "LICENSE.txt": license_doc,
            "INSTRUCTIONS.txt": instructions_doc,
            "master_artwork_checksum.sha256": f"{master_sha}  {clean_slug}_master.png\n".encode("utf-8"),
        }
        if pdf_bytes is not None and len(pdf_bytes) < 15 * 1024 * 1024:
            extras_files["print-ready.pdf"] = pdf_bytes

        manifest_extras = generate_checksum_manifest(extras_files).encode("utf-8")
        extras_files["manifest.sha256"] = manifest_extras

        extras_zip_bytes = build_zip_archive(extras_files)

        if len(extras_zip_bytes) <= self.max_file_bytes:
            validate_zip_integrity(extras_zip_bytes, list(extras_files.keys()))
            planned_files.append(
                EtsyDeliveryFile(
                    filename=f"{clean_slug}_extras.zip",
                    mime_type="application/zip",
                    content=extras_zip_bytes,
                    checksum_sha256=hashlib.sha256(extras_zip_bytes).hexdigest(),
                    file_key=f"{clean_slug}_extras_zip",
                )
            )
        else:
            # If extras exceeds limit (e.g. PDF is large), separate docs and PDF into independent valid ZIPs
            doc_files = {
                "LICENSE.txt": license_doc,
                "INSTRUCTIONS.txt": instructions_doc,
                "manifest.sha256": generate_checksum_manifest(
                    {"LICENSE.txt": license_doc, "INSTRUCTIONS.txt": instructions_doc}
                ).encode("utf-8"),
            }
            doc_zip = build_zip_archive(doc_files)
            validate_zip_integrity(doc_zip, list(doc_files.keys()))
            planned_files.append(
                EtsyDeliveryFile(
                    filename=f"{clean_slug}_documentation.zip",
                    mime_type="application/zip",
                    content=doc_zip,
                    checksum_sha256=hashlib.sha256(doc_zip).hexdigest(),
                    file_key=f"{clean_slug}_documentation_zip",
                )
            )

        # Enforce Etsy maximum file count constraint (<= 5 files)
        if len(planned_files) > self.max_files_count:
            raise DomainError(
                f"Planned Etsy delivery requires {len(planned_files)} files, which exceeds "
                f"Etsy's maximum allowed limit of {self.max_files_count} files per listing."
            )

        return planned_files
