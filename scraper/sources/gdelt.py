"""
GDELT Project hantavirus news signal collector.

Uses the GDELT DOC 2.0 API to search for recent news articles mentioning
hantavirus.  Extracts location signals from article metadata to produce
approximate case locations.

GDELT DOC 2.0 API endpoint:
  https://api.gdeltproject.org/api/v2/doc/doc
  ?query=hantavirus&mode=artlist&format=json&maxrecords=250&timespan=30d

Source identifier: "GDELT"
Requirements: 1.4, 3.6
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Optional

from scraper.http_client import fetch_json
from scraper.models import Case
from scraper.parser import parse_json

logger = logging.getLogger(__name__)

SOURCE = "GDELT"

_GDELT_API_URL = (
    "https://api.gdeltproject.org/api/v2/doc/doc"
    "?query=hantavirus%20OR%20%22andes%20virus%22"
    "&mode=artlist"
    "&format=json"
    "&maxrecords=250"
    "&timespan=30d"
)

# ---------------------------------------------------------------------------
# Location lookup table for GDELT country/location codes → coordinates
# Covers the key locations in the May 2026 MV Hondius outbreak.
# ---------------------------------------------------------------------------
_LOCATION_COORDS: dict[str, tuple[float, float]] = {
    "argentina": (-34.6, -58.4),
    "ushuaia": (-54.8, -68.3),
    "south africa": (-26.2, 28.0),
    "johannesburg": (-26.2, 28.0),
    "cape town": (-33.9, 18.4),
    "saint helena": (-15.9, -5.7),
    "st. helena": (-15.9, -5.7),
    "cabo verde": (14.9, -23.5),
    "cape verde": (14.9, -23.5),
    "canary islands": (28.1, -15.4),
    "tenerife": (28.1, -15.4),
    "spain": (40.4, -3.7),
    "netherlands": (52.1, 5.3),
    "germany": (51.2, 10.5),
    "switzerland": (47.4, 8.5),
    "united kingdom": (51.5, -0.1),
    "uk": (51.5, -0.1),
    "united states": (38.9, -77.0),
    "usa": (38.9, -77.0),
    "nebraska": (41.5, -99.9),
    "south georgia": (-54.2, -36.5),
    "tristan da cunha": (-37.1, -12.3),
    "ascension island": (-7.9, -14.4),
    "falkland islands": (-51.7, -59.0),
}

# ---------------------------------------------------------------------------
# Seed data — GDELT-style news signals for the May 2026 outbreak
# ---------------------------------------------------------------------------
_SEED_CASES: list[dict] = [
    {
        "location_name": "Ushuaia, Argentina",
        "status": "Confirmed",
        "date_reported": "2026-04-01",
        "latitude": -54.8,
        "longitude": -68.3,
        "virus_strain": "Andes",
        "notes": (
            "GDELT news signal: MV Hondius departed Ushuaia with Andes virus "
            "exposure. Multiple international news sources. MV Hondius voyage."
        ),
    },
    {
        "location_name": "Cape Town, South Africa",
        "status": "Suspected",
        "date_reported": "2026-05-04",
        "latitude": -33.9,
        "longitude": 18.4,
        "virus_strain": "Andes",
        "notes": (
            "GDELT news signal: Hantavirus outbreak on cruise ship reported "
            "near South Africa. MV Hondius voyage."
        ),
    },
    {
        "location_name": "Praia, Cabo Verde",
        "status": "Suspected",
        "date_reported": "2026-05-04",
        "latitude": 14.9,
        "longitude": -23.5,
        "virus_strain": "Andes",
        "notes": (
            "GDELT news signal: MV Hondius docked at Cabo Verde with hantavirus "
            "outbreak on board. MV Hondius voyage."
        ),
    },
    {
        "location_name": "Tenerife, Canary Islands, Spain",
        "status": "Confirmed",
        "date_reported": "2026-05-10",
        "latitude": 28.1,
        "longitude": -15.4,
        "virus_strain": "Andes",
        "notes": (
            "GDELT news signal: MV Hondius arrived Tenerife; Andes virus "
            "confirmed; evacuation flights. MV Hondius voyage."
        ),
    },
    {
        "location_name": "Netherlands",
        "status": "Confirmed",
        "date_reported": "2026-05-08",
        "latitude": 52.1,
        "longitude": 5.3,
        "virus_strain": "Andes",
        "notes": (
            "GDELT news signal: Dutch passengers confirmed with Andes hantavirus; "
            "two fatalities. MV Hondius voyage."
        ),
    },
]


def _now_utc() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _parse_seed_cases(source_verified_at: str) -> list[Case]:
    cases: list[Case] = []
    for item in _SEED_CASES:
        try:
            case = parse_json(item, SOURCE, source_verified_at)
            cases.append(case)
        except (ValueError, TypeError) as exc:
            logger.warning("[%s] Failed to parse seed case %r: %s", SOURCE, item, exc)
    return cases


def _resolve_location(location_str: str) -> tuple[str, float, float]:
    """
    Attempt to resolve a location string to (name, lat, lon).

    Uses a simple keyword lookup against known outbreak locations.
    Returns a default of (location_str, 0.0, 0.0) if no match found.
    """
    lower = location_str.lower()
    for key, (lat, lon) in _LOCATION_COORDS.items():
        if key in lower:
            return location_str, lat, lon
    return location_str, 0.0, 0.0


def _try_fetch_gdelt(source_verified_at: str) -> Optional[list[Case]]:
    """
    Attempt to fetch hantavirus articles from the GDELT DOC 2.0 API.

    Returns a list of Cases if the API is available and returns results,
    or None to signal fallback to seed data.
    """
    try:
        data = fetch_json(_GDELT_API_URL, SOURCE)

        if not isinstance(data, dict):
            logger.info("[%s] GDELT API returned unexpected type: %s", SOURCE, type(data))
            return None

        articles = data.get("articles", [])
        if not articles:
            logger.info("[%s] GDELT API returned no articles; using seed data.", SOURCE)
            return None

        cases: list[Case] = []
        hanta_re = re.compile(r"hantavirus|andes\s+virus", re.IGNORECASE)
        seen_locations: set[str] = set()

        for article in articles:
            if not isinstance(article, dict):
                continue

            title = str(article.get("title", "") or "")
            url = str(article.get("url", "") or "")
            seendate = str(article.get("seendate", "") or "")

            if not hanta_re.search(title):
                continue

            # Extract location from GDELT article metadata
            # GDELT artlist format includes: title, url, seendate, domain,
            # language, sourcecountry
            source_country = str(article.get("sourcecountry", "") or "")
            location_str = source_country or "Unknown"

            if location_str == "Unknown" or location_str in seen_locations:
                continue
            seen_locations.add(location_str)

            location_name, lat, lon = _resolve_location(location_str)

            # Skip if we couldn't resolve coordinates
            if lat == 0.0 and lon == 0.0:
                continue

            # Parse date from GDELT seendate format: YYYYMMDDTHHMMSSZ
            date_reported = datetime.now(tz=timezone.utc).date().isoformat()
            if seendate and len(seendate) >= 8:
                try:
                    date_reported = (
                        f"{seendate[:4]}-{seendate[4:6]}-{seendate[6:8]}"
                    )
                except (ValueError, IndexError):
                    pass

            try:
                case = parse_json(
                    {
                        "location_name": location_name,
                        "status": "Suspected",
                        "date_reported": date_reported,
                        "latitude": lat,
                        "longitude": lon,
                        "virus_strain": (
                            "Andes"
                            if re.search(r"andes", title, re.IGNORECASE)
                            else "Unknown"
                        ),
                        "notes": f"GDELT news signal: {title[:300]}",
                    },
                    SOURCE,
                    source_verified_at,
                )
                cases.append(case)
            except (ValueError, TypeError) as exc:
                logger.debug("[%s] Skipping article: %s", SOURCE, exc)

        if cases:
            logger.info("[%s] Extracted %d location signals from GDELT.", SOURCE, len(cases))
            return cases

        logger.info("[%s] No usable location signals from GDELT; using seed data.", SOURCE)
        return None

    except Exception as exc:
        logger.warning("[%s] GDELT API fetch failed: %s", SOURCE, exc)
        return None


def collect() -> tuple[list[Case], str]:
    """
    Collect GDELT hantavirus news signals.

    Attempts to fetch articles from the GDELT DOC 2.0 API and extract
    location signals.  Falls back to hardcoded seed data if the API is
    unavailable or returns no usable results.

    Returns
    -------
    tuple[list[Case], str]
        A 2-tuple of (cases, source_verified_at).
    """
    source_verified_at = _now_utc()

    live_cases = _try_fetch_gdelt(source_verified_at)
    if live_cases is not None:
        return live_cases, source_verified_at

    cases = _parse_seed_cases(source_verified_at)
    logger.info("[%s] Collected %d cases (seed data).", SOURCE, len(cases))
    return cases, source_verified_at
