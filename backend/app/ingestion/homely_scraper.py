"""Homely.com.au scraper.

Scrapes Sydney for-sale listings using httpx + BeautifulSoup.
Homely uses server-side rendered HTML, making it scrapeable without
a headless browser unlike Domain, REA, and OnTheHouse.

Rate limiting: 1.5s delay between page requests (polite crawling).
Pagination: ?page=N, stops when no listing cards are found on a page.

NOTE: CSS selectors are in the _CSS_* constants below. Update them if
      the site's markup changes — the scraper logs a warning and skips
      cards gracefully rather than crashing.
"""

import asyncio
import re
from datetime import datetime, timezone
from hashlib import md5
from typing import Optional

import httpx
import structlog
from bs4 import BeautifulSoup

from app.ingestion.base import BaseIngester, RawProperty

logger = structlog.get_logger(__name__)

_BASE_URL = "https://www.homely.com.au"
_SEARCH_URL = f"{_BASE_URL}/buy/sydney-nsw"
_MAX_PAGES = 50  # safety cap (~25 listings/page → ~1,250 listings max per run)
_PAGE_DELAY = 1.5  # seconds between requests

# CSS selectors — update these if the site markup changes
_CSS_LISTING_CARD = (
    "article[data-testid='listing-card'], "
    "article.listing-card, "
    "div[class*='ListingCard'], "
    "div[class*='listing-card'], "
    "div[class*='property-card']"
)
_CSS_ADDRESS = (
    "[data-testid='listing-address'], "
    "h2[class*='address'], "
    "span[class*='address'], "
    "p[class*='address'], "
    "h2.listing-title"
)
_CSS_PRICE = (
    "[data-testid='listing-price'], "
    "span[class*='price'], "
    "p[class*='price'], "
    "div[class*='Price']"
)
_CSS_BEDS = (
    "[data-testid='beds'], "
    "span[data-label='Bedrooms'], "
    "span[class*='bed'], "
    "li[class*='bed']"
)
_CSS_BATHS = (
    "[data-testid='baths'], "
    "span[data-label='Bathrooms'], "
    "span[class*='bath'], "
    "li[class*='bath']"
)
_CSS_CARS = (
    "[data-testid='cars'], "
    "span[data-label='Car spaces'], "
    "span[class*='car'], "
    "li[class*='parking']"
)
_CSS_LINK = "a[href*='/for-sale/'], a[href*='/buy/']"
_CSS_IMAGE = "img[src*='homely'], img[class*='listing'], img[class*='property']"
_CSS_AGENT = (
    "[class*='agent-name'], "
    "[class*='AgentName'], "
    "span[class*='agent']"
)
_CSS_AGENCY = (
    "[class*='agency-name'], "
    "[class*='AgencyName'], "
    "span[class*='agency']"
)


def _extract_int(text: str) -> Optional[int]:
    m = re.search(r"\d+", text or "")
    return int(m.group()) if m else None


def _parse_price(text: str) -> Optional[int]:
    """Extract price in AUD cents from a price string."""
    if not text:
        return None
    cleaned = re.sub(r"[^0-9.]", "", text.replace(",", ""))
    try:
        value = float(cleaned)
        if value > 100:  # avoid interpreting "3" beds as a price
            return int(value * 100)
    except (ValueError, TypeError):
        pass
    return None


def _parse_price_guide(text: str) -> tuple[Optional[int], Optional[int]]:
    """Parse a price guide range like '$1.1m - $1.2m' → (110000000, 120000000)."""
    if not text:
        return None, None

    def _parse_one(s: str) -> Optional[int]:
        s = s.strip().lower().replace(",", "")
        m = re.search(r"[\d.]+", s)
        if not m:
            return None
        val = float(m.group())
        if "m" in s:
            val *= 1_000_000
        elif "k" in s:
            val *= 1_000
        return int(val * 100)

    parts = re.split(r"\s*[-–—to]\s*", text, maxsplit=1)
    low = _parse_one(parts[0]) if len(parts) >= 1 else None
    high = _parse_one(parts[1]) if len(parts) == 2 else None
    return low, high


def _parse_property_type(card_html: str, url: str) -> str:
    html_lower = card_html.lower()
    url_lower = url.lower()
    if any(k in html_lower or k in url_lower for k in ["townhouse", "town-house"]):
        return "townhouse"
    if any(k in html_lower or k in url_lower for k in ["apartment", "unit", "flat"]):
        return "apartment"
    if any(k in html_lower or k in url_lower for k in ["land", "vacant"]):
        return "land"
    return "house"


def _parse_suburb_postcode(text: str) -> tuple[Optional[str], Optional[str]]:
    """Extract suburb and postcode from an address string."""
    # e.g. "12 Main St, Parramatta NSW 2150"
    m = re.search(r",\s*([A-Za-z\s]+)\s+NSW\s+(\d{4})", text or "")
    if m:
        return m.group(1).strip().title(), m.group(2)
    # Fallback: last word that's 4 digits
    m2 = re.search(r"(\d{4})\s*$", text or "")
    if m2:
        before = text[: m2.start()].rstrip(",. ").strip()
        # Extract suburb — last comma-delimited segment before postcode
        parts = before.rsplit(",", 1)
        suburb_raw = parts[-1].strip() if parts else before
        return suburb_raw.title() or None, m2.group(1)
    return None, None


class HomelyScraper(BaseIngester):
    """Scrapes Homely.com.au for active Sydney for-sale listings."""

    async def fetch(self) -> list[RawProperty]:
        results: list[RawProperty] = []

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-AU,en;q=0.9",
        }

        async with httpx.AsyncClient(headers=headers, timeout=30, follow_redirects=True) as client:
            for page in range(1, _MAX_PAGES + 1):
                url = f"{_SEARCH_URL}?page={page}"
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                except httpx.HTTPError as e:
                    logger.warning("Homely fetch error", page=page, error=str(e))
                    break

                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.select(_CSS_LISTING_CARD)

                if not cards:
                    logger.info("Homely: no more listing cards found", page=page)
                    break

                for card in cards:
                    raw = self._parse_card(card)
                    if raw:
                        results.append(raw)

                logger.info("Homely page scraped", page=page, cards=len(cards), total=len(results))
                await asyncio.sleep(_PAGE_DELAY)

        logger.info("Homely scrape complete", total=len(results))
        return results

    def _parse_card(self, card) -> Optional[RawProperty]:
        try:
            # --- Link / external ID ---
            link_el = card.select_one(_CSS_LINK)
            if not link_el:
                return None
            href = link_el.get("href", "")
            if not href.startswith("http"):
                href = _BASE_URL + href
            if not href:
                return None
            external_id = md5(href.encode()).hexdigest()[:16]

            # --- Address ---
            addr_el = card.select_one(_CSS_ADDRESS)
            address_text = addr_el.get_text(strip=True) if addr_el else ""
            suburb, postcode = _parse_suburb_postcode(address_text)

            # Strip suburb/postcode from street part
            street = address_text
            if suburb and postcode:
                street = re.sub(
                    r",?\s*" + re.escape(suburb) + r"\s+NSW\s+" + re.escape(postcode),
                    "",
                    street,
                    flags=re.IGNORECASE,
                ).strip().rstrip(",").strip()

            # --- Price ---
            price_el = card.select_one(_CSS_PRICE)
            price_text = price_el.get_text(strip=True) if price_el else ""
            list_price = _parse_price(price_text)
            price_low, price_high = _parse_price_guide(price_text)

            # --- Specs ---
            beds_el = card.select_one(_CSS_BEDS)
            baths_el = card.select_one(_CSS_BATHS)
            cars_el = card.select_one(_CSS_CARS)
            bedrooms = _extract_int(beds_el.get_text() if beds_el else "")
            bathrooms = _extract_int(baths_el.get_text() if baths_el else "")
            car_spaces = _extract_int(cars_el.get_text() if cars_el else "")

            # --- Image ---
            img_el = card.select_one(_CSS_IMAGE)
            images = []
            if img_el:
                src = img_el.get("src") or img_el.get("data-src") or ""
                if src:
                    images = [src]

            # --- Agent / Agency ---
            agent_el = card.select_one(_CSS_AGENT)
            agency_el = card.select_one(_CSS_AGENCY)
            agent_name = agent_el.get_text(strip=True) if agent_el else None
            agency_name = agency_el.get_text(strip=True) if agency_el else None

            # --- Property type from card context ---
            property_type = _parse_property_type(card.decode(), href)

            return RawProperty(
                external_id=external_id,
                source="homely",
                url=href,
                status="for_sale",
                property_type=property_type,
                address_street=street or None,
                address_suburb=suburb,
                address_postcode=postcode,
                bedrooms=bedrooms,
                bathrooms=bathrooms,
                car_spaces=car_spaces,
                list_price=list_price,
                price_guide_low=price_low,
                price_guide_high=price_high,
                images=images,
                agent_name=agent_name,
                agency_name=agency_name,
                raw_json={"scraped_at": datetime.now(timezone.utc).isoformat()},
            )

        except Exception as e:
            logger.warning("Homely: failed to parse card", error=str(e))
            return None
