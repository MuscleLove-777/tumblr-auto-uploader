"""Optional existing LINE notification; provider failures must be visible."""
import json
import os
import sys
from urllib.request import Request, urlopen


def main(status):
    channel_token = os.environ.get("LINE_CHANNEL_TOKEN")
    user_id = os.environ.get("LINE_USER_ID")
    if not channel_token or not user_id:
        print("LINE_NOTIFY_SKIPPED credentials_unavailable")
        return 0
    run = os.environ.get("GITHUB_RUN_ID", "")
    body = {"to": user_id, "messages": [{"type": "text", "text":
            f"Tumblr自動投稿: {status}\n"
            f"https://github.com/MuscleLove-777/tumblr-auto-uploader/actions/runs/{run}"}]}
    request = Request("https://api.line.me/v2/bot/message/push",
                      data=json.dumps(body).encode("utf-8"), method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("Authorization", "Bearer " + channel_token)
    with urlopen(request, timeout=30) as response:
        print(f"LINE_NOTIFY_HTTP status={response.status}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
