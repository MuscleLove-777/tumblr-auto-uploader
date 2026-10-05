"""PC-independent daily Actions audit and bounded Tumblr schedule recovery."""
import json
import os
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

OWN = "MuscleLove-777/tumblr-auto-uploader"
REPOS = ["tumblr-auto-uploader"]
PUBLISHERS = {
    "tumblr-auto-uploader": {".github/workflows/upload.yml"},
}


def gh(*args):
    result = subprocess.run(["gh", *args], capture_output=True, text=True,
                            encoding="utf-8", timeout=45)
    if result.returncode:
        raise RuntimeError("GitHub API request failed")
    return json.loads(result.stdout) if result.stdout.strip() else None


def post_time(posts):
    times = []
    for post in posts:
        if not post.get("post_id"):
            continue
        try:
            # The existing ledger is written by UTC GitHub runners.
            at = datetime.fromisoformat(post["posted_at"])
            times.append(at.replace(tzinfo=timezone.utc) if at.tzinfo is None else at)
        except (ValueError, KeyError):
            continue
    return max(times) if times else None


def recover_own(workflow, runs, last_post, now, missing_schedule=False):
    repaired = []
    if workflow["state"] != "active":
        gh("api", "--method", "PUT", f"repos/{OWN}/actions/workflows/upload.yml/enable")
        repaired.append("enabled_cloud_publisher")
    busy = any(r["status"] != "completed" for r in runs)
    window = timedelta(hours=6 if missing_schedule else 24)
    recent = any(datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
                 > now - window for r in runs)
    stale = last_post is None or last_post < now - window
    # Do not repeat a potentially accepted upload following a recent failure.
    # The normal three daily slots remain active and handle future publication.
    if stale and not busy and not recent:
        gh("api", "--method", "POST", f"repos/{OWN}/actions/workflows/upload.yml/dispatches",
           "-f", "ref=main", "-F", "inputs[dry_run]=false")
        repaired.append("dispatched_one_missing_slot")
    return repaired


def main():
    now = datetime.now(timezone.utc)
    report = {"checked_at": now.isoformat(), "repairs": [], "channels": []}
    publisher = Path(".github/workflows/upload.yml")
    missing_schedule = not publisher.exists() or "  schedule:" not in publisher.read_text(encoding="utf-8")
    report["schedule_present"] = not missing_schedule
    for repo in REPOS:
        row = {"repo": repo, "issues": []}
        try:
            data = gh("api", f"repos/MuscleLove-777/{repo}/actions/workflows?per_page=100")
            workflows = [w for w in data["workflows"] if w["path"] in PUBLISHERS[repo]]
            row["workflows"] = [{"path": w["path"], "state": w["state"]} for w in workflows]
            runs_data = gh("api", f"repos/MuscleLove-777/{repo}/actions/runs?per_page=20")
            runs = [r for r in runs_data["workflow_runs"] if r.get("path") in PUBLISHERS[repo]]
            row["latest_run"] = ({k: runs[0].get(k) for k in
                                  ("id", "created_at", "status", "conclusion", "event")}
                                 if runs else None)
            if not any(w["state"] == "active" for w in workflows):
                row["issues"].append("no_active_publisher")
            if not runs:
                row["issues"].append("no_publisher_runs")
            elif runs[0]["conclusion"] in {"failure", "cancelled", "timed_out"}:
                row["issues"].append("latest_publisher_failed")
            elif datetime.fromisoformat(runs[0]["created_at"].replace("Z", "+00:00")) < now - timedelta(hours=48):
                row["issues"].append("publisher_run_older_than_48h")
            if repo == "tumblr-auto-uploader":
                data = json.loads(Path("posted_log.json").read_text(encoding="utf-8"))
                posts = data if isinstance(data, list) else data.get("posts", [])
                last = post_time(posts)
                row["last_confirmed_post"] = last.isoformat() if last else None
                if last is None or last < now - timedelta(hours=24):
                    row["issues"].append("confirmed_post_older_than_24h")
                workflow = next(w for w in workflows if w["path"] == ".github/workflows/upload.yml")
                own_runs = [r for r in runs if r["workflow_id"] == workflow["id"]]
                report["repairs"].extend(recover_own(workflow, own_runs, last, now, missing_schedule))
                if missing_schedule:
                    row["issues"].append("schedule_missing_daily_dispatch_fallback")
        except Exception as error:
            row["issues"].append(f"audit_error:{type(error).__name__}")
        report["channels"].append(row)
    Path("cloud_watchdog_latest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    summary = "# Cloud uploader daily audit\n\n"
    summary += "\n".join(f"- {r['repo']}: {', '.join(r['issues']) or 'workflow observed'}"
                         for r in report["channels"])
    summary += "\n\nRepairs: " + (", ".join(report["repairs"]) or "none")
    Path(os.environ.get("GITHUB_STEP_SUMMARY", "cloud_watchdog_summary.md")).write_text(summary, encoding="utf-8")
    print(summary)
    return int(any(r["issues"] for r in report["channels"]))


if __name__ == "__main__":
    raise SystemExit(main())
