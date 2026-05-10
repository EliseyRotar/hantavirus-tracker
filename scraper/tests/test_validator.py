"""
Unit tests for scraper/validator.py.

Covers:
- Valid case passes with no errors
- Missing location_name returns an error
- Invalid status returns an error
- Out-of-range latitude returns an error
- Out-of-range longitude returns an error
"""

import pytest

from scraper.models import Case
from scraper.validator import validate_case


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_valid_case(**overrides) -> Case:
    """Return a fully valid Case, optionally overriding specific fields."""
    defaults = dict(
        case_id="abc123",
        status="Confirmed",
        date_reported="2026-05-01",
        source="WHO",
        latitude=-54.8,
        longitude=-68.3,
        location_name="Ushuaia, Argentina",
        virus_strain="Andes",
        source_verified_at="2026-05-10T12:00:00Z",
        notes="",
    )
    defaults.update(overrides)
    return Case(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestValidCase:
    def test_valid_case_returns_no_errors(self):
        case = _make_valid_case()
        assert validate_case(case) == []

    def test_all_valid_statuses_accepted(self):
        for status in ("Confirmed", "Probable", "Suspected"):
            case = _make_valid_case(status=status)
            assert validate_case(case) == [], f"Expected no errors for status={status!r}"

    def test_boundary_coordinates_are_valid(self):
        """Exact boundary values should be accepted."""
        for lat, lon in [(-90, -180), (90, 180), (0, 0), (-90, 180), (90, -180)]:
            case = _make_valid_case(latitude=lat, longitude=lon)
            errors = validate_case(case)
            assert errors == [], f"Expected no errors for lat={lat}, lon={lon}; got {errors}"


class TestMissingLocationName:
    def test_empty_string_location_name_returns_error(self):
        case = _make_valid_case(location_name="")
        errors = validate_case(case)
        assert len(errors) == 1
        assert "location_name" in errors[0]

    def test_whitespace_only_location_name_returns_error(self):
        case = _make_valid_case(location_name="   ")
        errors = validate_case(case)
        assert any("location_name" in e for e in errors)


class TestInvalidStatus:
    def test_unknown_status_returns_error(self):
        case = _make_valid_case(status="Unknown")
        errors = validate_case(case)
        assert len(errors) == 1
        assert "status" in errors[0]

    def test_empty_status_returns_error(self):
        case = _make_valid_case(status="")
        errors = validate_case(case)
        assert any("status" in e for e in errors)

    def test_case_sensitive_status_rejected(self):
        """Status values are case-sensitive; lowercase should be rejected."""
        case = _make_valid_case(status="confirmed")
        errors = validate_case(case)
        assert any("status" in e for e in errors)


class TestOutOfRangeLatitude:
    def test_latitude_above_90_returns_error(self):
        case = _make_valid_case(latitude=90.1)
        errors = validate_case(case)
        assert len(errors) == 1
        assert "latitude" in errors[0]

    def test_latitude_below_minus_90_returns_error(self):
        case = _make_valid_case(latitude=-90.1)
        errors = validate_case(case)
        assert len(errors) == 1
        assert "latitude" in errors[0]

    def test_extreme_latitude_returns_error(self):
        case = _make_valid_case(latitude=1000.0)
        errors = validate_case(case)
        assert any("latitude" in e for e in errors)


class TestOutOfRangeLongitude:
    def test_longitude_above_180_returns_error(self):
        case = _make_valid_case(longitude=180.1)
        errors = validate_case(case)
        assert len(errors) == 1
        assert "longitude" in errors[0]

    def test_longitude_below_minus_180_returns_error(self):
        case = _make_valid_case(longitude=-180.1)
        errors = validate_case(case)
        assert len(errors) == 1
        assert "longitude" in errors[0]

    def test_extreme_longitude_returns_error(self):
        case = _make_valid_case(longitude=-999.0)
        errors = validate_case(case)
        assert any("longitude" in e for e in errors)


class TestMultipleErrors:
    def test_multiple_invalid_fields_return_multiple_errors(self):
        """All validation failures should be reported, not just the first."""
        case = _make_valid_case(
            location_name="",
            status="BadStatus",
            latitude=200.0,
            longitude=400.0,
        )
        errors = validate_case(case)
        assert len(errors) == 4
