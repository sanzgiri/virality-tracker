# US Virality Tracker — specification

Built 2026-10-29. Purpose: a daily, data-first digest of what is actually
viral in the United States across YouTube, TikTok, X, Reddit, Facebook/
Instagram, LinkedIn and Google Trends — plus memes — without any platform
API keys, accounts or logins, and without listicle/clickbait presentation.
Every entry links to the original item on its own platform and carries a
short summary so the reader can skip clicks that don't interest them.

## Definition of virality

Raw counts are not comparable across platforms (a million TikTok views is
routine; a million Reddit upvotes is historic). So virality is defined
**relative to each platform's own daily distribution**, then combined:

    V = 0.35·Reach + 0.25·Velocity + 0.20·Engagement + 0.20·Spread   (0–100)

- **Reach** — percentile of the item's headline audience metric today on its
  own platform (views / upvotes / search volume / posts). Log-scaled.
  Where a platform exposes no metric (Reddit RSS, X mirror, KYM, LinkedIn),
  rank on the platform's own list is the reach signal — never an invented
  number.
- **Velocity** — position on the platform's trending list (rank 1 ≈ 100,
  decaying across the list), blended with day-over-day change when the item
  was in yesterday's snapshot (state/ keeps one JSON per day). For
  metric-less platforms Reach and Velocity both derive from rank and are
  correlated by construction — on Reddit that mirrors reality (top-of-day
  rank *is* upvote velocity), but it means those items' scores lean on
  fewer independent signals, which the tier caps reflect.
- **Engagement** — percentile of (likes + comments + shares) / audience,
  where the source exposes those counts; neutral 50 where it does not.
- **Spread** — cross-platform resonance: how many *other* platforms today's
  cluster for this topic spans. This is the term no single-platform trending
  page can give you, and the main reason this tool exists.

**Qualification** (an item is a "viral hit" for the day if any holds):
V ≥ 60 · or its topic cluster spans ≥ 3 platforms · or it is top-10 on its
platform with top-quintile (≥80th pct) engagement.
**Tiers:** Mega ≥ 85 · Viral 70–84.9 · Rising 60–69.9 · Watch = qualified
only via a cluster/top-10 rule.

**Memes** are items from meme sources (r/memes, r/funny, Know Your Meme) or
flagged meme/comedy formats elsewhere. Meme *templates* matter more than
single posts, so meme clusters are reported in the commonality section.

## Commonality (cross-platform analysis)

Items are clustered across platforms by shared named entities (capitalized
phrases, hashtags) or ≥ 2 shared significant content tokens, via connected
components — deterministic, and every cluster lists the terms that caused
the grouping. Terms must be *distinctive* (tokens in ≤ 3% of the day's items; entities in ≤ 8%).
Small-sample guard: a platform returning < 8 items cannot mint a Viral-tier
score on its own (cap V ≤ 69) unless a cross-platform cluster lifts it.
Short titles (X trends, search terms) also merge by containment: all of a
1–2-term title appearing inside a longer title elsewhere. The digest reports: clusters spanning ≥ 2 platforms, the
most-overlapping platform pairs, and the meme share of the day's hits.
Known limit: token clustering misses paraphrases ("Game 7" vs "World
Series finale") and can over-merge on a dominant news day. It errs toward
precision: a missed cluster understates commonality, never invents it.

## Sources (all public, no keys — verified working 2026-10-29)

| Platform | Source | What it gives | Status |
|---|---|---|---|
| YouTube | ytdetective.com daily snapshot of the official US trending chart | rank, views, likes, comments, channel, category | OK (YouTube's own page no longer renders its chart logged-out) |
| TikTok | Endless Social Radar, US TikTok trending feed | rank, views, likes, author, sound | OK (TikTok Creative Center API now 401s anonymously) |
| X | trends24.in US card (mirror of X's US trends, hourly) | rank, tweet volume when published | OK |
| Reddit | reddit.com official RSS: r/popular, r/memes, r/funny, top of day | rank (score-ordered), subreddit, author | OK with pacing (JSON is 403 to anonymous IPs; RSS 429s if bursted) |
| Google Trends | trends.google.com/trending/rss?geo=US | term, approx. search volume, driving news story | OK (official) |
| LinkedIn | linkedin.com/showcase/linkedin-news public posts | LinkedIn News editor picks, text | LIMITED — no public trending feed or metrics exist |
| Facebook | facebook.com/watch | — | BLOCKED — login/app shell only |
| Instagram | instagram.com/explore | — | BLOCKED — login/app shell only |
| Memes | knowyourmeme.com front page | meme entries surfacing today | OK (signal-grade) |

Facebook/Instagram are reported BLOCKED rather than proxied: since Meta
shut down CrowdTangle (Aug 2024), no anonymous public surface ranks FB/IG
virality, and the Meta Content Library is application-only. Upgrade path:
connect Meta in Muse and replace `virality/sources/facebook_instagram.py`,
or feed it a Content Library export — the rest of the pipeline is unchanged.

US restriction: every source above is its US edition/chart. Reddit is the
one caveat — it publishes no US-only feed; r/popular served to US egress is
US-weighted.

## Output

`digests/YYYY-MM-DD.md` (human digest) + `.json` (all items, scores,
clusters, coverage). Sections: coverage · cross-platform commonality ·
top hits · memes · per-platform · method. Runs daily ~9am PT via Muse
cron `daily-virality-digest` (from the workspace mirror — scheduled runs
can't execute code on the Mac, same seam as the social digest); the code
canonical copy lives on the Mac in ~/projects/virality-tracker and runs
standalone there too: `python3 run_daily.py`.

## Non-goals / honesty rules

- No engagement bait, no rewritten headlines, no affiliate anything.
- No metric is ever estimated silently: missing metrics score neutral and
  the digest's coverage section says what each platform actually returned.
- Politeness: browser UA, ≤ 1 request/sec per host, retries ≤ 2. These are
  public pages/feeds read at human cadence, once a day.
