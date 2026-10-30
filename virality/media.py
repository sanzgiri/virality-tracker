"""Media resolution for the website build.

The ladder (user's rules, 2026-10-29): a card uses the source's own image
when one exists; else the source's video (official embed); else the top
relevant web-search image, credited; else a designed typographic tile.
Images are downloaded and validated at build time so a dead URL degrades
to the next rung before anything is published. Stdlib only.
"""
from __future__ import annotations
import hashlib, json, re, struct, urllib.parse, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp"}

def _get(url: str, timeout: int = 25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.headers.get_content_type(), r.read()

def image_size(data: bytes):
    """(w, h) for PNG/JPEG/GIF, else None."""
    try:
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            return struct.unpack(">II", data[16:24])
        if data[:6] in (b"GIF87a", b"GIF89a"):
            return struct.unpack("<HH", data[6:10])
        if data[:2] == b"\xff\xd8":
            i = 2
            while i < len(data) - 9:
                if data[i] != 0xFF: i += 1; continue
                marker = data[i + 1]
                if marker in (0xC0, 0xC1, 0xC2):
                    h, w = struct.unpack(">HH", data[i + 5:i + 9])
                    return (w, h)
                seg = struct.unpack(">H", data[i + 2:i + 4])[0]
                i += 2 + seg
    except Exception:
        return None
    return None

def download_image(url: str, dest_dir, key_hint: str = ""):
    """Download + validate an image into dest_dir. Returns dict
    {file, w, h} or None. Reuses an existing file for the same URL."""
    from pathlib import Path
    dest_dir = Path(dest_dir); dest_dir.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha1(url.encode()).hexdigest()[:12]
    for ext in EXT.values():
        f = dest_dir / f"{h}{ext}"
        if f.exists() and f.stat().st_size > 0:
            size = image_size(f.read_bytes())
            return {"file": f.name, "w": size[0] if size else None, "h": size[1] if size else None}
    try:
        ctype, data = _get(url)
    except Exception:
        return None
    if ctype not in EXT or not (6000 <= len(data) <= 10_000_000):
        return None
    if not (data[:3] == b"\xff\xd8\xff" or data[:8] == b"\x89PNG\r\n\x1a\n"
            or data[:6] in (b"GIF87a", b"GIF89a") or data[:4] == b"RIFF"):
        return None
    f = dest_dir / f"{h}{EXT[ctype]}"
    f.write_bytes(data)
    size = image_size(data)
    return {"file": f.name, "w": size[0] if size else None, "h": size[1] if size else None}

def search_image(query: str):
    """Top relevant web image for a topic (Bing Images public page).
    Returns (image_url, source_page_url) or None. Best-effort."""
    try:
        url = "https://www.bing.com/images/search?q=" + urllib.parse.quote(query) + "&form=HDRSC2&first=1"
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=25) as r:
            page = r.read().decode("utf-8", "ignore")
    except Exception:
        return None
    import html as _html
    page = _html.unescape(page)  # Bing HTML-escapes the embedded result JSON
    cands = []
    for m in re.finditer(r'"murl":"(https?://[^"]+?)"', page):
        murl = m.group(1).replace("\\/", "/")
        if any(bad in murl for bad in ("bing.net/th", "mm.bing.net")):
            continue  # search-engine cache thumbnails are not a durable source
        window = page[max(0, m.start() - 1600): m.end() + 1600]
        pm = re.search(r'"purl":"(https?://[^"]+?)"', window)
        cands.append((murl, pm.group(1).replace("\\/", "/") if pm else ""))
        if len(cands) >= 8: break
    for want_ext in ((".jpg", ".jpeg", ".png"), (".webp", ".gif", "")):
        for murl, purl in cands:
            if murl.lower().split("?")[0].endswith(want_ext):
                return murl, purl
    return None

def domain_of(url: str) -> str:
    try:
        host = urllib.parse.urlparse(url).netloc
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return "web search"
