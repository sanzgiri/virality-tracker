# virality-tracker

Daily US virality digest across YouTube, TikTok, X, Reddit, Google Trends,
LinkedIn, Facebook/Instagram (blocked — reported honestly, see SPEC.md)
and memes. No API keys, no accounts, Python stdlib only (3.10+).

Run it:

    python3 run_daily.py                # today's digest -> digests/
    python3 run_daily.py --date 2026-10-29

Output: `digests/YYYY-MM-DD.md` + `.json`. Yesterday's scores in `state/`
feed the velocity term, so day 2+ runs get better.

Layout: `run_daily.py` (entry) · `virality/` (models, http, scoring,
cluster, summarize, render) · `virality/sources/` (one file per platform —
swap or add a source there) · `SPEC.md` (virality definition, sources,
limits) · `tests/`.

## Website

The same data publishes as a static site in `docs/` (GitHub Pages serves
it from the main branch): a visual front page (Today), a Details & method
page with all scores and coverage, and a permanent per-day History.

    python3 build_site.py               # digests/*.json -> docs/

Site rules: one card per story (cross-platform stories are deduplicated,
with a chip per platform); images are the source's own when available,
else the source's video embed, else a credited web-search image, else a
title tile — never stretched; primary links never require a login
(X-only topics link to a news search instead).

`.github/workflows/daily.yml` runs the collector + site build daily
(~17:00 UTC ≈ 9–10am Pacific) and commits the results back to this repo.
