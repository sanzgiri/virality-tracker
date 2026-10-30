"""Render the website (static HTML) from digest JSON payloads.

Implements the site's settled rules (user, 2026-10-29):
- Front page is minimal and visual: image-forward story cards, one-line
  summaries, no metrics. Metrics live on the Details page.
- Stories are deduplicated across platforms (the digest's clusters): one
  card per story, platform chips for every platform it is moving on.
- Media ladder: source's own image -> source's video (official embed) ->
  top web-search image (credited) -> designed typographic tile. Images are
  never stretched: native aspect, contain-fit, blurred backdrop (or plain
  matte for portraits/faces).
- Primary links never require a login: an item's own link on an open
  platform; for a cross-platform story, the login-free platform's version;
  X-only topics link to a Google News search, with the X link kept in
  Details labeled "login required".
- Caption-less items (no title/summary from the source) are not featured
  on the front page; they appear in Details' Also scored with the reason.
"""
from __future__ import annotations
import html, urllib.parse
from datetime import date as _date
from .models import Item
from .summarize import summary as item_summary, why as item_why, PLATFORM_LABEL

OPEN_PLATFORMS = {"youtube", "reddit", "tiktok", "memes", "google_trends"}
ORDER = ["youtube", "tiktok", "x", "reddit", "google_trends", "linkedin", "facebook", "instagram", "memes"]
WATCHING = {
    "youtube": "No login needed", "tiktok": "Plays logged out; may prompt to sign in",
    "x": "Login required to view", "reddit": "No login needed",
    "google_trends": "No login needed", "memes": "No login needed",
    "linkedin": "Partial without login",
    "facebook": "Login required (and no public trending surface)",
    "instagram": "Login required (and no public trending surface)",
}
SITE_TITLE = "Crosscurrent"
TAGLINE = "What's actually viral in the US today — measured across platforms, not listicled."

def esc(s) -> str:
    return html.escape(str(s or ""), quote=True)

def pretty_date(date_str: str) -> str:
    d = _date.fromisoformat(date_str)
    return f"{d:%A, %B} {d.day}, {d.year}"

def news_search_url(topic: str) -> str:
    return "https://news.google.com/search?q=" + urllib.parse.quote(topic) + "&hl=en-US&gl=US&ceid=US%3Aen"

def _trim(s: str, n: int = 110) -> str:
    s = " ".join(str(s).split())
    if len(s) <= n: return s
    return s[:n].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"

def _presentable(it: Item) -> bool:
    return bool(it.title) and not it.title.startswith("TikTok video by")

def build_stories(payload: dict) -> list[dict]:
    items = [Item.from_dict(d) for d in payload["items"]]
    by_uid = {it.uid: it for it in items}
    qualified = set(payload.get("qualified_uids", []))
    stories, used = [], set()
    for c in payload.get("clusters", []):
        if len(c.get("platforms", [])) < 2: continue
        members = [by_uid[u] for u in c["uids"] if u in by_uid]
        if not members: continue
        members.sort(key=lambda it: -it.virality)
        if not any(m.uid in qualified for m in members): continue
        stories.append(_make_story(members, crossing=True))
        used.update(m.uid for m in members)
    for it in items:
        if it.uid in qualified and it.uid not in used:
            stories.append(_make_story([it], crossing=False))
    stories.sort(key=lambda s: -s["max_v"])
    return stories

def _make_story(members: list[Item], crossing: bool) -> dict:
    rep = members[0]
    presentable_members = [m for m in members if _presentable(m)]
    face = presentable_members[0] if presentable_members else rep
    # story title
    x_titles = [m.title for m in members if m.platform == "x"]
    if len(x_titles) >= 2 and all(len(t.split()) <= 3 for t in x_titles[:2]):
        title = " / ".join(x_titles[:2])
    elif len(rep.title.split()) <= 2:
        longer = next((m.title.split(" | ")[0] for m in members
                       if m is not rep and rep.title.lower() in m.title.lower()
                       and len(m.title) > len(rep.title)), None)
        title = longer or rep.title
    else:
        title = rep.title
    platforms = sorted({m.platform for m in members}, key=lambda p: ORDER.index(p) if p in ORDER else 99)
    # primary (login-free) link
    primary = None
    if rep.platform in OPEN_PLATFORMS:
        primary = rep.url
    else:
        open_member = next((m for m in members if m.platform in OPEN_PLATFORMS), None)
        primary = open_member.url if open_member else news_search_url(title)
    return {
        "key": rep.uid, "title": title, "members": members, "rep": rep, "face": face,
        "platforms": platforms, "max_v": rep.virality, "tier": rep.tier,
        "is_meme": any(m.is_meme for m in members), "crossing": crossing,
        "presentable": bool(presentable_members),
        "summary": _trim(item_summary(face), 110),
        "primary_url": primary,
        "x_links": [m.url for m in members if m.platform == "x"],
        "why": item_why(rep, platforms if crossing else None),
    }

def select_front_page(stories: list[dict], payload: dict):
    """(top_hits, videos, memes, also_scored) per the front-page rules."""
    shown = set()
    top_hits = []
    for s in stories:
        if len(top_hits) >= 10: break
        if s["presentable"]:
            top_hits.append(s); shown.add(s["key"])
    items = [Item.from_dict(d) for d in payload["items"]]
    member_uids_shown = {m.uid for s in top_hits for m in s["members"]}
    videos = []
    for it in sorted([i for i in items if i.platform == "youtube"], key=lambda i: -i.virality):
        if len(videos) >= 3: break
        if it.uid in member_uids_shown or not _presentable(it): continue
        videos.append(_make_story([it], crossing=False)); member_uids_shown.add(it.uid)
    memes = []
    for s in stories:
        if len(memes) >= 4: break
        if s["is_meme"] and s["presentable"] and s["key"] not in shown:
            memes.append(s); shown.add(s["key"])
    also = [s for s in stories if s["key"] not in shown
            and all(v["key"] != s["key"] for v in videos)]
    return top_hits, videos, memes, also

# ---------- HTML ----------

def _chips(story) -> str:
    out = "".join(f'<span class="chip chip-{p}">{esc(PLATFORM_LABEL.get(p, p))}</span>' for p in story["platforms"])
    if story["crossing"]: out += '<span class="chip chip-cross">Crossing platforms</span>'
    return out

def _tile(story) -> str:
    return f'<div class="tile"><span>{esc(story["title"])}</span></div>'

def _media(story, media, prefix: str, date_str: str) -> str:
    chips = f'<div class="chips">{_chips(story)}</div>'
    if media and media.get("type") == "image":
        src = f'{prefix}assets/{date_str}/{media["file"]}'
        cls = "media matte" if media.get("matte") else "media"
        bg = "" if media.get("matte") else f'<img class="bg" src="{src}" alt="" aria-hidden="true" onerror="this.remove()">'
        credit = f'<div class="credit">{esc(media["credit"])}</div>' if media.get("credit") else ""
        return (f'<div class="{cls}">{bg}<img class="fg" src="{src}" alt="{esc(story["title"])}" '
                f'onerror="imgFail(this)">{_tile(story)}{chips}{credit}</div>')
    if media and media.get("type") == "embed":
        return (f'<div class="media media-video"><div class="video-fallback"><div class="play">▶</div>'
                f'<div class="vf-title">{esc(story["title"])}</div>'
                f'<a href="{esc(story["primary_url"])}">Watch on {esc(PLATFORM_LABEL.get(story["rep"].platform, ""))}</a></div>'
                f'<iframe src="{esc(media["embed"])}" loading="lazy" title="{esc(story["title"])}" '
                f'allow="accelerometer; autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" allowfullscreen></iframe>'
                f'{_tile(story)}{chips}</div>')
    return f'<div class="media tileonly">{_tile(story)}{chips}</div>'

def _card(story, media, prefix: str, date_str: str) -> str:
    return (f'<article class="card"><a class="media-link" href="{esc(story["primary_url"])}">{_media(story, media, prefix, date_str)}</a>'
            f'<div class="card-body"><h3><a href="{esc(story["primary_url"])}">{esc(story["title"])}</a></h3>'
            f'<p>{esc(story["summary"])}</p></div></article>')

def _page(title: str, body: str, prefix: str, active: str, date_str: str = "") -> str:
    nav = "".join(
        f'<a href="{href}" class="{"on" if key == active else ""}">{label}</a>'
        for key, href, label in [("today", "index.html", "Today"), ("details", "details.html", "Details &amp; method"),
                                 ("history", f"{prefix}history.html", "History")])
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} — {SITE_TITLE}</title><link rel="stylesheet" href="{prefix}assets/site.css">
<script>function imgFail(el){{var c=el.closest('.card, .media');if(c)c.classList.add('noimg');}}</script></head>
<body><header class="masthead"><div class="brand">{SITE_TITLE}</div><div class="tagline">{TAGLINE}</div>
<div class="dateline">{esc(pretty_date(date_str)) if date_str else ""}</div><nav>{nav}</nav></header>
<main>{body}</main>
<footer><nav>{nav}</nav><p>{SITE_TITLE} · Data: public trending surfaces, collected daily. Facebook &amp; Instagram have no public trending surface since CrowdTangle shut down in 2024 — shown as blocked, never proxied.</p></footer>
</body></html>"""

def render_today(date_str, payload, stories, sets, media_map, prefix=""):
    top_hits, videos, memes, _also = sets
    cov = payload["coverage"]
    ok = [c for c in cov if c["status"].startswith("OK")]
    limited = [c["platform"] for c in cov if c["status"].startswith("LIMITED")]
    blocked = [c["platform"] for c in cov if "BLOCKED" in c["status"]]
    cov_line = (f'Today across {", ".join(PLATFORM_LABEL.get(c["platform"], c["platform"]) for c in ok)}'
                + (f' · {", ".join(PLATFORM_LABEL.get(p, p) for p in limited)} limited' if limited else "")
                + (f' · {", ".join(PLATFORM_LABEL.get(p, p) for p in blocked)} unavailable' if blocked else "")
                + ' · <a href="details.html">coverage &amp; method</a>')
    parts = [f'<p class="covline">{cov_line}</p>']
    parts.append('<section><h2>Top hits</h2><p class="sub">The ten biggest stories of the day, in order.</p><div class="grid">')
    parts += [_card(s, media_map.get(s["key"]), prefix, date_str) for s in top_hits]
    parts.append('</div></section>')
    if videos:
        parts.append('<section><h2>Top video today</h2><div class="grid">')
        parts += [_card(s, media_map.get(s["key"]), prefix, date_str) for s in videos]
        parts.append('</div></section>')
    if memes:
        parts.append('<section><h2>Memes moving</h2><div class="grid">')
        parts += [_card(s, media_map.get(s["key"]), prefix, date_str) for s in memes]
        parts.append('</div></section>')
    trends = sorted([Item.from_dict(d) for d in payload["items"] if d["platform"] == "google_trends"],
                    key=lambda i: i.rank or 999)
    if trends:
        rows = []
        for it in trends:
            headline = (it.metrics or {}).get("news_title", "")
            src = (it.metrics or {}).get("news_source", "")
            nurl = (it.metrics or {}).get("news_url", "")
            if headline:
                expl = (f'<a href="{esc(nurl)}">{esc(headline)}</a>' if nurl else esc(headline))
                if src: expl += f' <span class="tsrc">· {esc(src)}</span>'
            else:
                expl = '<span class="tsrc">No single story is driving this one.</span>'
            rows.append(f'<div class="trow"><a class="gchip" href="{esc(it.url)}">{esc(it.title)}</a>'
                        f'<span class="texpl">{expl}</span></div>')
        parts.append('<section><h2>US is searching</h2><p class="sub">The headline driving each search, per Google Trends.</p>'
                     f'<div class="tlist">{"".join(rows)}</div></section>')
    return _page(pretty_date(date_str), "".join(parts), prefix, "today", date_str)

def render_details(date_str, payload, stories, sets, media_map, prefix=""):
    top_hits, _v, _m, also = sets
    items = payload["items"]
    multi = sum(1 for s in stories if s["crossing"])
    top_v = max((s["max_v"] for s in stories), default=0)
    parts = ['<section><h2>Details &amp; method</h2>']
    parts.append(f'<div class="stats"><div><b>{len(items)}</b><span>items tracked</span></div>'
                 f'<div><b>{len(payload.get("qualified_uids", []))}</b><span>qualified as viral</span></div>'
                 f'<div><b>{multi}</b><span>stories crossed platforms</span></div>'
                 f'<div><b>{top_v:.0f}</b><span>top virality score</span></div></div></section>')
    # coverage + watching
    parts.append('<section><h2>Coverage today</h2><table class="cov"><tr><th>Platform</th><th>Status</th><th>Watching — login?</th></tr>')
    for c in payload["coverage"]:
        p = c["platform"]
        parts.append(f'<tr><td>{esc(PLATFORM_LABEL.get(p, p))}</td><td>{esc(c["status"])}</td>'
                     f'<td>{esc(WATCHING.get(p, ""))}</td></tr>')
    parts.append('</table><p class="note">This site never requires login. Only some outbound platforms do.</p></section>')
    # top 10 table
    parts.append('<section><h2>Top 10 — with the numbers</h2><table class="top"><tr><th>#</th><th>Story</th><th>Platforms</th><th>Virality</th><th>Why it is here</th></tr>')
    for i, s in enumerate(top_hits, 1):
        plats = ", ".join(PLATFORM_LABEL.get(p, p) for p in s["platforms"])
        xl = "".join(f' <a class="xlink" href="{esc(u)}">X (login required)</a>' for u in s["x_links"])
        parts.append(f'<tr><td>{i}</td><td><a href="{esc(s["primary_url"])}">{esc(s["title"])}</a>{xl}</td>'
                     f'<td>{esc(plats)}</td><td><span class="vchip tier-{esc(s["tier"])}">{s["max_v"]:.0f} · {esc(s["tier"])}</span>'
                     f'<span class="bar"><span style="width:{s["max_v"]:.0f}%"></span></span></td><td>{esc(s["why"])}</td></tr>')
    parts.append('</table></section>')
    # also scored
    if also:
        parts.append('<section><h2>Also scored today</h2><ul class="also">')
        for s in also:
            note = "" if s["presentable"] else " No caption or title is exposed by the source, so it is not featured on the front page."
            plats = ", ".join(PLATFORM_LABEL.get(p, p) for p in s["platforms"])
            parts.append(f'<li><a href="{esc(s["primary_url"])}">{esc(s["title"])}</a> — {esc(plats)} · '
                         f'V {s["max_v"]:.0f} ({esc(s["tier"])}) · {esc(s["why"])}{esc(note)}</li>')
        parts.append('</ul></section>')
    # by platform
    parts.append('<section><h2>By platform</h2>')
    by_plat = {}
    for d in items: by_plat.setdefault(d["platform"], []).append(Item.from_dict(d))
    for p in ORDER:
        group = sorted(by_plat.get(p, []), key=lambda i: -i.virality)[:5]
        if not group: continue
        parts.append(f'<h3>{esc(PLATFORM_LABEL.get(p, p))}</h3><ul class="also">')
        for it in group:
            url = it.url if p in OPEN_PLATFORMS else news_search_url(it.title)
            xl = f' <a class="xlink" href="{esc(it.url)}">{esc(PLATFORM_LABEL.get(p, p))} (login required)</a>' if p not in OPEN_PLATFORMS else ""
            parts.append(f'<li><a href="{esc(url)}">{esc(it.title)}</a>{xl} — {esc(item_why(it))}</li>')
        parts.append('</ul>')
    parts.append('</section>')
    # method
    parts.append('''<section><h2>Method &amp; limits</h2><div class="method">
<p><b>Virality V</b> = 0.35·Reach + 0.25·Velocity + 0.20·Engagement + 0.20·Spread, computed as within-platform percentiles (raw counts are not comparable across platforms). A story qualifies at V ≥ 60, via a ≥3-platform cluster, or as a top-10 platform item with top-quintile engagement. Tiers: Mega ≥ 85 · Viral 70–84 · Rising 60–69 · Watch = qualified by cluster/top-10 rule only.</p>
<p><b>US only.</b> Sources are the US editions/charts of each platform. Reddit publishes no US-only feed — r/popular from US egress is US-weighted, not US-exclusive.</p>
<p><b>Media.</b> If a source provides no usable image, the card falls back to the source's video, then to a designed title tile. Broken image placeholders are never shown. Where an item's own page provides no image, the card may use the top relevant web-search image for the topic, credited to its source. Images are shown at their native aspect ratio, never stretched; portraits sit on a plain matte.</p>
<p><b>Links.</b> Links prefer a destination you can open without an account: where a story runs on several platforms, the card links the login-free version; X-only topics link to a news search, with the X link kept here and labeled "login required".</p>
<p><b>Facebook / Instagram.</b> No public anonymous trending surface exists since Meta shut down CrowdTangle in Aug 2024 (the Content Library is application-only). Reported as BLOCKED rather than filled with proxied or invented data.</p>
<p><b>LinkedIn.</b> No public trending feed; only LinkedIn News editor picks, no metrics — labeled LIMITED, and a small source cannot mint a high tier on its own.</p>
<p>Summaries and "why" lines are generated from the sources' own text and measured metrics only.</p>
</div></section>''')
    return _page("Details & method", "".join(parts), prefix, "details", date_str)

def render_history(day_summaries, prefix=""):
    rows = []
    for d in day_summaries:
        rows.append(f'<tr><td><a href="{prefix}days/{d["date"]}/index.html">{esc(pretty_date(d["date"]))}</a></td>'
                    f'<td>{esc(d["top_story"])}</td><td>{d["qualified"]}</td><td>{d["crossing"]}</td></tr>')
    body = ('<section><h2>History</h2><p class="sub">Every day\'s edition is kept permanently.</p>'
            '<table class="cov"><tr><th>Date</th><th>Top story</th><th>Qualified</th><th>Cross-platform</th></tr>'
            + "".join(rows) + '</table>'
            '<p class="note">History accrues one edition per day.</p></section>')
    return _page("History", body, prefix, "history")

SITE_CSS = """
:root{--bg:#0b0e13;--panel:#12161e;--panel2:#171c26;--ink:#e8ecf1;--dim:#9aa5b1;--line:#232a36;--accent:#ff7a1a;--blue:#57b6ff;--violet:#b78cff;--gray:#8a94a3}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 -apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif}
a{color:var(--ink)}a:hover{color:var(--accent)}
.masthead{padding:28px 20px 10px;max-width:1180px;margin:0 auto}
.brand{font-size:34px;font-weight:800;letter-spacing:-.5px}.tagline{color:var(--dim);margin-top:2px}
.dateline{color:var(--dim);margin-top:6px;font-size:14px}
nav{margin-top:12px;display:flex;gap:16px}nav a{color:var(--dim);text-decoration:none;font-weight:600}nav a.on{color:var(--ink);border-bottom:2px solid var(--accent)}
main{max-width:1180px;margin:0 auto;padding:10px 20px 30px}
.covline{color:var(--dim);font-size:14px;border:1px solid var(--line);background:var(--panel);border-radius:10px;padding:10px 14px}
section{margin-top:28px}h2{font-size:22px;margin:0 0 4px}h3{margin:18px 0 6px}.sub{color:var(--dim);margin:0 0 14px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;overflow:hidden;display:flex;flex-direction:column}
.card-body{padding:12px 14px 14px}.card-body h3{margin:0 0 6px;font-size:17px;line-height:1.3}.card-body p{margin:0;color:var(--dim);font-size:14px}
.media{position:relative;aspect-ratio:16/10;background:#05070a;overflow:hidden}
.media img.bg{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;filter:blur(22px) brightness(.42);transform:scale(1.18)}
.media img.fg{position:absolute;inset:0;width:100%;height:100%;object-fit:contain}
.media.matte img.fg{object-fit:contain}
.media .tile{display:none;position:absolute;inset:0;padding:18px;align-items:flex-end;background:linear-gradient(140deg,#1b2432,#0d1118)}
.media .tile span{font-size:24px;font-weight:800;line-height:1.2}
.media.tileonly .tile,.card.noimg .media .tile,.noimg .media .tile{display:flex}
.card.noimg .media img,.noimg .media img{display:none}
.chips{position:absolute;top:10px;left:10px;display:flex;gap:6px;flex-wrap:wrap;z-index:3}
.chip{font-size:11px;font-weight:700;padding:3px 8px;border-radius:999px;background:rgba(10,12,16,.82);color:var(--ink);border:1px solid var(--line)}
.chip-cross{background:var(--accent);color:#14100b;border-color:transparent}
.credit{position:absolute;right:10px;bottom:8px;z-index:3;font-size:11px;color:var(--dim);background:rgba(10,12,16,.75);padding:2px 7px;border-radius:6px}
.media-video iframe{position:absolute;inset:0;width:100%;height:100%;border:0;z-index:1;background:transparent}
.video-fallback{position:absolute;inset:0;z-index:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;background:linear-gradient(160deg,#1a2230,#0a0d12);color:var(--dim)}
.video-fallback .play{font-size:44px;color:var(--ink)}.video-fallback a{font-weight:700}
.chipsrow{display:flex;gap:8px;flex-wrap:wrap}
.tlist{display:flex;flex-direction:column;gap:8px}
.trow{display:flex;gap:12px;align-items:baseline;flex-wrap:wrap;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:9px 12px}
.trow .gchip{flex:none}.texpl{color:var(--dim);font-size:14px}.texpl a{color:var(--ink);text-decoration:none}.texpl a:hover{color:var(--accent)}.tsrc{color:var(--gray)}
.gchip{border:1px solid var(--line);background:var(--panel);border-radius:999px;padding:7px 13px;text-decoration:none;font-weight:600}
.gchip:hover{border-color:var(--accent);color:var(--accent)}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.stats div{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px}
.stats b{display:block;font-size:28px}.stats span{color:var(--dim);font-size:13px}
table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--line);vertical-align:top;font-size:14px}
th{color:var(--dim);font-weight:700}.note{color:var(--dim);font-size:14px}
.vchip{font-weight:800;padding:2px 8px;border-radius:6px;background:var(--panel2);white-space:nowrap}
.tier-Viral{color:var(--accent)}.tier-Rising{color:var(--blue)}.tier-Mega{color:var(--violet)}.tier-Watch{color:var(--gray)}
.bar{display:block;height:5px;background:#0a0d12;border-radius:3px;margin-top:5px;min-width:90px}.bar span{display:block;height:100%;background:var(--accent);border-radius:3px}
.also{list-style:none;padding:0;margin:0}.also li{padding:7px 0;border-bottom:1px solid var(--line);font-size:14px;color:var(--dim)}
.also a{font-weight:600}.xlink{font-size:12px;color:var(--dim)}
.method p{color:var(--dim);max-width:75ch}.method b{color:var(--ink)}
footer{max-width:1180px;margin:0 auto;padding:10px 20px 40px;color:var(--dim);font-size:13px;border-top:1px solid var(--line)}
footer nav{margin:8px 0}
@media (max-width:640px){.brand{font-size:27px}.grid{grid-template-columns:1fr}}
"""
