"""NSW Property Sales Information loader.

Data: https://data.nsw.gov.au/data/dataset/nsw-property-sales-information
Format: Quarterly bulk ZIP/CSV downloads.
Drop extracted CSV files into: data/nsw_sales/*.csv

Column format (varies slightly by year):
  District Code, District Name, Property Id, Sale Counter, Download Date,
  Property Name, Unit Number, Street Number, Street Name, Street Type,
  Street Suffix, Suburb, Postcode, Area, Area Type, Contract Date,
  Settlement Date, Purchase Price, Zoning, Nature of Property,
  Primary Purpose, Strata Lot Number, Component Code, Sale Code, Interest of Sale,
  Dealing Number
"""

import csv
import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


def _parse_price(value: str) -> Optional[int]:
    if not value:
        return None
    cleaned = re.sub(r"[^0-9.]", "", value)
    try:
        return int(float(cleaned) * 100)
    except (ValueError, TypeError):
        return None


def _parse_date(value: str) -> Optional[date]:
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d%m%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


def load_nsw_sales_csv(file_path: str) -> list[dict]:
    """
    Parse one NSW Property Sales CSV. Returns list of dicts:
    {address_street, address_suburb, address_postcode, sold_price_cents, sold_at, land_size_sqm, raw}
    """
    records = []
    with open(file_path, newline="", encoding="utf-8-sig") as f:
        # Some NSW sales files have a 2-line header; skip non-data rows
        content = f.read()

    lines = content.splitlines()
    # Find the header row (contains 'Suburb' or 'SUBURB')
    header_idx = 0
    for i, line in enumerate(lines):
        if "suburb" in line.lower() and "price" in line.lower():
            header_idx = i
            break

    import io
    reader = csv.DictReader(io.StringIO("\n".join(lines[header_idx:])))
    headers = [h.strip() for h in (reader.fieldnames or [])]

    def _col(candidates: list[str]) -> Optional[str]:
        lower_h = {h.lower(): h for h in headers}
        for c in candidates:
            if c.lower() in lower_h:
                return lower_h[c.lower()]
        return None

    suburb_col = _col(["Suburb", "SUBURB"])
    postcode_col = _col(["Postcode", "POST_CODE"])
    street_no_col = _col(["Street Number", "STREET_NUMBER"])
    street_name_col = _col(["Street Name", "STREET_NAME"])
    street_type_col = _col(["Street Type", "STREET_TYPE"])
    price_col = _col(["Purchase Price", "PURCHASE_PRICE", "Sale Price"])
    contract_date_col = _col(["Contract Date", "CONTRACT_DATE"])
    area_col = _col(["Area", "AREA"])
    area_type_col = _col(["Area Type", "AREA_TYPE"])

    for row in reader:
        price = _parse_price(row.get(price_col, "") if price_col else "")
        if not price or price <= 0:
            continue

        sold_date = _parse_date(row.get(contract_date_col, "") if contract_date_col else "")

        # Build street address
        parts = [
            row.get(street_no_col, "") if street_no_col else "",
            row.get(street_name_col, "") if street_name_col else "",
            row.get(street_type_col, "") if street_type_col else "",
        ]
        street = " ".join(p.strip() for p in parts if p.strip())

        # Land size — only if area_type is "M" (square metres)
        land_sqm = None
        if area_col and area_type_col:
            area_type = row.get(area_type_col, "").strip().upper()
            if area_type == "M":
                try:
                    land_sqm = float(row.get(area_col, "").strip())
                except (ValueError, TypeError):
                    pass

        suburb = row.get(suburb_col, "").strip().title() if suburb_col else None
        postcode = row.get(postcode_col, "").strip()[:4] if postcode_col else None

        records.append({
            "address_street": street or None,
            "address_suburb": suburb,
            "address_postcode": postcode,
            "sold_price_cents": price,
            "sold_at": sold_date,
            "land_size_sqm": land_sqm,
        })

    logger.info("NSW Sales CSV parsed", file=file_path, records=len(records))
    return records


def load_all_nsw_sales(data_dir: Optional[str] = None) -> list[dict]:
    sales_dir = Path(data_dir or settings.data_dir) / "nsw_sales"
    all_records = []
    for csv_file in sorted(sales_dir.glob("*.csv")):
        try:
            all_records.extend(load_nsw_sales_csv(str(csv_file)))
        except Exception as e:
            logger.error("Failed to parse NSW Sales CSV", file=str(csv_file), error=str(e))
    return all_records
