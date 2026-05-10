"""
Core data model for the Hantavirus Tracker.

Defines the Case dataclass representing a single hantavirus case entry,
as specified in the design document.
"""

from dataclasses import dataclass, field


@dataclass
class Case:
    """
    Represents a single hantavirus case collected from a public health source.

    Fields
    ------
    case_id : str
        Deterministic hash of (source, location_name, date_reported).
        Used for deduplication and stable identification across runs.
    status : str
        One of "Confirmed", "Probable", or "Suspected".
    date_reported : str
        ISO 8601 date string (e.g. "2026-05-01").
    source : str
        Identifier of the data source (e.g. "WHO", "CDC", "ECDC").
    latitude : float
        Geographic latitude in decimal degrees [-90, 90].
    longitude : float
        Geographic longitude in decimal degrees [-180, 180].
    location_name : str
        Human-readable location name (e.g. "Ushuaia, Argentina").
    virus_strain : str
        Hantavirus strain name (e.g. "Andes", "Sin Nombre", "Unknown").
    source_verified_at : str
        ISO 8601 timestamp of the last successful fetch from the source.
    notes : str
        Optional free-text notes about the case.
    """

    case_id: str
    status: str           # "Confirmed" | "Probable" | "Suspected"
    date_reported: str    # ISO 8601 date string
    source: str           # source identifier
    latitude: float
    longitude: float
    location_name: str
    virus_strain: str     # e.g. "Andes", "Sin Nombre", "Unknown"
    source_verified_at: str  # ISO 8601 timestamp of last successful fetch
    notes: str = field(default="")

    # Valid status values
    VALID_STATUSES = frozenset({"Confirmed", "Probable", "Suspected"})
