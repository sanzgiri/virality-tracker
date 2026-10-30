"""Render the daily digest (Markdown) from scored items + clusters."""
from __future__ import annotations
from collections import Counter
from .models import Item
from .summarize import summary, why, PLATFORM_LABEL
from .util import clean

ORDER = ["youtube", "tiktok", "x", "reddit", "google_trends", "linkedin", "facebook", "instagram", "memes"]

def _item_block(it: Item, cluster_platforms=None) -> str:
    title = clean(it.title, 140)
    lines = [f"- **[{title}]({it.url})** — {PLATFORM_LABEL.get(it.platform, it.platform)}",
             f"  {summary(it)}",
             f"  _{why(it, cluster_platforms)}_"]
    return "\n".join(lines)

def render(date_str: str, items: list[Item], clusters: list[dict],
           coverage: list[dict], qualified: list[Item]) -> str:
    by_uid = {it.uid: it for it in items}
    cluster_of = {}
    for c in clusters:
        for uid in c["uids"]: cluster_of[uid] = c["platforms"]
    out = [f"# US Virality Digest — {date_str}", ""]
    out.append("What's actually viral in the US today, across platforms — data first, no listicle copy. "
               "Virality = Reach + Velocity + Engagement + Cross-platform Spread (see Method at the end).")
    out.append("")
    # Coverage
    out.append("## Coverage today")
    for c in coverage:
        n = sum(1 for it in items if it.platform == c["platform"])
        out.append(f"- **{PLATFORM_LABEL.get(c['platform'], c['platform'])}**: {c['status']}" + (f" · {n} items pulled" if n else ""))
    out.append("")
    # Commonality
    multi = [c for c in clusters if len(c["platforms"]) >= 2]
    out.append("## What's common across platforms")
    if multi:
        for c in multi[:10]:
            plats = ", ".join(PLATFORM_LABEL.get(p, p) for p in c["platforms"])
            terms = ", ".join(c["shared_terms"][:5])
            out.append(f"- **{clean(c['label'], 110)}** — on {plats}" + (f" · shared: {terms}" if terms else ""))
        pair_counts = Counter()
        for c in multi:
            ps = c["platforms"]
            for i in range(len(ps)):
                for j in range(i + 1, len(ps)): pair_counts[(ps[i], ps[j])] += 1
        if pair_counts:
            top_pairs = "; ".join(f"{PLATFORM_LABEL.get(a,a)}×{PLATFORM_LABEL.get(b,b)} ({n})" for (a, b), n in pair_counts.most_common(3))
            out.append(f"- Most overlapping pairs today: {top_pairs}.")
        meme_share = sum(1 for it in qualified if it.is_meme)
        out.append(f"- {len(multi)} stories/formats crossed platforms; {meme_share} of today's {len(qualified)} qualifying hits are memes or meme-adjacent.")
    else:
        out.append("- Nothing crossed platforms today by the clustering rules — each platform's hits were platform-native. (Unusual; more often a sign of a quiet news day than of no overlap.)")
    out.append("")
    # Top hits
    out.append("## Top viral hits (all platforms)")
    top = sorted(qualified, key=lambda it: -it.virality)[:25]
    for it in top: out.append(_item_block(it, cluster_of.get(it.uid)))
    out.append("")
    # Memes
    meme_items = [it for it in sorted(qualified, key=lambda x: -x.virality) if it.is_meme][:15]
    out.append("## Memes")
    if meme_items:
        for it in meme_items: out.append(_item_block(it, cluster_of.get(it.uid)))
    else:
        out.append("- No meme cleared the virality bar today.")
    out.append("")
    # Per platform
    out.append("## By platform")
    for p in ORDER:
        group = sorted([it for it in items if it.platform == p], key=lambda x: (x.rank or 999))[:10]
        if not group: continue
        out.append(f"### {PLATFORM_LABEL.get(p, p)}")
        for it in group: out.append(_item_block(it, cluster_of.get(it.uid)))
        out.append("")
    out.append("## Method & limits")
    out.append("- **Virality score (0–100)** = 0.35·Reach + 0.25·Velocity + 0.20·Engagement + 0.20·Spread, all computed as within-platform percentiles so counts are comparable across platforms. An item qualifies at V ≥ 60, or by appearing in a ≥3-platform cluster, or as a top-10 platform item with top-quintile engagement. Full definition in SPEC.md.")
    out.append("- **US only**: sources are the US editions/charts of each platform. Reddit publishes no US-only feed — r/popular from US egress is US-weighted, not US-exclusive.")
    out.append("- **Facebook/Instagram**: no public anonymous trending surface exists since Meta shut down CrowdTangle in Aug 2024 (Content Library is application-only). Reported as BLOCKED rather than filled with proxied or invented data.")
    out.append("- **LinkedIn**: no public trending feed; LinkedIn News editor picks only, no metrics — low weight by construction.")
    out.append("- Summaries and 'why' lines are generated from the source's own text and measured metrics only.")
    return "\n".join(out) + "\n"
