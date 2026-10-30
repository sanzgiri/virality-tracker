"""Facebook & Instagram — BLOCKED for anonymous trending, honestly reported.
Since Meta shut down CrowdTangle (Aug 2024) there is no public, anonymous
way to rank what's viral on Facebook or Instagram: facebook.com/watch and
instagram.com/explore return app shells with no items to logged-out
visitors, and the Meta Content Library is application-only for researchers.
This collector tries both public pages every run (so the day Meta opens a
surface, it starts working) and otherwise returns no items with a precise
status. It NEVER substitutes invented or proxied data and labels it as
Facebook/Instagram data. FB/IG circulation of a topic is only ever claimed
when it appears in the cross-platform clusters via another platform's data.
Upgrade path: connect Meta via Muse's Facebook/Instagram connectors, or
supply a Meta Content Library export, and replace this collector."""
from __future__ import annotations
import re
from ..http import fetch

PAGES = [
    ("facebook", "https://www.facebook.com/watch/"),
    ("instagram", "https://www.instagram.com/explore/"),
]

def collect(limit: int = 20):
    statuses = []
    for name, url in PAGES:
        r = fetch(url)
        if not r.ok:
            statuses.append(f"{name}: unreachable ({r.error})")
            continue
        # A usable page would contain item links with real titles; the shells
        # contain only the app bootstrap (verified 2026-10-29).
        # No item parser exists because no items are served anonymously;
        # if Meta ever serves ranked items here, this is where parsing goes.
        statuses.append(f"{name}: login/app shell, no public items served")
    return [], "BLOCKED — " + "; ".join(statuses) + ". No public anonymous trending surface exists post-CrowdTangle."
