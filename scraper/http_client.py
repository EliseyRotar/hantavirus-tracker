"""
Shared HTTP client for the Hantavirus Tracker scraper.

Provides retry-aware fetch functions that:
- Retry up to 3 times with exponential backoff (1s, 2s, 4s)
- Respect robots.txt via urllib.robotparser before fetching
- Log each failure with source name and attempt number
- Set a consistent User-Agent header for all requests

Requirements: 6.4, 6.5, 6.7
"""

import logging
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

logger = logging.getLogger(__name__)

USER_AGENT = "HantavirusTracker/1.0 (public health research)"
MAX_RETRIES = 3
BACKOFF_SECONDS = [1, 2, 4]  # delay before attempt 2, 3, and after final failure


def _check_robots(url: str) -> None:
    """
    Check robots.txt for the given URL.

    Raises PermissionError if the URL is disallowed for our User-Agent.
    Silently allows fetching if robots.txt cannot be retrieved (fail-open).
    """
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    rp = RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
    except Exception as exc:
        # If we can't read robots.txt, log a warning and proceed (fail-open)
        logger.warning("Could not read robots.txt from %s: %s", robots_url, exc)
        return

    if not rp.can_fetch(USER_AGENT, url):
        raise PermissionError(
            f"Fetching {url!r} is disallowed by robots.txt at {robots_url!r} "
            f"for User-Agent {USER_AGENT!r}"
        )


def fetch(url: str, source_name: str, *, timeout: int = 30) -> requests.Response:
    """
    Fetch a URL with retry logic and robots.txt compliance.

    Parameters
    ----------
    url : str
        The URL to fetch.
    source_name : str
        Human-readable name of the data source (used in log messages).
    timeout : int
        Request timeout in seconds (default: 30).

    Returns
    -------
    requests.Response
        The successful HTTP response.

    Raises
    ------
    PermissionError
        If robots.txt disallows fetching the URL.
    Exception
        The last exception raised after all retry attempts are exhausted.
    """
    # Check robots.txt before making any requests
    _check_robots(url)

    headers = {"User-Agent": USER_AGENT}
    last_exception: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response
        except Exception as exc:
            last_exception = exc
            logger.error(
                "[%s] Attempt %d/%d failed for %s: %s",
                source_name,
                attempt,
                MAX_RETRIES,
                url,
                exc,
            )
            if attempt < MAX_RETRIES:
                sleep_time = BACKOFF_SECONDS[attempt - 1]
                logger.debug(
                    "[%s] Retrying in %ds (attempt %d/%d)...",
                    source_name,
                    sleep_time,
                    attempt + 1,
                    MAX_RETRIES,
                )
                time.sleep(sleep_time)

    raise last_exception


def fetch_text(url: str, source_name: str) -> str:
    """
    Fetch a URL and return the response body as text.

    Parameters
    ----------
    url : str
        The URL to fetch.
    source_name : str
        Human-readable name of the data source.

    Returns
    -------
    str
        The response body decoded as text.
    """
    return fetch(url, source_name).text


def fetch_json(url: str, source_name: str) -> dict | list:
    """
    Fetch a URL and return the response body parsed as JSON.

    Parameters
    ----------
    url : str
        The URL to fetch.
    source_name : str
        Human-readable name of the data source.

    Returns
    -------
    dict | list
        The parsed JSON response body.
    """
    return fetch(url, source_name).json()
