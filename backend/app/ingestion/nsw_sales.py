"""NSW Property Sales Information loader.

Data source: https://www.valuergeneral.nsw.gov.au/design/bulk_psi_content/bulk_psi
Format: Weekly ZIP files per Local Government Area (LGA), each containing one or
        more .DAT files (semicolon-delimited, no header row, record-type prefixed).

Download and drop ZIP files directly into: data/nsw_sales/
The loader handles nested ZIPs automatically (common in the weekly downloads).

Record types in each .DAT file:
  A — file header (one per file)
  B — property sale record (one per transaction) ← we parse these
  C — legal description continuation (one or more per B record)
  D — owner details (suppressed in public bulk download)
  Z — file trailer

B record field positions (0-indexed after split on ";"):
  0  Record type = "B"
  1  District code
  2  Property id
  3  Sale counter
  4  Download date/time
  5  Property name
  6  Unit number
  7  House number
  8  Street name
  9  Locality (suburb)
  10 Postcode
  11 Area
  12 Area type  (M = sq metres, H = hectares)
  13 Contract date  (CCYYMMDD)
  14 Settlement date  (CCYYMMDD)
  15 Purchase price
  16 Zoning
  17 Nature of property  (V = Vacant, R = Residence, 3 = Other)
  18 Primary purpose
  19 Strata lot number   (non-empty → apartment)
  20 Component code
  21 Sale code
  22 % Interest of sale
  23 Dealing number

Legacy CSV files (older format, e.g. from data.nsw.gov.au) in data/nsw_sales/*.csv
are still supported for backwards compatibility.
"""

import io
import csv
import re
import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _parse_price(value: str) -> Optional[int]:
    """Return price in AUD cents, or None."""
    if not value:
        return None
    cleaned = re.sub(r"[^0-9.]", "", value.replace(",", ""))
    try:
        val = float(cleaned)
        return int(val * 100) if val > 0 else None
    except (ValueError, TypeError):
        return None


def _parse_date_ccyymmdd(value: str) -> Optional[date]:
    """Parse CCYYMMDD (the DAT format). Returns None on any failure."""
    v = value.strip()
    if len(v) == 8:
        try:
            return datetime.strptime(v, "%Y%m%d").date()
        except ValueError:
            pass
    return None


def _parse_date_any(value: str) -> Optional[date]:
    """Parse CSV-style dates as well as CCYYMMDD."""
    d = _parse_date_ccyymmdd(value)
    if d:
        return d
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


def _f(fields: list[str], idx: int) -> str:
    """Safe field accessor for DAT record fields."""
    try:
        return fields[idx].strip()
    except IndexError:
        return ""


# ---------------------------------------------------------------------------
# DAT parser — native NSW VG format
# ---------------------------------------------------------------------------

def _parse_dat_record(line: str) -> Optional[dict]:
    """
    Parse one 'B' record line from a .DAT file.
    Returns a normalised sale dict or None if the record should be skipped.
    """
    # Every record ends with a trailing semicolon; split produces an empty last element
    fields = line.rstrip("\n\r").split(";")

    if not fields or fields[0] != "B":
        return None

    price = _parse_price(_f(fields, 15))
    if not price:
        return None

    # Address: unit + house_number + street_name form the street address
    unit = _f(fields, 6)
    house_no = _f(fields, 7)
    street_name = _f(fields, 8).title()
    parts = [p for p in [unit, house_no, street_name] if p]
    street = " ".join(parts) or None

    # Area — only use when area_type == "M" (square metres)
    area_raw = _f(fields, 11)
    area_type = _f(fields, 12).upper()
    land_sqm: Optional[float] = None
    if area_type == "M" and area_raw:
        try:
            land_sqm = float(area_raw)
        except ValueError:
            pass

    suburb = _f(fields, 9).title() or None
    postcode = _f(fields, 10)[:4] or None
    sold_date = _parse_date_ccyymmdd(_f(fields, 13))
    is_strata = bool(_f(fields, 19))  # non-empty strata lot → apartment
    property_id = _f(fields, 2)
    sale_counter = _f(fields, 3)

    return {
        "address_street": street,
        "address_suburb": suburb,
        "address_postcode": postcode,
        "sold_price_cents": price,
        "sold_at": sold_date,
        "land_size_sqm": land_sqm,
        "strata": is_strata,
        # Keep a stable key for deduplication in coordinator
        "_source_key": f"{property_id}_{sale_counter}",
    }


def load_nsw_sales_dat(content: str, source_name: str = "") -> list[dict]:
    """Parse the text content of one .DAT file. Returns normalised sale dicts."""
    records = []
    for line in content.splitlines():
        rec = _parse_dat_record(line)
        if rec:
            records.append(rec)
    logger.info("NSW Sales DAT parsed", source=source_name, records=len(records))
    return records


# ---------------------------------------------------------------------------
# ZIP extractor — handles nested ZIPs (common in weekly bulk downloads)
# ---------------------------------------------------------------------------

def _extract_dat_files(zip_path: Path) -> list[tuple[str, str]]:
    """
    Recursively extract all .DAT file contents from a ZIP (and nested ZIPs).
    Returns list of (filename, text_content) tuples.
    """
    results: list[tuple[str, str]] = []

    def _read_zip(zf: zipfile.ZipFile, prefix: str = "") -> None:
        for info in zf.infolist():
            name_lower = info.filename.lower()
            if name_lower.endswith(".dat"):
                try:
                    raw = zf.read(info)
                    text = raw.decode("utf-8", errors="replace")
                    results.append((f"{prefix}/{info.filename}", text))
                except Exception as e:
                    logger.warning("Failed to read DAT from ZIP", file=info.filename, error=str(e))
            elif name_lower.endswith(".zip"):
                try:
                    inner_bytes = zf.read(info)
                    with zipfile.ZipFile(io.BytesIO(inner_bytes)) as inner_zf:
                        _read_zip(inner_zf, prefix=f"{prefix}/{info.filename}")
                except Exception as e:
                    logger.warning("Failed to open nested ZIP", file=info.filename, error=str(e))

    try:
        with zipfile.ZipFile(zip_path) as zf:
            _read_zip(zf, prefix=str(zip_path.name))
    except Exception as e:
        logger.error("Failed to open ZIP", file=str(zip_path), error=str(e))

    return results


def load_nsw_sales_zip(zip_path: Path) -> list[dict]:
    """Load all sales records from a .zip file (with nested ZIP support)."""
    records = []
    for name, content in _extract_dat_files(zip_path):
        records.extend(load_nsw_sales_dat(content, source_name=name))
    logger.info("NSW Sales ZIP loaded", file=str(zip_path), records=len(records))
    return records


# ---------------------------------------------------------------------------
# Legacy CSV parser (backwards compatibility)
# ---------------------------------------------------------------------------

def load_nsw_sales_csv(file_path: str) -> list[dict]:
    """
    Parse one NSW Property Sales CSV (older format from data.nsw.gov.au).
    Kept for backwards compatibility — prefer .zip/.dat files.
    """
    records = []
    with open(file_path, newline="", encoding="utf-8-sig") as f:
        content = f.read()

    lines = content.splitlines()
    header_idx = 0
    for i, line in enumerate(lines):
        if "suburb" in line.lower() and "price" in line.lower():
            header_idx = i
            break

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
    strata_col = _col(["Strata Lot Number", "STRATA_LOT_NUMBER"])

    for row in reader:
        price = _parse_price(row.get(price_col, "") if price_col else "")
        if not price or price <= 0:
            continue

        sold_date = _parse_date_any(row.get(contract_date_col, "") if contract_date_col else "")

        parts = [
            row.get(street_no_col, "") if street_no_col else "",
            row.get(street_name_col, "") if street_name_col else "",
            row.get(street_type_col, "") if street_type_col else "",
        ]
        street = " ".join(p.strip() for p in parts if p.strip())

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
        strata_val = row.get(strata_col, "").strip() if strata_col else ""
        is_strata = bool(strata_val and strata_val not in ("0", ""))

        records.append({
            "address_street": street or None,
            "address_suburb": suburb,
            "address_postcode": postcode,
            "sold_price_cents": price,
            "sold_at": sold_date,
            "land_size_sqm": land_sqm,
            "strata": is_strata,
        })

    logger.info("NSW Sales CSV parsed", file=file_path, records=len(records))
    return records


# ---------------------------------------------------------------------------
# Top-level loader — auto-detects .zip, .dat, .csv
# ---------------------------------------------------------------------------

def load_all_nsw_sales(data_dir: Optional[str] = None) -> list[dict]:
    """
    Load all NSW sales records from data/nsw_sales/.
    Supports: *.zip (preferred — native bulk download format), *.dat, *.csv (legacy).
    """
    sales_dir = Path(data_dir or settings.data_dir) / "nsw_sales"
    all_records: list[dict] = []

    for zip_file in sorted(sales_dir.glob("*.zip")):
        try:
            all_records.extend(load_nsw_sales_zip(zip_file))
        except Exception as e:
            logger.error("Failed to load NSW Sales ZIP", file=str(zip_file), error=str(e))

    for dat_file in sorted(sales_dir.glob("*.dat")):
        try:
            content = dat_file.read_text(encoding="utf-8", errors="replace")
            all_records.extend(load_nsw_sales_dat(content, source_name=str(dat_file)))
        except Exception as e:
            logger.error("Failed to load NSW Sales DAT", file=str(dat_file), error=str(e))

    for csv_file in sorted(sales_dir.glob("*.csv")):
        try:
            all_records.extend(load_nsw_sales_csv(str(csv_file)))
        except Exception as e:
            logger.error("Failed to load NSW Sales CSV", file=str(csv_file), error=str(e))

    logger.info(
        "NSW Sales load complete",
        total=len(all_records),
        zips=len(list(sales_dir.glob("*.zip"))),
        dats=len(list(sales_dir.glob("*.dat"))),
        csvs=len(list(sales_dir.glob("*.csv"))),
    )
    return all_records
