"""Memes — Know Your Meme homepage trending/new entries, plus meme flags
from Reddit's meme feeds (handled in reddit.py). KYM is the closest thing
to a cross-platform meme registry: its entries document templates that
circulate across TikTok, X, Reddit, Instagram and Facebook."""
from __future__ import annotations
import html, re
from ..http import fetch
from ..models import Item

URL = "https://knowyourmeme.com/"

def parse(page: str, limit: int = 12) -> list[Item]:
    items, seen = [], set()
    for m in re.finditer(r'href="(/memes/[^"]+)"[^>]*title="([^"]+)"', page):
        path, title = m.group(1), html.unescape(m.group(2)).strip()
        if path in seen or len(title) < 3: continue
        seen.add(path)
        items.append(Item(
            platform="memes", title=title, url="https://knowyourmeme.com" + path,
            rank=len(items) + 1, list_size=20, author="Know Your Meme",
            summary_src="Meme entry surfacing on Know Your Meme's front page today.",
            is_meme=True,
        ))
        if len(items) >= limit: break
    if len(items) < 4:  # fallback: bare links in document order
        for m in re.finditer(r'href="(/memes/[^"]+)"', page):
            path = m.group(1)
            if path in seen or path == "/memes": continue
            seen.add(path)
            title = path.rsplit("/", 1)[-1].replace("-", " ").title()
            items.append(Item(
                platform="memes", title=title, url="https://knowyourmeme.com" + path,
                rank=len(items) + 1, list_size=20, author="Know Your Meme",
                summary_src="Meme entry surfacing on Know Your Meme's front page today.",
                is_meme=True,
            ))
            if len(items) >= limit: break
    return items

def collect(limit: int = 12):
    r = fetch(URL)
    if not r.ok: return [], f"FAILED ({r.error})"
    items = parse(r.text, limit)
    if not items: return [], "FAILED (no meme entries parsed)"
    for it in items:  # each entry page's og:image is the meme's own picture
        try:
            p = fetch(it.url)
            if p.ok:
                m = re.search(r"""property=["']og:image["']\s+content=["']([^"']+)["']""", p.text) or \
                    re.search(r"""content=["']([^"']+)["']\s+property=["']og:image["']""", p.text)
                if m: it.metrics["image"] = html.unescape(m.group(1))
        except Exception:
            pass
    return items, f"OK — {len(items)} meme entries from Know Your Meme front page"
