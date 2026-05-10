"""
End-to-end checkpoint test for the hantavirus scraper.

Runs the full scraper pipeline with all HTTP calls mocked (sources fall back
to their hardcoded seed data), then validates the resulting GeoJSON output.

Covers:
- Scraper completes without raising exceptions
- data/cases.geojson is written with type=FeatureCollection
- features list is non-empty
- All feature coordinates are valid (lon ∈ [-180,180], lat ∈ [-90,90])
- All required properties are present on every feature
- All status values are valid
- metadata contains generated_at and source_timestamps
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import requests


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REQUIRED_PROPERTIES = {
    "case_id",
    "status",
    "date_reported",
    "source",
    "latitude",
    "longitude",
    "location_name",
    "virus_strain",
    "source_verified_at",
    "notes",
}

VALID_STATUSES = {"Confirmed", "Probable", "Suspected"}


def _run_scraper_with_mocked_http(output_path: str) -> None:
    """Run main() with all HTTP calls mocked to raise ConnectionError.

    Sources fall back to their hardcoded seed data, so the pipeline
    exercises the full validate → deduplicate → serialize path without
    any real network access.
    """
    # Patch the geojson output path so we write to a temp file.
    # Also patch time.sleep so exponential-backoff retries don't actually wait.
    with patch("scraper.http_client._check_robots", return_value=None), \
         patch("requests.get", side_effect=requests.ConnectionError("mocked")), \
         patch("scraper.http_client.time.sleep", return_value=None), \
         patch("scraper.main._GEOJSON_PATH", Path(output_path)):
        # Re-import main inside the patch context to pick up the patched path
        import scraper.main as scraper_main
        scraper_main._GEOJSON_PATH = Path(output_path)
        scraper_main.main()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestEndToEndScraper:
    """End-to-end scraper checkpoint tests."""

    @pytest.fixture(autouse=True)
    def _tmp_geojson(self, tmp_path):
        """Provide a temporary output path and run the scraper once."""
        self.output_path = str(tmp_path / "cases.geojson")
        _run_scraper_with_mocked_http(self.output_path)
        with open(self.output_path, encoding="utf-8") as fh:
            self.data = json.load(fh)

    # --- File and top-level structure ---

    def test_output_file_exists(self):
        assert os.path.exists(self.output_path)

    def test_type_is_feature_collection(self):
        assert self.data["type"] == "FeatureCollection"

    def test_features_key_present(self):
        assert "features" in self.data

    def test_features_is_list(self):
        assert isinstance(self.data["features"], list)

    def test_features_non_empty(self):
        assert len(self.data["features"]) > 0, "Expected at least one feature in output"

    # --- Metadata ---

    def test_metadata_present(self):
        assert "metadata" in self.data

    def test_metadata_has_generated_at(self):
        assert "generated_at" in self.data["metadata"]

    def test_metadata_generated_at_is_iso_string(self):
        from datetime import datetime
        dt = datetime.fromisoformat(self.data["metadata"]["generated_at"])
        assert dt is not None

    def test_metadata_has_source_timestamps(self):
        assert "source_timestamps" in self.data["metadata"]

    def test_source_timestamps_non_empty(self):
        assert len(self.data["metadata"]["source_timestamps"]) > 0

    def test_all_five_sources_present_in_timestamps(self):
        ts = self.data["metadata"]["source_timestamps"]
        for source in ("WHO", "ECDC", "CDC", "HealthMap", "GDELT"):
            assert source in ts, f"Missing source timestamp for {source}"

    # --- Feature structure ---

    def test_all_features_have_type_feature(self):
        for i, feature in enumerate(self.data["features"]):
            assert feature.get("type") == "Feature", f"Feature {i} has wrong type"

    def test_all_features_have_geometry(self):
        for i, feature in enumerate(self.data["features"]):
            assert "geometry" in feature, f"Feature {i} missing geometry"

    def test_all_features_have_properties(self):
        for i, feature in enumerate(self.data["features"]):
            assert "properties" in feature, f"Feature {i} missing properties"

    # --- Coordinate validity ---

    def test_all_coordinates_valid_longitude(self):
        invalid = []
        for i, feature in enumerate(self.data["features"]):
            lon = feature["geometry"]["coordinates"][0]
            if not (-180 <= lon <= 180):
                invalid.append(f"Feature {i}: lon={lon}")
        assert not invalid, f"Invalid longitudes: {invalid}"

    def test_all_coordinates_valid_latitude(self):
        invalid = []
        for i, feature in enumerate(self.data["features"]):
            lat = feature["geometry"]["coordinates"][1]
            if not (-90 <= lat <= 90):
                invalid.append(f"Feature {i}: lat={lat}")
        assert not invalid, f"Invalid latitudes: {invalid}"

    def test_coordinates_are_lon_lat_order(self):
        """GeoJSON spec: coordinates are [longitude, latitude]."""
        for i, feature in enumerate(self.data["features"]):
            coords = feature["geometry"]["coordinates"]
            assert len(coords) == 2, f"Feature {i}: expected 2 coordinates"
            lon, lat = coords
            # Longitude range is wider than latitude, so if they were swapped
            # a lat value > 90 would appear as lon — catch that here.
            assert -90 <= lat <= 90, f"Feature {i}: second coord {lat} looks like lon not lat"

    # --- Required properties ---

    def test_all_required_properties_present(self):
        missing = []
        for i, feature in enumerate(self.data["features"]):
            props = feature.get("properties", {})
            for prop in REQUIRED_PROPERTIES:
                if prop not in props:
                    missing.append(f"Feature {i}: missing '{prop}'")
        assert not missing, f"Missing properties: {missing}"

    # --- Status validity ---

    def test_all_statuses_valid(self):
        invalid = []
        for i, feature in enumerate(self.data["features"]):
            status = feature["properties"].get("status")
            if status not in VALID_STATUSES:
                invalid.append(f"Feature {i}: status={status!r}")
        assert not invalid, f"Invalid statuses: {invalid}"

    # --- Source coverage ---

    def test_cases_from_multiple_sources(self):
        sources = {f["properties"]["source"] for f in self.data["features"]}
        assert len(sources) >= 2, f"Expected cases from multiple sources; got {sources}"

    def test_andes_virus_cases_present(self):
        andes = [f for f in self.data["features"] if f["properties"].get("virus_strain") == "Andes"]
        assert len(andes) > 0, "Expected at least one Andes virus case"
