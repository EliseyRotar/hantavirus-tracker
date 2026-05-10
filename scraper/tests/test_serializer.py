"""
Unit tests for scraper/serializer.py.

Covers:
- serialize_cases: structure of the returned FeatureCollection
- serialize_cases: correct GeoJSON coordinate order [lon, lat]
- serialize_cases: all Case fields present in feature properties
- serialize_cases: metadata fields (generated_at, source_timestamps)
- serialize_cases: empty case list produces valid FeatureCollection
- write_geojson: file is written with 2-space indentation
- write_geojson: written file is valid JSON that round-trips correctly
"""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from scraper.models import Case
from scraper.serializer import serialize_cases, write_geojson


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_case(**overrides) -> Case:
    """Return a fully populated Case with sensible defaults."""
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
        notes="Test note",
    )
    defaults.update(overrides)
    return Case(**defaults)


SOURCE_TIMESTAMPS = {"WHO": "2026-05-10T12:00:00Z", "CDC": "2026-05-09T08:00:00Z"}


# ---------------------------------------------------------------------------
# serialize_cases — top-level structure
# ---------------------------------------------------------------------------


class TestSerializeCasesStructure:
    def test_returns_dict(self):
        result = serialize_cases([], {})
        assert isinstance(result, dict)

    def test_type_is_feature_collection(self):
        result = serialize_cases([], {})
        assert result["type"] == "FeatureCollection"

    def test_has_metadata_key(self):
        result = serialize_cases([], {})
        assert "metadata" in result

    def test_has_features_key(self):
        result = serialize_cases([], {})
        assert "features" in result

    def test_features_is_list(self):
        result = serialize_cases([], {})
        assert isinstance(result["features"], list)


# ---------------------------------------------------------------------------
# serialize_cases — metadata
# ---------------------------------------------------------------------------


class TestSerializeCasesMetadata:
    def test_metadata_has_generated_at(self):
        result = serialize_cases([], {})
        assert "generated_at" in result["metadata"]

    def test_generated_at_is_iso_string(self):
        result = serialize_cases([], {})
        generated_at = result["metadata"]["generated_at"]
        # Should be parseable as an ISO 8601 datetime
        from datetime import datetime
        # Python's fromisoformat handles the +00:00 offset produced by timezone.utc
        dt = datetime.fromisoformat(generated_at)
        assert dt is not None

    def test_metadata_has_source_timestamps(self):
        result = serialize_cases([], SOURCE_TIMESTAMPS)
        assert "source_timestamps" in result["metadata"]

    def test_source_timestamps_are_preserved(self):
        result = serialize_cases([], SOURCE_TIMESTAMPS)
        assert result["metadata"]["source_timestamps"] == SOURCE_TIMESTAMPS

    def test_empty_source_timestamps(self):
        result = serialize_cases([], {})
        assert result["metadata"]["source_timestamps"] == {}

    def test_source_timestamps_dict_is_a_copy(self):
        """Mutating the original dict should not affect the serialized output."""
        ts = {"WHO": "2026-05-10T12:00:00Z"}
        result = serialize_cases([], ts)
        ts["NEW"] = "2026-01-01T00:00:00Z"
        assert "NEW" not in result["metadata"]["source_timestamps"]


# ---------------------------------------------------------------------------
# serialize_cases — features
# ---------------------------------------------------------------------------


class TestSerializeCasesFeatures:
    def test_empty_cases_produces_empty_features(self):
        result = serialize_cases([], {})
        assert result["features"] == []

    def test_one_case_produces_one_feature(self):
        case = _make_case()
        result = serialize_cases([case], {})
        assert len(result["features"]) == 1

    def test_multiple_cases_produce_correct_count(self):
        cases = [_make_case(case_id=f"id{i}", location_name=f"City {i}") for i in range(5)]
        result = serialize_cases(cases, {})
        assert len(result["features"]) == 5

    def test_feature_type_is_feature(self):
        result = serialize_cases([_make_case()], {})
        assert result["features"][0]["type"] == "Feature"

    def test_feature_has_geometry(self):
        result = serialize_cases([_make_case()], {})
        assert "geometry" in result["features"][0]

    def test_feature_has_properties(self):
        result = serialize_cases([_make_case()], {})
        assert "properties" in result["features"][0]


# ---------------------------------------------------------------------------
# serialize_cases — geometry (coordinate order)
# ---------------------------------------------------------------------------


class TestSerializeCasesGeometry:
    def test_geometry_type_is_point(self):
        result = serialize_cases([_make_case()], {})
        assert result["features"][0]["geometry"]["type"] == "Point"

    def test_coordinates_are_lon_lat_order(self):
        """GeoJSON spec requires [longitude, latitude] — not [lat, lon]."""
        case = _make_case(latitude=-54.8, longitude=-68.3)
        result = serialize_cases([case], {})
        coords = result["features"][0]["geometry"]["coordinates"]
        assert coords[0] == pytest.approx(-68.3), "First coordinate should be longitude"
        assert coords[1] == pytest.approx(-54.8), "Second coordinate should be latitude"

    def test_coordinates_list_has_two_elements(self):
        result = serialize_cases([_make_case()], {})
        coords = result["features"][0]["geometry"]["coordinates"]
        assert len(coords) == 2

    def test_positive_coordinates(self):
        case = _make_case(latitude=51.5, longitude=-0.1)
        result = serialize_cases([case], {})
        coords = result["features"][0]["geometry"]["coordinates"]
        assert coords[0] == pytest.approx(-0.1)
        assert coords[1] == pytest.approx(51.5)


# ---------------------------------------------------------------------------
# serialize_cases — properties completeness
# ---------------------------------------------------------------------------


class TestSerializeCasesProperties:
    REQUIRED_FIELDS = {
        "case_id", "status", "date_reported", "source",
        "latitude", "longitude", "location_name",
        "virus_strain", "source_verified_at", "notes",
    }

    def test_all_required_fields_present(self):
        result = serialize_cases([_make_case()], {})
        props = result["features"][0]["properties"]
        for field in self.REQUIRED_FIELDS:
            assert field in props, f"Missing property: {field}"

    def test_case_id_matches(self):
        case = _make_case(case_id="deadbeef")
        result = serialize_cases([case], {})
        assert result["features"][0]["properties"]["case_id"] == "deadbeef"

    def test_status_matches(self):
        case = _make_case(status="Probable")
        result = serialize_cases([case], {})
        assert result["features"][0]["properties"]["status"] == "Probable"

    def test_date_reported_matches(self):
        case = _make_case(date_reported="2026-06-15")
        result = serialize_cases([case], {})
        assert result["features"][0]["properties"]["date_reported"] == "2026-06-15"

    def test_source_matches(self):
        case = _make_case(source="ECDC")
        result = serialize_cases([case], {})
        assert result["features"][0]["properties"]["source"] == "ECDC"

    def test_latitude_matches(self):
        case = _make_case(latitude=10.5)
        result = serialize_cases([case], {})
        assert result["features"][0]["properties"]["latitude"] == pytest.approx(10.5)

    def test_longitude_matches(self):
        case = _make_case(longitude=20.5)
        result = serialize_cases([case], {})
        assert result["features"][0]["properties"]["longitude"] == pytest.approx(20.5)

    def test_location_name_matches(self):
        case = _make_case(location_name="Buenos Aires, Argentina")
        result = serialize_cases([case], {})
        assert result["features"][0]["properties"]["location_name"] == "Buenos Aires, Argentina"

    def test_virus_strain_matches(self):
        case = _make_case(virus_strain="Sin Nombre")
        result = serialize_cases([case], {})
        assert result["features"][0]["properties"]["virus_strain"] == "Sin Nombre"

    def test_source_verified_at_matches(self):
        case = _make_case(source_verified_at="2026-05-10T12:00:00Z")
        result = serialize_cases([case], {})
        assert result["features"][0]["properties"]["source_verified_at"] == "2026-05-10T12:00:00Z"

    def test_notes_matches(self):
        case = _make_case(notes="Cluster case near port")
        result = serialize_cases([case], {})
        assert result["features"][0]["properties"]["notes"] == "Cluster case near port"

    def test_empty_notes_preserved(self):
        case = _make_case(notes="")
        result = serialize_cases([case], {})
        assert result["features"][0]["properties"]["notes"] == ""


# ---------------------------------------------------------------------------
# write_geojson — file output
# ---------------------------------------------------------------------------


class TestWriteGeojson:
    def test_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "cases.geojson")
            write_geojson([], {}, path)
            assert os.path.exists(path)

    def test_file_contains_valid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "cases.geojson")
            write_geojson([_make_case()], SOURCE_TIMESTAMPS, path)
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            assert data["type"] == "FeatureCollection"

    def test_file_uses_2_space_indentation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "cases.geojson")
            write_geojson([_make_case()], {}, path)
            with open(path, encoding="utf-8") as fh:
                content = fh.read()
            # 2-space indented JSON has lines starting with exactly 2 spaces
            lines = content.splitlines()
            indented_lines = [l for l in lines if l.startswith(" ")]
            assert indented_lines, "Expected indented lines in output"
            # No line should start with 4 spaces at the first indent level
            first_indent_lines = [l for l in indented_lines if not l.startswith("    ")]
            assert all(l.startswith("  ") for l in first_indent_lines)

    def test_written_features_match_input(self):
        case = _make_case()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "cases.geojson")
            write_geojson([case], {}, path)
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            assert len(data["features"]) == 1
            props = data["features"][0]["properties"]
            assert props["case_id"] == case.case_id
            assert props["location_name"] == case.location_name

    def test_written_coordinates_are_lon_lat(self):
        case = _make_case(latitude=-54.8, longitude=-68.3)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "cases.geojson")
            write_geojson([case], {}, path)
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            coords = data["features"][0]["geometry"]["coordinates"]
            assert coords[0] == pytest.approx(-68.3)
            assert coords[1] == pytest.approx(-54.8)

    def test_overwrites_existing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "cases.geojson")
            # Write once with one case
            write_geojson([_make_case()], {}, path)
            # Overwrite with empty
            write_geojson([], {}, path)
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            assert data["features"] == []

    def test_source_timestamps_in_written_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "cases.geojson")
            write_geojson([], SOURCE_TIMESTAMPS, path)
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            assert data["metadata"]["source_timestamps"] == SOURCE_TIMESTAMPS
