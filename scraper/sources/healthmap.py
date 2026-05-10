"""
HealthMap.org hantavirus alert collector.

HealthMap aggregates disease alerts from news, official reports, and eyewitness
accounts.  The public-facing site (https://healthmap.org/en/) does not expose
a stable machine-readable API, so this collector:

  1. Attempts to fetch the HealthMap JSON alert feed filtered for hantavirus.
  2. Falls back to hardcoded seed data derived from known May 2026 alerts
     if the live fetch fails or returns no relevant results.

Source identifier: "HealthMap"
Requirements: 1.4, 3.6
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Optional

from scraper.http_client import fetch_json, fetch_text
from scraper.models import Case
from scraper.parser import parse_json

logger = logging.getLogger(__name__)

SOURCE = "HealthMap"

# HealthMap JSON alert feed — disease_id 38 = hantavirus
_HEALTHMAP_FEED_URL = (
    "https://healthmap.org/getAlerts.php?disease_id=38&striphtml=1&json=1"
)

# ---------------------------------------------------------------------------
# Seed data — HealthMap-style alerts for the May 2026 MV Hondius outbreak
# These represent the news-signal layer that HealthMap would aggregate.
# ---------------------------------------------------------------------------
_SEED_CASES: list[dict] = [
    # Initial alert — South Africa / Atlantic Ocean
    {
        "location_name": "Cape Town, South Africa",
        "status": "Suspected",
        "date_reported": "2026-05-04",
        "latitude": -33.9,
        "longitude": 18.4,
        "virus_strain": "Andes",
        "notes": (
            "HealthMap alert: Suspected hantavirus outbreak on cruise ship "
            "reported near South Africa. Three dead, several ill. "
            "MV Hondius voyage."
        ),
    },
    # Alert — Cabo Verde
    {
        "location_name": "Praia, Cabo Verde",
        "status": "Suspected",
        "date_reported": "2026-05-04",
        "latitude": 14.9,
        "longitude": -23.5,
        "virus_strain": "Andes",
        "notes": (
            "HealthMap alert: MV Hondius docked at Praia, Cabo Verde. "
            "Hantavirus outbreak on board; no disembarkation. MV Hondius voyage."
        ),
    },
    # Alert — Canary Islands
    {
        "location_name": "Tenerife, Canary Islands, Spain",
        "status": "Confirmed",
        "date_reported": "2026-05-10",
        "latitude": 28.1,
        "longitude": -15.4,
        "virus_strain": "Andes",
        "notes": (
            "HealthMap alert: MV Hondius arrived Tenerife. Andes virus confirmed. "
            "Evacuation flights underway. MV Hondius voyage."
        ),
    },
    # Alert — Netherlands (repatriated cases)
    {
        "location_name": "Netherlands",
        "status": "Confirmed",
        "date_reported": "2026-05-08",
        "latitude": 52.1,
        "longitude": 5.3,
        "virus_strain": "Andes",
        "notes": (
            "HealthMap alert: Dutch passengers confirmed with Andes hantavirus. "
            "Two fatalities. MV Hondius voyage."
        ),
    },
    # Alert — Ushuaia, Argentina (origin)
    {
        "location_name": "Ushuaia, Argentina",
        "status": "Confirmed",
        "date_reported": "2026-04-01",
        "latitude": -54.8,
        "longitude": -68.3,
        "virus_strain": "Andes",
        "notes": (
            "HealthMap alert: MV Hondius departed Ushuaia. Andes virus "
            "exposure likely during Patagonia shore excursion. MV Hondius voyage."
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


def _try_fetch_live(source_verified_at: str) -> Optional[list[Case]]:
    """
    Attempt to fetch live HealthMap alerts for hantavirus.

    Returns a list of Cases if the feed is available and parseable,
    or None to signal fallback to seed data.
    """
    try:
        data = fetch_json(_HEALTHMAP_FEED_URL, SOURCE)

        if not isinstance(data, list) or len(data) == 0:
            logger.info("[%s] HealthMap feed returned empty or non-list response.", SOURCE)
            return None

        cases: list[Case] = []
        hanta_re = re.compile(r"hantavirus|andes\s+virus", re.IGNORECASE)

        for alert in data:
            if not isinstance(alert, dict):
                continue
            # HealthMap alert fields: place_name, country, lat, lng, summary,
            # link, disease, date
            summary = str(alert.get("summary", "") or "")
            disease = str(alert.get("disease", "") or "")
            if not (hanta_re.search(summary) or hanta_re.search(disease)):
                continue

            try:
                case = parse_json(
                    {
                        "location_name": (
                            alert.get("place_name")
                            or alert.get("country")
                            or "Unknown"
                        ),
                        "status": "Suspected",
                        "date_reported": (
                            alert.get("date", "")[:10]
                            if alert.get("date")
                            else datetime.now(tz=timezone.utc).date().isoformat()
                        ),
                        "latitude": alert.get("lat", 0.0),
                        "longitude": alert.get("lng", 0.0),
                        "virus_strain": "Andes" if "andes" in disease.lower() else "Unknown",
                        "notes": summary[:500],
                    },
                    SOURCE,
                    source_verified_at,
                )
                cases.append(case)
            except (ValueError, TypeError) as exc:
                logger.debug("[%s] Skipping alert: %s", SOURCE, exc)

        if cases:
            logger.info("[%s] Fetched %d live alerts.", SOURCE, len(cases))
            return cases

        logger.info("[%s] No hantavirus alerts in live feed; using seed data.", SOURCE)
        return None

    except Exception as exc:
        logger.warning("[%s] Live feed fetch failed: %s", SOURCE, exc)
        return None


def collect() -> tuple[list[Case], str]:
    """
    Collect HealthMap hantavirus alerts.

    Attempts to fetch live alerts from the HealthMap JSON feed.  Falls back
    to hardcoded seed data if the feed is unavailable or returns no results.

    Returns
    -------
    tuple[list[Case], str]
        A 2-tuple of (cases, source_verified_at).
    """
    source_verified_at = _now_utc()

    live_cases = _try_fetch_live(source_verified_at)
    if live_cases is not None:
        return live_cases, source_verified_at

    cases = _parse_seed_cases(source_verified_at)
    logger.info("[%s] Collected %d cases (seed data).", SOURCE, len(cases))
    return cases, source_verified_at
