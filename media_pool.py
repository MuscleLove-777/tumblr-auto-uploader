# -*- coding: utf-8 -*-
"""Folder-based media selection for Tumblr.

Every supported video below ``000_Tumblr_movie`` is approved by its placement
there. No approval manifest is read. SHA-256 is used only to suppress
byte-identical copies from the same candidate pool.
"""
import hashlib
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".wmv", ".mkv", ".webm"}
MAX_FILE_SIZE = 500 * 1024 * 1024


def eligible_videos(paths, manifest=None):
    """Validate and byte-deduplicate an explicit path list.

    ``manifest`` is ignored and kept only so older callers do not break. Local
    approval comes solely from :func:`local_videos` and folder membership.
    """
    del manifest
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
        if key not in seen:
            selected.append(str(path.resolve()))
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
    files = (path for path in root.rglob("*")
             if path.is_file() and path.resolve().is_relative_to(resolved))
    return eligible_videos(files)


def audit():
    root = local_media_root()
    if root is None:
        return {
            "approval_basis": "folder_membership",
            "source_files": None,
            "local_available": None,
            "duplicate_copies": None,
            "invalid_files": None,
            "cloud_deployment_verified": False,
            "external_actions": [],
        }
    source_files = sum(1 for path in root.rglob("*")
                       if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS)
    videos = local_videos() or []
    return {
        "approval_basis": "folder_membership",
        "source_files": source_files,
        "local_available": len(videos),
        "duplicate_copies": source_files - len(videos),
        "invalid_files": 0,
        "cloud_deployment_verified": False,
        "external_actions": [],
    }
