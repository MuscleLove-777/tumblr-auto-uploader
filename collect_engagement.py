# -*- coding: utf-8 -*-
"""
Tumblr投稿の反応(notes数)を回収して engagement.json へ書き出す。
posted_log.json の変種記録と post_id で結合し、autonomy/analyze_variants.py が
「どのキャプション変種が反応を取ったか」を採点する材料になる。

GitHub Actions で upload 後に実行し、posted_log.json と一緒に commit する。
失敗しても exit 0（計測は投稿を絶対に止めない）。
"""
import json
import os
import sys
import time

import pytumblr

BLOG_NAME = "muscular-japanese-girls"
OUT_PATH = "engagement.json"
MAX_POSTS = 60  # 直近60投稿分のnotesを追跡（それより古い変種評価は確定済み扱い）


def main():
    consumer_key = os.environ.get("TUMBLR_CONSUMER_KEY", "")
    consumer_secret = os.environ.get("TUMBLR_CONSUMER_SECRET", "")
    oauth_token = os.environ.get("TUMBLR_OAUTH_TOKEN", "")
    oauth_token_secret = os.environ.get("TUMBLR_OAUTH_TOKEN_SECRET", "")
    if not all([consumer_key, consumer_secret, oauth_token, oauth_token_secret]):
        print("skip: missing Tumblr credentials")
        return 0

    client = pytumblr.TumblrRestClient(
        consumer_key, consumer_secret, oauth_token, oauth_token_secret)

    existing = {}
    if os.path.exists(OUT_PATH):
        try:
            with open(OUT_PATH, "r", encoding="utf-8") as f:
                existing = json.load(f).get("posts", {})
        except Exception:
            existing = {}

    posts = {}
    offset = 0
    while offset < MAX_POSTS:
        try:
            resp = client.posts(BLOG_NAME, limit=20, offset=offset)
        except Exception as e:
            print(f"fetch error at offset {offset}: {e}")
            break
        batch = resp.get("posts", []) if isinstance(resp, dict) else []
        if not batch:
            break
        for p in batch:
            pid = str(p.get("id", ""))
            if not pid:
                continue
            posts[pid] = {
                "notes": int(p.get("note_count", 0) or 0),
                "url": p.get("post_url", ""),
                "date": p.get("date", ""),
            }
        offset += 20

    if not posts:
        print("no posts fetched; keeping existing engagement.json")
        return 0

    # 古い記録は保持しつつ新しい値で上書き（notesは増えるだけなので単純merge）
    existing.update(posts)
    out = {
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "blog": BLOG_NAME,
        "posts": existing,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"engagement.json updated: {len(posts)} fetched / {len(existing)} total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
