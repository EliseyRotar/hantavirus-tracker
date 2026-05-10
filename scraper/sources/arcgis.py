"""
ArcGIS Feature Service collector — ANDV Hantavirus 2026 dashboard.

Primary data source: University of Toledo / K. Panozzo
Dashboard: https://www.arcgis.com/apps/dashboards/5c68442d2afc42d7ba2696e4cd393729
Feature Service: https://services1.arcgis.com/wb4Og4gH5mvzQAIV/arcgis/rest/services/Tracking_Hantavirus_2026/FeatureServer/1

Fields: CASE_, STATUS, AGE, SEX, ONSET, DEATH, SOURCE, LASTLOCATION, DETAILS, Exposure_Group
"""

from __future__ import annotations
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

from scraper.http_client import fetch_json
from scraper.models import Case

logger = logging.getLogger(__name__)

SOURCE = "ANDV_Dashboard"

_ARCGIS_URL = (
    "https://services1.arcgis.com/wb4Og4gH5mvzQAIV/arcgis/rest/services/"
    "Tracking_Hantavirus_2026/FeatureServer/1/query"
    "?where=1%3D1&outFields=*&f=geojson&returnGeometry=true&orderByFields=CASE_%20ASC"
)

_STATUS_MAP = {
    "CONFIRMED":  "Confirmed",
    "SUSPECTED":  "Suspected",
    "DECEASED":   "Deceased",
    "MONITORING": "Monitoring",
}


def _now_utc() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _epoch_to_iso(ms) -> str:
    if ms is None:
        return ""
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return ""


def _cid(location: str, date: str) -> str:
    return hashlib.sha256(f"{SOURCE}|{location}|{date}".encode()).hexdigest()


def collect() -> tuple[list[Case], str]:
    """Fetch all cases from the ArcGIS Feature Service."""
    source_verified_at = _now_utc()
    try:
        data = fetch_json(_ARCGIS_URL, SOURCE, skip_robots=True)
        features = data.get("features", [])
        if not features:
            raise ValueError("Empty feature list returned")

        cases: list[Case] = []
        for feat in features:
            props = feat.get("properties") or {}
            geom  = feat.get("geometry") or {}
            coords = geom.get("coordinates", [None, None])

            lon = coords[0] if coords and len(coords) > 0 else None
            lat = coords[1] if coords and len(coords) > 1 else None
            if lat is None or lon is None:
                logger.debug("[%s] Skipping feature with no geometry: %s", SOURCE, props.get("CASE_"))
                continue

            raw_status = str(props.get("STATUS") or "MONITORING").upper()
            status = _STATUS_MAP.get(raw_status, "Monitoring")
            location = str(props.get("LASTLOCATION") or "Unknown")
            date_reported = _epoch_to_iso(props.get("ONSET")) or _now_utc()[:10]

            sex_code = props.get("SEX")
            sex = "♂" if sex_code == 1 else "♀" if sex_code == 2 else ""
            age = props.get("AGE")
            age_str = f"Age {age}" if age else ""
            sex_age = ", ".join(filter(None, [age_str, sex]))

            details = str(props.get("DETAILS") or "")
            exposure = str(props.get("Exposure_Group") or "")
            notes_parts = [details, exposure, sex_age]
            notes = ". ".join(p for p in notes_parts if p).strip(". ")

            source_url = str(props.get("SOURCE") or "")

            cases.append(Case(
                case_id=_cid(location, date_reported),
                status=status,
                date_reported=date_reported,
                source=SOURCE,
                latitude=float(lat),
                longitude=float(lon),
                location_name=location,
                virus_strain="Andes",
                source_verified_at=source_verified_at,
                notes=notes + (f" Source: {source_url}" if source_url else ""),
            ))

        logger.info("[%s] Collected %d cases from ArcGIS Feature Service", SOURCE, len(cases))
        return cases, source_verified_at

    except Exception as exc:
        logger.error("[%s] Failed to fetch from ArcGIS: %s", SOURCE, exc)
        return [], source_verified_at
