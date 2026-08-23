"""Official USPTO Trademark Bulk Dataset Ingestion Engine.

Streams and ingests official USPTO Trademark bulk datasets (XML, CSV, JSON/JSONL)
into PostgreSQL with low memory overhead and idempotent batch upserts.

Supported source formats:
1. USPTO Daily & Annual XML (TrademarkBag / CaseFile XML schemas)
2. USPTO Bulk CSV exports
3. USPTO Bulk JSON / JSONL records
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
import xml.etree.ElementTree as ET
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Add backend directory to sys.path
backend_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_root))

from app.infrastructure.repositories.trademark import SqlTrademarkRepository


def _parse_xml_trademark_stream(filepath: Path) -> Generator[dict[str, Any], None, None]:
    """Memory-efficient streaming parser for USPTO XML datasets."""
    # Iterparse allows streaming large multi-gigabyte XML files without loading DOM into memory
    context = ET.iterparse(str(filepath), events=("end",))

    for event, elem in context:
        tag_lower = elem.tag.lower()
        if tag_lower in ("trademark", "casefile", "case-file", "case_file"):
            record = _extract_xml_record(elem)
            if record and record.get("mark_text"):
                yield record
            elem.clear()


def _extract_xml_record(elem: ET.Element) -> dict[str, Any] | None:
    """Extract trademark fields from XML element."""
    mark_text = None
    serial_number = None
    registration_number = None
    status_code = None
    status_text = "REGISTERED"
    is_live = True
    classes: list[str] = []
    goods_services: list[str] = []
    owner_name = None
    filing_date = None
    registration_date = None

    for child in elem.iter():
        t = child.tag.lower()
        val = (child.text or "").strip()
        if not val:
            continue

        if t in (
            "wordmark",
            "marktext",
            "markliteraltext",
            "mark-literal-text",
            "markidentification",
            "mark-identification",
        ):
            if not mark_text:
                mark_text = val
        elif t in ("serialnumber", "serial-number", "serial_number", "application-number"):
            if not serial_number:
                serial_number = val
        elif t in ("registrationnumber", "registration-number", "registration_number"):
            if not registration_number:
                registration_number = val
        elif t in ("statuscode", "status-code"):
            status_code = val
        elif t in (
            "statusdesc",
            "statusdescription",
            "status-description",
            "statusdescriptiontext",
        ):
            status_text = val
        elif t in ("livedeadindicator", "live-dead-indicator", "live_dead_indicator"):
            is_live = "LIVE" in val.upper() or val.upper() == "L"
        elif t in (
            "classcode",
            "class-code",
            "internationalclassnumber",
            "international-class-number",
            "international-code",
        ):
            clean_cls = val.zfill(3)
            if clean_cls not in classes:
                classes.append(clean_cls)
        elif t in (
            "goodsdescription",
            "goods-description",
            "statementtext",
            "statement-text",
            "goods-and-services-description",
        ):
            if val not in goods_services:
                goods_services.append(val)
        elif t in ("partyname", "party-name", "ownername", "owner-name", "organizationname"):
            if not owner_name:
                owner_name = val
        elif t in ("filingdate", "filing-date"):
            if not filing_date:
                filing_date = val
        elif t in ("registrationdate", "registration-date"):
            if not registration_date:
                registration_date = val

    if not mark_text:
        return None

    return {
        "mark_text": mark_text,
        "serial_number": serial_number,
        "registration_number": registration_number,
        "status_code": status_code,
        "status_text": status_text,
        "is_live": is_live,
        "classes": classes,
        "goods_services": "; ".join(goods_services) if goods_services else None,
        "owner_name": owner_name,
        "filing_date": filing_date,
        "registration_date": registration_date,
    }


def _parse_csv_trademark_stream(filepath: Path) -> Generator[dict[str, Any], None, None]:
    """Streaming parser for USPTO CSV datasets."""
    with open(filepath, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            mark_text = (
                row.get("mark_text")
                or row.get("mark")
                or row.get("wordmark")
                or row.get("mark_literal_text")
            )
            if not mark_text or not mark_text.strip():
                continue

            classes_raw = row.get("classes") or row.get("international_classes") or ""
            classes_list: list[str] = []
            if classes_raw:
                try:
                    parsed = json.loads(classes_raw)
                    if isinstance(parsed, list):
                        classes_list = [str(c).strip().zfill(3) for c in parsed]
                except Exception:
                    classes_list = [c.strip().zfill(3) for c in classes_raw.split(",") if c.strip()]

            live_val = str(row.get("is_live") or row.get("live_dead_indicator") or "TRUE").upper()
            is_live = live_val in ("TRUE", "LIVE", "1", "YES", "L")

            yield {
                "mark_text": mark_text.strip(),
                "serial_number": row.get("serial_number") or row.get("serial"),
                "registration_number": row.get("registration_number") or row.get("registration"),
                "status_code": row.get("status_code"),
                "status_text": row.get("status_text") or row.get("status") or "REGISTERED",
                "is_live": is_live,
                "classes": classes_list,
                "goods_services": row.get("goods_services") or row.get("goods_and_services"),
                "owner_name": row.get("owner_name") or row.get("owner"),
                "filing_date": row.get("filing_date"),
                "registration_date": row.get("registration_date"),
            }


def _parse_json_trademark_stream(filepath: Path) -> Generator[dict[str, Any], None, None]:
    """Streaming parser for USPTO JSON / JSONL datasets."""
    with open(filepath, encoding="utf-8", errors="replace") as f:
        first_char = f.read(1)
        f.seek(0)
        if first_char == "[":
            # JSON array
            data = json.load(f)
            for item in data:
                mark_text = (
                    item.get("mark_text")
                    or item.get("mark")
                    or item.get("markLiteralText")
                    or item.get("wordmark")
                )
                if mark_text:
                    classes_raw = item.get("classes") or item.get("internationalClassCodes") or []
                    classes = (
                        [str(c).zfill(3) for c in classes_raw]
                        if isinstance(classes_raw, list)
                        else []
                    )
                    live_val = str(
                        item.get("is_live") or item.get("liveDeadIndicator") or "LIVE"
                    ).upper()
                    is_live = live_val in ("TRUE", "LIVE", "1", "L")
                    yield {
                        "mark_text": str(mark_text).strip(),
                        "serial_number": str(
                            item.get("serial_number") or item.get("serialNumber") or ""
                        )
                        or None,
                        "registration_number": str(
                            item.get("registration_number") or item.get("registrationNumber") or ""
                        )
                        or None,
                        "status_code": str(item.get("status_code") or item.get("statusCode") or "")
                        or None,
                        "status_text": str(
                            item.get("status_text")
                            or item.get("status")
                            or item.get("statusDesc")
                            or "REGISTERED"
                        ),
                        "is_live": is_live,
                        "classes": classes,
                        "goods_services": item.get("goods_services")
                        or item.get("goodsAndServicesDescriptionText"),
                        "owner_name": item.get("owner_name")
                        or item.get("owner")
                        or item.get("ownerName"),
                        "filing_date": str(item.get("filing_date") or item.get("filingDate") or "")
                        or None,
                        "registration_date": str(
                            item.get("registration_date") or item.get("registrationDate") or ""
                        )
                        or None,
                    }
        else:
            # JSONL format (line by line)
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    item = json.loads(line_str)
                    mark_text = (
                        item.get("mark_text")
                        or item.get("mark")
                        or item.get("markLiteralText")
                        or item.get("wordmark")
                    )
                    if mark_text:
                        classes_raw = (
                            item.get("classes") or item.get("internationalClassCodes") or []
                        )
                        classes = (
                            [str(c).zfill(3) for c in classes_raw]
                            if isinstance(classes_raw, list)
                            else []
                        )
                        live_val = str(
                            item.get("is_live") or item.get("liveDeadIndicator") or "LIVE"
                        ).upper()
                        is_live = live_val in ("TRUE", "LIVE", "1", "L")
                        yield {
                            "mark_text": str(mark_text).strip(),
                            "serial_number": str(
                                item.get("serial_number") or item.get("serialNumber") or ""
                            )
                            or None,
                            "registration_number": str(
                                item.get("registration_number")
                                or item.get("registrationNumber")
                                or ""
                            )
                            or None,
                            "status_code": str(
                                item.get("status_code") or item.get("statusCode") or ""
                            )
                            or None,
                            "status_text": str(
                                item.get("status_text")
                                or item.get("status")
                                or item.get("statusDesc")
                                or "REGISTERED"
                            ),
                            "is_live": is_live,
                            "classes": classes,
                            "goods_services": item.get("goods_services")
                            or item.get("goodsAndServicesDescriptionText"),
                            "owner_name": item.get("owner_name")
                            or item.get("owner")
                            or item.get("ownerName"),
                            "filing_date": str(
                                item.get("filing_date") or item.get("filingDate") or ""
                            )
                            or None,
                            "registration_date": str(
                                item.get("registration_date") or item.get("registrationDate") or ""
                            )
                            or None,
                        }
                except Exception:
                    continue


async def ingest_file(
    filepath: Path,
    db_url: str,
    mode: str = "incremental",
    batch_size: int = 1000,
    source_updated_at: datetime | None = None,
) -> dict[str, int]:
    """Ingest a bulk file into PostgreSQL."""
    if not filepath.exists():
        print(f"❌ File not found: {filepath}")
        return {"inserted": 0, "updated": 0, "skipped": 0, "failed": 0}

    print(f"📦 Starting USPTO bulk ingestion [{mode.upper()}] from: {filepath.name}")
    suffix = filepath.suffix.lower()

    if suffix in (".xml", ".zip"):
        record_stream = _parse_xml_trademark_stream(filepath)
    elif suffix in (".csv", ".tsv"):
        record_stream = _parse_csv_trademark_stream(filepath)
    elif suffix in (".json", ".jsonl"):
        record_stream = _parse_json_trademark_stream(filepath)
    else:
        print(f"❌ Unsupported file extension: {suffix}. Supported: .xml, .csv, .json, .jsonl")
        return {"inserted": 0, "updated": 0, "skipped": 0, "failed": 0}

    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    source_date = source_updated_at or datetime.now(UTC)
    source_file_name = filepath.name

    total_inserted = 0
    total_updated = 0
    total_failed = 0
    total_processed = 0

    batch: list[dict[str, Any]] = []

    async with session_factory() as session:
        repo = SqlTrademarkRepository(session)

        for rec in record_stream:
            rec["source_file"] = source_file_name
            rec["source_updated_at"] = source_date
            batch.append(rec)
            total_processed += 1

            if len(batch) >= batch_size:
                counts = await repo.bulk_upsert(batch)
                await session.commit()
                total_inserted += counts["inserted"]
                total_updated += counts["updated"]
                total_failed += counts["failed"]
                batch.clear()
                print(
                    f"  Processed {total_processed:,} records (Inserted: {total_inserted:,}, Updated: {total_updated:,})..."
                )

        if batch:
            counts = await repo.bulk_upsert(batch)
            await session.commit()
            total_inserted += counts["inserted"]
            total_updated += counts["updated"]
            total_failed += counts["failed"]

    await engine.dispose()

    print("\n" + "=" * 50)
    print("🎯 USPTO Bulk Ingestion Completed")
    print(f"  • Source File:      {source_file_name}")
    print(f"  • Total Processed:  {total_processed:,}")
    print(f"  • Newly Inserted:   {total_inserted:,}")
    print(f"  • Records Updated:  {total_updated:,}")
    print(f"  • Records Failed:   {total_failed:,}")
    print("=" * 50)

    return {
        "processed": total_processed,
        "inserted": total_inserted,
        "updated": total_updated,
        "failed": total_failed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest official USPTO bulk trademark datasets into PostgreSQL."
    )
    parser.add_argument("filepath", type=Path, help="Path to bulk XML, CSV, or JSON file")
    parser.add_argument(
        "--mode", choices=["full", "incremental"], default="incremental", help="Ingestion mode"
    )
    parser.add_argument(
        "--batch-size", type=int, default=1000, help="Batch size for database upserts"
    )
    parser.add_argument("--db-url", type=str, default=None, help="PostgreSQL connection string")
    parser.add_argument(
        "--source-date",
        type=str,
        default=None,
        help="ISO date of dataset release (e.g. 2026-08-18)",
    )

    args = parser.parse_args()

    db_url = args.db_url or os.getenv("DATABASE_URL")
    if not db_url:
        db_url = "postgresql+asyncpg://etsy:etsy_local_password@localhost:55432/etsy_automation"

    source_date = None
    if args.source_date:
        try:
            source_date = datetime.fromisoformat(args.source_date)
        except Exception:
            pass

    asyncio.run(
        ingest_file(
            filepath=args.filepath,
            db_url=db_url,
            mode=args.mode,
            batch_size=args.batch_size,
            source_updated_at=source_date,
        )
    )


if __name__ == "__main__":
    main()
