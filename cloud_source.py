"""Download one video from the existing public Drive source, without cookie files."""
import json
import random
from pathlib import Path

from media_pool import VIDEO_EXTENSIONS, eligible_videos


def candidate_order(inventory, posts, rng=random):
    last = {}
    for post in posts:
        if post.get("post_id") and post.get("file"):
            last[post["file"]] = str(post.get("posted_at", ""))
    candidates = [item for item in inventory
                  if Path(item.path).suffix.lower() in VIDEO_EXTENSIONS]
    rng.shuffle(candidates)
    return sorted(candidates, key=lambda item: last.get(Path(item.path).name, ""))


def download_one(gdown, folder_id, ledger="posted_log.json", output="videos"):
    if not folder_id:
        raise ValueError("Cloud source configuration is missing")
    inventory = gdown.download_folder(id=folder_id, output=output,
                                     skip_download=True, quiet=True,
                                     use_cookies=False, timeout=60)
    try:
        data = json.loads(Path(ledger).read_text(encoding="utf-8"))
        posts = data if isinstance(data, list) else data.get("posts", [])
    except (OSError, ValueError):
        posts = []
    candidates = candidate_order(inventory, posts)
    print(f"CLOUD_POOL videos={len(candidates)} download_limit=3")
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=True)
    for item in candidates[:3]:
        target = root / Path(item.path).name
        if not target.is_relative_to(root):
            continue
        try:
            gdown.download(id=item.id, output=str(target), quiet=True,
                           use_cookies=False, timeout=60, retries=1)
            eligible = eligible_videos([target])
            if eligible:
                return eligible
        except Exception as error:
            # Provider errors may contain private folder identifiers or URLs.
            print(f"CLOUD_DOWNLOAD_FAILED type={type(error).__name__}")
    raise RuntimeError("No usable cloud video after bounded acquisition")
