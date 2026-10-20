"""Shared polite HTTP client: fixed minimum gap between requests + exponential backoff."""

import logging
import random
import time

import requests

log = logging.getLogger(__name__)

USER_AGENT = "broadway-rush/0.1 (personal research project; polite, rate-limited)"


class PoliteClient:
    def __init__(self, min_interval: float = 1.0, max_retries: int = 8, max_backoff: float = 120.0):
        self.min_interval = min_interval
        self.max_retries = max_retries
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
        {"error": "Timeout..."}: waits for the server's x-ratelimit-reset when given, else backs off."""
        for attempt in range(self.max_retries + 1):
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
            except (requests.RequestException, ValueError) as e:
                if attempt == self.max_retries:
                    break
                backoff = min(self.max_backoff, 2 ** (attempt + 2))
                delay = (int(reset) + 1 if reset and reset.isdigit() and attempt < 2 else backoff)
                delay += random.uniform(0, 1)
                log.warning("retry %d/%d in %.0fs (%s)", attempt + 1, self.max_retries, delay, e)
                time.sleep(delay)
        raise RuntimeError(f"giving up after {self.max_retries} retries: {url} {params}")
