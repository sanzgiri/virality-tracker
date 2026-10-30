"""Google Trends (US) — public RSS feed, no key.
Feed: trends.google.com/trending/rss?geo=US
Each item: search term, approx. search volume, and the news stories driving it."""
from __future__ import annotations
import re, xml.etree.ElementTree as ET
from ..http import fetch
from ..models import Item

URL = "https://trends.google.com/trending/rss?geo=US"
NS = {"ht": "https://trends.google.com/trending/rss"}

def parse_volume(s: str) -> int:
    m = re.match(r"([\d.]+)([KM]?)\+", (s or "").strip())
    if not m: return 0
    v = float(m.group(1)); mult = {"K": 1_000, "M": 1_000_000}.get(m.group(2), 1)
    return int(v * mult)

def collect(limit: int = 25):
    r = fetch(URL)
    if not r.ok: return [], f"FAILED ({r.error})"
    items = []
    try:
        root = ET.fromstring(r.text)
    except ET.ParseError as e:
        return [], f"FAILED (RSS parse: {e})"
    for i, node in enumerate(root.iter("item"), start=1):
        title = (node.findtext("title") or "").strip()
        if not title: continue
        vol = parse_volume(node.findtext("ht:approx_traffic", default="", namespaces=NS))
        news = node.findall("ht:news_item", NS)
        snippet, news_url = "", ""
        if news:
            snippet = (news[0].findtext("ht:news_item_snippet", default="", namespaces=NS) or "").strip()
            src = (news[0].findtext("ht:news_item_source", default="", namespaces=NS) or "").strip()
            news_url = (news[0].findtext("ht:news_item_url", default="", namespaces=NS) or "").strip()
            if src: snippet = f"{snippet} (via {src})" if snippet else f"via {src}"
        items.append(Item(
            platform="google_trends", title=title, rank=i, list_size=25,
            url=f"https://trends.google.com/trending?geo=US&search={title.replace(' ', '%20')}",
            summary_src=snippet or "Trending search in the US on Google today.",
            metrics={"search_volume": vol, "news_url": news_url},
        ))
        if len(items) >= limit: break
    return items, f"OK — {len(items)} trending US searches (RSS)"
