"""
Deduplication logic for the Hantavirus Tracker.

Cases are considered duplicates when they share the same composite key:
    (location_name, date_reported, source)

When duplicates exist, the one with the most recent ``source_verified_at``
timestamp is kept.  Order of first occurrence is preserved for non-duplicates.

Public API
----------
deduplicate(cases)
    Deduplicate a single list of Case objects.

merge_with_existing(new_cases, existing_cases)
    Merge new cases into an existing list, deduplicating across both.
"""

from __future__ import annotations

from typing import Tuple

from scraper.models import Case


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _composite_key(case: Case) -> Tuple[str, str, str]:
    """Return the (location_name, date_reported, source) composite key."""
    return (case.location_name, case.date_reported, case.source)


def _is_more_recent(candidate: Case, current: Case) -> bool:
    """Return True if *candidate* has a more recent source_verified_at than *current*.

    Comparison is done lexicographically on the ISO 8601 timestamp strings,
    which is correct as long as timestamps are in a consistent format
    (e.g. "2026-05-10T12:00:00Z").  An empty string is treated as the
    oldest possible timestamp.
    """
    return (candidate.source_verified_at or "") > (current.source_verified_at or "")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def deduplicate(cases: list[Case]) -> list[Case]:
    """Deduplicate *cases* by (location_name, date_reported, source).

    When two or more cases share the same composite key, the one with the
    most recent ``source_verified_at`` timestamp is kept.  The relative
    order of first-occurrence entries is preserved.

    Parameters
    ----------
    cases:
        Input list of Case objects (may contain duplicates).

    Returns
    -------
    list[Case]
        Deduplicated list in first-occurrence order.
    """
    # Maps composite key → index in `result` list
    seen: dict[Tuple[str, str, str], int] = {}
    result: list[Case] = []

    for case in cases:
        key = _composite_key(case)
        if key not in seen:
            # First time we see this key — append and record position.
            seen[key] = len(result)
            result.append(case)
        else:
            # Duplicate — keep the one with the more recent timestamp.
            idx = seen[key]
            if _is_more_recent(case, result[idx]):
                result[idx] = case

    return result


def merge_with_existing(
    new_cases: list[Case],
    existing_cases: list[Case],
) -> list[Case]:
    """Merge *new_cases* into *existing_cases*, deduplicating across both.

    Historical data (existing_cases) is preserved.  New cases are added
    where they do not duplicate an existing entry.  When a new case
    duplicates an existing one, the entry with the more recent
    ``source_verified_at`` timestamp wins.

    The returned list preserves the order of existing cases first, followed
    by genuinely new cases in their original order.

    Parameters
    ----------
    new_cases:
        Cases collected in the current scraper run.
    existing_cases:
        Cases already stored (e.g. loaded from ``data/cases.geojson``).

    Returns
    -------
    list[Case]
        Merged, deduplicated list.
    """
    # Combine existing first so their order is preserved, then new cases.
    combined = list(existing_cases) + list(new_cases)
    return deduplicate(combined)
