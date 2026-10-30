#!/usr/bin/env python3
"""Build the static website (GitHub Pages, served from docs/) from the
daily digest JSONs in digests/.

Usage:  python3 build_site.py [--digests DIR] [--out DIR]
Stdlib only. Images are downloaded + validated into docs/assets/<date>/
on first build and recorded in that day's media.json manifest, so older
days never change when the site is rebuilt.
"""
from __future__ import annotations
import argparse, json, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from virality import media as media_mod
from virality import render_site as rs

def resolve_media(story, assets_dir: Path, manifest: dict) -> dict:
    key = story["key"]
    if key in manifest:
        return manifest[key]
    result = {"type": "tile"}
    # 1) the source's own image (representative first, then other members)
    for m in story["members"]:
        url = (m.metrics or {}).get("image")
        if not url:
            continue
        got = media_mod.download_image(url, assets_dir)
        if got:
            result = {"type": "image", "file": got["file"], "credit": "",
                      "matte": bool(got["w"] and got["h"] and got["h"] > got["w"])}
            break
    # 2) the source's own video (official embed)
    if result["type"] == "tile":
        for m in story["members"]:
            emb = (m.metrics or {}).get("embed")
            if emb:
                result = {"type": "embed", "embed": emb}
                break
    # 3) top web-search image for the topic, credited
    if result["type"] == "tile" and story["presentable"]:
        query = story["title"] + (" news" if story["rep"].platform == "x" else "")
        found = media_mod.search_image(query)
        if found:
            img_url, page_url = found
            got = media_mod.download_image(img_url, assets_dir)
            if got:
                result = {"type": "image", "file": got["file"],
                          "credit": "Image: " + media_mod.domain_of(page_url or img_url),
                          "matte": bool(got["w"] and got["h"] and got["h"] > got["w"])}
    manifest[key] = result
    return result

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--digests", default=str(ROOT / "digests"))
    ap.add_argument("--out", default=str(ROOT / "docs"))
    args = ap.parse_args()
    dig_dir, out = Path(args.digests), Path(args.out)
    (out / "assets").mkdir(parents=True, exist_ok=True)
    (out / "assets" / "site.css").write_text(rs.SITE_CSS)
    (out / "data").mkdir(exist_ok=True)
    (out / ".nojekyll").write_text("")

    payloads = []
    for f in sorted(dig_dir.glob("*.json")):
        try:
            payloads.append(json.loads(f.read_text()))
        except Exception as e:
            print(f"skip {f.name}: {e}")
    if not payloads:
        print("no digest JSONs found"); return 1
    payloads.sort(key=lambda p: p["date"])

    summaries = []
    for payload in payloads:
        date_str = payload["date"]
        stories = rs.build_stories(payload)
        sets = rs.select_front_page(stories, payload)
        assets_dir = out / "assets" / date_str
        assets_dir.mkdir(parents=True, exist_ok=True)
        man_path = assets_dir / "media.json"
        manifest = json.loads(man_path.read_text()) if man_path.exists() else {}
        media_map = {}
        for group in sets[:3]:
            for s in group:
                media_map[s["key"]] = resolve_media(s, assets_dir, manifest)
        man_path.write_text(json.dumps(manifest, indent=1))
        day_dir = out / "days" / date_str
        day_dir.mkdir(parents=True, exist_ok=True)
        (day_dir / "index.html").write_text(rs.render_today(date_str, payload, stories, sets, media_map, prefix="../../"))
        (day_dir / "details.html").write_text(rs.render_details(date_str, payload, stories, sets, media_map, prefix="../../"))
        shutil.copyfile(dig_dir / f"{date_str}.json", out / "data" / f"{date_str}.json")
        summaries.append({"date": date_str, "qualified": len(payload.get("qualified_uids", [])),
                          "top_story": stories[0]["title"] if stories else "—",
                          "crossing": sum(1 for s in stories if s["crossing"])})
        print(f"{date_str}: {len(stories)} stories, top = {summaries[-1]['top_story'][:60]}")

    latest = payloads[-1]
    date_str = latest["date"]
    stories = rs.build_stories(latest)
    sets = rs.select_front_page(stories, latest)
    man = json.loads((out / "assets" / date_str / "media.json").read_text())
    (out / "index.html").write_text(rs.render_today(date_str, latest, stories, sets, man, prefix=""))
    (out / "details.html").write_text(rs.render_details(date_str, latest, stories, sets, man, prefix=""))
    (out / "history.html").write_text(rs.render_history(list(reversed(summaries)), prefix=""))
    print(f"Site built in {out} — latest {date_str}, {len(summaries)} day(s) of history")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
