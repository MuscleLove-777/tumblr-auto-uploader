# -*- coding: utf-8 -*-
"""
Tumblr動画ランダムアップロード（GitHub Actions用）
Google Driveからダウンロード → ランダム1本アップロード（重複許可）
"""
import argparse
import json
import sys, os, random
from pathlib import Path

try:
    import pytumblr
except ImportError:
    pytumblr = None

try:
    import gdown
except ImportError:
    gdown = None

# 変種バンディット（重み付き抽選＋投稿ログ）。無くても一様ランダムで動く。
try:
    from variant_bandit import pick as bandit_pick, with_utm_content, log_post
except Exception:
    def bandit_pick(kind, options, rng=random):
        o = rng.choice(options)
        return o, ""
    def with_utm_content(url, key):
        return url
    def log_post(platform, record):
        pass

GDRIVE_FOLDER_ID = os.environ.get("GDRIVE_FOLDER_ID", "")
BLOG_NAME = "muscular-japanese-girls"
PATREON_LINK = "https://www.patreon.com/c/MuscleLove?utm_source=tumblr"
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.wmv', '.mkv', '.webm'}
MAX_FILE_SIZE = 500 * 1024 * 1024
DRY_RUN_VIDEO_NAME = os.environ.get("TUMBLR_DRY_RUN_VIDEO_NAME", "training_flex_preview.mp4")
DRY_RUN_ARTIFACT = "dry_run_tumblr_preview.json"
PREVIEW_BLOCK_TERMS = [
    "GOOGLE_API_KEY",
    "Google API",
    "Google Cloud",
    "cookie",
    "secret",
]

CONTENT_TAG_MAP = {
    'training': ['筋トレ', 'workout', 'training', 'gym', 'fitness'],
    'workout': ['筋トレ', 'workout', 'training', 'gym', 'fitness'],
    'toilet': ['筋肉女子', 'muscle girl', 'muscular woman'],
    'pullups': ['懸垂', 'pullups', 'pull ups', 'back workout', 'calisthenics'],
    'posing': ['ポージング', 'posing', 'bodybuilding', 'physique'],
    'flex': ['フレックス', 'flex', 'muscle', 'bodybuilding'],
    'muscle': ['筋肉', 'muscle', 'muscular', 'fitness'],
    'bicep': ['上腕二頭筋', 'biceps', 'arms', 'muscle'],
    'abs': ['腹筋', 'abs', 'sixpack', 'core'],
    'leg': ['脚トレ', 'legs', 'quads', 'legday'],
    'back': ['背中', 'back', 'lats', 'backday'],
    'squat': ['スクワット', 'squat', 'legs', 'legday'],
    'deadlift': ['デッドリフト', 'deadlift', 'powerlifting'],
    'bench': ['ベンチプレス', 'benchpress', 'chest'],
}

# Tumblr実タグ厳選。先頭ほど検索露出が強い(Tumblrは先頭~20-25タグのみ検索対象)ので、
# muscle/FBBコミュニティの"実リブログ動線"タグを核に前詰め。過剰な性的シグナル/弱い/重複タグは排除。
BASE_TAGS = [
    'female muscle', 'muscle girl', 'fbb', 'female bodybuilder', 'girls with muscle',
    'muscular woman', 'strong women', 'muscle worship', 'fit girl', 'gym girl',
    'bodybuilding', 'physique', 'biceps', 'abs', 'fitness',
    'fitfam', 'women with muscle', '筋肉女子', '筋トレ女子', 'MuscleLove',
]

# ローテ用プール(毎回ここから数個サンプル=同一タグ連打のスパム判定回避+変化)。
# Google Trends(pytrends)は"musclegirlbar"等の的外れ語を拾うため不使用。Tumblr実タグに限定。
TUMBLR_ROTATING_TAGS = [
    'muscular', 'strong is beautiful', 'fitness motivation', 'workout motivation',
    'gains', 'aesthetic', 'gym life', 'strong girl', 'muscle beauty', 'ai art',
    'ai generated', 'fitness girl', 'flexing', 'muscular women', 'fit women',
    'body goals', 'strong and beautiful', 'shredded', 'toned', 'gymrat',
]

# --- MuscleLove バックリンクプール（Tumblr adult OK: アダルト+フィットネス両方） ---
ML_BACKLINK_POOL = [
    ("https://musclelove-777.github.io/female-physique-queens/", "Female Physique Queens"),
    ("https://musclelove-777.github.io/muscle-meal-girls/", "Muscle Meal Girls"),
    ("https://musclelove-777.github.io/armwrestling-girls-navi/", "Armwrestling Girls Navi"),
    ("https://musclelove-777.github.io/physique-girls-navi/", "Physique Girls Navi"),
    ("https://musclelove-777.github.io/fighting-girls-navi/", "Fighting Girls Navi"),
    ("https://musclelove-777.github.io/joshi-prowrestling-navi/", "Joshi ProWrestling Navi"),
    ("https://musclelove-777.github.io/network/fitness/", "MuscleLove Fitness Network"),
    ("https://musclelove-777.github.io/network/academy/", "MuscleLove Academy 77"),
]


def build_backlink_block(variant_key=""):
    """MuscleLoveバックリンクHTMLブロック（ランダム2件、冪等マーカー付き）
    utm付与: GA4側で「tumblrのどの変種投稿が流入を生んだか」を測る生命線。"""
    try:
        k = min(2, len(ML_BACKLINK_POOL))
        selected = random.sample(ML_BACKLINK_POOL, k=k)
        def _track(u):
            sep = "&" if "?" in u else "?"
            u = f"{u}{sep}utm_source=tumblr&utm_medium=autopost"
            return with_utm_content(u, variant_key)
        items = " | ".join([f'<a href="{_track(u)}">{n}</a>' for u, n in selected])
        return (
            "\n"
            "<!-- ML_BACKLINK -->\n"
            f'<p><small>🔗 Related: {items}</small></p>\n'
            "<!-- /ML_BACKLINK -->\n"
        )
    except Exception:
        return ""

CAPTION_TEMPLATES = [
    # Public captions stay abstract: no fixed character names or source-specific incidents.
    '<p><b>{category}</b></p>\n<p>この一枚、肩と背中の圧がいい。強い身体はそれだけで見せ場になる。</p>\n<p><a href="{patreon_link}">More on Patreon -> MuscleLove</a></p>\n<p>{hashtags}</p>',
    '<p><b>{category}</b></p>\n<p>今日の筋肉美女。線が出てる、姿勢が強い、保存して見返したくなる仕上がり。</p>\n<p><a href="{patreon_link}">Daily drops on Patreon -> MuscleLove</a></p>\n<p>{hashtags}</p>',
    '<p><b>{category}</b></p>\n<p>Strong is beautiful. ただ細いだけじゃない、鍛えた輪郭が刺さる。</p>\n<p><a href="{patreon_link}">Full collection on Patreon -> MuscleLove</a></p>\n<p>{hashtags}</p>',
    '<p><b>{category}</b></p>\n<p>腕、腹筋、背中。見どころをちゃんと残して、Tumblr向けに濃いめで出す。</p>\n<p><a href="{patreon_link}">More muscle art on Patreon -> MuscleLove</a></p>\n<p>{hashtags}</p>',
    '<p><b>{category}</b></p>\n<p>バキバキ。でも美しい。こういう強さを毎日積み上げる。</p>\n<p><a href="{patreon_link}">Patreon-exclusive drops -> MuscleLove</a></p>\n<p>{hashtags}</p>',
    '<p><b>{category}</b></p>\n<p>筋肉美女はやっぱり最高。ポーズ、厚み、視線の流れまで強い。</p>\n<p><a href="{patreon_link}">Unlock more on Patreon -> MuscleLove</a></p>\n<p>{hashtags}</p>',
    '<p><b>{category}</b></p>\n<p>今日はこの圧。リブログで刺さる人に届けばそれでいい。</p>\n<p><a href="{patreon_link}">More from MuscleLove on Patreon</a></p>\n<p>{hashtags}</p>',
    '<p><b>{category}</b></p>\n<p>鍛えた身体の説得力。シンプルに強くて、シンプルにきれい。</p>\n<p><a href="{patreon_link}">Full gallery on Patreon -> MuscleLove</a></p>\n<p>{hashtags}</p>',
]


def download_videos():
    if gdown is None:
        print("Error: gdown is required for live Google Drive material download. Use --dry-run for local preview.")
        return []
    dl_dir = "videos"
    os.makedirs(dl_dir, exist_ok=True)
    url = f"https://drive.google.com/drive/folders/{GDRIVE_FOLDER_ID}"
    print(f"Downloading from Google Drive: {url}")
    try:
        gdown.download_folder(url, output=dl_dir, quiet=False)
    except Exception as e:
        print(f"Download error: {e}")

    files = []
    for root, dirs, filenames in os.walk(dl_dir):
        for fname in filenames:
            fpath = os.path.join(root, fname)
            ext = os.path.splitext(fname)[1].lower()
            if ext in VIDEO_EXTENSIONS:
                size = os.path.getsize(fpath)
                if size <= MAX_FILE_SIZE:
                    files.append(fpath)
    return files


def generate_tags(video_path):
    tags = list(BASE_TAGS)
    path_lower = video_path.lower().replace('\\', '/').replace('-', ' ').replace('_', ' ')
    matched = set()
    for keyword, keyword_tags in CONTENT_TAG_MAP.items():
        if keyword in path_lower:
            for t in keyword_tags:
                if t not in matched:
                    tags.append(t)
                    matched.add(t)
    seen = set()
    unique_tags = []
    for t in tags:
        if t.lower() not in seen:
            seen.add(t.lower())
            unique_tags.append(t)
    return unique_tags


def load_pool_insights():
    """Read mature_muscle content_pool data without making it mandatory."""
    try:
        from pool_loader import as_insights
        return as_insights("mature_muscle", platform="tumblr")
    except Exception as e:
        print(f"pool_loader skipped: {e}")
        return {}


def merge_pool_tags(tags, insights):
    seen = {t.lower() for t in tags}
    for t in insights.get("recommended_tags", []):
        if t.lower() not in seen:
            tags.append(t)
            seen.add(t.lower())
    avoid = {a.lower() for a in insights.get("avoid_tags", [])}
    if avoid:
        tags = [t for t in tags if t.lower() not in avoid]
    return tags


def add_rotating_tags(tags):
    seen = {t.lower() for t in tags}
    for t in random.sample(TUMBLR_ROTATING_TAGS, k=min(6, len(TUMBLR_ROTATING_TAGS))):
        if t.lower() not in seen:
            tags.append(t)
            seen.add(t.lower())
    return tags


def scan_preview(caption, tags, insights):
    text = f"{caption}\n{' '.join(tags)}"
    blocked = list(PREVIEW_BLOCK_TERMS) + list(insights.get("avoid_tags", []))
    hits = []
    lower_text = text.lower()
    for term in blocked:
        if term and term.lower() in lower_text:
            hits.append(term)
    return sorted(set(hits), key=str.lower)


def prepare_post(video_path):
    tags = generate_tags(video_path)
    insights = load_pool_insights()
    tags = merge_pool_tags(tags, insights)
    tags = add_rotating_tags(tags)
    tags = tags[:25]
    caption, cap_vid = build_caption(video_path, tags, insights)
    return tags, caption, cap_vid, insights


def choose_dry_run_video(sample_name=""):
    local = []
    if os.path.isdir("videos"):
        for root, dirs, filenames in os.walk("videos"):
            for fname in filenames:
                if os.path.splitext(fname)[1].lower() in VIDEO_EXTENSIONS:
                    local.append(os.path.join(root, fname))
    if local:
        return random.choice(local), "local videos folder"
    return os.path.join("dry_run", sample_name or DRY_RUN_VIDEO_NAME), "synthetic sample"


def run_dry_run(sample_name=""):
    video, source = choose_dry_run_video(sample_name)
    tags, caption, cap_vid, insights = prepare_post(video)
    blocked_hits = scan_preview(caption, tags, insights)
    if blocked_hits:
        print(f"DRY RUN FAILED: blocked terms in preview: {', '.join(blocked_hits)}")
        return 1

    platform_focus = insights.get("platform_focus", {})
    artifact = {
        "mode": "dry-run",
        "media_source": source,
        "selected": os.path.basename(video),
        "lane": "mature_muscle",
        "platform": "tumblr",
        "pool_version": insights.get("updated_at_jst", ""),
        "platform_focus": platform_focus,
        "conversion_focus": insights.get("conversion_focus", {}),
        "caption_variant": cap_vid or "",
        "tags": tags,
        "caption": caption,
    }
    Path(DRY_RUN_ARTIFACT).write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("Tumblr Auto Uploader DRY RUN")
    print(f"Pool: {insights.get('updated_at_jst', 'hardcoded')}")
    print(f"Media source: {source}")
    print(f"Selected: {os.path.basename(video)}")
    if platform_focus:
        print(
            "Platform focus: "
            f"action={platform_focus.get('action', '')} "
            f"cadence={platform_focus.get('cadence_hint', '')} "
            f"sessions_28d={platform_focus.get('sessions_28d', 0)}"
        )
    print(f"Tags: {', '.join(tags[:10])}...")
    print(f"Caption variant: {cap_vid or '(uniform)'}")
    print(f"Preview artifact: {DRY_RUN_ARTIFACT}")
    print("DRY RUN OK: no auth, download, upload, posted_log, or notification was attempted.")
    return 0


def env_flag(name, default=False):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def build_caption(video_path, tags, insights=None):
    """キャプション生成。バンディット抽選＋変種キー(utm_content)付与。
    return (caption, caption_variant_id)"""
    insights = insights or {}
    parts = video_path.replace('\\', '/').split('/')
    category = "Muscle"
    for p in parts:
        if p not in ['videos', ''] and '.' not in p:
            category = p
            break
    hashtags = ' '.join([f'#{t.replace(" ", "")}' for t in tags[:15]])
    templates = insights.get("recommended_templates") or CAPTION_TEMPLATES
    template, cap_vid = bandit_pick("tumblr.caption", templates)
    variant_key = f"cap{cap_vid}" if cap_vid else ""
    patreon_link = with_utm_content(PATREON_LINK, variant_key)
    try:
        caption = template.format(category=category, hashtags=hashtags, patreon_link=patreon_link)
    except KeyError:
        caption = template.format(hashtags=hashtags)
    ctas = insights.get("recommended_ctas", [])
    if ctas:
        cta = random.choice(ctas)
        if cta and cta not in caption:
            caption = caption.rstrip() + f"\n<p>{cta}</p>"
    return caption.rstrip() + build_backlink_block(variant_key), cap_vid


def _cadence_slots():
    """自動運営機構(channel_weights)が決めた今回の投稿本数。
    勝ち媒体は平均1.25本/実行へ増枠、流入ゼロ継続は半減、停止中は0本。
    プールが無ければ1本＝従来挙動（絶対に死なない）。"""
    try:
        import variant_bandit
        return variant_bandit.posts_this_run("tumblr")
    except Exception:
        return 1


def main(argv=None):
    _slots = _cadence_slots()
    if _slots < 1:
        print("[cadence] 自動頻度調整により今回はスキップします")
        return 0
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Build a Tumblr post preview without auth, download, or upload.")
    parser.add_argument("--sample-name", default="", help="Synthetic video name for dry-run when no local videos exist.")
    args = parser.parse_args(argv)

    if args.dry_run or env_flag("TUMBLR_DRY_RUN") or env_flag("DRY_RUN"):
        return run_dry_run(args.sample_name.strip())

    if pytumblr is None:
        print("Error: pytumblr is required for live Tumblr upload. Use --dry-run for local preview.")
        return 1
    if gdown is None:
        print("Error: gdown is required for live Google Drive material download. Use --dry-run for local preview.")
        return 1

    consumer_key = os.environ.get("TUMBLR_CONSUMER_KEY", "")
    consumer_secret = os.environ.get("TUMBLR_CONSUMER_SECRET", "")
    oauth_token = os.environ.get("TUMBLR_OAUTH_TOKEN", "")
    oauth_token_secret = os.environ.get("TUMBLR_OAUTH_TOKEN_SECRET", "")

    if not all([consumer_key, consumer_secret, oauth_token, oauth_token_secret]):
        print("Error: Missing Tumblr credentials")
        return 1

    client = pytumblr.TumblrRestClient(consumer_key, consumer_secret, oauth_token, oauth_token_secret)
    info = client.info()
    if 'user' in info:
        print(f"Auth OK: {info['user']['name']}")
    else:
        print(f"Auth error: {info}")
        return 1

    videos = download_videos()
    if not videos:
        print("No videos found!")
        return 0

    print(f"\nTotal videos: {len(videos)}")
    video = random.choice(videos)
    fname = os.path.basename(video)
    print(f"Selected: {fname}")

    tags, caption, cap_vid, insights = prepare_post(video)
    blocked_hits = scan_preview(caption, tags, insights)
    if blocked_hits:
        print(f"Blocked preview terms detected: {', '.join(blocked_hits)}")
        return 1
    print(f"Tags: {', '.join(tags[:10])}...")
    print(f"Caption variant: {cap_vid or '(uniform)'}")

    try:
        result = client.create_video(BLOG_NAME, data=video, caption=caption, tags=tags)
        if isinstance(result, dict) and ('id' in result or (result.get('meta', {}).get('status') == 201)):
            post_id = result.get('id', '')
            print(f"Success! {post_id}")
            log_post("tumblr", {
                "post_id": str(post_id),
                "file": fname,
                "variants": {"tumblr.caption": cap_vid},
                "tags_count": len(tags),
            })
            return 0
        else:
            print(f"Failed: {result}")
            return 1
    except Exception as e:
        print(f"Upload error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
