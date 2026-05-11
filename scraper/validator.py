"""
Validator for Case dataclass instances.

Validates required fields, status values, and coordinate ranges.
Returns a list of error strings — an empty list means the case is valid.
"""

from __future__ import annotations

from scraper.constants import VALID_STATUSES
from scraper.models import Case


def validate_case(case: Case) -> list[str]:
    """Validate a Case instance and return a list of error strings.

    Parameters
    ----------
    case:
        The Case object to validate.

    Returns
    -------
    list[str]
        A list of human-readable error messages describing every validation
        failure found.  An empty list means the case is fully valid.
    """
    errors: list[str] = []

    # --- Required string fields must be non-empty ---
    if not isinstance(case.location_name, str) or not case.location_name.strip():
        errors.append(
            "location_name must be a non-empty string; "
            f"got {case.location_name!r}"
        )

    if not isinstance(case.date_reported, str) or not case.date_reported.strip():
        errors.append(
            "date_reported must be a non-empty string; "
            f"got {case.date_reported!r}"
        )

    if not isinstance(case.status, str) or not case.status.strip():
        errors.append(
            "status must be a non-empty string; "
            f"got {case.status!r}"
        )
    elif case.status not in VALID_STATUSES:
        errors.append(
            f"status must be one of {sorted(VALID_STATUSES)}; "
            f"got {case.status!r}"
        )

    # --- Coordinate range checks ---
    if not (-90.0 <= case.latitude <= 90.0):
        errors.append(
            f"latitude must be in [-90, 90]; got {case.latitude!r}"
        )

    if not (-180.0 <= case.longitude <= 180.0):
        errors.append(
            f"longitude must be in [-180, 180]; got {case.longitude!r}"
        )

    return errors
