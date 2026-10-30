"""LinkedIn — LIMITED by design. LinkedIn publishes no public trending feed
and its /news top-stories page requires login. The only public, ranked-ish
signal is the LinkedIn News showcase page, whose recent posts are its
editors' own picks (top stories / Daily Rundown). We surface those posts,
label them as editor picks, and give them no reach metrics (none are
public). LinkedIn's real contribution to this digest is via cross-platform
clusters: when a story trending elsewhere matches, it shows up there."""
from __future__ import annotations
import html, re
from ..http import fetch
from ..models import Item
from ..util import clean

URL = "https://www.linkedin.com/showcase/linkedin-news/"

def parse(page: str, limit: int = 8) -> list[Item]:
    items, seen = [], set()
    # guest feed cards: post link + following text paragraphs
    for m in re.finditer(r'href="(https://www\.linkedin\.com/posts/linkedin-news_activity-[^"]+)"', page):
        url = m.group(1)
        if url in seen: continue
        seen.add(url)
        window = page[m.start():m.start() + 20000]
        paras = re.findall(r'<p[^>]*>(.*?)</p>', window, re.S)
        texts = [clean(p, 400) for p in paras]
        texts = [t for t in texts if len(t) > 40 and "User Agreement" not in t]
        if not texts: continue
        body = texts[0]
        title = body.split(". ")[0][:110]
        items.append(Item(
            platform="linkedin", title=title, url=url,
            rank=len(items) + 1, list_size=10, author="LinkedIn News",
            summary_src=body,
        ))
        if len(items) >= limit: break
    return items

def collect(limit: int = 8):
    r = fetch(URL)
    if not r.ok: return [], f"LIMITED (showcase page unreachable: {r.error})"
    items = parse(r.text, limit)
    if not items: return [], "LIMITED (no public LinkedIn News posts parsed — login wall)"
    return items, f"LIMITED — {len(items)} LinkedIn News editor-pick posts (no public trending feed or metrics exist)"
