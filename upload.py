# -*- coding: utf-8 -*-
"""
Tumblr動画ランダムアップロード（GitHub Actions用）
Google Driveからダウンロード → ランダム1本アップロード（重複許可）
"""
import sys, os, random

import pytumblr
import gdown

GDRIVE_FOLDER_ID = os.environ.get("GDRIVE_FOLDER_ID", "")
BLOG_NAME = "muscular-japanese-girls"
PATREON_LINK = "https://www.patreon.com/cw/MuscleLove?utm_source=tumblr"
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.wmv', '.mkv', '.webm'}
MAX_FILE_SIZE = 500 * 1024 * 1024

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

BASE_TAGS = [
    'muscle girl', 'muscular woman', 'female muscle', 'strong women',
    'fbb', 'fitness motivation', 'gym girl', '筋肉女子', '筋トレ女子', 'fitfam',
    'musclebeauty', 'thicc', 'thickfit', 'armpitfetish', 'tonedbody',
    'fitchick', 'muscleworship', 'hardbody', 'girlswithmuscle', 'strongissexy',
    'musclegirl', 'fitnessbabe', 'gymbabe', 'shredded', 'MuscleLove',
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


def build_backlink_block():
    """MuscleLoveバックリンクHTMLブロック（ランダム2件、冪等マーカー付き）"""
    try:
        k = min(2, len(ML_BACKLINK_POOL))
        selected = random.sample(ML_BACKLINK_POOL, k=k)
        items = " | ".join([f'<a href="{u}">{n}</a>' for u, n in selected])
        return (
            "\n"
            "<!-- ML_BACKLINK -->\n"
            f'<p><small>🔗 Related: {items}</small></p>\n'
            "<!-- /ML_BACKLINK -->\n"
        )
    except Exception:
        return ""

CAPTION_TEMPLATES = [
    '<p><b>{category}</b> — Raw power, no filter.</p>\n<p><a href="{patreon_link}">🔥 Exclusive content on Patreon → MuscleLove</a></p>\n<p>{hashtags}</p>',
    '<p>💪 <b>{category}</b></p>\n<p>Stronger than yesterday. Follow the journey.</p>\n<p><a href="{patreon_link}">👉 Full videos on Patreon → MuscleLove</a></p>\n<p>{hashtags}</p>',
    '<p><b>{category}</b> | Built, not bought.</p>\n<p><a href="{patreon_link}">🔥 More muscle content on Patreon → MuscleLove</a></p>\n<p>{hashtags}</p>',
    '<p><b>{category}</b></p>\n<p>She didn\'t skip a single rep. 💥</p>\n<p><a href="{patreon_link}">Support & see more → MuscleLove on Patreon</a></p>\n<p>{hashtags}</p>',
    '<p>✨ <b>{category}</b> ✨</p>\n<p>Muscle is art. Strength is beauty.</p>\n<p><a href="{patreon_link}">🔥 Unlock the full collection on Patreon → MuscleLove</a></p>\n<p>{hashtags}</p>',
    '<p><b>{category}</b></p>\n<p>Iron therapy in session. 🏋️</p>\n<p><a href="{patreon_link}">Want more? Join us on Patreon → MuscleLove</a></p>\n<p>{hashtags}</p>',
    '<p><b>{category}</b> — Peak physique, zero excuses.</p>\n<p><a href="{patreon_link}">💪 Patreon-exclusive drops → MuscleLove</a></p>\n<p>{hashtags}</p>',
    '<p>🔥 <b>{category}</b></p>\n<p>This is what dedication looks like.</p>\n<p><a href="{patreon_link}">See the uncensored version on Patreon → MuscleLove</a></p>\n<p>{hashtags}</p>',
    '<p><b>{category}</b></p>\n<p>Thick. Strong. Unstoppable. 💪</p>\n<p><a href="{patreon_link}">Daily posts on Patreon → MuscleLove</a></p>\n<p>{hashtags}</p>',
    '<p><b>{category}</b> — Sweat, steel & discipline.</p>\n<p><a href="{patreon_link}">🔥 Become a patron → MuscleLove on Patreon</a></p>\n<p>{hashtags}</p>',
]


def download_videos():
    dl_dir = "videos"
    os.makedirs(dl_dir, exist_ok=True)
    url = f"https://drive.google.com/drive/folders/{GDRIVE_FOLDER_ID}"
    print(f"Downloading from Google Drive: {url}")
    try:
        gdown.download_folder(url, output=dl_dir, quiet=False, remaining_ok=True)
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


def build_caption(video_path, tags):
    parts = video_path.replace('\\', '/').split('/')
    category = "Muscle"
    for p in parts:
        if p not in ['videos', ''] and '.' not in p:
            category = p
            break
    hashtags = ' '.join([f'#{t.replace(" ", "")}' for t in tags[:15]])
    template = random.choice(CAPTION_TEMPLATES)
    caption = template.format(category=category, hashtags=hashtags, patreon_link=PATREON_LINK)
    return caption.rstrip() + build_backlink_block()


def main():
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

    tags = generate_tags(video)

    # Google Trendsからトレンドタグを追加
    from trending import get_trending_tags
    trend_tags = get_trending_tags(max_tags=5)
    if trend_tags:
        seen = {t.lower() for t in tags}
        for t in trend_tags:
            if t.lower() not in seen:
                tags.append(t)
                seen.add(t.lower())

    caption = build_caption(video, tags)
    print(f"Tags: {', '.join(tags[:10])}...")

    try:
        result = client.create_video(BLOG_NAME, data=video, caption=caption, tags=tags)
        if isinstance(result, dict) and ('id' in result or (result.get('meta', {}).get('status') == 201)):
            print(f"Success! {result.get('id', '')}")
            return 0
        else:
            print(f"Failed: {result}")
            return 1
    except Exception as e:
        print(f"Upload error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
