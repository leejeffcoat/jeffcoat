"""Shared polite HTTP helper for API collectors.

Adds a User-Agent, a small inter-request courtesy delay, and retry-with-backoff
on rate-limit / transient errors (429, 502, 503) honoring Retry-After. Keeps
collectors from hammering free public APIs.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
import urllib.error
import urllib.request

USER_AGENT = "jeffcoat-genealogy/0.1 (personal family research)"
# Some sites (FindAGrave) 403 a bot UA but serve real HTML to a browser UA.
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
RETRY_STATUS = {429, 502, 503}


def get_bytes(
    url: str,
    user_agent: str = USER_AGENT,
    retries: int = 3,
    courtesy_delay: float = 0.5,
    timeout: int = 30,
) -> bytes:
    """GET raw bytes, retrying politely on rate-limit/transient errors."""
    time.sleep(courtesy_delay)
    headers = {"User-Agent": user_agent}
    if user_agent == BROWSER_UA:
        # Some sites fingerprint on the full header set, not just UA.
        headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "identity",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })
    attempt = 0
    while True:
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code in RETRY_STATUS and attempt < retries:
                wait = _retry_after(e) or (2 ** attempt)
                time.sleep(wait)
                attempt += 1
                continue
            raise


def get_json(url: str, **kwargs) -> dict | list:
    """GET a URL and parse JSON."""
    return json.loads(get_bytes(url, **kwargs).decode("utf-8"))


def get_html(url: str, use_curl: bool = False, **kwargs) -> str:
    """GET a URL as HTML text using a browser User-Agent by default.

    Some Cloudflare-fronted sites (FindAGrave) fingerprint the TLS handshake and
    403 Python's urllib while serving curl/browsers fine. For those, pass
    use_curl=True to shell out to the system curl, which presents a browser-like
    TLS signature.
    """
    kwargs.setdefault("user_agent", BROWSER_UA)
    if use_curl:
        return _get_via_curl(url, kwargs.get("user_agent", BROWSER_UA),
                             kwargs.get("courtesy_delay", 0.5),
                             kwargs.get("timeout", 30))
    return get_bytes(url, **kwargs).decode("utf-8", errors="replace")


def _get_via_curl(url: str, user_agent: str, courtesy_delay: float, timeout: int) -> str:
    curl = shutil.which("curl")
    if not curl:
        raise RuntimeError(
            "this source needs 'curl' on PATH (Cloudflare blocks Python's TLS). "
            "curl ships with Windows 10+, macOS, and Linux."
        )
    time.sleep(courtesy_delay)
    proc = subprocess.run(
        [curl, "-s", "-L", "--compressed", "-A", user_agent,
         "-H", "Accept-Language: en-US,en;q=0.9", "--max-time", str(timeout), url],
        capture_output=True,  # bytes; decode UTF-8 ourselves (avoids cp1252 on Windows)
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"curl failed ({proc.returncode}): {proc.stderr.decode('utf-8', 'replace').strip()[:200]}"
        )
    return proc.stdout.decode("utf-8", errors="replace")


def _retry_after(e: urllib.error.HTTPError) -> float | None:
    val = e.headers.get("Retry-After") if e.headers else None
    if val and val.isdigit():
        return float(val)
    return None
