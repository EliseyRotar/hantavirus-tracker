"""
GeoJSON serializer for hantavirus case data.

Converts a list of Case objects into a valid GeoJSON FeatureCollection,
including metadata with generation timestamp and per-source timestamps.

GeoJSON coordinate order
------------------------
Per the GeoJSON spec (RFC 7946), coordinates are [longitude, latitude].
This module enforces that ordering.

Output schema
-------------
{
  "type": "FeatureCollection",
  "metadata": {
    "generated_at": "<ISO 8601 UTC timestamp>",
    "source_timestamps": { "<source_id>": "<ISO 8601 timestamp>", ... }
  },
  "features": [
    {
      "type": "Feature",
      "geometry": { "type": "Point", "coordinates": [longitude, latitude] },
      "properties": {
        "case_id": "...",
        "status": "Confirmed",
        "date_reported": "2026-05-01",
        "source": "WHO",
        "latitude": -54.8,
        "longitude": -68.3,
        "location_name": "Ushuaia, Argentina",
        "virus_strain": "Andes",
        "source_verified_at": "2026-05-10T12:00:00Z",
        "notes": ""
      }
    }
  ]
}
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from scraper.models import Case


def _case_to_feature(case: Case) -> dict[str, Any]:
    """Convert a single Case into a GeoJSON Feature dict."""
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            # GeoJSON spec: [longitude, latitude]
            "coordinates": [case.longitude, case.latitude],
        },
        "properties": {
            "case_id": case.case_id,
            "status": case.status,
            "date_reported": case.date_reported,
            "source": case.source,
            "latitude": case.latitude,
            "longitude": case.longitude,
            "location_name": case.location_name,
            "virus_strain": case.virus_strain,
            "source_verified_at": case.source_verified_at,
            "notes": case.notes,
        },
    }


def serialize_cases(
    cases: list[Case],
    source_stats: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Serialize a list of Case objects into a GeoJSON FeatureCollection dict.

    Parameters
    ----------
    cases:
        List of Case objects to serialize.
    source_stats:
        Mapping of source identifier to a dict containing stats like
        ``verified_at`` and ``status``.

    Returns
    -------
    dict
        A valid GeoJSON FeatureCollection dictionary with ``type``,
        ``metadata``, and ``features`` keys.
    """
    generated_at = datetime.now(tz=timezone.utc).isoformat()

    return {
        "type": "FeatureCollection",
        "metadata": {
            "generated_at": generated_at,
            "source_stats": dict(source_stats),
        },
        "features": [_case_to_feature(case) for case in cases],
    }


def write_geojson(
    cases: list[Case],
    source_stats: dict[str, dict[str, Any]],
    path: str,
) -> None:
    """Serialize cases to GeoJSON and write the result to a file.

    Parameters
    ----------
    cases:
        List of Case objects to serialize.
    source_stats:
        Mapping of source identifier to status/timestamp metadata.
    path:
        Filesystem path where the GeoJSON file will be written.
        The file is created or overwritten.
    """
    geojson = serialize_cases(cases, source_stats)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(geojson, fh, indent=2, ensure_ascii=False)
        fh.write("\n")  # trailing newline for POSIX compatibility
