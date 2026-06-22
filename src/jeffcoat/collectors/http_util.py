"""Shared polite HTTP helper for API collectors.

Adds a User-Agent, a small inter-request courtesy delay, and retry-with-backoff
on rate-limit / transient errors (429, 502, 503) honoring Retry-After. Keeps
collectors from hammering free public APIs.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

USER_AGENT = "jeffcoat-genealogy/0.1 (personal family research)"
RETRY_STATUS = {429, 502, 503}


def get_json(url: str, retries: int = 3, courtesy_delay: float = 0.5, timeout: int = 30) -> dict | list:
    """GET a URL and parse JSON, retrying politely on rate-limit/transient errors."""
    time.sleep(courtesy_delay)
    attempt = 0
    while True:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in RETRY_STATUS and attempt < retries:
                wait = _retry_after(e) or (2 ** attempt)
                time.sleep(wait)
                attempt += 1
                continue
            raise


def _retry_after(e: urllib.error.HTTPError) -> float | None:
    val = e.headers.get("Retry-After") if e.headers else None
    if val and val.isdigit():
        return float(val)
    return None
