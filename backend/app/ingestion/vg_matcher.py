"""Fuzzy VG record → property matching.

Uses rapidfuzz token_set_ratio to link valuer_general_records rows
to properties rows by normalised address similarity (threshold >= 85).

Matching is one-to-one: once a VG record is linked it won't be re-matched
unless its property_id is manually cleared.

CLI usage:
    python -m app.ingestion.vg_matcher
    python -m app.ingestion.vg_matcher --threshold 90
"""

from __future__ import annotations

import argparse
import asyncio

import structlog
from rapidfuzz import fuzz
from sqlalchemy import select, update

from app.db.models.property import Property
from app.db.models.valuer_general import ValuerGeneralRecord
from app.db.session import AsyncSessionLocal
from app.utils.logger import configure_logging

logger = structlog.get_logger(__name__)

DEFAULT_THRESHOLD = 85   # rapidfuzz score 0–100; 85 = "strong" fuzzy match
BATCH_SIZE = 500          # rows to commit per transaction


def _normalise(street: str | None, suburb: str | None) -> str:
    """Lowercase + strip punctuation for fuzzy comparison."""
    parts: list[str] = []
    if street:
        # Remove common abbreviations that vary between sources
        s = street.lower().strip()
        s = s.replace(" st ", " street ").replace(" rd ", " road ").replace(" ave ", " avenue ")
        parts.append(s)
    if suburb:
        parts.append(suburb.lower().strip())
    return " ".join(parts)


async def run_vg_matching(threshold: int = DEFAULT_THRESHOLD) -> dict:
    """Link unmatched VG records to properties using fuzzy address matching.

    Returns a dict with 'matched' and 'unmatched' counts.
    """
    configure_logging()

    async with AsyncSessionLocal() as db:
        # Load VG records that have no property_id yet
        vg_result = await db.execute(
            select(ValuerGeneralRecord).where(ValuerGeneralRecord.property_id.is_(None))
        )
        vg_records: list[ValuerGeneralRecord] = list(vg_result.scalars().all())
        logger.info("Loaded unmatched VG records", count=len(vg_records))

        if not vg_records:
            return {"matched": 0, "unmatched": 0}

        # Load property id + address columns (lightweight — no ORM overhead)
        prop_result = await db.execute(
            select(Property.id, Property.address_street, Property.address_suburb)
        )
        raw_props = prop_result.all()
        logger.info("Loaded properties for matching", count=len(raw_props))

        # Build normalised address list for bulk comparison
        prop_index: list[tuple[int, str]] = [
            (row.id, _normalise(row.address_street, row.address_suburb))
            for row in raw_props
            if row.address_street or row.address_suburb
        ]

        matched = 0
        unmatched = 0

        for i, vg in enumerate(vg_records):
            vg_addr = _normalise(vg.address_street, vg.address_suburb)
            if not vg_addr.strip():
                unmatched += 1
                continue

            best_score = 0
            best_id: int | None = None

            for prop_id, prop_addr in prop_index:
                # token_set_ratio handles word-order differences + abbreviations
                score = fuzz.token_set_ratio(vg_addr, prop_addr)
                if score > best_score:
                    best_score = score
                    best_id = prop_id

            if best_score >= threshold and best_id is not None:
                await db.execute(
                    update(ValuerGeneralRecord)
                    .where(ValuerGeneralRecord.id == vg.id)
                    .values(property_id=best_id)
                )
                matched += 1
                logger.debug(
                    "Matched VG record",
                    vg_id=vg.id,
                    property_id=best_id,
                    score=best_score,
                    vg_addr=vg_addr,
                )
            else:
                unmatched += 1

            if (i + 1) % BATCH_SIZE == 0:
                await db.commit()
                logger.info(
                    "VG matching progress",
                    processed=i + 1,
                    total=len(vg_records),
                    matched=matched,
                    threshold=threshold,
                )

        await db.commit()

        match_rate = f"{matched / len(vg_records) * 100:.1f}%" if vg_records else "n/a"
        logger.info(
            "VG matching complete",
            matched=matched,
            unmatched=unmatched,
            match_rate=match_rate,
            threshold=threshold,
        )
        return {"matched": matched, "unmatched": unmatched}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fuzzy VG record → property matching")
    parser.add_argument(
        "--threshold",
        type=int,
        default=DEFAULT_THRESHOLD,
        help=f"rapidfuzz score threshold 0-100 (default: {DEFAULT_THRESHOLD})",
    )
    args = parser.parse_args()
    asyncio.run(run_vg_matching(threshold=args.threshold))
