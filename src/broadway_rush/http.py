"""Shared polite HTTP client: fixed minimum gap between requests + exponential backoff."""

import logging
import random
import time

import requests

log = logging.getLogger(__name__)

USER_AGENT = "broadway-rush/0.1 (personal research project; polite, rate-limited)"
OFFLINE_WAIT = 300  # seconds between attempts while the network is down


class PoliteClient:
    def __init__(self, min_interval: float = 1.0, max_retries: int = 8, max_backoff: float = 120.0,
                 max_offline: float = 3 * 3600):
        self.min_interval = min_interval
        self.max_retries = max_retries
        self.max_offline = max_offline
        self.max_backoff = max_backoff
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._last = 0.0
        self.n_requests = 0

    def _wait_turn(self):
        gap = time.monotonic() - self._last
        if gap < self.min_interval:
            time.sleep(self.min_interval - gap)
        self._last = time.monotonic()

    def get_json(self, url: str, params: dict) -> dict:
        """GET and return parsed JSON. Retries network errors, 429/5xx and Arctic Shift's
        {"error": "Timeout..."}: waits for the server's x-ratelimit-reset when given, else backs off.
        Connection failures (Wi-Fi drop, laptop sleep) don't use up retries: wait and retry for up
        to max_offline seconds."""
        attempt, offline_since = 0, None
        while True:
            self._wait_turn()
            self.n_requests += 1
            reset = None
            try:
                r = self.session.get(url, params=params, timeout=90)
                reset = r.headers.get("x-ratelimit-reset")
                try:
                    body = r.json()
                except ValueError:
                    body = {}
                # Arctic Shift sends "Timeout. Maybe slow down a bit" with HTTP 422, so check the body first
                err = body.get("error") if isinstance(body, dict) else None
                if (err and "timeout" in err.lower()) or r.status_code == 429 or r.status_code >= 500:
                    raise requests.HTTPError(err or f"HTTP {r.status_code}")
                if r.status_code >= 400 or err:
                    raise RuntimeError(f"HTTP {r.status_code}: {err or r.text[:200]} params={params}")
                return body
            except requests.ConnectionError as e:  # DNS failure, refused, connect timeout
                offline_since = offline_since or time.monotonic()
                down = time.monotonic() - offline_since
                if down > self.max_offline:
                    raise RuntimeError(f"no connection for {down / 60:.0f} min, giving up: {url} {params}") from e
                log.warning("connection failed (offline %.0f min), retrying in %ds: %s",
                            down / 60, OFFLINE_WAIT, type(e).__name__)
                time.sleep(OFFLINE_WAIT)
            except (requests.RequestException, ValueError) as e:
                offline_since = None
                if attempt == self.max_retries:
                    raise RuntimeError(f"giving up after {self.max_retries} retries: {url} {params}") from e
                backoff = min(self.max_backoff, 2 ** (attempt + 2))
                delay = (int(reset) + 1 if reset and reset.isdigit() and attempt < 2 else backoff)
                delay += random.uniform(0, 1)
                attempt += 1
                log.warning("retry %d/%d in %.0fs (%s)", attempt, self.max_retries, delay, e)
                time.sleep(delay)
