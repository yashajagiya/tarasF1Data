"""
update_notification.py
─────────────────────
Reads notification.json, checks 16-minute cooldown via
notificationhistory.json, auto-increments ID, and pushes
to yashajagiya/Taras repo via GitHub REST API.

Usage:
  set GITHUB_TOKEN=ghp_...
  python update_notification.py
"""

import base64
import json
import os
import sys
from datetime import datetime, timezone

# Ensure emojis and Unicode print safely on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import requests

REPO_OWNER = "yashajagiya"
REPO_NAME = "Taras"
FILE_PATH = "notification/notification.json"
BRANCH = "master"

COOLDOWN_MINUTES = 16  # Must wait this long between notifications

# ── File paths (same folder as this script) ────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(SCRIPT_DIR, "notification.json")
HISTORY_PATH = os.path.join(SCRIPT_DIR, "notificationhistory.json")
TOKEN_PATH = os.path.join(SCRIPT_DIR, "token.json")


def load_token() -> str:
    """Read GitHub token from local token.json."""
    if not os.path.exists(TOKEN_PATH):
        print("[ERROR] token.json not found! Create it with:")
        print('   { "github_token": "ghp_..." }')
        exit(1)
    with open(TOKEN_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["github_token"]


def load_history() -> list:
    """Load notification history from local file."""
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return []
                return json.loads(content)
        except Exception as e:
            print(f"[WARN] Could not parse history file: {e}")
            return []
    return []


def save_history(history: list):
    """Save notification history to local file."""
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def get_next_id(history: list) -> int:
    """Auto-increment: max ID in history + 1."""
    if not history:
        return 1
    return max(entry["id"] for entry in history) + 1


def check_cooldown(history: list) -> tuple[bool, float]:
    """
    Returns (can_send, remaining_minutes).
    can_send = True if last notification was >= COOLDOWN_MINUTES ago.
    """
    if not history:
        return True, 0.0

    last_sent_str = history[-1]["sent_at"]
    last_sent = datetime.fromisoformat(last_sent_str)
    now = datetime.now(timezone.utc)
    elapsed = (now - last_sent).total_seconds() / 60.0
    remaining = COOLDOWN_MINUTES - elapsed

    if remaining <= 0:
        return True, 0.0
    return False, remaining


def push_to_github(notification_id: int, title: str, message: str) -> bool:
    """Push notification.json to GitHub via Contents API."""
    token = load_token()
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    # 1. Get current file SHA
    response = requests.get(url, headers=headers, params={"ref": BRANCH})
    sha = response.json().get("sha") if response.status_code == 200 else None

    # 2. Encode new payload
    payload_data = {
        "id": notification_id,
        "title": title,
        "message": message,
    }
    encoded_content = base64.b64encode(
        json.dumps(payload_data, indent=2).encode("utf-8")
    ).decode("utf-8")

    # 3. Commit
    commit_payload = {
        "message": f"Broadcast notification ID {notification_id}",
        "content": encoded_content,
        "branch": BRANCH,
    }
    if sha:
        commit_payload["sha"] = sha

    put_response = requests.put(url, headers=headers, json=commit_payload)
    if put_response.status_code in (200, 201):
        print(f"[OK] Notification ID {notification_id} pushed to GitHub Pages.")
        return True
    else:
        print(f"[ERROR] {put_response.status_code}: {put_response.text}")
        return False


# ── Main ───────────────────────────────────────────────────
if __name__ == "__main__":

    # 1. Load notification.json (user edits title + message here)
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 2. Load history & check cooldown
    history = load_history()
    can_send, remaining = check_cooldown(history)

    if not can_send:
        print(f"[WAIT] Cooldown active -- wait {remaining:.1f} more minutes.")
        print(f"   Last sent: {history[-1]['sent_at']}")
        print(f"   Title was: {history[-1]['title']}")
        exit(0)

    # 3. Auto-increment ID
    next_id = get_next_id(history)

    print("--- Push Notification to GitHub Pages ---")
    print(f"  ID:      {next_id}  (auto)")
    print(f"  Title:   {data['title']}")
    print(f"  Message: {data['message']}")

    # 4. Push to GitHub
    success = push_to_github(next_id, data["title"], data["message"])

    if success:
        # 5. Update local notification.json with the new ID
        data["id"] = next_id
        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        # 6. Append to history
        history.append({
            "id": next_id,
            "title": data["title"],
            "message": data["message"],
            "sent_at": datetime.now(timezone.utc).isoformat(),
        })
        save_history(history)
        print(f"[SAVED] History saved ({len(history)} total notifications)")
