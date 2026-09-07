# -*- coding: utf-8 -*-
"""Dispatch one local source-folder video to the credentialed Tumblr workflow.

The Windows task runs this file. It selects every unique video below
``../000_Tumblr_movie`` before any reuse, stages exactly one short-lived GitHub
Release asset, and asks the existing GitHub Actions workflow to publish it.
Tumblr credentials remain in GitHub Secrets; the temporary asset is deleted
after the workflow finishes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
COLLECTION_ROOT = HERE.parent
if str(COLLECTION_ROOT) not in sys.path:
    sys.path.insert(0, str(COLLECTION_ROOT))

try:
    from source_video_pool import folder_approved_entries  # noqa: E402
except ImportError:  # standalone clone: selection tests remain runnable
    from media_pool import VIDEO_EXTENSIONS, eligible_videos

    def folder_approved_entries(root):
        root = Path(root).resolve()
        candidates = [path for path in root.rglob("*")
                      if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS]
        selected = eligible_videos(candidates)
        entries = []
        for raw in selected:
            path = Path(raw)
            entries.append({
                "path": str(path),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "category": "Training",
                "priority": 5,
            })
        return entries, {
            "source_files": len(candidates),
            "eligible_files": len(candidates),
            "unique_media": len(entries),
            "duplicate_copies": len(candidates) - len(entries),
            "invalid_files": 0,
            "approval_basis": "folder_membership",
        }

SOURCE_ROOT = (COLLECTION_ROOT / "000_Tumblr_movie").resolve()
STATE_PATH = HERE / "local_dispatch_state.json"
POSTED_LOG = HERE / "posted_log.json"
REPO = os.environ.get("TUMBLR_GH_REPO", "MuscleLove-777/tumblr-auto-uploader")
WORKFLOW = "upload.yml"
RELEASE_TAG = "media-host"
JST = timezone(timedelta(hours=9))


def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return default


def _save_state(state: dict, path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def _posted_names(path: Path = POSTED_LOG) -> set[str]:
    data = _load_json(path, {"posts": []})
    rows = data.get("posts", []) if isinstance(data, dict) else []
    return {str(row.get("file", "")).lower() for row in rows if isinstance(row, dict)}


def select_entry(
    entries: list[dict],
    state: dict,
    posted_names: set[str],
    *,
    min_repost_days: int = 14,
    now: datetime | None = None,
) -> dict | None:
    """Exhaust unseen content, then reuse only the oldest item after cooldown."""
    attempts = state.get("attempts", []) if isinstance(state, dict) else []
    succeeded = {row.get("sha256") for row in attempts if row.get("status") == "success"}
    counts: dict[str, int] = {}
    for row in attempts:
        digest = str(row.get("sha256", ""))
        counts[digest] = counts.get(digest, 0) + 1

    fresh = [entry for entry in entries
             if entry["sha256"] not in succeeded
             and Path(entry["path"]).name.lower() not in posted_names]
    if not fresh:
        now = now or datetime.now(JST)
        last_success: dict[str, datetime] = {}
        for row in attempts:
            if row.get("status") != "success" or not row.get("sha256"):
                continue
            try:
                when = datetime.strptime(str(row.get("at_jst", "")), "%Y-%m-%d %H:%M:%S JST").replace(tzinfo=JST)
            except ValueError:
                continue
            digest = str(row["sha256"])
            if digest not in last_success or when > last_success[digest]:
                last_success[digest] = when
        reusable = [entry for entry in entries
                    if Path(entry["path"]).name.lower() not in posted_names
                    and entry["sha256"] in last_success
                    and now - last_success[entry["sha256"]] >= timedelta(days=min_repost_days)]
        if not reusable:
            return None
        return min(reusable, key=lambda entry: last_success[entry["sha256"]])
    minimum = min(counts.get(entry["sha256"], 0) for entry in fresh)
    least_attempted = [entry for entry in fresh
                       if counts.get(entry["sha256"], 0) == minimum]
    return random.choice(least_attempted)


def _gh(*args: str, timeout: int = 120, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["gh", *args], cwd=HERE, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout, shell=False,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "gh command failed").strip()
        raise RuntimeError(detail[-2000:])
    return result


def _ensure_release() -> None:
    if _gh("release", "view", RELEASE_TAG, "--repo", REPO, check=False).returncode == 0:
        return
    _gh(
        "release", "create", RELEASE_TAG, "--repo", REPO, "--target", "main",
        "--title", "Tumblr media bridge", "--notes",
        "Short-lived local-to-Actions media bridge. Assets are deleted after each run.",
        "--prerelease",
    )


def _run_ids() -> set[int]:
    result = _gh(
        "run", "list", "--repo", REPO, "--workflow", WORKFLOW,
        "--event", "workflow_dispatch", "--limit", "20", "--json", "databaseId",
    )
    return {int(row["databaseId"]) for row in json.loads(result.stdout or "[]")}


def _find_run(previous: set[int], digest: str, timeout_s: int = 120) -> int:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        result = _gh(
            "run", "list", "--repo", REPO, "--workflow", WORKFLOW,
            "--event", "workflow_dispatch", "--limit", "20", "--json",
            "databaseId,displayTitle,createdAt",
        )
        for row in json.loads(result.stdout or "[]"):
            run_id = int(row["databaseId"])
            if run_id not in previous and digest[:12] in str(row.get("displayTitle", "")):
                return run_id
        time.sleep(5)
    raise RuntimeError("Dispatched workflow run was not found")


def _cleanup_asset(name: str) -> None:
    _gh(
        "release", "delete-asset", RELEASE_TAG, name, "--repo", REPO, "-y",
        check=False,
    )


def dispatch(entry: dict) -> tuple[bool, int | None, str]:
    source = Path(entry["path"])
    asset_name = f"tumblr_{entry['sha256']}{source.suffix.lower()}"
    run_id = None
    _ensure_release()
    previous = _run_ids()
    try:
        with tempfile.TemporaryDirectory(prefix="tumblr_dispatch_") as temp_dir:
            staged = Path(temp_dir) / asset_name
            shutil.copy2(source, staged)
            _gh("release", "upload", RELEASE_TAG, str(staged), "--repo", REPO, "--clobber", timeout=600)
        _gh(
            "workflow", "run", WORKFLOW, "--repo", REPO,
            "-f", "dry_run=false",
            "-f", f"source_asset_name={asset_name}",
            "-f", f"source_sha256={entry['sha256']}",
        )
        run_id = _find_run(previous, entry["sha256"])
        watched = _gh(
            "run", "watch", str(run_id), "--repo", REPO,
            "--exit-status", "--interval", "10", timeout=1200, check=False,
        )
        ok = watched.returncode == 0
        detail = (watched.stdout or watched.stderr or "").strip()[-2000:]
        return ok, run_id, detail
    finally:
        _cleanup_asset(asset_name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--source-root", type=Path, default=SOURCE_ROOT)
    args = parser.parse_args(argv)

    entries, stats = folder_approved_entries(args.source_root)
    state = _load_json(STATE_PATH, {"version": 1, "attempts": []})
    posted_names = _posted_names()
    chosen = select_entry(
        entries,
        state,
        posted_names,
        min_repost_days=int(os.environ.get("TUMBLR_MIN_REPOST_DAYS", "14")),
    )
    print(
        f"SOURCE_POOL files={stats['source_files']} unique={stats['unique_media']} "
        f"duplicates={stats['duplicate_copies']} posted_names={len(posted_names)}"
    )
    if chosen is None:
        print("ALL_CURRENT_SOURCE_VIDEOS_ALREADY_POSTED_OR_DISPATCHED")
        return 0
    print(f"SELECTED {Path(chosen['path']).name} sha256={chosen['sha256'][:12]}")
    if args.dry_run:
        print("DRY_RUN_OK live_actions=[]")
        return 0

    ok, run_id, detail = dispatch(chosen)
    record = {
        "sha256": chosen["sha256"],
        "file": Path(chosen["path"]).name,
        "run_id": run_id,
        "status": "success" if ok else "failed",
        "at_jst": datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S JST"),
    }
    state.setdefault("attempts", []).append(record)
    _save_state(state)
    print(f"WORKFLOW_{record['status'].upper()} run_id={run_id}")
    if detail:
        print(detail)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
