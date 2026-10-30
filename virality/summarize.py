"""Per-item digest text: a 1-2 line summary (so the user can skip the click
if it doesn't interest them) and a 'why it's here' line built only from
data we actually measured — never invented."""
from __future__ import annotations
from .models import Item
from .util import clean, fmt_count

PLATFORM_LABEL = {
    "youtube": "YouTube", "tiktok": "TikTok", "x": "X", "reddit": "Reddit",
    "google_trends": "Google Trends", "linkedin": "LinkedIn",
    "facebook": "Facebook", "instagram": "Instagram", "memes": "Know Your Meme",
}

def summary(it: Item) -> str:
    base = clean(it.summary_src, 220)
    bits = []
    if it.author: bits.append(f"by {it.author}")
    if it.published_hint: bits.append(it.published_hint)
    head = " ".join(bits)
    if base and base.lower() not in it.title.lower():
        return (f"{head} — {base}" if head else base)
    # no usable source description: say what it is, factually
    m = it.metrics
    facts = []
    if m.get("views"): facts.append(f"{fmt_count(m['views'])} views")
    if m.get("search_volume"): facts.append(f"~{fmt_count(m['search_volume'])}+ US searches today")
    label = PLATFORM_LABEL.get(it.platform, it.platform)
    desc = f"{label} item"
    if it.rank: desc = f"#{it.rank} on {label} today"
    if head: desc += f", {head}"
    if facts: desc += " — " + ", ".join(facts)
    return desc + "."

def why(it: Item, cluster_platforms: list[str] | None = None) -> str:
    label = PLATFORM_LABEL.get(it.platform, it.platform)
    parts = [f"V {it.virality:.0f} ({it.tier})"]
    if it.rank: parts.append(f"#{it.rank} on {label}")
    m = it.metrics
    if m.get("views"): parts.append(f"{fmt_count(m['views'])} views")
    if m.get("likes"): parts.append(f"{fmt_count(m['likes'])} likes")
    if m.get("comments"): parts.append(f"{fmt_count(m['comments'])} comments")
    if m.get("search_volume"): parts.append(f"{fmt_count(m['search_volume'])}+ searches")
    if cluster_platforms and len(cluster_platforms) > 1:
        others = [PLATFORM_LABEL.get(p, p) for p in cluster_platforms if p != it.platform]
        if others: parts.append("also moving on " + ", ".join(others))
    return " · ".join(parts)
