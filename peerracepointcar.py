"""
F1 Constructor Standings Extractor
Fetches and displays F1 constructor standings from the ESPN API.
Uses only the Python standard library — no pip installs needed.
"""

import urllib.request
import json
import ssl
import subprocess
import os
from datetime import datetime

API_URL = "https://site.api.espn.com/apis/v2/sports/racing/f1/standings"

# Path to the cloned GitHub repo (assuming script is in the repo root)
REPO_DIR = os.path.dirname(os.path.abspath(__file__))


def fetch_standings():
    """Fetch raw standings data from the ESPN F1 API."""
    # Create an SSL context that doesn't verify certs (some envs lack CA bundles)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(API_URL, headers={"User-Agent": "F1StandingsBot/1.0"})
    with urllib.request.urlopen(req, context=ctx) as resp:
        return json.loads(resp.read().decode("utf-8"))


def extract_standings(data):
    """
    Extract structured constructor standings from the raw API response.

    The ESPN API nests the constructor standings inside:
      data -> children[1] -> standings

    Each entry contains:
      - team: { name, displayName, color, ... }
      - stats: flat list of typed objects:
          type "rank"    -> constructor rank
          type "points"  -> championship points
          type "overall" -> ignored
          everything else -> individual race results

    Returns a dict with:
      - displayName: str
      - season: str
      - entries: list of constructor dicts, each containing:
          - rank, team
          - points: { value, displayValue }
          - races: list of { name, displayName, played, value, displayValue }
    """
    # Navigate to the constructor standings object (children[1])
    children = data.get("children", [])
    if len(children) < 2:
        return {"displayName": "", "season": "", "entries": []}

    standings_data = children[1].get("standings", {})

    standings = {
        "displayName": standings_data.get("displayName", ""),
        "season": standings_data.get("season", ""),
        "entries": [],
    }

    for entry in standings_data.get("entries", []):
        team = entry.get("team", {})
        stats = entry.get("stats", [])

        # Build lookup from the stats array
        rank = 0
        pts_value = 0
        pts_display = "0"
        races = []

        for stat in stats:
            stat_type = stat.get("type", "")

            if stat_type == "rank":
                rank = int(stat.get("value", 0))

            elif stat_type == "points":
                pts_value = int(stat.get("value", 0))
                pts_display = stat.get("displayValue", "0")

            elif stat_type == "overall":
                # Summary row — skip
                continue

            else:
                # Individual race result
                races.append({
                    "name": stat.get("name", ""),
                    "displayName": stat.get("displayName", ""),
                    "played": stat.get("played", False),
                    "value": int(stat.get("value", 0)),
                    "displayValue": stat.get("displayValue", "").strip(),
                })

        constructor = {
            "rank": rank,
            "team": team.get("displayName", ""),
            "points": {
                "value": pts_value,
                "displayValue": pts_display,
            },
            "races": races,
        }

        standings["entries"].append(constructor)

    return standings


def print_standings(standings):
    """Pretty-print the standings to the console."""
    print(f"\n{'='*60}")
    print(f"  {standings['displayName']}  --  Season {standings['season']}")
    print(f"{'='*60}\n")

    for constructor in standings["entries"]:
        pts = constructor["points"]
        print(f"  #{constructor['rank']:>2}  {constructor['team']}")
        print(f"       Points: {pts['displayValue']}")

        played_races = [r for r in constructor["races"] if r["played"]]
        if played_races:
            race_strs = [f"{r['name']}({r['displayValue']})" for r in played_races]
            print(f"       Races:  {', '.join(race_strs)}")
        print()

    print(f"{'='*60}")
    print(f"  Total constructors: {len(standings['entries'])}")
    print(f"{'='*60}\n")


def save_standings(standings, filename="carperrace.json"):
    """Save the extracted standings to the GitHub repo directory."""
    filepath = os.path.join(REPO_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(standings, f, indent=2, ensure_ascii=False)
    print(f"Standings saved to {filepath}")
    return filepath


def git_commit_and_push(filepath, message=None):
    """Auto-commit and push the file to GitHub."""
    if message is None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"Auto-update constructor standings — {now}"

    filename = os.path.basename(filepath)

    try:
        # Stage the file
        subprocess.run(["git", "add", filename], cwd=REPO_DIR,
                        capture_output=True, text=True, check=True)

        # Check if there are changes to commit
        result = subprocess.run(["git", "diff", "--cached", "--quiet"],
                                 cwd=REPO_DIR, capture_output=True)
        if result.returncode == 0:
            print("No changes to commit — standings are already up to date.")
            return

        # Commit locally
        subprocess.run(["git", "commit", "-m", message], cwd=REPO_DIR,
                        capture_output=True, text=True, check=True)
        print(f"Committed: {message}")

        # Pull latest (rebase on top) to avoid merge conflicts
        subprocess.run(["git", "pull", "--rebase"], cwd=REPO_DIR,
                        capture_output=True, text=True, check=True)

        # Push
        subprocess.run(["git", "push"], cwd=REPO_DIR,
                        capture_output=True, text=True, check=True)
        print("Pushed to GitHub successfully!")

    except subprocess.CalledProcessError as e:
        print(f"Git error: {e.stderr or e.stdout or e}")


def main():
    print("Fetching F1 constructor standings from ESPN API...")
    raw_data = fetch_standings()

    standings = extract_standings(raw_data)

    print_standings(standings)
    filepath = save_standings(standings)
    git_commit_and_push(filepath)


if __name__ == "__main__":
    main()
