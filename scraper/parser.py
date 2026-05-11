"""
Parser for hantavirus case data from multiple source formats.

Supports JSON (dict), XML (lxml/ElementTree element), and CSV (DictReader row)
inputs, converting each into a standardized Case object.

Case ID generation
------------------
Each Case gets a deterministic ``case_id`` computed as the SHA-256 hex digest
of the concatenation ``<source>|<location_name>|<date_reported>``.  This means
the same logical case always maps to the same ID regardless of when or how it
was collected.

Field mapping (all formats)
---------------------------
- location_name : "location_name" or "location"
- status        : "status"  (default "Suspected" if missing)
- date_reported : "date_reported" or "date"
- latitude      : "latitude" or "lat"
- longitude     : "longitude" or "lon" or "lng"
- virus_strain  : "virus_strain" or "strain"  (default "Unknown")
- notes         : "notes"  (default "")
"""

from __future__ import annotations

import hashlib
from typing import Any

from scraper.constants import VALID_STATUSES
from scraper.models import Case

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _make_case_id(source: str, location_name: str, date_reported: str) -> str:
    """Return a deterministic SHA-256 hex digest for the given triple."""
    raw = f"{source}|{location_name}|{date_reported}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _get(mapping: dict, *keys: str, default: Any = None) -> Any:
    """Return the first non-None value found for any of *keys* in *mapping*."""
    for key in keys:
        value = mapping.get(key)
        if value is not None:
            return value
    return default


def _require_str(value: Any, field_name: str) -> str:
    """Coerce *value* to a non-empty string or raise ValueError."""
    if value is None:
        raise ValueError(f"Missing required field: '{field_name}'")
    s = str(value).strip()
    if not s:
        raise ValueError(f"Required field '{field_name}' must not be empty")
    return s


def _parse_float(value: Any, field_name: str) -> float:
    """Coerce *value* to float or raise a descriptive ValueError."""
    if value is None:
        raise ValueError(f"Missing required field: '{field_name}'")
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(
            f"Field '{field_name}' must be a numeric value; got {value!r}"
        )


def _normalise_status(raw: Any) -> str:
    """Return a valid status string, defaulting to 'Suspected' if absent."""
    if raw is None:
        return "Suspected"
    s = str(raw).strip()
    if not s:
        return "Suspected"
    if s not in VALID_STATUSES:
        raise ValueError(
            f"Field 'status' must be one of {sorted(VALID_STATUSES)}; got {s!r}"
        )
    return s


def _build_case(
    location_name: str,
    status: str,
    date_reported: str,
    latitude: float,
    longitude: float,
    virus_strain: str,
    notes: str,
    source: str,
    source_verified_at: str,
) -> Case:
    """Assemble and return a Case with a freshly computed case_id."""
    case_id = _make_case_id(source, location_name, date_reported)
    return Case(
        case_id=case_id,
        status=status,
        date_reported=date_reported,
        source=source,
        latitude=latitude,
        longitude=longitude,
        location_name=location_name,
        virus_strain=virus_strain,
        source_verified_at=source_verified_at,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_json(data: dict, source: str, source_verified_at: str) -> Case:
    """Parse a single case dict (from a JSON source) into a Case object.

    Parameters
    ----------
    data:
        A flat dictionary containing case fields.
    source:
        Identifier of the originating data source (e.g. ``"WHO"``).
    source_verified_at:
        ISO 8601 timestamp of the last successful fetch from the source.

    Returns
    -------
    Case
        A fully populated Case object.

    Raises
    ------
    ValueError
        If any required field is missing or invalid.
    """
    location_name = _require_str(
        _get(data, "location_name", "location"), "location_name"
    )
    date_reported = _require_str(
        _get(data, "date_reported", "date"), "date_reported"
    )
    latitude = _parse_float(_get(data, "latitude", "lat"), "latitude")
    longitude = _parse_float(_get(data, "longitude", "lon", "lng"), "longitude")
    status = _normalise_status(_get(data, "status"))
    virus_strain = str(_get(data, "virus_strain", "strain", default="Unknown")).strip() or "Unknown"
    notes = str(_get(data, "notes", default="") or "")

    return _build_case(
        location_name=location_name,
        status=status,
        date_reported=date_reported,
        latitude=latitude,
        longitude=longitude,
        virus_strain=virus_strain,
        notes=notes,
        source=source,
        source_verified_at=source_verified_at,
    )


def parse_xml_element(element, source: str, source_verified_at: str) -> Case:
    """Parse an lxml / ElementTree element into a Case object.

    The element is expected to have child elements (or attributes) whose
    *tag* (or *name*) matches the field mapping described in the module
    docstring.  Both child-element text and element attributes are
    consulted, with child elements taking priority.

    Parameters
    ----------
    element:
        An ``xml.etree.ElementTree.Element`` or lxml ``_Element``.
    source:
        Identifier of the originating data source.
    source_verified_at:
        ISO 8601 timestamp of the last successful fetch.

    Returns
    -------
    Case

    Raises
    ------
    ValueError
        If any required field is missing or invalid.
    """
    # Build a flat dict from child element text values, then fall back to
    # element attributes so callers can use either representation.
    flat: dict[str, str] = {}

    # Attributes first (lower priority)
    flat.update(element.attrib)

    # Child element text values override attributes
    for child in element:
        tag = child.tag
        # Strip namespace prefix if present: "{http://...}tag" → "tag"
        if "}" in tag:
            tag = tag.split("}", 1)[1]
        text = (child.text or "").strip()
        if text:
            flat[tag] = text

    return parse_json(flat, source, source_verified_at)


def parse_csv_row(row: dict, source: str, source_verified_at: str) -> Case:
    """Parse a ``csv.DictReader`` row into a Case object.

    Parameters
    ----------
    row:
        A dict produced by ``csv.DictReader`` (all values are strings).
    source:
        Identifier of the originating data source.
    source_verified_at:
        ISO 8601 timestamp of the last successful fetch.

    Returns
    -------
    Case

    Raises
    ------
    ValueError
        If any required field is missing or invalid.
    """
    # csv.DictReader may produce empty strings for missing columns; treat
    # empty strings the same as None so _get / _require_str handle them.
    cleaned = {k: (v if v != "" else None) for k, v in row.items()}
    return parse_json(cleaned, source, source_verified_at)


def parse_cases_from_json(
    data: list[dict],
    source: str,
    source_verified_at: str,
) -> tuple[list[Case], list[str]]:
    """Parse a list of case dicts, collecting successes and errors separately.

    Parameters
    ----------
    data:
        A list of flat dicts, each representing one case.
    source:
        Identifier of the originating data source.
    source_verified_at:
        ISO 8601 timestamp of the last successful fetch.

    Returns
    -------
    tuple[list[Case], list[str]]
        A 2-tuple of ``(cases, errors)`` where *cases* contains every
        successfully parsed Case and *errors* contains one descriptive
        string per failed row.
    """
    cases: list[Case] = []
    errors: list[str] = []

    for index, item in enumerate(data):
        try:
            cases.append(parse_json(item, source, source_verified_at))
        except (ValueError, TypeError, AttributeError) as exc:
            errors.append(f"Row {index}: {exc}")

    return cases, errors
