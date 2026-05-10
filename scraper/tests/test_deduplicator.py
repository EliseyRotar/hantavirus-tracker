"""
Unit tests for scraper/deduplicator.py.

Covers:
- deduplicate: empty list
- deduplicate: no duplicates — all cases preserved in order
- deduplicate: exact duplicates — only one kept
- deduplicate: duplicate key, keep most-recent source_verified_at
- deduplicate: first-occurrence order preserved
- deduplicate: multiple distinct keys, each deduplicated independently
- deduplicate: empty source_verified_at treated as oldest
- merge_with_existing: new cases added to existing
- merge_with_existing: existing cases preserved when no overlap
- merge_with_existing: duplicate across new/existing — winner by timestamp
- merge_with_existing: existing order preserved, new cases appended
- merge_with_existing: empty new_cases returns copy of existing
- merge_with_existing: empty existing_cases returns deduplicated new_cases
"""

from __future__ import annotations

import pytest

from scraper.models import Case
from scraper.deduplicator import deduplicate, merge_with_existing


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_case(
    location_name: str = "Ushuaia, Argentina",
    date_reported: str = "2026-05-01",
    source: str = "WHO",
    source_verified_at: str = "2026-05-10T12:00:00Z",
    **overrides,
) -> Case:
    """Return a Case with sensible defaults, overridable per-field."""
    defaults = dict(
        case_id="abc123",
        status="Confirmed",
        date_reported=date_reported,
        source=source,
        latitude=-54.8,
        longitude=-68.3,
        location_name=location_name,
        virus_strain="Andes",
        source_verified_at=source_verified_at,
        notes="",
    )
    defaults.update(overrides)
    return Case(**defaults)


# ---------------------------------------------------------------------------
# deduplicate — basic behaviour
# ---------------------------------------------------------------------------

class TestDeduplicateEmpty:
    def test_empty_list_returns_empty(self):
        assert deduplicate([]) == []


class TestDeduplicateNoDuplicates:
    def test_single_case_returned_unchanged(self):
        case = _make_case()
        result = deduplicate([case])
        assert result == [case]

    def test_distinct_locations_all_preserved(self):
        cases = [
            _make_case(location_name="City A"),
            _make_case(location_name="City B"),
            _make_case(location_name="City C"),
        ]
        result = deduplicate(cases)
        assert len(result) == 3

    def test_distinct_dates_all_preserved(self):
        cases = [
            _make_case(date_reported="2026-01-01"),
            _make_case(date_reported="2026-01-02"),
            _make_case(date_reported="2026-01-03"),
        ]
        result = deduplicate(cases)
        assert len(result) == 3

    def test_distinct_sources_all_preserved(self):
        cases = [
            _make_case(source="WHO"),
            _make_case(source="CDC"),
            _make_case(source="ECDC"),
        ]
        result = deduplicate(cases)
        assert len(result) == 3


class TestDeduplicateExactDuplicates:
    def test_two_identical_cases_returns_one(self):
        case = _make_case()
        result = deduplicate([case, case])
        assert len(result) == 1

    def test_three_identical_cases_returns_one(self):
        case = _make_case()
        result = deduplicate([case, case, case])
        assert len(result) == 1

    def test_duplicate_key_different_fields_returns_one(self):
        """Same composite key but different notes — still a duplicate."""
        case1 = _make_case(notes="first")
        case2 = _make_case(notes="second")
        result = deduplicate([case1, case2])
        assert len(result) == 1


# ---------------------------------------------------------------------------
# deduplicate — timestamp-based winner selection
# ---------------------------------------------------------------------------

class TestDeduplicateTimestampWinner:
    def test_more_recent_timestamp_wins(self):
        older = _make_case(source_verified_at="2026-05-01T00:00:00Z", notes="older")
        newer = _make_case(source_verified_at="2026-05-10T12:00:00Z", notes="newer")
        result = deduplicate([older, newer])
        assert len(result) == 1
        assert result[0].notes == "newer"

    def test_earlier_in_list_but_newer_timestamp_wins(self):
        newer = _make_case(source_verified_at="2026-05-10T12:00:00Z", notes="newer")
        older = _make_case(source_verified_at="2026-05-01T00:00:00Z", notes="older")
        result = deduplicate([newer, older])
        assert len(result) == 1
        assert result[0].notes == "newer"

    def test_equal_timestamps_first_occurrence_kept(self):
        ts = "2026-05-10T12:00:00Z"
        first = _make_case(source_verified_at=ts, notes="first")
        second = _make_case(source_verified_at=ts, notes="second")
        result = deduplicate([first, second])
        assert len(result) == 1
        assert result[0].notes == "first"

    def test_empty_source_verified_at_treated_as_oldest(self):
        empty_ts = _make_case(source_verified_at="", notes="no-timestamp")
        with_ts = _make_case(source_verified_at="2026-05-01T00:00:00Z", notes="has-timestamp")
        result = deduplicate([empty_ts, with_ts])
        assert result[0].notes == "has-timestamp"

    def test_empty_vs_empty_first_occurrence_kept(self):
        first = _make_case(source_verified_at="", notes="first")
        second = _make_case(source_verified_at="", notes="second")
        result = deduplicate([first, second])
        assert result[0].notes == "first"


# ---------------------------------------------------------------------------
# deduplicate — order preservation
# ---------------------------------------------------------------------------

class TestDeduplicateOrderPreservation:
    def test_first_occurrence_order_preserved(self):
        cases = [
            _make_case(location_name="A"),
            _make_case(location_name="B"),
            _make_case(location_name="C"),
        ]
        result = deduplicate(cases)
        assert [c.location_name for c in result] == ["A", "B", "C"]

    def test_duplicate_does_not_change_position(self):
        """The slot of the first occurrence is kept; only the value may change."""
        first = _make_case(location_name="A", source_verified_at="2026-01-01T00:00:00Z", notes="first")
        dup_newer = _make_case(location_name="A", source_verified_at="2026-06-01T00:00:00Z", notes="newer")
        other = _make_case(location_name="B")
        result = deduplicate([first, other, dup_newer])
        # "A" should still be at index 0, "B" at index 1
        assert result[0].location_name == "A"
        assert result[1].location_name == "B"
        assert len(result) == 2

    def test_interleaved_duplicates_preserve_first_occurrence_positions(self):
        a1 = _make_case(location_name="A", source_verified_at="2026-01-01T00:00:00Z")
        b = _make_case(location_name="B")
        a2 = _make_case(location_name="A", source_verified_at="2026-06-01T00:00:00Z")
        result = deduplicate([a1, b, a2])
        assert [c.location_name for c in result] == ["A", "B"]


# ---------------------------------------------------------------------------
# deduplicate — composite key semantics
# ---------------------------------------------------------------------------

class TestDeduplicateCompositeKey:
    def test_same_location_different_date_not_duplicate(self):
        c1 = _make_case(location_name="City", date_reported="2026-01-01")
        c2 = _make_case(location_name="City", date_reported="2026-01-02")
        assert len(deduplicate([c1, c2])) == 2

    def test_same_date_different_location_not_duplicate(self):
        c1 = _make_case(location_name="City A", date_reported="2026-01-01")
        c2 = _make_case(location_name="City B", date_reported="2026-01-01")
        assert len(deduplicate([c1, c2])) == 2

    def test_same_location_date_different_source_not_duplicate(self):
        c1 = _make_case(source="WHO")
        c2 = _make_case(source="CDC")
        assert len(deduplicate([c1, c2])) == 2

    def test_all_three_key_fields_must_match_for_duplicate(self):
        base = _make_case(location_name="City", date_reported="2026-01-01", source="WHO")
        diff_loc = _make_case(location_name="Other", date_reported="2026-01-01", source="WHO")
        diff_date = _make_case(location_name="City", date_reported="2026-01-02", source="WHO")
        diff_src = _make_case(location_name="City", date_reported="2026-01-01", source="CDC")
        exact_dup = _make_case(location_name="City", date_reported="2026-01-01", source="WHO")
        result = deduplicate([base, diff_loc, diff_date, diff_src, exact_dup])
        assert len(result) == 4  # base + 3 distinct, exact_dup removed


# ---------------------------------------------------------------------------
# merge_with_existing — basic behaviour
# ---------------------------------------------------------------------------

class TestMergeWithExistingBasic:
    def test_empty_both_returns_empty(self):
        assert merge_with_existing([], []) == []

    def test_empty_new_returns_existing(self):
        existing = [_make_case(location_name="A"), _make_case(location_name="B")]
        result = merge_with_existing([], existing)
        assert result == existing

    def test_empty_existing_returns_deduplicated_new(self):
        new = [_make_case(location_name="A"), _make_case(location_name="A")]
        result = merge_with_existing(new, [])
        assert len(result) == 1

    def test_non_overlapping_cases_all_preserved(self):
        existing = [_make_case(location_name="A", source="WHO")]
        new = [_make_case(location_name="B", source="CDC")]
        result = merge_with_existing(new, existing)
        assert len(result) == 2

    def test_existing_cases_appear_before_new_cases(self):
        existing = [_make_case(location_name="Existing")]
        new = [_make_case(location_name="New", source="CDC")]
        result = merge_with_existing(new, existing)
        assert result[0].location_name == "Existing"
        assert result[1].location_name == "New"


# ---------------------------------------------------------------------------
# merge_with_existing — deduplication across lists
# ---------------------------------------------------------------------------

class TestMergeWithExistingDeduplication:
    def test_duplicate_across_lists_returns_one(self):
        case = _make_case()
        result = merge_with_existing([case], [case])
        assert len(result) == 1

    def test_newer_new_case_replaces_older_existing(self):
        existing = _make_case(source_verified_at="2026-01-01T00:00:00Z", notes="old")
        new = _make_case(source_verified_at="2026-06-01T00:00:00Z", notes="new")
        result = merge_with_existing([new], [existing])
        assert len(result) == 1
        assert result[0].notes == "new"

    def test_older_new_case_does_not_replace_newer_existing(self):
        existing = _make_case(source_verified_at="2026-06-01T00:00:00Z", notes="existing-newer")
        new = _make_case(source_verified_at="2026-01-01T00:00:00Z", notes="new-older")
        result = merge_with_existing([new], [existing])
        assert len(result) == 1
        assert result[0].notes == "existing-newer"

    def test_multiple_new_cases_some_duplicate(self):
        existing = [
            _make_case(location_name="A", source="WHO"),
            _make_case(location_name="B", source="WHO"),
        ]
        new = [
            _make_case(location_name="A", source="WHO"),   # duplicate
            _make_case(location_name="C", source="CDC"),   # new
        ]
        result = merge_with_existing(new, existing)
        assert len(result) == 3
        locations = {c.location_name for c in result}
        assert locations == {"A", "B", "C"}

    def test_historical_data_preserved_when_no_overlap(self):
        existing = [_make_case(location_name=f"City {i}") for i in range(5)]
        new = [_make_case(location_name="New City", source="CDC")]
        result = merge_with_existing(new, existing)
        assert len(result) == 6

    def test_existing_order_preserved_new_appended(self):
        existing = [
            _make_case(location_name="E1"),
            _make_case(location_name="E2"),
        ]
        new = [
            _make_case(location_name="N1", source="CDC"),
            _make_case(location_name="N2", source="ECDC"),
        ]
        result = merge_with_existing(new, existing)
        assert result[0].location_name == "E1"
        assert result[1].location_name == "E2"
        assert result[2].location_name == "N1"
        assert result[3].location_name == "N2"
