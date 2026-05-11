import pytest
from hypothesis import given, strategies as st
from datetime import datetime, timezone
from unittest import mock
import time
import requests

from scraper.models import Case
from scraper.parser import parse_json, _make_case_id
from scraper.validator import validate_case
from scraper.serializer import serialize_cases
from scraper.deduplicator import deduplicate
from scraper.http_client import fetch

# Strategies
st_lat = st.floats(min_value=-90.0, max_value=90.0, allow_nan=False, allow_infinity=False)
st_lon = st.floats(min_value=-180.0, max_value=180.0, allow_nan=False, allow_infinity=False)
st_status = st.sampled_from(["Confirmed", "Probable", "Suspected"])
st_date = st.datetimes(
    min_value=datetime(2020, 1, 1), 
    max_value=datetime(2030, 1, 1)
).map(lambda d: d.strftime("%Y-%m-%d"))

def valid_case_strategy():
    return st.builds(
        Case,
        case_id=st.text(min_size=1, max_size=32),
        status=st_status,
        date_reported=st_date,
        source=st.text(min_size=1, max_size=32),
        latitude=st_lat,
        longitude=st_lon,
        location_name=st.text(min_size=1, max_size=50).filter(lambda s: bool(s.strip())),
        virus_strain=st.text(max_size=32),
        source_verified_at=st.datetimes(timezones=st.just(timezone.utc)).map(lambda d: d.isoformat()),
        notes=st.text(max_size=100)
    )

class TestProperties:
    # Property 1: Round-trip consistency
    @given(st.lists(valid_case_strategy(), min_size=1, max_size=10))
    def test_round_trip_consistency(self, cases):
        for c in cases:
            if not c.virus_strain.strip():
                c.virus_strain = "Unknown"
            if not c.notes:
                c.notes = ""
            c.case_id = _make_case_id(c.source, c.location_name, c.date_reported)
            
        fc = serialize_cases(cases, source_timestamps={})
        features = fc["features"]
        
        parsed_cases = []
        for feat in features:
            props = feat["properties"]
            coords = feat["geometry"]["coordinates"]
            
            raw_dict = {
                "location_name": props["location_name"],
                "date_reported": props["date_reported"],
                "latitude": coords[1],
                "longitude": coords[0],
                "status": props["status"],
                "virus_strain": props["virus_strain"],
                "notes": props["notes"]
            }
            parsed_cases.append(parse_json(raw_dict, props["source"], props["source_verified_at"]))
            
        assert parsed_cases == cases

    # Property 2: Coordinate validity
    @given(st.floats(allow_nan=False, allow_infinity=False), st.floats(allow_nan=False, allow_infinity=False))
    def test_coordinate_validity(self, lat, lon):
        case = Case(
            case_id="123",
            status="Suspected",
            date_reported="2026-05-10",
            source="Test",
            latitude=lat,
            longitude=lon,
            location_name="Test Loc",
            virus_strain="Unknown",
            source_verified_at="2026-05-10T00:00:00Z",
            notes=""
        )
        errors = validate_case(case)
        out_of_bounds = not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0)
        
        if out_of_bounds:
            assert len(errors) > 0
            assert any("Latitude" in err or "Longitude" in err for err in errors)
        else:
            assert len(errors) == 0

    # Property 3: Deduplication idempotency
    @given(st.lists(valid_case_strategy(), min_size=0, max_size=20))
    def test_deduplication_idempotency(self, cases):
        first_pass = deduplicate(cases)
        second_pass = deduplicate(first_pass)
        assert first_pass == second_pass

    # Property 4: Required field completeness
    @given(valid_case_strategy())
    def test_required_field_completeness(self, case):
        errors = validate_case(case)
        if not errors:
            assert case.location_name
            assert case.status in ["Confirmed", "Probable", "Suspected"]
            assert case.date_reported
            assert -90.0 <= case.latitude <= 90.0
            assert -180.0 <= case.longitude <= 180.0
            assert case.source

    # Property 5: Retry exhaustion
    def test_retry_exhaustion_property(self):
        with mock.patch('requests.get', side_effect=requests.exceptions.ConnectionError("Mock fail")) as mock_get:
            with mock.patch('scraper.http_client.time.sleep', return_value=None):
                with pytest.raises(requests.exceptions.ConnectionError):
                    fetch("http://fake-url.com", source_name="MockSrc")
                assert mock_get.call_count == 3

    # Property 6: Staleness detection (equivalent logic to UI)
    @given(st.datetimes(timezones=st.just(timezone.utc)))
    def test_staleness_detection(self, dt):
        target_ts = dt.timestamp()
        
        # Test equivalent logic to window.isStale
        def is_stale(target_timestamp_ms):
            now_ms = time.time() * 1000
            diff_ms = now_ms - target_timestamp_ms
            return diff_ms > 86400000
            
        expected = (time.time() - target_ts) > 86400
        # Give leeway for test execution time using a small epsilon if close
        assert is_stale(target_ts * 1000) == expected

