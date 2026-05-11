"""
ArcGIS Feature Service collector — ANDV Hantavirus 2026 dashboard.
Primary data source: University of Toledo / K. Panozzo
Dashboard: https://www.arcgis.com/apps/dashboards/5c68442d2afc42d7ba2696e4cd393729
"""

from __future__ import annotations
import hashlib
import logging
import math
from datetime import datetime, timezone
from typing import Optional

from scraper.http_client import fetch_json
from scraper.models import Case

logger = logging.getLogger(__name__)
SOURCE = "ANDV_Dashboard"

_ARCGIS_URL = (
    "https://services1.arcgis.com/wb4Og4gH5mvzQAIV/arcgis/rest/services/"
    "Tracking_Hantavirus_2026/FeatureServer/1/query"
    "?where=1%3D1&outFields=*&f=geojson&returnGeometry=true"
    "&orderByFields=CASE_%20ASC&resultRecordCount=500"
)

_STATUS_MAP = {
    "CONFIRMED":  "Confirmed",
    "SUSPECTED":  "Suspected",
    "DECEASED":   "Deceased",
    "MONITORING": "Monitoring",
    "UNKNOWN":    "Monitoring",  # treat unknown as monitoring
}

# Coordinate lookup for cases with missing/invalid geometry
_LOCATION_COORDS = {
    "ITALY": (41.9, 12.5), "FINLAND": (61.9, 25.7), "DENMARK": (56.0, 10.0),
    "SWEDEN": (59.3, 18.1), "SPAIN": (40.4, -3.7), "FRANCE": (46.2, 2.2),
    "GERMANY": (51.2, 10.5), "NETHERLANDS": (52.1, 5.3), "BELGIUM": (50.5, 4.5),
    "SWITZERLAND": (47.4, 8.5), "UNITED KINGDOM": (51.5, -0.1), "UK": (51.5, -0.1),
    "IRELAND": (53.4, -8.2), "GREECE": (39.1, 21.8), "TURKEY": (39.9, 32.9),
    "SOUTH AFRICA": (-26.2, 28.0), "JOHANNESBURG": (-26.2, 28.0),
    "SINGAPORE": (1.35, 103.8), "AUSTRALIA": (-25.3, 133.8),
    "NEW ZEALAND": (-40.9, 174.9), "CANADA": (56.1, -106.3),
    "UNITED STATES": (37.1, -95.7), "USA": (37.1, -95.7),
    "NEBRASKA, USA": (41.5, -99.9), "GEORGIA, USA": (32.2, -83.4),
    "TEXAS": (31.0, -100.0), "CALIFORNIA": (36.8, -119.4),
    "ARIZONA, USA": (34.0, -111.1), "VIRGINIA": (37.4, -78.7),
    "NEW JERSEY": (40.1, -74.7), "ARGENTINA": (-34.6, -58.4),
    "USHUAIA": (-54.8, -68.3), "JAPAN": (36.2, 138.3),
    "INDIA": (20.6, 78.9), "PHILIPPINES": (12.9, 121.8),
    "GUATEMALA": (15.8, -90.2), "MONTENEGRO": (42.7, 19.4),
    "TRISTAN DA CUNHA": (-37.1, -12.3), "ST HELENA": (-15.9, -5.7),
    "SAINT HELENA": (-15.9, -5.7), "PRAIA, CAPE VERDE": (14.9, -23.5),
    "CAPE VERDE": (14.9, -23.5), "ALICANTE, SPAIN": (38.3, -0.5),
    "ZURICH": (47.4, 8.5), "MV HONDIUS": (28.1, -15.4), "MV HONDUS": (28.1, -15.4),
    "TENERIFE": (28.1, -15.4), "CANARY ISLANDS": (28.1, -15.4),
}


def _resolve_coords(location: str, details: str, lon: float, lat: float):
    """Return (lat, lon) resolving from geometry or location lookup."""
    if lon and lat and -180 <= lon <= 180 and -90 <= lat <= 90 and (lon != 0 or lat != 0):
        return lat, lon
    loc = (location or "").upper().strip()
    det = (details or "").upper()
    for key, coords in _LOCATION_COORDS.items():
        if key in loc or key in det:
            return coords
    return None


def _epoch_to_iso(ms) -> str:
    if ms is None:
        return ""
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return ""


def _cid(location: str, date: str) -> str:
    return hashlib.sha256(f"{SOURCE}|{location}|{date}".encode()).hexdigest()


def _now_utc() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def collect() -> tuple[list[Case], str]:
    source_verified_at = _now_utc()
    try:
        data = fetch_json(_ARCGIS_URL, SOURCE, skip_robots=True)
        features = data.get("features", [])
        if not features:
            raise ValueError("Empty feature list")

        cases: list[Case] = []
        for feat in features:
            props = feat.get("properties") or {}
            geom  = feat.get("geometry") or {}
            coords = geom.get("coordinates", [None, None])
            lon = coords[0] if coords and len(coords) > 0 else None
            lat = coords[1] if coords and len(coords) > 1 else None

            location = str(props.get("LASTLOCATION") or "Unknown")
            details  = str(props.get("DETAILS") or "")
            resolved = _resolve_coords(location, details, lon or 0, lat or 0)
            if not resolved:
                logger.debug("[%s] Skipping unresolvable location: %s / %s", SOURCE, location, details[:40])
                continue

            rlat, rlon = resolved
            raw_status = str(props.get("STATUS") or "MONITORING").upper()
            status = _STATUS_MAP.get(raw_status, "Monitoring")

            # Fix location name for UNKNOWN cases
            if not location or location.upper() in ("UNKNOWN", "NONE"):
                for key in LOCATION_COORDS:
                    if key in details.upper():
                        location = key.title()
                        break
                else:
                    location = "Unknown location"

            date_reported = _epoch_to_iso(props.get("ONSET")) or _now_utc()[:10]
            sex_code = props.get("SEX")
            sex = "♂" if sex_code == 1 else "♀" if sex_code == 2 else ""
            age = props.get("AGE")
            age_str = f"Age {age}" if age else ""
            sex_age = ", ".join(filter(None, [age_str, sex]))
            exposure = str(props.get("Exposure_Group") or "")
            source_url = str(props.get("SOURCE") or "")
            notes_parts = [details, exposure, sex_age]
            notes = ". ".join(p for p in notes_parts if p).strip(". ")
            if source_url:
                notes += f" Source: {source_url}"

            cases.append(Case(
                case_id=_cid(location, date_reported),
                status=status,
                date_reported=date_reported,
                source=SOURCE,
                latitude=float(rlat),
                longitude=float(rlon),
                location_name=location,
                virus_strain="Andes",
                source_verified_at=source_verified_at,
                notes=notes,
            ))

        logger.info("[%s] Collected %d cases", SOURCE, len(cases))
        return cases, source_verified_at

    except Exception as exc:
        logger.error("[%s] Failed: %s", SOURCE, exc)
        return [], source_verified_at
