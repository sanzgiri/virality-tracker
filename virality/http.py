"""Stdlib-only HTTP fetching. No API keys, no accounts, no cookies.
Polite: browser UA, short timeout, one retry, per-host delay handled by callers."""
from __future__ import annotations
import time, urllib.request, urllib.error

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

class FetchResult:
    def __init__(self, url, ok, status, text, error=""):
        self.url, self.ok, self.status, self.text, self.error = url, ok, status, text, error

def fetch(url: str, timeout: int = 25, headers: dict | None = None) -> FetchResult:
    hdrs = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
    if headers: hdrs.update(headers)
    last = None
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                charset = r.headers.get_content_charset() or "utf-8"
                return FetchResult(url, True, r.status, raw.decode(charset, errors="ignore"))
        except Exception as e:  # HTTPError, URLError, timeout — all mean "source unavailable"
            last = FetchResult(url, False, getattr(e, "code", 0) or 0, "", f"{type(e).__name__}: {e}")
            if attempt == 0: time.sleep(2)
    return last
