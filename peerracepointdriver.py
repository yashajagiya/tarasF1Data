"""
F1 Driver Standings Extractor
Fetches and displays F1 driver standings from the ESPN API.
Uses only the Python standard library — no pip installs needed.
"""

import urllib.request
import json
import ssl
import subprocess
import os
from datetime import datetime

API_URL = "https://site.api.espn.com/apis/v2/sports/racing/f1/standings"
OPENF1_DRIVERS_URL = "https://api.openf1.org/v1/drivers"

# Path to the cloned GitHub repo (assuming script is in the repo root)
REPO_DIR = os.path.dirname(os.path.abspath(__file__))



def _fetch_json(url):
    """Fetch JSON from a URL (shared helper)."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(url, headers={"User-Agent": "F1StandingsBot/1.0"})
    with urllib.request.urlopen(req, context=ctx) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_driver_info():
    """
    Fetch driver info from the OpenF1 API and return a dict keyed by
    name_acronym (e.g. "NOR", "HAM") with driver_number and team_name.
    """
    drivers = _fetch_json(OPENF1_DRIVERS_URL)
    lookup = {}
    for d in drivers:
        acronym = d.get("name_acronym", "")
        if acronym:
            lookup[acronym] = {
                "driver_number": d.get("driver_number"),
                "team_name": d.get("team_name", ""),
            }
    return lookup


def fetch_standings():
    """Fetch raw standings data from the ESPN F1 API."""
    return _fetch_json(API_URL)


def extract_standings(data, driver_info):
    """
    Extract structured driver standings from the raw API response.

    The ESPN API nests the standings inside:
      data -> children[0] -> standings

    Each entry contains:
      - athlete: { displayName, shortName, abbreviation, flag, ... }
      - stats: flat list of typed objects:
          type "rank"    -> driver rank
          type "points"  -> championship points (+ topFinish)
          type "overall" -> ignored
          everything else -> individual race results

    Returns a dict with:
      - displayName: str
      - season: str
      - entries: list of driver dicts, each containing:
          - rank, name, shortName, abbreviation, flagUrl
          - championshipPts: { value, displayValue, topFinish }
          - races: list of { name, abbreviation, displayName, played, value, displayValue }
    """
    # Navigate to the actual standings object
    children = data.get("children", [])
    if not children:
        return {"displayName": "", "season": "", "entries": []}

    standings_data = children[0].get("standings", {})

    standings = {
        "displayName": standings_data.get("displayName", ""),
        "season": standings_data.get("season", ""),
        "entries": [],
    }

    for entry in standings_data.get("entries", []):
        athlete = entry.get("athlete", {})
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

        flag = athlete.get("flag", {})
        abbr = athlete.get("abbreviation", "")
        info = driver_info.get(abbr, {})

        driver = {
            "rank": rank,
            "driver_number": info.get("driver_number", None),
            "name": athlete.get("displayName", ""),
            "shortName": athlete.get("shortName", ""),
            "abbreviation": abbr,
            "team_name": info.get("team_name", ""),
            "nationality": flag.get("alt", ""),
            "championshipPts": {
                "value": pts_value,
                "displayValue": pts_display,
            },
            "races": races,
        }

        standings["entries"].append(driver)

    return standings


def print_standings(standings):
    """Pretty-print the standings to the console."""
    print(f"\n{'='*60}")
    print(f"  {standings['displayName']}  --  Season {standings['season']}")
    print(f"{'='*60}\n")

    for driver in standings["entries"]:
        pts = driver["championshipPts"]
        nat = f" ({driver['nationality']})" if driver.get("nationality") else ""
        num = f"#{driver['driver_number']:<3}" if driver.get("driver_number") else "#?  "
        team = f" [{driver['team_name']}]" if driver.get("team_name") else ""
        print(f"  #{driver['rank']:>2}  {num} {driver['abbreviation']}  {driver['name']}{nat}{team}")
        print(f"       Points: {pts['displayValue']}")

        played_races = [r for r in driver["races"] if r["played"]]
        if played_races:
            race_strs = [f"{r['name']}({r['displayValue']})" for r in played_races]
            print(f"       Races:  {', '.join(race_strs)}")
        print()

    print(f"{'='*60}")
    print(f"  Total drivers: {len(standings['entries'])}")
    print(f"{'='*60}\n")


def save_standings(standings, filename="driversperrace.json"):
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
        message = f"Auto-update driver standings — {now}"

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
    print("Fetching driver info from OpenF1 API...")
    driver_info = fetch_driver_info()
    print(f"  Loaded {len(driver_info)} drivers from OpenF1.")

    print("Fetching F1 standings from ESPN API...")
    raw_data = fetch_standings()

    standings = extract_standings(raw_data, driver_info)

    print_standings(standings)
    filepath = save_standings(standings)
    git_commit_and_push(filepath)


if __name__ == "__main__":
    main()
