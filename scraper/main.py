"""
Hantavirus Tracker — main scraper orchestrator.

Calls all source collectors, validates and deduplicates the results, merges
with any existing data, and writes the final GeoJSON to data/cases.geojson.
Also writes a run summary to scraper/scrape.log.

Usage
-----
    python scraper/main.py

Requirements: 1.5, 1.6, 3.5, 6.3, 7.1, 7.2, 7.6
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

# Ensure the repo root is on sys.path so `scraper.*` imports work whether
# this script is run as `python scraper/main.py` or `python -m scraper.main`.
_SCRIPT_DIR = Path(__file__).parent
_REPO_ROOT_CANDIDATE = _SCRIPT_DIR.parent
if str(_REPO_ROOT_CANDIDATE) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT_CANDIDATE))

# ---------------------------------------------------------------------------
# Logging setup — write to both stderr and scrape.log
# ---------------------------------------------------------------------------
_LOG_PATH = Path(__file__).parent / "scrape.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler(_LOG_PATH, mode="w", encoding="utf-8"),
    ],
)
logger = logging.getLogger("scraper.main")

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).parent.parent
_GEOJSON_PATH = _REPO_ROOT / "data" / "cases.geojson"

# ---------------------------------------------------------------------------
# MV Hondius itinerary seed data (Task 5.8)
# Hardcoded voyage stops; used to ensure coverage even when live sources
# return no data for these remote locations.
# ---------------------------------------------------------------------------
_HONDIUS_ITINERARY: list[dict] = [
    {
        "location_name": "Ushuaia, Argentina",
        "latitude": -54.8,
        "longitude": -68.3,
        "date_reported": "2026-04-01",
        "status": "Confirmed",
        "notes": "MV Hondius voyage — departure port. Andes virus exposure likely during Patagonia shore excursion.",
    },
    {
        "location_name": "Falkland Islands",
        "latitude": -51.7,
        "longitude": -59.0,
        "date_reported": "2026-04-05",
        "status": "Suspected",
        "notes": "MV Hondius voyage — stop at Falkland Islands.",
    },
    {
        "location_name": "South Georgia",
        "latitude": -54.2,
        "longitude": -36.5,
        "date_reported": "2026-04-08",
        "status": "Suspected",
        "notes": "MV Hondius voyage — stop at South Georgia.",
    },
    {
        "location_name": "Tristan da Cunha",
        "latitude": -37.1,
        "longitude": -12.3,
        "date_reported": "2026-04-15",
        "status": "Suspected",
        "notes": "MV Hondius voyage — stop at Tristan da Cunha.",
    },
    {
        "location_name": "Saint Helena",
        "latitude": -15.9,
        "longitude": -5.7,
        "date_reported": "2026-04-20",
        "status": "Confirmed",
        "notes": (
            "MV Hondius voyage — first fatality removed from vessel here. "
            "30 passengers disembarked; all contact-traced by UK Health Security Agency."
        ),
    },
    {
        "location_name": "Ascension Island",
        "latitude": -7.9,
        "longitude": -14.4,
        "date_reported": "2026-04-25",
        "status": "Suspected",
        "notes": "MV Hondius voyage — stop at Ascension Island.",
    },
    {
        "location_name": "Praia, Cabo Verde",
        "latitude": 16.0,
        "longitude": -24.0,
        "date_reported": "2026-05-01",
        "status": "Suspected",
        "notes": (
            "MV Hondius voyage — docked at Praia for 3 days. "
            "No passengers disembarked; local facilities unable to handle evacuation."
        ),
    },
    {
        "location_name": "Tenerife, Canary Islands, Spain",
        "latitude": 28.1,
        "longitude": -15.4,
        "date_reported": "2026-05-10",
        "status": "Confirmed",
        "notes": (
            "MV Hondius voyage — final port. Passengers disembarked onto "
            "repatriation flights to 6 European countries and Canada."
        ),
    },
]


# ---------------------------------------------------------------------------
# Source collectors registry
# ---------------------------------------------------------------------------
def _load_collectors() -> list[tuple[str, Callable]]:
    """Import all source collector modules and return (name, collect_fn) pairs."""
    from scraper.sources import arcgis, who, ecdc, cdc, healthmap, gdelt

    return [
        ("ANDV_Dashboard", arcgis.collect),   # primary — ArcGIS live data
        ("WHO", who.collect),
        ("ECDC", ecdc.collect),
        ("CDC", cdc.collect),
        ("HealthMap", healthmap.collect),
        ("GDELT", gdelt.collect),
    ]


# ---------------------------------------------------------------------------
# Existing GeoJSON loader
# ---------------------------------------------------------------------------
def _load_existing_cases() -> list:
    """Load existing cases from data/cases.geojson, if it exists."""
    from scraper.models import Case

    if not _GEOJSON_PATH.exists():
        logger.info("No existing cases.geojson found; starting fresh.")
        return []

    try:
        with open(_GEOJSON_PATH, encoding="utf-8") as fh:
            data = json.load(fh)

        features = data.get("features", [])
        cases: list[Case] = []
        for feature in features:
            props = feature.get("properties", {})
            try:
                cases.append(
                    Case(
                        case_id=props["case_id"],
                        status=props["status"],
                        date_reported=props["date_reported"],
                        source=props["source"],
                        latitude=props["latitude"],
                        longitude=props["longitude"],
                        location_name=props["location_name"],
                        virus_strain=props.get("virus_strain", "Unknown"),
                        source_verified_at=props.get("source_verified_at", ""),
                        notes=props.get("notes", ""),
                    )
                )
            except (KeyError, TypeError) as exc:
                logger.warning("Skipping malformed existing feature: %s", exc)

        logger.info("Loaded %d existing cases from %s", len(cases), _GEOJSON_PATH)
        return cases

    except Exception as exc:
        logger.error("Failed to load existing cases.geojson: %s", exc)
        return []


# ---------------------------------------------------------------------------
# MV Hondius seed case builder (Task 5.8)
# ---------------------------------------------------------------------------
def _build_hondius_seed_cases(
    existing_location_names: set[str],
    source_verified_at: str,
) -> list:
    """
    Build seed Case objects for MV Hondius itinerary stops not already covered.

    Only adds a seed case for a location if no case with that location_name
    already exists in the collected data.
    """
    from scraper.models import Case
    from scraper.parser import _make_case_id  # type: ignore[attr-defined]

    seed_source = "MV_Hondius_Seed"
    cases: list[Case] = []

    for stop in _HONDIUS_ITINERARY:
        loc = stop["location_name"]
        if loc in existing_location_names:
            logger.debug("Hondius seed: %r already covered; skipping.", loc)
            continue

        case_id = _make_case_id(seed_source, loc, stop["date_reported"])
        cases.append(
            Case(
                case_id=case_id,
                status=stop["status"],
                date_reported=stop["date_reported"],
                source=seed_source,
                latitude=stop["latitude"],
                longitude=stop["longitude"],
                location_name=loc,
                virus_strain="Andes",
                source_verified_at=source_verified_at,
                notes=stop["notes"],
            )
        )

    logger.info("Added %d MV Hondius itinerary seed cases.", len(cases))
    return cases


# ---------------------------------------------------------------------------
# Andes virus flagging (Task 5.8)
# ---------------------------------------------------------------------------
def _flag_andes_cases(cases: list) -> list:
    """
    Append an Andes-virus flag note to cases from South American sources
    where virus_strain == "Andes".

    This is a non-destructive annotation — the case_id and other fields
    are preserved; only the notes field is augmented if not already flagged.
    """
    from dataclasses import replace

    south_american_locations = {
        "argentina", "ushuaia", "patagonia", "chile", "brazil", "bolivia",
        "peru", "colombia", "venezuela", "ecuador", "paraguay", "uruguay",
    }

    flagged: list = []
    for case in cases:
        if (
            case.virus_strain == "Andes"
            and any(
                loc in case.location_name.lower()
                for loc in south_american_locations
            )
            and "⚠ Andes virus" not in case.notes
        ):
            new_notes = (
                f"⚠ Andes virus (South American source — person-to-person "
                f"transmission possible). {case.notes}"
            ).strip()
            case = replace(case, notes=new_notes)
        flagged.append(case)

    return flagged


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def main() -> None:
    run_start = datetime.now(tz=timezone.utc)
    logger.info("=" * 60)
    logger.info("Hantavirus Tracker scraper started at %s", run_start.isoformat())
    logger.info("=" * 60)

    from scraper.validator import validate_case
    from scraper.deduplicator import merge_with_existing
    from scraper.serializer import write_geojson

    # ------------------------------------------------------------------
    # 1. Load existing cases
    # ------------------------------------------------------------------
    existing_cases = _load_existing_cases()

    # ------------------------------------------------------------------
    # 2. Run all source collectors in parallel
    # ------------------------------------------------------------------
    collectors = _load_collectors()
    all_new_cases: list = []
    source_timestamps: dict[str, str] = {}
    collector_stats: dict[str, dict] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(collectors)) as executor:
        future_to_source = {
            executor.submit(collect_fn): source_name 
            for source_name, collect_fn in collectors
        }
        for future in concurrent.futures.as_completed(future_to_source):
            source_name = future_to_source[future]
            logger.info("--- Collecting from %s ---", source_name)
            try:
                cases, verified_at = future.result()
                source_timestamps[source_name] = verified_at
                collector_stats[source_name] = {
                    "status": "ok",
                    "cases_collected": len(cases),
                    "verified_at": verified_at,
                }
                all_new_cases.extend(cases)
                logger.info(
                    "[%s] Collected %d cases (verified_at=%s)",
                    source_name,
                    len(cases),
                    verified_at,
                )
            except Exception as exc:
                logger.error("[%s] Collector failed: %s", source_name, exc, exc_info=True)
                collector_stats[source_name] = {
                    "status": "error",
                    "error": str(exc),
                }

    logger.info("Total raw cases collected: %d", len(all_new_cases))

    # ------------------------------------------------------------------
    # 3. Validate — skip invalid cases
    # ------------------------------------------------------------------
    valid_cases: list = []
    invalid_count = 0
    for case in all_new_cases:
        errors = validate_case(case)
        if errors:
            logger.warning(
                "Invalid case %r (%s): %s",
                case.case_id[:12],
                case.location_name,
                "; ".join(errors),
            )
            invalid_count += 1
        else:
            valid_cases.append(case)

    logger.info(
        "Validation: %d valid, %d invalid (skipped)",
        len(valid_cases),
        invalid_count,
    )

    # ------------------------------------------------------------------
    # 4. Add MV Hondius itinerary seed cases (Task 5.8)
    # ------------------------------------------------------------------
    existing_location_names = {c.location_name for c in valid_cases}
    hondius_seed_verified_at = datetime.now(tz=timezone.utc).isoformat()
    source_timestamps["MV_Hondius_Seed"] = hondius_seed_verified_at

    hondius_cases = _build_hondius_seed_cases(
        existing_location_names, hondius_seed_verified_at
    )
    valid_cases.extend(hondius_cases)

    # ------------------------------------------------------------------
    # 5. Flag Andes virus cases from South American sources (Task 5.8)
    # ------------------------------------------------------------------
    valid_cases = _flag_andes_cases(valid_cases)

    # ------------------------------------------------------------------
    # 6. Merge with existing data and deduplicate
    # ------------------------------------------------------------------
    merged_cases = merge_with_existing(valid_cases, existing_cases)
    logger.info(
        "After merge+dedup: %d total cases (%d existing + %d new → %d merged)",
        len(merged_cases),
        len(existing_cases),
        len(valid_cases),
        len(merged_cases),
    )

    # ------------------------------------------------------------------
    # 7. Write GeoJSON output
    # ------------------------------------------------------------------
    _GEOJSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_geojson(merged_cases, collector_stats, str(_GEOJSON_PATH))
    logger.info("Wrote %d cases to %s", len(merged_cases), _GEOJSON_PATH)

    # ------------------------------------------------------------------
    # 8. Write run summary to scrape.log (appended section)
    # ------------------------------------------------------------------
    run_end = datetime.now(tz=timezone.utc)
    duration_s = (run_end - run_start).total_seconds()

    summary_lines = [
        "",
        "=" * 60,
        "RUN SUMMARY",
        "=" * 60,
        f"Started:          {run_start.isoformat()}",
        f"Finished:         {run_end.isoformat()}",
        f"Duration:         {duration_s:.1f}s",
        f"Output:           {_GEOJSON_PATH}",
        f"Total cases:      {len(merged_cases)}",
        f"  - Existing:     {len(existing_cases)}",
        f"  - New (valid):  {len(valid_cases)}",
        f"  - Invalid:      {invalid_count}",
        "",
        "Source results:",
    ]
    for src, stats in collector_stats.items():
        if stats["status"] == "ok":
            summary_lines.append(
                f"  {src:15s}  OK   {stats['cases_collected']:3d} cases  "
                f"verified_at={stats['verified_at']}"
            )
        else:
            summary_lines.append(
                f"  {src:15s}  ERR  {stats['error']}"
            )
    summary_lines.append("=" * 60)

    summary = "\n".join(summary_lines) + "\n"
    logger.info(summary)

    # Also append the summary directly to the log file for easy reading
    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(summary)

    logger.info("Scraper run complete.")


if __name__ == "__main__":
    main()
