"""TikTok (US) — TikTok's own trending surfaces need login or signed API
calls (Creative Center API now returns 401 'no permission' anonymously).
Primary source: Endless Social Radar's US TikTok page, which republishes
TikTok's US trending feed (most-viewed in the last 24h) several times a day
with views and likes, and links back to the original videos."""
from __future__ import annotations
import html, re
from ..http import fetch
from ..models import Item
from ..util import parse_count

URL = "https://endless.app/radar/tiktok/united-states"

def parse(page: str, limit: int = 30) -> list[Item]:
    items = []
    for seg in re.findall(r'<li class="flex scroll-mt-24[^"]*" id="video-(\d+)">(.*?)</li>\s*(?=<li class="flex scroll-mt-24|<h2|</ol>)', page, re.S):
        rank, block = int(seg[0]), seg[1]
        m = re.search(r'href="(https://www\.tiktok\.com/@[^"]+/video/\d+)"[^>]*>(.*?)</a>', block, re.S)
        if not m: continue
        url, title = m.group(1), html.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip()
        author = ""
        am = re.search(r"Cover of @([A-Za-z0-9._]+)", block) or re.search(r"@<!-- -->([A-Za-z0-9._]+)", block)
        if am: author = "@" + am.group(1)
        if title.startswith("@"): title = ""
        views = likes = 0
        vm = re.search(r"([\d.]+[KMB]?)\s*views", block)
        lm = re.search(r"([\d.]+[KMB]?)\s*likes", block)
        if vm: views = parse_count(vm.group(1))
        if lm: likes = parse_count(lm.group(1))
        sm = re.search(r"Sound:\s*([^<]+)", block)
        cm = re.search(r'<img[^>]+src="(https?://[^"]+)"[^>]*alt="Cover of', block) or \
             re.search(r'<img[^>]+src="(https?://[^"]+)"', block)
        vid = url.rstrip("/").rsplit("/", 1)[-1]
        items.append(Item(
            platform="tiktok", title=title or f"TikTok video by {author}", url=url,
            rank=rank, list_size=30, author=author,
            summary_src=(f"Sound: {sm.group(1).strip()}." if sm else ""),
            metrics={"views": views, "likes": likes,
                     "image": html.unescape(cm.group(1)) if cm else "",
                     "embed": f"https://www.tiktok.com/player/v1/{vid}?embed_from=oembed&music_info=1&description=1" if vid.isdigit() else ""},
            is_meme=bool(re.search(r"\bmeme|funny|comedy\b", title, re.I)),
        ))
        if len(items) >= limit: break
    items.sort(key=lambda it: it.rank or 999)
    return items

def collect(limit: int = 30):
    r = fetch(URL)
    if not r.ok: return [], f"FAILED ({r.error})"
    items = parse(r.text, limit)
    if not items: return [], "FAILED (no video entries parsed — radar layout changed?)"
    return items, f"OK — {len(items)} most-viewed US TikToks, last 24h (Endless radar of TikTok's trending feed)"
