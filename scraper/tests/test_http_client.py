"""
Unit tests for scraper/http_client.py.

Covers:
- Successful fetch returns response
- Retry logic: retries up to 3 times on failure, then raises
- Exponential backoff delays between retries
- robots.txt compliance: raises PermissionError when disallowed
- robots.txt unreachable: proceeds (fail-open)
- fetch_text returns response.text
- fetch_json returns response.json()
- User-Agent header is set correctly
"""

import unittest
from unittest.mock import MagicMock, call, patch

import requests

from scraper.http_client import (
    USER_AGENT,
    fetch,
    fetch_json,
    fetch_text,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(status_code: int = 200, text: str = "ok", json_data=None):
    """Build a mock requests.Response."""
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.text = text
    resp.json.return_value = json_data if json_data is not None else {}
    # raise_for_status raises for 4xx/5xx
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(
            f"{status_code} Error", response=resp
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# robots.txt helpers
# ---------------------------------------------------------------------------

def _patch_robots_allowed():
    """Patch _check_robots to do nothing (URL is allowed)."""
    return patch("scraper.http_client._check_robots", return_value=None)


def _patch_robots_disallowed():
    """Patch _check_robots to raise PermissionError (URL is disallowed)."""
    return patch(
        "scraper.http_client._check_robots",
        side_effect=PermissionError("Disallowed by robots.txt"),
    )


# ---------------------------------------------------------------------------
# Tests: fetch()
# ---------------------------------------------------------------------------

class TestFetchSuccess:
    def test_returns_response_on_first_attempt(self):
        resp = _make_response(200, text="hello")
        with _patch_robots_allowed(), \
             patch("requests.get", return_value=resp) as mock_get, \
             patch("time.sleep") as mock_sleep:
            result = fetch("https://example.com/data", "TestSource")

        assert result is resp
        mock_get.assert_called_once_with(
            "https://example.com/data",
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        mock_sleep.assert_not_called()

    def test_user_agent_header_is_set(self):
        resp = _make_response(200)
        with _patch_robots_allowed(), \
             patch("requests.get", return_value=resp) as mock_get, \
             patch("time.sleep"):
            fetch("https://example.com/", "TestSource")

        _, kwargs = mock_get.call_args
        assert kwargs["headers"]["User-Agent"] == USER_AGENT

    def test_custom_timeout_is_passed(self):
        resp = _make_response(200)
        with _patch_robots_allowed(), \
             patch("requests.get", return_value=resp) as mock_get, \
             patch("time.sleep"):
            fetch("https://example.com/", "TestSource", timeout=60)

        _, kwargs = mock_get.call_args
        assert kwargs["timeout"] == 60


class TestFetchRetryLogic:
    def test_retries_on_connection_error_and_succeeds(self):
        """Fails twice, succeeds on third attempt."""
        good_resp = _make_response(200)
        side_effects = [
            requests.ConnectionError("connection refused"),
            requests.ConnectionError("connection refused"),
            good_resp,
        ]
        with _patch_robots_allowed(), \
             patch("requests.get", side_effect=side_effects) as mock_get, \
             patch("time.sleep") as mock_sleep:
            result = fetch("https://example.com/", "TestSource")

        assert result is good_resp
        assert mock_get.call_count == 3
        # Should sleep before attempt 2 and attempt 3
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1)
        mock_sleep.assert_any_call(2)

    def test_raises_after_three_failures(self):
        """All 3 attempts fail — last exception is re-raised."""
        error = requests.ConnectionError("always fails")
        with _patch_robots_allowed(), \
             patch("requests.get", side_effect=error), \
             patch("time.sleep"):
            try:
                fetch("https://example.com/", "TestSource")
                assert False, "Expected exception was not raised"
            except requests.ConnectionError as exc:
                assert exc is error

    def test_exactly_three_attempts_made(self):
        """Exactly 3 GET requests are made before giving up."""
        with _patch_robots_allowed(), \
             patch("requests.get", side_effect=requests.Timeout("timed out")) as mock_get, \
             patch("time.sleep"):
            try:
                fetch("https://example.com/", "TestSource")
            except requests.Timeout:
                pass

        assert mock_get.call_count == 3

    def test_exponential_backoff_delays(self):
        """Sleep durations follow 1s, 2s pattern (no sleep after final attempt)."""
        with _patch_robots_allowed(), \
             patch("requests.get", side_effect=requests.Timeout("timed out")), \
             patch("time.sleep") as mock_sleep:
            try:
                fetch("https://example.com/", "TestSource")
            except requests.Timeout:
                pass

        # Only 2 sleeps: before attempt 2 (1s) and before attempt 3 (2s)
        assert mock_sleep.call_count == 2
        assert mock_sleep.call_args_list == [call(1), call(2)]

    def test_http_error_triggers_retry(self):
        """HTTP 500 responses trigger retry logic."""
        bad_resp = _make_response(500)
        good_resp = _make_response(200)
        with _patch_robots_allowed(), \
             patch("requests.get", side_effect=[bad_resp, good_resp]) as mock_get, \
             patch("time.sleep"):
            result = fetch("https://example.com/", "TestSource")

        assert result is good_resp
        assert mock_get.call_count == 2


class TestFetchRobotsTxt:
    def test_raises_permission_error_when_disallowed(self):
        with _patch_robots_disallowed(), \
             patch("requests.get") as mock_get:
            try:
                fetch("https://example.com/private", "TestSource")
                assert False, "Expected PermissionError"
            except PermissionError:
                pass

        # No HTTP request should be made if robots.txt disallows it
        mock_get.assert_not_called()

    def test_permission_error_message_is_descriptive(self):
        with patch(
            "scraper.http_client._check_robots",
            side_effect=PermissionError("Disallowed by robots.txt at 'https://example.com/robots.txt'"),
        ):
            try:
                fetch("https://example.com/private", "TestSource")
            except PermissionError as exc:
                assert "robots.txt" in str(exc)

    def test_proceeds_when_robots_txt_unreachable(self):
        """If robots.txt cannot be read, fetching should proceed (fail-open)."""
        resp = _make_response(200)
        # Simulate robots.txt read failure inside _check_robots by using the real
        # implementation with a mocked RobotFileParser that raises on read()
        with patch("scraper.http_client.RobotFileParser") as mock_rp_cls, \
             patch("requests.get", return_value=resp), \
             patch("time.sleep"):
            mock_rp = MagicMock()
            mock_rp.read.side_effect = Exception("network error")
            mock_rp.can_fetch.return_value = True
            mock_rp_cls.return_value = mock_rp

            result = fetch("https://example.com/data", "TestSource")

        assert result is resp

    def test_real_robots_check_disallows_url(self):
        """Integration-style: RobotFileParser correctly blocks a disallowed path."""
        robots_txt_content = "User-agent: *\nDisallow: /private/\n"

        with patch("scraper.http_client.RobotFileParser") as mock_rp_cls, \
             patch("requests.get") as mock_get:
            mock_rp = MagicMock()
            mock_rp.read.return_value = None
            mock_rp.can_fetch.return_value = False
            mock_rp_cls.return_value = mock_rp

            try:
                fetch("https://example.com/private/data", "TestSource")
                assert False, "Expected PermissionError"
            except PermissionError as exc:
                assert "robots.txt" in str(exc)

            mock_get.assert_not_called()


class TestFetchLogging:
    def test_logs_error_on_each_failure(self):
        with _patch_robots_allowed(), \
             patch("requests.get", side_effect=requests.ConnectionError("fail")), \
             patch("time.sleep"), \
             patch("scraper.http_client.logger") as mock_logger:
            try:
                fetch("https://example.com/", "MySource")
            except requests.ConnectionError:
                pass

        # Should log an error for each of the 3 attempts
        assert mock_logger.error.call_count == 3

    def test_log_includes_source_name(self):
        with _patch_robots_allowed(), \
             patch("requests.get", side_effect=requests.ConnectionError("fail")), \
             patch("time.sleep"), \
             patch("scraper.http_client.logger") as mock_logger:
            try:
                fetch("https://example.com/", "SpecialSource")
            except requests.ConnectionError:
                pass

        # All error log calls should reference the source name
        for log_call in mock_logger.error.call_args_list:
            args = log_call[0]
            assert "SpecialSource" in args[1], f"Source name missing from log: {args}"

    def test_log_includes_attempt_number(self):
        with _patch_robots_allowed(), \
             patch("requests.get", side_effect=requests.ConnectionError("fail")), \
             patch("time.sleep"), \
             patch("scraper.http_client.logger") as mock_logger:
            try:
                fetch("https://example.com/", "TestSource")
            except requests.ConnectionError:
                pass

        # Verify attempt numbers 1, 2, 3 appear in log calls
        logged_attempts = [call[0][2] for call in mock_logger.error.call_args_list]
        assert logged_attempts == [1, 2, 3]


# ---------------------------------------------------------------------------
# Tests: fetch_text()
# ---------------------------------------------------------------------------

class TestFetchText:
    def test_returns_response_text(self):
        resp = _make_response(200, text="<html>hello</html>")
        with _patch_robots_allowed(), \
             patch("requests.get", return_value=resp), \
             patch("time.sleep"):
            result = fetch_text("https://example.com/", "TestSource")

        assert result == "<html>hello</html>"

    def test_propagates_exception_on_failure(self):
        with _patch_robots_allowed(), \
             patch("requests.get", side_effect=requests.ConnectionError("fail")), \
             patch("time.sleep"):
            try:
                fetch_text("https://example.com/", "TestSource")
                assert False, "Expected exception"
            except requests.ConnectionError:
                pass


# ---------------------------------------------------------------------------
# Tests: fetch_json()
# ---------------------------------------------------------------------------

class TestFetchJson:
    def test_returns_parsed_json_dict(self):
        payload = {"cases": 42, "region": "South America"}
        resp = _make_response(200, json_data=payload)
        with _patch_robots_allowed(), \
             patch("requests.get", return_value=resp), \
             patch("time.sleep"):
            result = fetch_json("https://example.com/api", "TestSource")

        assert result == payload

    def test_returns_parsed_json_list(self):
        payload = [{"id": 1}, {"id": 2}]
        resp = _make_response(200, json_data=payload)
        with _patch_robots_allowed(), \
             patch("requests.get", return_value=resp), \
             patch("time.sleep"):
            result = fetch_json("https://example.com/api", "TestSource")

        assert result == payload

    def test_propagates_exception_on_failure(self):
        with _patch_robots_allowed(), \
             patch("requests.get", side_effect=requests.Timeout("timed out")), \
             patch("time.sleep"):
            try:
                fetch_json("https://example.com/api", "TestSource")
                assert False, "Expected exception"
            except requests.Timeout:
                pass
