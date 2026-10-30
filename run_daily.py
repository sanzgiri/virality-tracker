#!/usr/bin/env python3
"""US Virality Tracker — daily run.

Usage:  python3 run_daily.py [--date YYYY-MM-DD] [--out DIR]
No API keys, no accounts, stdlib only (Python 3.10+).
Writes digests/YYYY-MM-DD.md + .json, updates state/ for day-over-day velocity.
"""
from __future__ import annotations
import argparse, json, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from virality.models import Item
from virality import scoring, cluster as cluster_mod
from virality.render import render
from virality.sources import (google_trends, youtube, tiktok, x_trends,
                              reddit, linkedin, facebook_instagram, memes)

SOURCES = [
    ("youtube", youtube.collect),
    ("tiktok", tiktok.collect),
    ("x", x_trends.collect),
    ("reddit", reddit.collect),
    ("google_trends", google_trends.collect),
    ("linkedin", linkedin.collect),
    ("facebook_instagram", facebook_instagram.collect),  # returns [] + BLOCKED status, split below
    ("memes", memes.collect),
]

def load_yesterday(state_dir: Path, date_str: str) -> dict:
    prev = (datetime.fromisoformat(date_str) - timedelta(days=1)).date().isoformat()
    f = state_dir / f"{prev}.json"
    if f.exists():
        try: return json.loads(f.read_text()).get("scores", {})
        except Exception: return {}
    return {}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(timezone.utc).astimezone().date().isoformat())
    ap.add_argument("--out", default=str(ROOT / "digests"))
    args = ap.parse_args()
    date_str = args.date
    out_dir = Path(args.out); out_dir.mkdir(parents=True, exist_ok=True)
    state_dir = ROOT / "state"; state_dir.mkdir(exist_ok=True)

    items: list[Item] = []
    coverage: list[dict] = []
    for name, fn in SOURCES:
        try:
            got, status = fn()
        except Exception as e:
            got, status = [], f"FAILED (collector crashed: {type(e).__name__}: {e})"
        if name == "facebook_instagram":
            coverage.append({"platform": "facebook", "status": status})
            coverage.append({"platform": "instagram", "status": "Same Meta surface as Facebook — see above."})
            continue
        items.extend(got)
        coverage.append({"platform": name, "status": status})
        print(f"[{name}] {status}", flush=True)

    yesterday = load_yesterday(state_dir, date_str)
    scoring.score_items(items, yesterday)
    clusters = cluster_mod.cluster_items(items)
    scoring.apply_spread(items, clusters)
    qualified = [it for it in items if scoring.qualifies(it)]

    md = render(date_str, items, clusters, coverage, qualified)
    (out_dir / f"{date_str}.md").write_text(md)
    payload = {
        "date": date_str,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "coverage": coverage,
        "items": [it.to_dict() for it in sorted(items, key=lambda x: -x.virality)],
        "qualified_uids": [it.uid for it in qualified],
        "clusters": clusters,
    }
    (out_dir / f"{date_str}.json").write_text(json.dumps(payload, indent=1))
    (state_dir / f"{date_str}.json").write_text(json.dumps(
        {"scores": {it.uid: it.virality for it in items}}, indent=1))
    multi = sum(1 for c in clusters if len(c["platforms"]) >= 2)
    print(f"\n{len(items)} items · {len(qualified)} qualified · {multi} cross-platform clusters")
    print(f"Digest: {out_dir / (date_str + '.md')}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
