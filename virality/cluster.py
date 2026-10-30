"""Cross-platform commonality. Clusters items from different platforms that
are about the same thing, using TITLE tokens + named entities (capitalized
phrases and hashtags). Deterministic and explainable: every cluster lists
the terms that caused the grouping.

Rules (tuned 2026-10-29 after a first run over-merged on boilerplate):
- Titles only. Descriptions/summaries contain platform boilerplate
  ("Trending topic on X in the United States…") that chains everything.
- A term is *distinctive* only if it appears in <= 10% of today's items
  (document frequency), so common words can never cause a merge.
- Two items merge if they share >= 1 distinctive entity or >= 2 distinctive
  tokens. Connected components over that graph.
"""
from __future__ import annotations
import re
from collections import defaultdict, Counter
from .models import Item

STOP = set("""the a an and or of to in on for with is are was were be been it its it's this that these those
i you he she we they my your his her our their me him them who what when where why how all any some no not
but can could will would just like get got over under more most other others than then now here there from
into about after before between during out up down off again once only very too so such as at by an the
today tonight video videos watch live official trailer part parts full top best new news viral trending
fyp foryou foryoupage tiktok youtube shorts reel reels post posts day daily episode season game feat ft
hd 4k vs v s m re ll ve don didn isn aren wasn won let lets make makes made take takes took go goes went
man woman girl boy guy guys mr mrs get gets im i'm ive don't cant wont time never ever end ends welcome way still look looks looking thing things""".split())

def tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9][a-z0-9']+", text.lower())
    return {w for w in words if len(w) >= 3 and w not in STOP}

def entities(text: str) -> set[str]:
    ents = set()
    for m in re.findall(r"#(\w+)", text):
        if len(m) >= 3: ents.add(m.lower())
    for m in re.findall(r"\b([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+){1,3})\b", text):
        low = m.lower()
        if not any(w in STOP for w in low.split()): ents.add(low)
    return ents

def cluster_items(items: list[Item]) -> list[dict]:
    toks = {it.uid: tokens(it.title) for it in items}
    ents = {it.uid: entities(it.title) for it in items}
    df = Counter()
    for uid in toks:
        for t in toks[uid] | ents[uid]: df[t] += 1
    # Distinctiveness caps: tokens are weak evidence (tight cap), entities
    # (capitalized phrases / hashtags) are strong evidence (looser cap).
    tok_cap = max(3, int(0.03 * len(items)))
    ent_cap = max(3, int(0.08 * len(items)))
    toks = {u: {t for t in v if df[t] <= tok_cap} for u, v in toks.items()}
    ents = {u: {t for t in v if df[t] <= ent_cap} for u, v in ents.items()}
    parent = {it.uid: it.uid for it in items}
    def find(x):
        while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
        return x
    shared_why: dict[str, set] = defaultdict(set)
    uids = [it.uid for it in items]
    for i in range(len(uids)):
        for j in range(i + 1, len(uids)):
            a, b = uids[i], uids[j]
            shared_e = ents[a] & ents[b]
            shared_t = toks[a] & toks[b]
            # Containment: short titles (X trends, Google search terms are
            # often 1-2 words) merge when ALL their distinctive terms appear
            # in the other item — e.g. X "Doomsday" vs a YouTube title
            # "Avengers: Doomsday | Special Look".
            seta, setb = toks[a] | ents[a], toks[b] | ents[b]
            contained = (seta and len(seta) <= 2 and seta <= setb) or (setb and len(setb) <= 2 and setb <= seta)
            if contained: shared_t |= (seta & setb)
            if shared_e or len(shared_t) >= 2 or contained:
                ra, rb = find(a), find(b)
                if ra != rb: parent[rb] = ra
                shared_why[find(a)] |= (shared_e | shared_t)
    groups: dict[str, list[Item]] = defaultdict(list)
    by_uid = {it.uid: it for it in items}
    for uid in uids: groups[find(uid)].append(by_uid[uid])
    clusters = []
    for root, members in groups.items():
        platforms = sorted({m.platform for m in members})
        all_toks = Counter()
        for m in members: all_toks.update(toks[m.uid])
        common = [t for t, c in all_toks.most_common(6) if c >= 2]
        clusters.append({
            "uids": [m.uid for m in members],
            "platforms": platforms,
            "size": len(members),
            "label": max(members, key=lambda m: m.virality).title,
            "shared_terms": sorted(shared_why.get(root, set()))[:8] or common,
            "common_tokens": common,
            "max_virality": max(m.virality for m in members),
            "any_meme": any(m.is_meme for m in members),
        })
    clusters.sort(key=lambda c: (-len(c["platforms"]), -c["max_virality"]))
    return clusters
