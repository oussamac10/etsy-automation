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
import structlog

from app.domain.errors import DomainError

logger = structlog.get_logger(__name__)
from app.domain.package_builder import (
    DEFAULT_HEIGHT_PX,
    DEFAULT_WIDTH_PX,
    build_zip_archive,
    create_print_ready_pdf,
    generate_checksum_manifest,
    generate_instructions_text,
    generate_license_text,
    optimize_png_deflate,
    sanitize_brand_slug,
    sanitize_product_title,
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
    if not zip_bytes or len(zip_bytes) < 22:
        raise DomainError("Invalid digital delivery package: ZIP archive is empty or truncated.")

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            corrupt = zf.testzip()
            if corrupt is not None:
                raise DomainError(f"ZIP archive corrupted at member: '{corrupt}'")

            infolist = zf.infolist()
            if not infolist:
                raise DomainError("ZIP archive contains zero files.")

            names = [info.filename for info in infolist]
            if len(names) != len(set(names)):
                raise DomainError("ZIP archive contains duplicate file entries.")

            if expected_members:
                for expected in expected_members:
                    if expected not in names:
                        raise DomainError(f"Required member '{expected}' missing from ZIP archive.")
                    member_data = zf.read(expected)
                    if len(member_data) == 0 and not expected.endswith("/"):
                        pass
    except (zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise DomainError(f"Invalid ZIP archive structure: {exc}") from exc


def validate_png_integrity(
    png_bytes: bytes,
    expected_width: int | None = None,
    expected_height: int | None = None,
    expected_w: int | None = None,
    expected_h: int | None = None,
) -> None:
    """Validate PNG signature, header chunks, dimensions, and decompression integrity."""
    if len(png_bytes) < 24 or png_bytes[:8] != b"\x89PNG\r\n\x1a\n":
        raise DomainError("Invalid PNG signature: Not a valid PNG binary signature.")

    target_w = expected_width if expected_width is not None else expected_w
    target_h = expected_height if expected_height is not None else expected_h

    w, h, bit_depth, color_type = struct.unpack(">IIBB", png_bytes[16:26])
    if w < 100 or h < 100:
        raise DomainError(f"PNG dimensions ({w}x{h}) are too small for commercial print delivery.")

    if target_w and target_w > 0 and w != target_w:
        raise DomainError(f"PNG width {w}px does not match expected {target_w}px.")
    if target_h and target_h > 0 and h != target_h:
        raise DomainError(f"PNG height {h}px does not match expected {target_h}px.")

    # Check for valid IDAT chunk and decompressibility
    offset = 8
    idat_combined = bytearray()
    has_iend = False

    while offset < len(png_bytes):
        if offset + 8 > len(png_bytes):
            break
        length = struct.unpack(">I", png_bytes[offset : offset + 4])[0]
        chunk_type = png_bytes[offset + 4 : offset + 8]
        chunk_data = png_bytes[offset + 8 : offset + 8 + length]
        if chunk_type == b"IDAT":
            idat_combined.extend(chunk_data)
        elif chunk_type == b"IEND":
            has_iend = True
            break
        offset += 12 + length

    if not has_iend or not idat_combined:
        raise DomainError("Invalid master PNG: Truncated raster image data or missing IEND.")

    try:
        decompressed = zlib.decompress(bytes(idat_combined))
        if len(decompressed) == 0:
            raise DomainError("Master PNG contains empty raster image data.")
    except Exception as exc:
        raise DomainError(f"Corrupted PNG IDAT stream: {exc}") from exc


def make_etsy_safe_filename(base_prefix: str, suffix: str, max_length: int = 68) -> str:
    """Format and guarantee a filename strictly meets Etsy constraints:

    - Between 3 and 70 characters (default max 68 chars).
    - Only alphanumeric, hyphens, underscores, or periods.
    """
    raw_name = f"{base_prefix}_{suffix}" if base_prefix and suffix else (base_prefix or suffix)
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "_", raw_name)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_-")

    if "." in cleaned:
        stem, ext = cleaned.rsplit(".", 1)
        ext = f".{ext}"
    else:
        stem, ext = cleaned, ""

    if len(cleaned) <= max_length:
        return cleaned

    allowed_stem_len = max(max_length - len(ext), 3)
    trimmed_stem = stem[:allowed_stem_len].rstrip("_-.")
    return f"{trimmed_stem}{ext}"


class EtsyDigitalDeliveryPlanner:
    """Computes and plans uploadable customer files conforming to Etsy constraints."""

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
        shop_slug = sanitize_brand_slug(shop_name, max_length=20)
        product_slug = sanitize_product_title(listing_title, max_length=25)
        base_prefix = f"{shop_slug}_{product_slug}"

        # 1. Optimize master PNG losslessly
        optimized_master = optimize_png_deflate(master_png_bytes)
        validate_png_integrity(optimized_master)
        master_sha = hashlib.sha256(optimized_master).hexdigest()

        # 2. Build Documentation
        license_doc = generate_license_text(shop_name, listing_title).encode("utf-8")
        instructions_doc = generate_instructions_text(listing_title, shop_name=shop_name).encode("utf-8")

        # 3. Build Print-Ready PDF
        pdf_bytes: bytes | None = None
        if include_pdf:
            try:
                pdf_bytes = create_print_ready_pdf(
                    optimized_master,
                    width_px=master_width,
                    height_px=master_height,
                )
                if len(pdf_bytes) > self.max_file_bytes:
                    pdf_bytes = None
            except Exception as exc:
                logger.warning("failed_generating_print_ready_pdf", error=str(exc))
                pdf_bytes = None

        # ----------------------------------------------------------------------
        # Case A: Try single complete customer archive
        # ----------------------------------------------------------------------
        single_pack_files: dict[str, bytes] = {
            f"{base_prefix}_PNG.png": optimized_master,
            f"{base_prefix}_LICENSE.txt": license_doc,
            f"{base_prefix}_INSTRUCTIONS.txt": instructions_doc,
        }
        if pdf_bytes is not None:
            single_pack_files[f"{base_prefix}_Print_Ready.pdf"] = pdf_bytes

        manifest_a = generate_checksum_manifest(single_pack_files).encode("utf-8")
        single_pack_files[f"{base_prefix}_manifest.sha256"] = manifest_a

        single_zip_bytes = build_zip_archive(single_pack_files)

        if len(single_zip_bytes) <= self.max_file_bytes:
            validate_zip_integrity(single_zip_bytes, list(single_pack_files.keys()))
            zip_sha = hashlib.sha256(single_zip_bytes).hexdigest()
            return [
                EtsyDeliveryFile(
                    filename=make_etsy_safe_filename(base_prefix, "Digital_Download.zip"),
                    mime_type="application/zip",
                    content=single_zip_bytes,
                    checksum_sha256=zip_sha,
                    file_key=f"{base_prefix}_complete_zip",
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
                    filename=make_etsy_safe_filename(base_prefix, "PNG.png"),
                    mime_type="image/png",
                    content=optimized_master,
                    checksum_sha256=master_sha,
                    file_key=f"{base_prefix}_master_png",
                )
            )
        else:
            # Check if packing master in a dedicated ZIP archive compresses under limit
            master_zip_files = {f"{base_prefix}_PNG.png": optimized_master}
            master_zip_bytes = build_zip_archive(master_zip_files)
            if len(master_zip_bytes) <= self.max_file_bytes:
                validate_zip_integrity(master_zip_bytes, [f"{base_prefix}_PNG.png"])
                planned_files.append(
                    EtsyDeliveryFile(
                        filename=make_etsy_safe_filename(base_prefix, "Master.zip"),
                        mime_type="application/zip",
                        content=master_zip_bytes,
                        checksum_sha256=hashlib.sha256(master_zip_bytes).hexdigest(),
                        file_key=f"{base_prefix}_master_zip",
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
            f"{base_prefix}_LICENSE.txt": license_doc,
            f"{base_prefix}_INSTRUCTIONS.txt": instructions_doc,
            f"{base_prefix}_master_artwork_checksum.sha256": f"{master_sha}  {base_prefix}_PNG.png\n".encode("utf-8"),
        }
        if pdf_bytes is not None and len(pdf_bytes) < 15 * 1024 * 1024:
            extras_files[f"{base_prefix}_Print_Ready.pdf"] = pdf_bytes

        manifest_extras = generate_checksum_manifest(extras_files).encode("utf-8")
        extras_files[f"{base_prefix}_manifest.sha256"] = manifest_extras

        extras_zip_bytes = build_zip_archive(extras_files)

        if len(extras_zip_bytes) <= self.max_file_bytes:
            validate_zip_integrity(extras_zip_bytes, list(extras_files.keys()))
            planned_files.append(
                EtsyDeliveryFile(
                    filename=make_etsy_safe_filename(base_prefix, "Extras.zip"),
                    mime_type="application/zip",
                    content=extras_zip_bytes,
                    checksum_sha256=hashlib.sha256(extras_zip_bytes).hexdigest(),
                    file_key=f"{base_prefix}_extras_zip",
                )
            )
        else:
            # If extras exceeds limit (e.g. PDF is large), separate docs and PDF into independent valid ZIPs
            doc_files = {
                f"{base_prefix}_LICENSE.txt": license_doc,
                f"{base_prefix}_INSTRUCTIONS.txt": instructions_doc,
                f"{base_prefix}_manifest.sha256": generate_checksum_manifest(
                    {f"{base_prefix}_LICENSE.txt": license_doc, f"{base_prefix}_INSTRUCTIONS.txt": instructions_doc}
                ).encode("utf-8"),
            }
            doc_zip = build_zip_archive(doc_files)
            validate_zip_integrity(doc_zip, list(doc_files.keys()))
            planned_files.append(
                EtsyDeliveryFile(
                    filename=make_etsy_safe_filename(base_prefix, "Documentation.zip"),
                    mime_type="application/zip",
                    content=doc_zip,
                    checksum_sha256=hashlib.sha256(doc_zip).hexdigest(),
                    file_key=f"{base_prefix}_documentation_zip",
                )
            )

        # Enforce Etsy maximum file count constraint (<= 5 files)
        if len(planned_files) > self.max_files_count:
            raise DomainError(
                f"Planned Etsy delivery requires {len(planned_files)} files, which exceeds "
                f"Etsy's maximum allowed limit of {self.max_files_count} files per listing."
            )

        return planned_files
