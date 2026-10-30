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

def parse(xml_text: str, limit: int = 25) -> list[Item]:
    items = []
    root = ET.fromstring(xml_text)
    for i, node in enumerate(root.iter("item"), start=1):
        title = (node.findtext("title") or "").strip()
        if not title: continue
        vol = parse_volume(node.findtext("ht:approx_traffic", default="", namespaces=NS))
        news = node.findall("ht:news_item", NS)
        headline, src, news_url, snippet = "", "", "", ""
        if news:
            headline = (news[0].findtext("ht:news_item_title", default="", namespaces=NS) or "").strip()
            snippet = (news[0].findtext("ht:news_item_snippet", default="", namespaces=NS) or "").strip()
            src = (news[0].findtext("ht:news_item_source", default="", namespaces=NS) or "").strip()
            news_url = (news[0].findtext("ht:news_item_url", default="", namespaces=NS) or "").strip()
        # The headline of the story driving the searches IS the explanation
        # of an otherwise opaque term ("cameron boozer" -> the rookie story).
        explanation = headline or snippet
        summary = explanation
        if summary and src: summary = f"{summary} (via {src})"
        items.append(Item(
            platform="google_trends", title=title, rank=i, list_size=25,
            url=f"https://trends.google.com/trending?geo=US&search={title.replace(' ', '%20')}",
            summary_src=summary or "Trending search in the US on Google today.",
            metrics={"search_volume": vol, "news_url": news_url,
                     "news_title": headline, "news_source": src},
        ))
        if len(items) >= limit: break
    return items

def collect(limit: int = 25):
    r = fetch(URL)
    if not r.ok: return [], f"FAILED ({r.error})"
    try:
        items = parse(r.text, limit)
    except ET.ParseError as e:
        return [], f"FAILED (RSS parse: {e})"
    return items, f"OK — {len(items)} trending US searches (RSS)"
