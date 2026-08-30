"""Offline, hash-bound media approvals shared by local and cloud selection.

Owner permission is not platform clearance. Unreviewed/Mature entries remain
on hold until an appropriate review and verified content-label path exist.
"""
import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "approved_media.json"
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".wmv", ".mkv", ".webm"}
MAX_FILE_SIZE = 500 * 1024 * 1024


def load_manifest(path=MANIFEST):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("entries"), list):
        raise ValueError("Invalid media approval manifest")
    return data


def eligible_videos(paths, manifest=None):
    data = load_manifest() if manifest is None else manifest
    accepted = {e["sha256"] for e in data["entries"]
                if e.get("user_approved") is True and e.get("autopost_ready") is True
                and not e.get("requires_mature_review", True)}
    selected, seen = [], set()
    for raw in sorted(paths, key=str):
        path = Path(raw)
        if path.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        try:
            if not path.is_file() or not 0 < path.stat().st_size <= MAX_FILE_SIZE:
                continue
            digest = hashlib.sha256()
            with path.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
            key = digest.hexdigest()
        except OSError:
            continue
        if key in accepted and key not in seen:
            selected.append(str(path))
            seen.add(key)
    return selected


def local_media_root():
    """Local workspace first. A configured missing root must not fetch remotely."""
    explicit = os.environ.get("TUMBLR_LOCAL_MEDIA_DIR")
    root = Path(explicit) if explicit else HERE.parent / "000_Tumblr_movie"
    if explicit and not root.is_dir():
        raise ValueError("Configured local media root is missing")
    return root if root.is_dir() else None


def local_videos():
    root = local_media_root()
    if root is None:
        return None  # cloud host: Drive acquisition remains a separate live step
    resolved = root.resolve()
    files = (p for p in root.rglob("*") if p.resolve().is_relative_to(resolved))
    return eligible_videos(files)


def audit():
    data = load_manifest()
    videos = local_videos()
    return {"user_approved": sum(e.get("user_approved") is True for e in data["entries"]),
            "manifest_ready": sum(e.get("autopost_ready") is True for e in data["entries"]),
            "held": sum(e.get("autopost_ready") is not True for e in data["entries"]),
            "local_available": None if videos is None else len(videos),
            "cloud_deployment_verified": False, "external_actions": []}
