"""X (Twitter) trends, US — via trends24.in, a public mirror that republishes
X's own US trending list hourly (X itself offers no public trending page
without login). Rank order is X's; tweet counts are included when the
mirror has them."""
from __future__ import annotations
import html, re
from ..http import fetch
from ..models import Item
from ..util import parse_count

URL = "https://trends24.in/united-states/"

def parse(page: str, limit: int = 40) -> list[Item]:
    cards = re.findall(r"<ol class=trend-card__list>(.*?)</ol>", page, re.S)
    if not cards: return []
    items, seen = [], set()
    for li in re.findall(r"<li>(.*?)</li>", cards[0], re.S):
        m = re.search(r'class=trend-link>([^<]+)</a>', li)
        if not m: continue
        name = html.unescape(m.group(1)).strip()
        if not name or name.lower() in seen: continue
        seen.add(name.lower())
        cm = re.search(r'data-count="([\d,]+)"', li)
        items.append(Item(
            platform="x", title=name, rank=len(items) + 1, list_size=50,
            url=f"https://twitter.com/search?q={name.replace(' ', '%20')}",
            summary_src="Trending topic on X in the United States right now.",
            metrics={"tweet_volume": parse_count(cm.group(1)) if cm else 0},
            is_meme=bool(re.search(r"\bmeme\b", name, re.I)),
        ))
        if len(items) >= limit: break
    return items

def collect(limit: int = 40):
    r = fetch(URL)
    if not r.ok: return [], f"FAILED ({r.error})"
    items = parse(r.text, limit)
    if not items: return [], "FAILED (no trend card found — mirror layout changed?)"
    return items, f"OK — {len(items)} US trends (latest hourly card, via trends24 mirror of X)"
