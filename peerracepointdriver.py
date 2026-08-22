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
import unicodedata
import re
from datetime import datetime

API_URL = "https://site.api.espn.com/apis/v2/sports/racing/f1/standings"
OPENF1_DRIVERS_URL = "https://yashajagiya.github.io/tarasF1Data/f1Info/drivers_data.json"
DRIVERS_IMG_FALLBACK_URL = "https://yashajagiya.github.io/tarasF1Data/driversimg.json"

# Known 2026 driver acronyms mapping for abbreviation lookup
KNOWN_ACRONYMS = {
    "NOR": "lando norris", "VER": "max verstappen", "BOR": "gabriel bortoleto",
    "HAD": "isack hadjar", "GAS": "pierre gasly", "PER": "sergio perez",
    "ANT": "kimi antonelli", "ALO": "fernando alonso", "LEC": "charles leclerc",
    "STR": "lance stroll", "ALB": "alexander albon", "HUL": "nico hulkenberg",
    "LAW": "liam lawson", "OCO": "esteban ocon", "LIN": "arvid lindblad",
    "COL": "franco colapinto", "HAM": "lewis hamilton", "SAI": "carlos sainz",
    "RUS": "george russell", "BOT": "valtteri bottas", "PIA": "oscar piastri",
    "BEA": "oliver bearman",
}

# Path to the cloned GitHub repo (assuming script is in the repo root)
REPO_DIR = os.path.dirname(os.path.abspath(__file__))


def _normalize(s):
    """Normalize string: remove accents, spaces, and punctuation for fuzzy matching."""
    if not s:
        return ""
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode('utf-8')
    return re.sub(r'[^a-z0-9]', '', s.lower())


def _fetch_json(url):
    """Fetch JSON from a URL with no-cache headers."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "curl/8.4.0",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
        }
    )
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_driver_info():
    """
    Fetch driver info dynamically from local files (f1Info/drivers_data.json)
    or remote URLs. Automatically parses both drivers_data.json (hero format)
    and driversimg.json (flat format).
    """
    # 1. Try local candidate files first for instantaneous updates
    local_candidates = [
        os.path.join(REPO_DIR, "..", "f1Info", "drivers_data.json"),
        os.path.join(REPO_DIR, "f1Info", "drivers_data.json"),
        os.path.join(REPO_DIR, "..", "drivers_data.json"),
        os.path.join(REPO_DIR, "drivers_data.json"),
        os.path.join(REPO_DIR, "..", "driversimg.json"),
        os.path.join(REPO_DIR, "driversimg.json"),
    ]

    raw_drivers = None
    for path in local_candidates:
        abs_path = os.path.abspath(path)
        if os.path.exists(abs_path):
            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    raw_drivers = json.load(f)
                    print(f"Loaded driver details from local file: {abs_path}")
                    break
            except Exception as e:
                print(f"Could not read local file {abs_path}: {e}")

    # 2. If not found locally, fetch from OPENF1_DRIVERS_URL
    if not raw_drivers:
        try:
            print(f"Fetching driver info from {OPENF1_DRIVERS_URL}...")
            raw_drivers = _fetch_json(OPENF1_DRIVERS_URL)
        except Exception as e:
            print(f"Remote fetch from {OPENF1_DRIVERS_URL} failed ({e}). Trying fallback URL...")
            try:
                raw_drivers = _fetch_json(DRIVERS_IMG_FALLBACK_URL)
            except Exception as e2:
                print(f"Fallback URL also failed ({e2}).")

    lookup = {}
    if isinstance(raw_drivers, list):
        for d in raw_drivers:
            if not isinstance(d, dict):
                continue
            hero = d.get("hero", {})

            # Extract driver details dynamically (supports both hero and flat schemas)
            first_name = hero.get("first_name", d.get("first_name", ""))
            last_name = hero.get("last_name", d.get("last_name", ""))
            full_name = f"{first_name} {last_name}".strip() if (first_name or last_name) else d.get("full_name", "")

            num_val = hero.get("number", d.get("driver_number"))
            try:
                driver_number = int(num_val) if num_val is not None and str(num_val).strip() != "" else None
            except (ValueError, TypeError):
                driver_number = None

            team_name = hero.get("team", d.get("team_name", ""))
            country = hero.get("country", d.get("country", ""))
            team_color = hero.get("team_color", d.get("team_colour", ""))
            driver_image = hero.get("driver_image", d.get("headshot_url", ""))
            driver_number_logo = hero.get("driver_number_logo", d.get("racing_number_mask", ""))
            slug = d.get("slug", "")
            acronym = d.get("name_acronym", "")

            driver_info = {
                "driver_number": driver_number,
                "team_name": team_name,
                "first_name": first_name,
                "last_name": last_name,
                "nationality": country,
                "team_color": team_color,
                "driver_image": driver_image,
                "driver_number_logo": driver_number_logo,
            }

            # Map into multi-key lookup
            if acronym:
                lookup[acronym.upper()] = driver_info
            if full_name:
                lookup[_normalize(full_name)] = driver_info
            if last_name:
                lookup[_normalize(last_name)] = driver_info
            if slug:
                lookup[_normalize(slug)] = driver_info

        # Populate acronym keys if missing
        for tla, name_key in KNOWN_ACRONYMS.items():
            if tla not in lookup:
                norm_key = _normalize(name_key)
                if norm_key in lookup:
                    lookup[tla] = lookup[norm_key]

    if lookup:
        return lookup

    # 3. Fallback hardcoded data if all sources fail
    print("All driver sources failed. Using hardcoded fallback.")
    return {
        "NOR": {"driver_number": 1,  "team_name": "McLaren"},
        "VER": {"driver_number": 3,  "team_name": "Red Bull Racing"},
        "BOR": {"driver_number": 5,  "team_name": "Audi"},
        "HAD": {"driver_number": 6,  "team_name": "Red Bull Racing"},
        "GAS": {"driver_number": 10, "team_name": "Alpine"},
        "PER": {"driver_number": 11, "team_name": "Cadillac"},
        "ANT": {"driver_number": 12, "team_name": "Mercedes"},
        "ALO": {"driver_number": 14, "team_name": "Aston Martin"},
        "LEC": {"driver_number": 16, "team_name": "Ferrari"},
        "STR": {"driver_number": 18, "team_name": "Aston Martin"},
        "ALB": {"driver_number": 23, "team_name": "Williams"},
        "HUL": {"driver_number": 27, "team_name": "Audi"},
        "LAW": {"driver_number": 30, "team_name": "Racing Bulls"},
        "OCO": {"driver_number": 31, "team_name": "Haas F1 Team"},
        "LIN": {"driver_number": 41, "team_name": "Racing Bulls"},
        "COL": {"driver_number": 43, "team_name": "Alpine"},
        "HAM": {"driver_number": 44, "team_name": "Ferrari"},
        "SAI": {"driver_number": 55, "team_name": "Williams"},
        "RUS": {"driver_number": 63, "team_name": "Mercedes"},
        "BOT": {"driver_number": 77, "team_name": "Cadillac"},
        "PIA": {"driver_number": 81, "team_name": "McLaren"},
        "BEA": {"driver_number": 87, "team_name": "Haas F1 Team"},
    }


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
        display_name = athlete.get("displayName", "")
        last_word = display_name.split()[-1] if display_name.split() else ""

        # Match driver info by abbreviation, full name, or last name
        info = driver_info.get(abbr.upper())
        if not info:
            info = driver_info.get(_normalize(display_name))
        if not info:
            info = driver_info.get(_normalize(last_word), {})

        driver = {
            "rank": rank,
            "driver_number": info.get("driver_number", None),
            "name": athlete.get("displayName", ""),
            "shortName": athlete.get("shortName", ""),
            "abbreviation": abbr,
            "team_name": info.get("team_name", ""),
            "nationality": flag.get("alt", info.get("nationality", "")),
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
    """Auto-commit and push the file to GitHub reliably."""
    if message is None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"Auto-update driver standings — {now}"

    filename = os.path.basename(filepath)

    try:
        # Stage the file
        subprocess.run(["git", "add", filename], cwd=REPO_DIR,
                        capture_output=True, text=True, check=True)

        # Check if there are staged changes to commit
        result = subprocess.run(["git", "diff", "--cached", "--quiet"],
                                 cwd=REPO_DIR, capture_output=True)
        if result.returncode != 0:
            # Commit locally
            subprocess.run(["git", "commit", "-m", message], cwd=REPO_DIR,
                            capture_output=True, text=True, check=True)
            print(f"Committed: {message}")
        else:
            print("No new local file changes to commit.")

        # Pull latest with autostash to avoid merge/unstaged conflicts
        subprocess.run(["git", "pull", "--rebase", "--autostash"], cwd=REPO_DIR,
                        capture_output=True, text=True, check=False)

        # Push any local commits
        push_res = subprocess.run(["git", "push"], cwd=REPO_DIR,
                                   capture_output=True, text=True)
        if push_res.returncode == 0:
            print("Pushed to GitHub successfully!")
        else:
            # Retry push after rebase
            subprocess.run(["git", "pull", "--rebase", "--autostash"], cwd=REPO_DIR,
                            capture_output=True, text=True, check=False)
            retry = subprocess.run(["git", "push"], cwd=REPO_DIR,
                                    capture_output=True, text=True)
            if retry.returncode == 0:
                print("Pushed to GitHub successfully on retry!")
            else:
                print(f"Git push error: {retry.stderr or retry.stdout}")

    except Exception as e:
        print(f"Git error: {e}")


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
