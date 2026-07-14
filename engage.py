# -*- coding: utf-8 -*-
"""Tumblr リブログ経済ループ（超保守的・like中心）。

matureラベルでSFWタグ検索が弱い成人ミューズ系Tumblrは、伸びるのが「コミュニティの相互発見」。
その最小・最安全版として、自ニッチのタグの新着に少量だけ like を付ける。

★安全設計（Tumblrのbot判定/凍結を避けるのが最優先。稼働資産を守る）★
  - like のみ（follow/reblog はやらない = bot判定されにくい）
  - 1回 MAX_LIKES 件まで / 各likeの間に人間らしいランダム遅延
  - 自分の投稿・既likeはスキップ / 冪等ログ engaged_log.json
  - 1日1回想定。異常時は黙って止まる（投稿本体には一切影響しない別プロセス）

使い方:
  python engage.py --dry-run   # like せず「何にlikeするか」だけ表示（まず必ずこれで確認）
  python engage.py             # 実際に like
"""
import json
import os
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

LOG = HERE / "engaged_log.json"
DRY = "--dry-run" in sys.argv

# 自ニッチのコミュニティタグ（毎回ここから数個ローテ）
TARGET_TAGS = [
    "female muscle", "muscle girl", "fbb", "female bodybuilder",
    "girls with muscle", "muscle worship", "women with muscle", "muscular woman",
    "fit girl", "gym girl",
]
MAX_LIKES = 15           # 1回の上限（保守的）
TAGS_PER_RUN = 3         # 1回に見るタグ数
PER_TAG_SCAN = 15        # 各タグの新着スキャン数
MIN_DELAY, MAX_DELAY = 4, 11   # like間の遅延秒（人間らしく）
MAX_LOG = 3000


def build_client():
    import pytumblr
    keys = ["TUMBLR_CONSUMER_KEY", "TUMBLR_CONSUMER_SECRET",
            "TUMBLR_OAUTH_TOKEN", "TUMBLR_OAUTH_TOKEN_SECRET"]
    vals = [os.environ.get(k, "") for k in keys]
    if not all(vals):
        print("ERROR: TUMBLR_* 認証情報が未設定")
        return None
    return pytumblr.TumblrRestClient(*vals)


def load_log():
    try:
        return set(json.loads(LOG.read_text(encoding="utf-8")))
    except Exception:
        return set()


def save_log(s):
    data = sorted(s)
    if len(data) > MAX_LOG:
        data = data[-MAX_LOG:]
    LOG.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    cl = build_client()
    if cl is None:
        return 2
    info = cl.info()
    me = (info or {}).get("user", {}).get("name", "")
    if not me:
        print(f"Auth error: {info}")
        return 1
    print(f"engage as: {me}  dry_run={DRY}")

    done = load_log()
    liked = 0
    tags = random.sample(TARGET_TAGS, min(TAGS_PER_RUN, len(TARGET_TAGS)))
    print(f"target tags this run: {tags}")

    for tag in tags:
        if liked >= MAX_LIKES:
            break
        try:
            posts = cl.tagged(tag, limit=PER_TAG_SCAN) or []
        except Exception as e:
            print(f"tagged({tag}) error: {e}")
            continue
        random.shuffle(posts)
        for p in posts:
            if liked >= MAX_LIKES:
                break
            pid = str(p.get("id") or "")
            rk = p.get("reblog_key")
            bn = p.get("blog_name", "")
            if not pid or not rk or bn == me or pid in done:
                continue
            if DRY:
                print(f"[dry] would like {bn}/{pid}  (#{tag})")
                done.add(pid)
                liked += 1
                continue
            try:
                cl.like(pid, rk)
                print(f"liked {bn}/{pid}  (#{tag})")
                done.add(pid)
                liked += 1
                time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
            except Exception as e:
                print(f"like error {pid}: {e}")
                continue

    if not DRY:
        save_log(done)
    print(f"done. liked={liked} (dry_run={DRY})")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
