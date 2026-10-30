"""Core data model. Every collector returns Item objects; nothing else in the
pipeline knows where an item came from."""
from __future__ import annotations
import hashlib, json
from dataclasses import dataclass, field, asdict

@dataclass
class Item:
    platform: str            # youtube | tiktok | x | reddit | facebook | instagram | linkedin | google_trends | memes
    title: str
    url: str
    rank: int | None = None          # position on the source's own trending list (1 = top)
    list_size: int | None = None     # size of that list, for percentile math
    author: str = ""
    summary_src: str = ""            # raw description/snippet from the source, used for the digest summary
    published_hint: str = ""         # e.g. "3 hours ago" when the source exposes it
    is_meme: bool = False
    metrics: dict = field(default_factory=dict)   # views, likes, comments, shares, upvotes, search_volume ...
    # filled by scoring.py
    virality: float = 0.0
    tier: str = ""
    why: list = field(default_factory=list)       # human-readable reasons it qualified

    @property
    def uid(self) -> str:
        return hashlib.sha1((self.platform + "|" + self.url).encode()).hexdigest()[:12]

    def to_dict(self):
        d = asdict(self); d["uid"] = self.uid; return d

    @classmethod
    def from_dict(cls, d):
        d = dict(d); d.pop("uid", None)
        return cls(**d)
