import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from virality.models import Item
from virality import scoring, cluster as cm

def test_cluster_and_spread():
    items = [
        Item(platform="youtube", title="Dune: Part Three | Final Trailer", url="https://youtube.com/watch?v=a", rank=2, list_size=50, metrics={"views": 15_000_000, "likes": 150_000, "comments": 8_000}),
        Item(platform="x", title="Dune Part Three", url="https://twitter.com/search?q=Dune", rank=3, list_size=50, metrics={}),
        Item(platform="google_trends", title="dune part three", url="https://trends.google.com/x", rank=1, list_size=25, metrics={"search_volume": 500_000}),
        Item(platform="tiktok", title="BOW #golf #golfer", url="https://tiktok.com/@g/video/1", rank=4, list_size=30, metrics={"views": 25_000_000, "likes": 3_000_000}),
    ]
    scoring.score_items(items, {})
    clusters = cm.cluster_items(items)
    scoring.apply_spread(items, clusters)
    multi = [c for c in clusters if len(c["platforms"]) >= 2]
    assert multi and set(multi[0]["platforms"]) == {"youtube", "x", "google_trends"}, multi
    yt = items[0]
    assert yt.metrics["_platforms_in_cluster"] == 3
    assert yt.virality > items[3].virality or yt.metrics["_spread"] == 50.0
    print("ok")

if __name__ == "__main__":
    test_cluster_and_spread()

def test_containment():
    items = [
        Item(platform="x", title="Doomsday", url="https://x/1", rank=4, list_size=50),
        Item(platform="youtube", title="Avengers: Doomsday | Special Look", url="https://yt/1", rank=10, list_size=50, metrics={"views": 5_000_000}),
        Item(platform="tiktok", title="Doomsday dance challenge", url="https://tt/1", rank=9, list_size=30, metrics={"views": 9_000_000}),
    ]
    cs = cm.cluster_items(items)
    multi = [c for c in cs if len(c["platforms"]) >= 2]
    assert multi and set(multi[0]["platforms"]) == {"x", "youtube", "tiktok"}, multi
    print("ok containment")

def test_reddit_image_parse():
    from virality.sources.reddit import parse_feed
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
 <entry>
  <title>Test post</title>
  <link href="https://www.reddit.com/r/memes/comments/abc123/test_post/"/>
  <author><name>/u/tester</name></author>
  <content type="html">&lt;span&gt;&lt;a href="https://i.redd.it/xyz789.jpg"&gt;[link]&lt;/a&gt;&lt;/span&gt;</content>
 </entry>
</feed>"""
    items = parse_feed(xml, "memes", True, 15)
    assert len(items) == 1, items
    assert items[0].metrics["image"] == "https://i.redd.it/xyz789.jpg", items[0].metrics
