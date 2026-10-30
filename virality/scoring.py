"""Virality definition and scoring. See SPEC.md for the full write-up.

Summary: a 0-100 score built from within-platform percentiles, so a Reddit
post and a YouTube video can be compared without pretending their raw counts
mean the same thing.

  V = 0.35*Reach + 0.25*Velocity + 0.20*Engagement + 0.20*Spread

  Reach      percentile of the item's headline audience metric (views /
             upvotes / search volume) inside today's pull for that platform.
  Velocity   trending-list position (rank 1 -> 100, decaying by list size),
             blended with day-over-day acceleration when yesterday's snapshot
             has the same item (new entrant = strong prior).
  Engagement percentile of (likes+comments+shares)/audience where the source
             exposes it; neutral 50 when it does not. Never faked.
  Spread     cross-platform resonance, filled in AFTER clustering:
             100 * (platforms_in_cluster - 1) / 4, capped at 100.

Qualification (an item is in the digest if any holds):
  V >= 60, or its cluster spans >= 3 platforms, or it is top-10 on its own
  platform with engagement percentile >= 80.
Tiers: Mega >= 85 | Viral 70-84.9 | Rising 60-69.9 | Watch = qualified only
via cluster/top-10 rule.
"""
from __future__ import annotations
import math
from .models import Item

def _percentiles(values: list[float]) -> list[float]:
    if not values: return []
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    n = len(values)
    for pos, idx in enumerate(order):
        out[idx] = 100.0 if n == 1 else (pos / (n - 1)) * 100.0
    return out

def _headline_metric(it: Item) -> float | None:
    for k in ("views", "play_count", "upvotes", "score", "search_volume", "tweet_volume", "posts"):
        v = it.metrics.get(k)
        if isinstance(v, (int, float)) and v > 0: return float(v)
    return None

def _engagement_ratio(it: Item) -> float | None:
    base = _headline_metric(it)
    eng = sum(float(it.metrics.get(k) or 0) for k in ("likes", "comments", "shares", "diggs"))
    if base and eng > 0: return eng / base
    return None

def score_items(items: list[Item], yesterday: dict[str, float] | None = None) -> list[Item]:
    """First pass (Reach/Velocity/Engagement). Spread is added by
    apply_spread() after clustering. `yesterday`: uid -> yesterday's V."""
    yesterday = yesterday or {}
    by_platform: dict[str, list[Item]] = {}
    for it in items: by_platform.setdefault(it.platform, []).append(it)
    for platform, group in by_platform.items():
        def _reach_val(it):
            mv = _headline_metric(it)
            if mv and mv > 1: return math.log10(mv)
            return 50.0 - (it.rank or 25)   # no public metric (Reddit RSS, X, KYM, LinkedIn): rank is the signal
        reach_vals = [_reach_val(it) for it in group]
        reach_pct = _percentiles(reach_vals)
        ratios = [_engagement_ratio(it) or 0.0 for it in group]
        eng_pct = _percentiles(ratios)
        for it, rp, ep, ratio in zip(group, reach_pct, eng_pct, ratios):
            it.metrics["_group_size"] = len(group)
            it.metrics["_reach_pct"] = round(rp, 1)
            # Velocity from rank: top of a 50-list beats top of a 10-list slightly less naively
            if it.rank:
                size = it.list_size or max(20, len(group))
                vel = max(0.0, 100.0 * (1.0 - (it.rank - 1) / max(size, 1)))
            else:
                vel = rp  # unranked source: reach is the only velocity proxy
            prev = yesterday.get(it.uid)
            if prev is not None:
                vel = 0.6 * vel + 0.4 * min(100.0, max(0.0, vel - prev + 60.0))  # acceleration vs own yesterday
                it.metrics["_returning"] = True
            it.metrics["_velocity"] = round(vel, 1)
            it.metrics["_engagement_pct"] = round(ep, 1) if ratio > 0 else 50.0
            it.virality = round(0.35 * rp + 0.25 * vel + 0.20 * it.metrics["_engagement_pct"], 1)  # + spread later (max +20)
    return items

def apply_spread(items: list[Item], clusters: list[dict]) -> None:
    """Second pass: add the Spread component (up to +20) from cluster breadth,
    then final tier/qualification bookkeeping fields used by the renderer."""
    breadth = {}
    for c in clusters:
        for uid in c["uids"]:
            breadth[uid] = len(c["platforms"])
    for it in items:
        b = breadth.get(it.uid, 1)
        spread = min(100.0, 100.0 * (b - 1) / 4.0)
        it.metrics["_spread"] = spread
        it.metrics["_platforms_in_cluster"] = b
        it.virality = round(min(100.0, it.virality + 0.20 * spread), 1)
        if it.metrics.get("_group_size", 99) < 8 and b == 1:
            it.virality = min(it.virality, 69.0)  # small-sample guard: <8 items of evidence can't mint a Viral tier alone
        it.tier = ("Mega" if it.virality >= 85 else "Viral" if it.virality >= 70
                   else "Rising" if it.virality >= 60 else "Watch")

def qualifies(it: Item) -> bool:
    if it.virality >= 60: return True
    if it.metrics.get("_platforms_in_cluster", 1) >= 3: return True
    if it.rank and it.rank <= 10 and it.metrics.get("_engagement_pct", 0) >= 80: return True
    return False
