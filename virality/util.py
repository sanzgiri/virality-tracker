from __future__ import annotations
import html, re

def parse_count(s) -> int:
    """'63.7M' -> 63700000, '201K' -> 201000, '1,234' -> 1234, '' -> 0"""
    if s is None: return 0
    if isinstance(s, (int, float)): return int(s)
    s = str(s).replace(",", "").strip()
    m = re.match(r"([\d.]+)\s*([KMB])?", s, re.I)
    if not m: return 0
    v = float(m.group(1)); mult = {"K": 1e3, "M": 1e6, "B": 1e9}.get((m.group(2) or "").upper(), 1)
    return int(v * mult)

def clean(text: str, limit: int = 240) -> str:
    t = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > limit: t = t[:limit].rsplit(" ", 1)[0] + "…"
    return t

def fmt_count(n) -> str:
    n = float(n or 0)
    for unit, div in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if n >= div: return f"{n/div:.1f}".rstrip("0").rstrip(".") + unit
    return str(int(n))
