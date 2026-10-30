"""Reddit — official public RSS (reddit.com blocks anonymous JSON from many
IPs with 403, but the .rss feeds work if you pace requests; we sleep between
feeds and retry once inside http.fetch).
Feeds: r/popular top-of-day (Reddit's front door; US-weighted from US egress,
Reddit publishes no US-only feed), r/memes and r/funny top-of-day for memes.
RSS carries no upvote counts, so Reddit scoring leans on rank (Reddit's own
top sort IS score-ordered) with engagement neutral — see SPEC.md."""
from __future__ import annotations
import html, re, time, xml.etree.ElementTree as ET
from ..http import fetch
from ..models import Item

NS = {"a": "http://www.w3.org/2005/Atom"}
FEEDS = [
    ("popular", "https://www.reddit.com/r/popular/top/.rss?t=day&limit=25", False, 25),
    ("memes",   "https://www.reddit.com/r/memes/top/.rss?t=day&limit=15", True, 15),
    ("funny",   "https://www.reddit.com/r/funny/top/.rss?t=day&limit=10", True, 10),
]

def parse_feed(xml_text: str, sub: str, is_meme: bool, limit: int) -> list[Item]:
    items = []
    root = ET.fromstring(xml_text)
    for i, e in enumerate(root.findall("a:entry", NS), start=1):
        title = (e.findtext("a:title", default="", namespaces=NS) or "").strip()
        link_el = e.find("a:link", NS)
        url = link_el.get("href") if link_el is not None else ""
        author = (e.findtext("a:author/a:name", default="", namespaces=NS) or "").strip()
        if not title or not url: continue
        content = html.unescape(e.findtext("a:content", default="", namespaces=NS) or "")
        # Prefer the full-res i.redd.it URL (no signature needed); else the
        # complete preview URL including its signed query string.
        im = re.search(r'https://i\.redd\.it/[A-Za-z0-9._~%-]+', content) or \
             re.search(r'https://preview\.redd\.it/[^\s"<>]+', content)
        items.append(Item(
            platform="reddit", title=title, url=url, rank=i, list_size=limit,
            author=f"r/{sub} {author}".strip(),
            summary_src=f"Top of r/{sub} today on Reddit.",
            metrics={"image": im.group(0) if im else ""},
            is_meme=is_meme or sub == "memes",
        ))
        if len(items) >= limit: break
    return items

def collect(limit: int = 40):
    all_items, notes = [], []
    for sub, url, is_meme, lim in FEEDS:
        r = fetch(url)
        if not r.ok and "429" in r.error:  # Reddit burst-limits RSS too; one long backoff
            time.sleep(45)
            r = fetch(url)
        if not r.ok:
            notes.append(f"r/{sub} FAILED ({r.error})")
        else:
            try:
                got = parse_feed(r.text, sub, is_meme, lim)
                all_items.extend(got); notes.append(f"r/{sub} {len(got)}")
            except ET.ParseError as e:
                notes.append(f"r/{sub} FAILED (RSS parse: {e})")
        time.sleep(8)  # Reddit rate-limits bursts (429s) — pace the feeds
    status = ("OK — " + ", ".join(notes)) if all_items else ("FAILED — " + "; ".join(notes))
    return all_items[:limit], status
