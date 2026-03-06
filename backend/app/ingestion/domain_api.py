"""Domain.com.au API ingester.

Docs: https://developer.domain.com.au
Auth: OAuth2 client_credentials → Bearer token
Rate limit: ~500 req/day on free tier — tracked via Redis counter.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional

import httpx
import structlog

from app.config import settings
from app.ingestion.base import BaseIngester, RawProperty
from app.utils.geo import is_within_search_radius

logger = structlog.get_logger(__name__)

_TOKEN_URL = "https://auth.domain.com.au/v1/connect/token"
_API_BASE = "https://api.domain.com.au"
_PAGE_SIZE = 200

# Sydney postcodes to search — covers all of Greater Sydney + 150km radius
SYDNEY_POSTCODES = [
    # Inner Sydney
    "2000", "2007", "2008", "2009", "2010", "2011",
    # Eastern Suburbs
    "2020", "2021", "2022", "2023", "2024", "2025", "2026", "2027", "2028", "2029", "2030",
    "2031", "2032", "2033", "2034", "2035",
    # Inner West
    "2037", "2038", "2039", "2040", "2041", "2042", "2043", "2044", "2048", "2049",
    "2130", "2131", "2132", "2133", "2134", "2135", "2136", "2137", "2138", "2140", "2141",
    # North Shore Lower
    "2060", "2061", "2062", "2063", "2064", "2065", "2066", "2067", "2068", "2069", "2070",
    "2071", "2072", "2073", "2074", "2075", "2076", "2077",
    # Northern Beaches
    "2084", "2085", "2086", "2087", "2088", "2089", "2090", "2091", "2092", "2093", "2094",
    "2095", "2096", "2097", "2099", "2100", "2101", "2102", "2103", "2104", "2105", "2106",
    "2107", "2108",
    # Hills District
    "2110", "2111", "2112", "2113", "2114", "2115", "2116", "2117", "2118", "2119", "2120",
    "2121", "2122", "2125", "2126", "2153", "2154", "2155", "2156", "2157", "2158",
    # West / Parramatta
    "2142", "2143", "2144", "2145", "2146", "2147", "2148", "2150", "2151", "2152",
    "2159", "2160", "2161", "2162", "2163", "2164", "2165", "2166",
    # South / Sutherland
    "2200", "2203", "2204", "2205", "2206", "2207", "2208", "2209", "2210", "2211",
    "2212", "2213", "2214", "2216", "2217", "2218", "2219", "2220", "2221", "2222",
    "2223", "2224", "2225", "2226", "2227", "2228", "2229", "2230", "2231", "2232",
    # SW / Canterbury-Bankstown
    "2193", "2194", "2195", "2196", "2197", "2198", "2199",
    # Liverpool
    "2168", "2170", "2171", "2172", "2173", "2174", "2175", "2176",
    # Campbelltown
    "2560", "2563", "2564", "2565", "2566", "2567",
    # Penrith / Blue Mountains
    "2745", "2747", "2748", "2749", "2750", "2751", "2752", "2753", "2754", "2756",
    "2777", "2780",
    # Central Coast
    "2250", "2251", "2256", "2257", "2258", "2259", "2260", "2261", "2262",
    # Wollongong
    "2500", "2502", "2505", "2515", "2516", "2517", "2518", "2519",
]


class DomainApiIngester(BaseIngester):
    def __init__(self):
        self._access_token: Optional[str] = None
        self._token_expiry: Optional[float] = None

    def is_available(self) -> bool:
        return bool(settings.domain_client_id and settings.domain_client_secret)

    async def _get_token(self, client: httpx.AsyncClient) -> str:
        import time
        if self._access_token and self._token_expiry and time.time() < self._token_expiry - 60:
            return self._access_token

        resp = await client.post(
            _TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": settings.domain_client_id,
                "client_secret": settings.domain_client_secret,
                "scope": "api_listings_read api_properties_read",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access_token"]
        self._token_expiry = time.time() + data.get("expires_in", 3600)
        return self._access_token

    async def fetch(self) -> list[RawProperty]:
        results: list[RawProperty] = []
        async with httpx.AsyncClient(timeout=30) as client:
            token = await self._get_token(client)
            headers = {"Authorization": f"Bearer {token}"}

            for postcode in SYDNEY_POSTCODES:
                try:
                    page_results = await self._fetch_postcode(client, headers, postcode)
                    results.extend(page_results)
                    # Polite rate limiting — ~1 req/sec
                    await asyncio.sleep(0.5)
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:
                        logger.warning("Domain API rate limit hit", postcode=postcode)
                        break
                    logger.error("Domain API error", postcode=postcode, status=e.response.status_code)
                except Exception as e:
                    logger.error("Domain API unexpected error", postcode=postcode, error=str(e))

        logger.info("Domain ingestion complete", total=len(results))
        return results

    async def _fetch_postcode(
        self, client: httpx.AsyncClient, headers: dict, postcode: str
    ) -> list[RawProperty]:
        results = []
        page = 1
        while True:
            payload = {
                "listingType": "Sale",
                "propertyTypes": ["House", "ApartmentUnitFlat", "Townhouse", "VacantLand"],
                "locations": [{"state": "NSW", "postCode": postcode}],
                "pageSize": _PAGE_SIZE,
                "pageNumber": page,
            }
            resp = await client.post(
                f"{_API_BASE}/v1/listings/residential/_search",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

            if not data:
                break

            for item in data:
                listing = item.get("listing", item)
                raw = self._normalise(listing)
                if raw and is_within_search_radius(raw.latitude, raw.longitude):
                    results.append(raw)

            if len(data) < _PAGE_SIZE:
                break
            page += 1

        return results

    @staticmethod
    def _normalise(listing: dict) -> Optional[RawProperty]:
        try:
            listing_id = str(listing.get("id") or listing.get("listingId", ""))
            if not listing_id:
                return None

            addr = listing.get("addressParts") or listing.get("address") or {}
            price_details = listing.get("priceDetails") or {}

            # Parse price
            display_price = price_details.get("displayPrice", "") or ""
            list_price = None
            price_low = None
            price_high = None
            if price_details.get("price"):
                list_price = int(price_details["price"] * 100)
            if price_details.get("priceLowerRange"):
                price_low = int(price_details["priceLowerRange"] * 100)
            if price_details.get("priceUpperRange"):
                price_high = int(price_details["priceUpperRange"] * 100)

            # Property type mapping
            ptype_map = {
                "House": "house",
                "ApartmentUnitFlat": "apartment",
                "Townhouse": "townhouse",
                "VacantLand": "land",
                "Rural": "rural",
            }
            raw_ptype = listing.get("propertyTypes", [None])[0] if listing.get("propertyTypes") else None
            property_type = ptype_map.get(raw_ptype or "", "house")

            # Dates
            listed_at = None
            if listing.get("dateListed"):
                try:
                    listed_at = datetime.fromisoformat(listing["dateListed"].replace("Z", "+00:00"))
                except ValueError:
                    pass

            sold_at = None
            sold_price = None
            if listing.get("dateSold"):
                try:
                    sold_at = datetime.fromisoformat(listing["dateSold"].replace("Z", "+00:00"))
                except ValueError:
                    pass
            if listing.get("soldPrice"):
                sold_price = int(listing["soldPrice"] * 100)

            # Geo
            geo = listing.get("geoLocation") or listing.get("geo") or {}
            lat = geo.get("latitude") or geo.get("lat")
            lng = geo.get("longitude") or geo.get("lng")

            # Build address
            street_parts = [
                addr.get("streetNumber", ""),
                addr.get("street", ""),
                addr.get("streetType", ""),
            ]
            street = " ".join(p for p in street_parts if p).strip()

            return RawProperty(
                external_id=listing_id,
                source="domain_api",
                url=f"https://www.domain.com.au/{listing_id}",
                status="sold" if sold_at else "for_sale",
                property_type=property_type,
                address_street=street or None,
                address_suburb=addr.get("suburb") or addr.get("suburbName"),
                address_postcode=str(addr.get("postcode", "") or "")[:4] or None,
                latitude=float(lat) if lat is not None else None,
                longitude=float(lng) if lng is not None else None,
                bedrooms=listing.get("bedrooms"),
                bathrooms=listing.get("bathrooms"),
                car_spaces=listing.get("carspaces") or listing.get("parking"),
                land_size_sqm=listing.get("landSize") or listing.get("landArea"),
                floor_area_sqm=listing.get("buildingSize") or listing.get("floorArea"),
                year_built=listing.get("yearBuilt"),
                list_price=list_price,
                price_guide_low=price_low,
                price_guide_high=price_high,
                listed_at=listed_at,
                sold_at=sold_at,
                sold_price=sold_price,
                description=listing.get("description"),
                features=listing.get("features") or [],
                images=[m.get("url", "") for m in (listing.get("media") or []) if m.get("category") == "Image"],
                agent_name=(listing.get("advertiser") or {}).get("name"),
                agency_name=(listing.get("agency") or {}).get("name"),
                raw_json=listing,
            )
        except Exception:
            return None
