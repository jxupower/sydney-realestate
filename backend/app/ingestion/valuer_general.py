"""NSW Valuer General bulk CSV loader.

Data: https://data.nsw.gov.au/data/dataset/http-www-valuergeneral-nsw-gov-au-land-value-summaries-lv-php
Format: CSV per LGA, columns vary slightly by year.
Drop CSV files into: data/valuer_general/*.csv
"""

import csv
import os
from datetime import date
from pathlib import Path
from typing import Optional

import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

# Known column name variations across different VG CSV exports
_STREET_COLS = ["Property Address", "ADDRESS", "PROPERTY_ADDRESS"]
_SUBURB_COLS = ["Suburb Name", "SUBURB", "SUBURB_NAME"]
_POSTCODE_COLS = ["Postcode", "POST_CODE"]
_LGA_COLS = ["District Name", "LGA", "DISTRICT"]
_LOT_COLS = ["Lot/Plan", "LOT_PLAN", "LOTPLAN"]
_LAND_VALUE_COLS = ["Land Value", "LAND_VALUE"]
_CAPITAL_VALUE_COLS = ["Capital Value", "CAPITAL_VALUE", "Capital Improved Value"]
_BASE_DATE_COLS = ["Base Date", "BASE_DATE"]


def _find_col(headers: list[str], candidates: list[str]) -> Optional[str]:
    for c in candidates:
        if c in headers:
            return c
    # Case-insensitive fallback
    lower_map = {h.lower(): h for h in headers}
    for c in candidates:
        if c.lower() in lower_map:
            return lower_map[c.lower()]
    return None


def _parse_money(value: str) -> Optional[int]:
    """Parse dollar string like '$1,234,567' → int cents."""
    if not value:
        return None
    cleaned = value.strip().lstrip("$").replace(",", "").replace(" ", "")
    try:
        return int(float(cleaned) * 100)
    except (ValueError, TypeError):
        return None


def _parse_date(value: str) -> Optional[date]:
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return date.fromisoformat(value) if fmt == "%Y-%m-%d" else _strpdate(value, fmt)
        except (ValueError, AttributeError):
            continue
    return None


def _strpdate(value: str, fmt: str) -> date:
    from datetime import datetime
    return datetime.strptime(value, fmt).date()


def load_vg_csv(file_path: str) -> list[dict]:
    """Parse a single VG CSV file. Returns list of dicts ready for DB upsert."""
    records = []
    with open(file_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []

        street_col = _find_col(headers, _STREET_COLS)
        suburb_col = _find_col(headers, _SUBURB_COLS)
        postcode_col = _find_col(headers, _POSTCODE_COLS)
        lga_col = _find_col(headers, _LGA_COLS)
        lot_col = _find_col(headers, _LOT_COLS)
        land_col = _find_col(headers, _LAND_VALUE_COLS)
        capital_col = _find_col(headers, _CAPITAL_VALUE_COLS)
        date_col = _find_col(headers, _BASE_DATE_COLS)

        for row in reader:
            land_cents = _parse_money(row.get(land_col, "") if land_col else "")
            capital_cents = _parse_money(row.get(capital_col, "") if capital_col else "")
            improvement_cents = (
                capital_cents - land_cents
                if capital_cents is not None and land_cents is not None
                else None
            )

            records.append({
                "lot_plan": row.get(lot_col, "").strip() if lot_col else None,
                "address_street": row.get(street_col, "").strip() if street_col else None,
                "address_suburb": row.get(suburb_col, "").strip().title() if suburb_col else None,
                "address_postcode": row.get(postcode_col, "").strip()[:4] if postcode_col else None,
                "lga": row.get(lga_col, "").strip() if lga_col else None,
                "land_value_cents": land_cents,
                "capital_value_cents": capital_cents,
                "improvement_value_cents": improvement_cents,
                "base_date": _parse_date(row.get(date_col, "").strip() if date_col else ""),
            })

    logger.info("VG CSV parsed", file=file_path, records=len(records))
    return records


def load_all_vg_csvs(data_dir: Optional[str] = None) -> list[dict]:
    """Load all CSV files from data/valuer_general/."""
    vg_dir = Path(data_dir or settings.data_dir) / "valuer_general"
    all_records = []
    for csv_file in sorted(vg_dir.glob("*.csv")):
        try:
            all_records.extend(load_vg_csv(str(csv_file)))
        except Exception as e:
            logger.error("Failed to parse VG CSV", file=str(csv_file), error=str(e))
    return all_records
