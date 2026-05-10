"""
Unit tests for scraper/parser.py.

Covers:
- parse_json: happy path, field aliases, defaults, missing required fields,
  invalid coordinates, invalid status
- parse_xml_element: child-element text and attribute fallback
- parse_csv_row: normal row, empty-string handling
- parse_cases_from_json: mixed valid/invalid list
- case_id determinism and uniqueness
"""

from __future__ import annotations

import csv
import hashlib
import io
import xml.etree.ElementTree as ET

import pytest

from scraper.models import Case
from scraper.parser import (
    parse_cases_from_json,
    parse_csv_row,
    parse_json,
    parse_xml_element,
)

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

SOURCE = "TEST_SOURCE"
VERIFIED_AT = "2026-05-10T12:00:00Z"


def _minimal_dict(**overrides) -> dict:
    """Return the smallest valid case dict, with optional overrides."""
    base = {
        "location_name": "Ushuaia, Argentina",
        "date_reported": "2026-05-01",
        "latitude": -54.8,
        "longitude": -68.3,
    }
    base.update(overrides)
    return base


def _expected_case_id(location_name: str, date_reported: str) -> str:
    raw = f"{SOURCE}|{location_name}|{date_reported}"
    return hashlib.sha256(raw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# parse_json — happy path
# ---------------------------------------------------------------------------


class TestParseJsonHappyPath:
    def test_minimal_valid_dict_returns_case(self):
        case = parse_json(_minimal_dict(), SOURCE, VERIFIED_AT)
        assert isinstance(case, Case)
        assert case.location_name == "Ushuaia, Argentina"
        assert case.date_reported == "2026-05-01"
        assert case.latitude == pytest.approx(-54.8)
        assert case.longitude == pytest.approx(-68.3)

    def test_status_defaults_to_suspected_when_missing(self):
        case = parse_json(_minimal_dict(), SOURCE, VERIFIED_AT)
        assert case.status == "Suspected"

    def test_virus_strain_defaults_to_unknown_when_missing(self):
        case = parse_json(_minimal_dict(), SOURCE, VERIFIED_AT)
        assert case.virus_strain == "Unknown"

    def test_notes_defaults_to_empty_string_when_missing(self):
        case = parse_json(_minimal_dict(), SOURCE, VERIFIED_AT)
        assert case.notes == ""

    def test_source_and_verified_at_are_stored(self):
        case = parse_json(_minimal_dict(), SOURCE, VERIFIED_AT)
        assert case.source == SOURCE
        assert case.source_verified_at == VERIFIED_AT

    def test_all_fields_populated(self):
        data = {
            "location_name": "Ushuaia, Argentina",
            "date_reported": "2026-05-01",
            "latitude": -54.8,
            "longitude": -68.3,
            "status": "Confirmed",
            "virus_strain": "Andes",
            "notes": "Cluster case",
        }
        case = parse_json(data, SOURCE, VERIFIED_AT)
        assert case.status == "Confirmed"
        assert case.virus_strain == "Andes"
        assert case.notes == "Cluster case"


# ---------------------------------------------------------------------------
# parse_json — field aliases
# ---------------------------------------------------------------------------


class TestParseJsonFieldAliases:
    def test_location_alias(self):
        data = _minimal_dict()
        data.pop("location_name")
        data["location"] = "Buenos Aires, Argentina"
        case = parse_json(data, SOURCE, VERIFIED_AT)
        assert case.location_name == "Buenos Aires, Argentina"

    def test_date_alias(self):
        data = _minimal_dict()
        data.pop("date_reported")
        data["date"] = "2026-06-01"
        case = parse_json(data, SOURCE, VERIFIED_AT)
        assert case.date_reported == "2026-06-01"

    def test_lat_alias(self):
        data = _minimal_dict()
        data.pop("latitude")
        data["lat"] = 10.0
        case = parse_json(data, SOURCE, VERIFIED_AT)
        assert case.latitude == pytest.approx(10.0)

    def test_lon_alias(self):
        data = _minimal_dict()
        data.pop("longitude")
        data["lon"] = 20.0
        case = parse_json(data, SOURCE, VERIFIED_AT)
        assert case.longitude == pytest.approx(20.0)

    def test_lng_alias(self):
        data = _minimal_dict()
        data.pop("longitude")
        data["lng"] = -70.0
        case = parse_json(data, SOURCE, VERIFIED_AT)
        assert case.longitude == pytest.approx(-70.0)

    def test_strain_alias(self):
        data = _minimal_dict(strain="Sin Nombre")
        case = parse_json(data, SOURCE, VERIFIED_AT)
        assert case.virus_strain == "Sin Nombre"


# ---------------------------------------------------------------------------
# parse_json — status handling
# ---------------------------------------------------------------------------


class TestParseJsonStatus:
    @pytest.mark.parametrize("status", ["Confirmed", "Probable", "Suspected"])
    def test_valid_statuses_accepted(self, status):
        case = parse_json(_minimal_dict(status=status), SOURCE, VERIFIED_AT)
        assert case.status == status

    def test_invalid_status_raises_value_error(self):
        with pytest.raises(ValueError, match="status"):
            parse_json(_minimal_dict(status="Unknown"), SOURCE, VERIFIED_AT)

    def test_lowercase_status_raises_value_error(self):
        with pytest.raises(ValueError, match="status"):
            parse_json(_minimal_dict(status="confirmed"), SOURCE, VERIFIED_AT)

    def test_none_status_defaults_to_suspected(self):
        data = _minimal_dict()
        data["status"] = None
        case = parse_json(data, SOURCE, VERIFIED_AT)
        assert case.status == "Suspected"


# ---------------------------------------------------------------------------
# parse_json — missing / invalid required fields
# ---------------------------------------------------------------------------


class TestParseJsonMissingFields:
    def test_missing_location_name_raises(self):
        data = _minimal_dict()
        data.pop("location_name")
        with pytest.raises(ValueError, match="location_name"):
            parse_json(data, SOURCE, VERIFIED_AT)

    def test_missing_date_reported_raises(self):
        data = _minimal_dict()
        data.pop("date_reported")
        with pytest.raises(ValueError, match="date_reported"):
            parse_json(data, SOURCE, VERIFIED_AT)

    def test_missing_latitude_raises(self):
        data = _minimal_dict()
        data.pop("latitude")
        with pytest.raises(ValueError, match="latitude"):
            parse_json(data, SOURCE, VERIFIED_AT)

    def test_missing_longitude_raises(self):
        data = _minimal_dict()
        data.pop("longitude")
        with pytest.raises(ValueError, match="longitude"):
            parse_json(data, SOURCE, VERIFIED_AT)

    def test_non_numeric_latitude_raises(self):
        with pytest.raises(ValueError, match="latitude"):
            parse_json(_minimal_dict(latitude="not-a-number"), SOURCE, VERIFIED_AT)

    def test_non_numeric_longitude_raises(self):
        with pytest.raises(ValueError, match="longitude"):
            parse_json(_minimal_dict(longitude="bad"), SOURCE, VERIFIED_AT)

    def test_empty_location_name_raises(self):
        with pytest.raises(ValueError, match="location_name"):
            parse_json(_minimal_dict(location_name=""), SOURCE, VERIFIED_AT)

    def test_empty_date_reported_raises(self):
        with pytest.raises(ValueError, match="date_reported"):
            parse_json(_minimal_dict(date_reported="  "), SOURCE, VERIFIED_AT)


# ---------------------------------------------------------------------------
# parse_json — case_id determinism
# ---------------------------------------------------------------------------


class TestCaseIdDeterminism:
    def test_same_inputs_produce_same_case_id(self):
        data = _minimal_dict()
        case1 = parse_json(data, SOURCE, VERIFIED_AT)
        case2 = parse_json(data, SOURCE, VERIFIED_AT)
        assert case1.case_id == case2.case_id

    def test_case_id_matches_expected_sha256(self):
        data = _minimal_dict()
        case = parse_json(data, SOURCE, VERIFIED_AT)
        expected = _expected_case_id("Ushuaia, Argentina", "2026-05-01")
        assert case.case_id == expected

    def test_different_location_produces_different_case_id(self):
        case1 = parse_json(_minimal_dict(location_name="City A"), SOURCE, VERIFIED_AT)
        case2 = parse_json(_minimal_dict(location_name="City B"), SOURCE, VERIFIED_AT)
        assert case1.case_id != case2.case_id

    def test_different_date_produces_different_case_id(self):
        case1 = parse_json(_minimal_dict(date_reported="2026-01-01"), SOURCE, VERIFIED_AT)
        case2 = parse_json(_minimal_dict(date_reported="2026-01-02"), SOURCE, VERIFIED_AT)
        assert case1.case_id != case2.case_id

    def test_different_source_produces_different_case_id(self):
        data = _minimal_dict()
        case1 = parse_json(data, "WHO", VERIFIED_AT)
        case2 = parse_json(data, "CDC", VERIFIED_AT)
        assert case1.case_id != case2.case_id


# ---------------------------------------------------------------------------
# parse_xml_element
# ---------------------------------------------------------------------------


class TestParseXmlElement:
    def _make_element(self, fields: dict) -> ET.Element:
        root = ET.Element("case")
        for key, value in fields.items():
            child = ET.SubElement(root, key)
            child.text = str(value)
        return root

    def test_parses_child_elements(self):
        elem = self._make_element({
            "location_name": "Santiago, Chile",
            "date_reported": "2026-05-15",
            "latitude": "-33.45",
            "longitude": "-70.67",
            "status": "Probable",
        })
        case = parse_xml_element(elem, SOURCE, VERIFIED_AT)
        assert case.location_name == "Santiago, Chile"
        assert case.date_reported == "2026-05-15"
        assert case.latitude == pytest.approx(-33.45)
        assert case.longitude == pytest.approx(-70.67)
        assert case.status == "Probable"

    def test_falls_back_to_attributes(self):
        root = ET.Element("case", attrib={
            "location_name": "Lima, Peru",
            "date_reported": "2026-04-01",
            "latitude": "-12.05",
            "longitude": "-77.04",
        })
        case = parse_xml_element(root, SOURCE, VERIFIED_AT)
        assert case.location_name == "Lima, Peru"

    def test_child_elements_override_attributes(self):
        root = ET.Element("case", attrib={"location_name": "Attribute Location"})
        child = ET.SubElement(root, "location_name")
        child.text = "Child Location"
        # Add required fields via attributes
        root.attrib.update({
            "date_reported": "2026-05-01",
            "latitude": "-54.8",
            "longitude": "-68.3",
        })
        case = parse_xml_element(root, SOURCE, VERIFIED_AT)
        assert case.location_name == "Child Location"

    def test_namespace_stripped_from_tag(self):
        root = ET.Element("case")
        child = ET.SubElement(root, "{http://example.com/ns}location_name")
        child.text = "Namespaced Location"
        # Add other required fields
        for tag, val in [("date_reported", "2026-05-01"), ("latitude", "-54.8"), ("longitude", "-68.3")]:
            c = ET.SubElement(root, tag)
            c.text = val
        case = parse_xml_element(root, SOURCE, VERIFIED_AT)
        assert case.location_name == "Namespaced Location"

    def test_missing_required_field_raises(self):
        elem = self._make_element({
            "date_reported": "2026-05-01",
            "latitude": "-54.8",
            "longitude": "-68.3",
            # location_name intentionally omitted
        })
        with pytest.raises(ValueError, match="location_name"):
            parse_xml_element(elem, SOURCE, VERIFIED_AT)

    def test_location_alias_in_xml(self):
        elem = self._make_element({
            "location": "Bogotá, Colombia",
            "date_reported": "2026-05-01",
            "latitude": "4.71",
            "longitude": "-74.07",
        })
        case = parse_xml_element(elem, SOURCE, VERIFIED_AT)
        assert case.location_name == "Bogotá, Colombia"


# ---------------------------------------------------------------------------
# parse_csv_row
# ---------------------------------------------------------------------------


class TestParseCsvRow:
    def _csv_row(self, **fields) -> dict:
        """Simulate a csv.DictReader row (all values are strings)."""
        defaults = {
            "location_name": "Mendoza, Argentina",
            "date_reported": "2026-05-20",
            "latitude": "-32.89",
            "longitude": "-68.85",
        }
        defaults.update(fields)
        return {k: str(v) if v is not None else "" for k, v in defaults.items()}

    def test_parses_valid_csv_row(self):
        row = self._csv_row(status="Confirmed", virus_strain="Andes")
        case = parse_csv_row(row, SOURCE, VERIFIED_AT)
        assert case.location_name == "Mendoza, Argentina"
        assert case.status == "Confirmed"
        assert case.virus_strain == "Andes"

    def test_empty_string_treated_as_missing(self):
        """Empty CSV cells should trigger defaults, not errors for optional fields."""
        row = self._csv_row(status="", virus_strain="", notes="")
        case = parse_csv_row(row, SOURCE, VERIFIED_AT)
        assert case.status == "Suspected"
        assert case.virus_strain == "Unknown"
        assert case.notes == ""

    def test_missing_required_field_raises(self):
        row = self._csv_row()
        row["location_name"] = ""  # empty = missing
        with pytest.raises(ValueError, match="location_name"):
            parse_csv_row(row, SOURCE, VERIFIED_AT)

    def test_string_coordinates_are_coerced(self):
        row = self._csv_row(latitude="-10.5", longitude="105.3")
        case = parse_csv_row(row, SOURCE, VERIFIED_AT)
        assert case.latitude == pytest.approx(-10.5)
        assert case.longitude == pytest.approx(105.3)

    def test_real_csv_reader_integration(self):
        """End-to-end: parse a CSV string through csv.DictReader."""
        csv_content = (
            "location_name,date_reported,latitude,longitude,status\n"
            "Ushuaia,2026-05-01,-54.8,-68.3,Confirmed\n"
        )
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        case = parse_csv_row(rows[0], SOURCE, VERIFIED_AT)
        assert case.location_name == "Ushuaia"
        assert case.status == "Confirmed"


# ---------------------------------------------------------------------------
# parse_cases_from_json
# ---------------------------------------------------------------------------


class TestParseCasesFromJson:
    def test_all_valid_returns_cases_and_empty_errors(self):
        data = [_minimal_dict(), _minimal_dict(location_name="City B", date_reported="2026-06-01")]
        cases, errors = parse_cases_from_json(data, SOURCE, VERIFIED_AT)
        assert len(cases) == 2
        assert errors == []

    def test_all_invalid_returns_empty_cases_and_errors(self):
        data = [{"bad": "data"}, {"also": "bad"}]
        cases, errors = parse_cases_from_json(data, SOURCE, VERIFIED_AT)
        assert cases == []
        assert len(errors) == 2

    def test_mixed_valid_and_invalid(self):
        data = [
            _minimal_dict(),                    # valid
            {"missing": "required fields"},     # invalid
            _minimal_dict(location_name="B"),   # valid
        ]
        cases, errors = parse_cases_from_json(data, SOURCE, VERIFIED_AT)
        assert len(cases) == 2
        assert len(errors) == 1

    def test_error_messages_include_row_index(self):
        data = [{"bad": "row"}]
        _, errors = parse_cases_from_json(data, SOURCE, VERIFIED_AT)
        assert "Row 0" in errors[0]

    def test_empty_list_returns_empty_results(self):
        cases, errors = parse_cases_from_json([], SOURCE, VERIFIED_AT)
        assert cases == []
        assert errors == []

    def test_error_index_matches_position_in_input(self):
        data = [
            _minimal_dict(),        # index 0 — valid
            {"bad": "data"},        # index 1 — invalid
            _minimal_dict(),        # index 2 — valid
            {"also": "bad"},        # index 3 — invalid
        ]
        _, errors = parse_cases_from_json(data, SOURCE, VERIFIED_AT)
        assert any("Row 1" in e for e in errors)
        assert any("Row 3" in e for e in errors)
