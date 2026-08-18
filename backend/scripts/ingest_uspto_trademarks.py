"""CLI script to ingest official USPTO bulk trademark dataset files into PostgreSQL."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys

# Ensure backend root is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.infrastructure.repositories.trademark import SqlTrademarkRepository
from app.settings import Settings


async def ingest_file(file_path: str, source_label: str = "USPTO_BULK") -> None:
    if not os.path.exists(file_path):
        print(f"❌ Error: File not found: {file_path}")
        return

    records: list[dict[str, object]] = []

    if file_path.endswith(".json"):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            items = data if isinstance(data, list) else data.get("cases", data.get("records", []))
            for item in items:
                mark_text = item.get("mark_text") or item.get("markLiteralText") or item.get("wordmark")
                if not mark_text:
                    continue
                is_live_val = item.get("is_live")
                if is_live_val is None:
                    status_text = str(item.get("status", item.get("liveDeadIndicator", ""))).upper()
                    is_live_val = "LIVE" in status_text or "REGISTERED" in status_text or "PENDING" in status_text

                classes = item.get("classes") or item.get("internationalClassCodes") or []
                if isinstance(classes, str):
                    classes = [c.strip() for c in classes.split(",") if c.strip()]

                records.append({
                    "mark_text": mark_text,
                    "serial_number": str(item.get("serial_number") or item.get("serialNumber") or ""),
                    "registration_number": str(item.get("registration_number") or item.get("registrationNumber") or ""),
                    "status": str(item.get("status") or item.get("statusDescriptionText") or "REGISTERED"),
                    "is_live": bool(is_live_val),
                    "classes": list(classes),
                    "goods_services": item.get("goods_services") or item.get("goodsAndServicesDescriptionText"),
                    "owner": item.get("owner") or item.get("ownerName"),
                    "filing_date": item.get("filing_date") or item.get("filingDate"),
                    "registration_date": item.get("registration_date") or item.get("registrationDate"),
                    "source": source_label,
                })
    elif file_path.endswith(".csv"):
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                mark_text = row.get("mark_text") or row.get("mark") or row.get("wordmark")
                if not mark_text:
                    continue
                status = row.get("status", "REGISTERED").upper()
                is_live = "LIVE" in status or "REGISTERED" in status or row.get("is_live", "").lower() in ("true", "1", "yes")
                classes_str = row.get("classes", row.get("international_classes", ""))
                classes = [c.strip() for c in classes_str.split(",") if c.strip()]
                records.append({
                    "mark_text": mark_text,
                    "serial_number": row.get("serial_number"),
                    "registration_number": row.get("registration_number"),
                    "status": status,
                    "is_live": is_live,
                    "classes": classes,
                    "goods_services": row.get("goods_services"),
                    "owner": row.get("owner"),
                    "filing_date": row.get("filing_date"),
                    "registration_date": row.get("registration_date"),
                    "source": source_label,
                })

    print(f"📖 Loaded {len(records)} records from {file_path}. Ingesting into PostgreSQL...")
    settings = Settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    batch_size = 1000
    total_inserted = 0
    async with session_factory() as session:
        repo = SqlTrademarkRepository(session)
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            inserted = await repo.bulk_upsert(batch)
            total_inserted += inserted
            await session.commit()
            print(f"  Inserted {total_inserted}/{len(records)} records...")

    await engine.dispose()
    print(f"✅ Ingestion complete! Total records upserted: {total_inserted}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest USPTO trademark datasets into PostgreSQL")
    parser.add_argument("file_path", help="Path to JSON or CSV trademark file")
    parser.add_argument("--source", default="USPTO_BULK", help="Source dataset label")
    args = parser.parse_args()
    asyncio.run(ingest_file(args.file_path, args.source))
