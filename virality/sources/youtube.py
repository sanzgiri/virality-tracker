"""YouTube Trending (US).
YouTube's own /feed/trending page no longer server-renders its chart to
logged-out visitors (it returns an empty grid; the chart loads via signed
client calls). Primary source: YTDetective's daily US trending snapshot,
which republishes the official chart (freshness-stamped, refreshed daily)
as a schema.org ItemList plus rows with channel, category, views, likes and
comments. All links point at the original youtube.com videos.
Fallback: parse youtube.com/feed/trending directly if it ever renders again."""
from __future__ import annotations
import html, json, re
from ..http import fetch
from ..models import Item
from ..util import parse_count

MIRROR = "https://www.ytdetective.com/rankings/trending/us"
DIRECT = "https://www.youtube.com/feed/trending?gl=US&hl=en"

def parse_mirror(page: str, limit: int = 30) -> list[Item]:
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>', page, re.S)
    if not m: return []
    try: data = json.loads(m.group(1))
    except Exception: return []
    lists = data if isinstance(data, list) else [data]
    entries = []
    for d in lists:
        if isinstance(d, dict) and d.get("@type") == "ItemList":
            entries = d.get("itemListElement", [])
    if not entries: return []
    # per-video stats from the ranking rows
    stats = {}
    for row in re.findall(r'data-testid="ranking-row">(.*?)</tr>', page, re.S):
        vm = re.search(r'youtube\.com/watch\?v=([\w-]{11})', row)
        if not vm: continue
        nums = re.findall(r'text-right font-mono[^>]*>([\d.]+[KMB]?)<', row)
        chan = re.search(r'block truncate text-xs[^>]*>([^<]+)</span>', row)
        cat = re.search(r'rounded-sm bg-\[#F3F4F5\][^>]*>([^<]+)</span>', row)
        stats[vm.group(1)] = {
            "views": parse_count(nums[0]) if len(nums) > 0 else 0,
            "likes": parse_count(nums[1]) if len(nums) > 1 else 0,
            "comments": parse_count(nums[2]) if len(nums) > 2 else 0,
            "channel": html.unescape(chan.group(1)).strip() if chan else "",
            "category": html.unescape(cat.group(1)).strip() if cat else "",
        }
    items = []
    for e in entries[:limit]:
        url = e.get("url", "")
        vid = url.rsplit("v=", 1)[-1] if "v=" in url else ""
        st = stats.get(vid, {})
        items.append(Item(
            platform="youtube", title=html.unescape(e.get("name", "")), url=url,
            rank=e.get("position"), list_size=50,
            author=st.get("channel", ""),
            summary_src=(f"{st['category']} video." if st.get("category") else ""),
            metrics={"views": st.get("views", 0), "likes": st.get("likes", 0), "comments": st.get("comments", 0),
                     "image": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg" if vid else ""},
            is_meme=bool(re.search(r"\bmeme\b", e.get("name", ""), re.I)),
        ))
    return items

def collect(limit: int = 30):
    r = fetch(MIRROR)
    if r.ok:
        items = parse_mirror(r.text, limit)
        if items:
            stamp = re.search(r'data-testid="freshness-stamp">.*?dateTime="([^"]+)"', r.text, re.S)
            when = f" (snapshot {stamp.group(1)[:10]})" if stamp else ""
            return items, f"OK — {len(items)} trending US videos{when} (daily mirror of YouTube's official US chart)"
    r2 = fetch(DIRECT)
    if r2.ok:
        return [], "FAILED (mirror unreachable; direct trending page renders no chart to logged-out visitors)"
    return [], f"FAILED (mirror: {r.error}; direct: {r2.error})"
