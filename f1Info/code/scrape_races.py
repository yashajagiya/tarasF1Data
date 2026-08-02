"""
F1 2026 Race Data Scraper
Fetches race calendar from https://f1api.dev/api/current and extracts:
  - Championship info
  - Race schedule (race, qualy, FP1–FP3, sprint qualy, sprint race)
  - Circuit details
  - Winner: driver number + full name combined
  - Winning team
Also fetches the latest race result from the GitHub-hosted JSON to patch in
winner data that the F1 API may not have updated yet (matched by circuitId).
Outputs: races_data.json
"""

import requests
import json
import shutil
import subprocess
import sys
import os

# Fix Windows console encoding
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

API_URL = "https://f1api.dev/api/current"
RACE_RESULTS_URL = "https://yashajagiya.github.io/tarasF1Data/race-result/race_results.json"
RACES_IMG_URL = "https://yashajagiya.github.io/tarasF1Data/racesimg.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def extract_race(race: dict) -> dict:
    """Extract and flatten a single race entry from the API response."""

    # ── Schedule ─────────────────────────────────────────────────
    schedule_raw = race.get("schedule", {})
    schedule = {}
    for session_key in ("race", "qualy", "fp1", "fp2", "fp3", "sprintQualy", "sprintRace"):
        session = schedule_raw.get(session_key, {})
        date = session.get("date")
        time_ = session.get("time")
        if date:
            schedule[session_key] = {
                "date": date,
                "time": time_,
            }

    # ── Circuit ──────────────────────────────────────────────────
    circuit_raw = race.get("circuit", {})
    circuit = {
        "circuitId": circuit_raw.get("circuitId"),
        "circuitName": circuit_raw.get("circuitName"),
        "country": circuit_raw.get("country"),
        "city": circuit_raw.get("city"),
        "circuitLength": circuit_raw.get("circuitLength"),
        "lapRecord": circuit_raw.get("lapRecord"),
        "firstParticipationYear": circuit_raw.get("firstParticipationYear"),
        "corners": circuit_raw.get("corners"),
        "url": circuit_raw.get("url"),
    }

    # ── Winner (driver number + full name only) ─────────────────
    winner_raw = race.get("winner")
    winner = None
    if winner_raw:
        number = winner_raw.get("number", "")
        name = winner_raw.get("name", "")
        surname = winner_raw.get("surname", "")
        full_name = f"{name} {surname}".strip()
        winner = {
            "number": number,
            "fullName": full_name,
        }

    # ── Team Winner (name only) ──────────────────────────────────
    team_raw = race.get("teamWinner")
    team_winner = team_raw.get("teamName") if team_raw else None

    return {
        "raceId": race.get("raceId"),
        "raceName": race.get("raceName"),
        "round": race.get("round"),
        "laps": race.get("laps"),
        "url": race.get("url"),
        "schedule": schedule,
        "circuit": circuit,
        "winner": winner,
        "teamWinner": team_winner,
    }


def fetch_latest_result() -> dict | None:
    """Fetch the latest race result from the GitHub-hosted JSON.
    Returns a dict with circuitId, winner number/name, and team, or None."""
    print(f"Fetching latest race result from GitHub...", end=" ", flush=True)
    try:
        resp = requests.get(RACE_RESULTS_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        circuit_id = data.get("circuitId")
        results = data.get("results", [])
        if not circuit_id or not results:
            print("SKIP  (no data)")
            return None

        # Position 1 = winner
        p1 = next((r for r in results if r.get("position") == "1"), None)
        if not p1:
            print("SKIP  (no P1 found)")
            return None

        result = {
            "circuitId": circuit_id,
            "winner": {
                "number": int(p1.get("driverNumber", 0)),
                "fullName": p1.get("driverName", ""),
            },
            "teamWinner": p1.get("team", ""),
        }
        print(f"OK  ({data.get('raceName', circuit_id)} -> #{result['winner']['number']} {result['winner']['fullName']})")
        return result
    except Exception as e:
        print(f"FAIL  ({e})")
        return None


def fetch_race_images() -> dict:
    """Fetch track images and GP names from GitHub-hosted JSON.
    Returns a dict mapping circuitId to {'trackImage': ..., 'gpName': ...}."""
    print(f"Fetching race images from GitHub...", end=" ", flush=True)
    try:
        resp = requests.get(RACES_IMG_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        
        mapping = {}
        for item in data:
            cid = item.get("circuit_id")
            if cid:
                mapping[cid] = {
                    "trackImage": item.get("track_image"),
                    "gpName": item.get("gp_name")
                }
        print(f"OK  ({len(mapping)} images found)")
        return mapping
    except Exception as e:
        print(f"FAIL  ({e})")
        return {}


def fetch_races() -> dict:
    """Fetch the current season race data from the F1 API."""
    print(f"Fetching race data from {API_URL}...", end=" ", flush=True)

    resp = requests.get(API_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    api_data = resp.json()

    season = api_data.get("season")
    championship = api_data.get("championship", {})
    races_raw = api_data.get("races", [])

    print(f"OK  ({len(races_raw)} races found)")
    
    # ── Fetch race images/names mapping ──────────────────────────
    images_mapping = fetch_race_images()

    races = []
    for race in races_raw:
        extracted = extract_race(race)
        
        # Patch in track image and GP name
        circuit_id = extracted.get("circuit", {}).get("circuitId")
        img_data = images_mapping.get(circuit_id, {})
        extracted["trackImage"] = img_data.get("trackImage")
        extracted["gpName"] = img_data.get("gpName")
        
        races.append(extracted)

    # ── Patch missing winners from GitHub race result ────────────
    latest = fetch_latest_result()
    patched_circuit = None
    if latest:
        for race in races:
            circuit_id = race.get("circuit", {}).get("circuitId")
            if circuit_id == latest["circuitId"] and race["winner"] is None:
                race["winner"] = latest["winner"]
                race["teamWinner"] = latest["teamWinner"]
                patched_circuit = circuit_id
                print(f"  >> Patched R{race['round']} ({race['raceName']}) with GitHub result")

    # ── Log all races ────────────────────────────────────────────
    print()
    for extracted in races:
        winner_info = ""
        if extracted["winner"]:
            w = extracted["winner"]
            tw = extracted.get("teamWinner") or "TBD"
            src = " [GitHub]" if extracted.get("circuit", {}).get("circuitId") == patched_circuit else ""
            winner_info = f" | Winner: #{w['number']} {w['fullName']} ({tw}){src}"
        else:
            winner_info = " | TBD"

        print(f"  R{extracted['round']:>2}: {extracted['raceName']}{winner_info}")

    return {
        "season": season,
        "championship": {
            "championshipId": championship.get("championshipId"),
            "championshipName": championship.get("championshipName"),
            "year": championship.get("year"),
            "url": championship.get("url"),
        },
        "totalRaces": len(races),
        "races": races,
    }


def main():
    print("=" * 60)
    print("  F1 2026 Race Data Scraper")
    print("=" * 60)
    print()

    try:
        result = fetch_races()
    except requests.RequestException as e:
        print(f"FAIL  ERROR: {e}")
        return

    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'races_data.json'))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print()
    print(f"Done! Saved {result['totalRaces']} races to {out_path}")

    # GitHub Upload – copy f1Info folder to tarasF1Data and push
    script_dir = os.path.dirname(os.path.abspath(__file__))
    source_dir = os.path.dirname(script_dir)  # m:\taras\f1Info
    target_repo = os.path.abspath(os.path.join(source_dir, '..', 'tarasF1Data'))
    target_dir = os.path.join(target_repo, 'f1Info')

    if os.path.exists(target_repo):
        print(f"\nSyncing to Git repository: {target_repo}")

        # Pull latest changes first
        try:
            subprocess.run(["git", "pull", "--rebase", "origin", "main"], cwd=target_repo, check=True)
        except subprocess.CalledProcessError:
            pass

        # Copy the entire f1Info folder to tarasF1Data
        shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)

        # Git add, check for changes, commit and push
        try:
            subprocess.run(["git", "add", "f1Info"], cwd=target_repo, check=True)

            status = subprocess.run(["git", "status", "--porcelain", "f1Info"], cwd=target_repo, capture_output=True, text=True)
            if not status.stdout.strip():
                print("No changes detected in f1Info. Skipping Git push.")
            else:
                subprocess.run(["git", "commit", "-m", "Auto-update f1Info JSON data"], cwd=target_repo, check=True)
                subprocess.run(["git", "push", "origin", "main"], cwd=target_repo, check=True)
                print("Successfully pushed f1Info to GitHub!")
        except subprocess.CalledProcessError as e:
            print(f"Error during git push: {e}")
    else:
        print(f"Repo path {target_repo} not found. Skipped GitHub upload.")

    # Quick summary
    print()
    print("-" * 80)
    print(f"{'R#':<4} {'Race':<50} {'Winner':<25}")
    print("-" * 80)
    for r in result["races"]:
        rnd = f"R{r['round']}"
        name = r["raceName"][:48]
        if r["winner"]:
            w = f"#{r['winner']['number']} {r['winner']['fullName']}"
        else:
            w = "TBD"
        print(f"{rnd:<4} {name:<50} {w:<25}")
    print("-" * 80)


if __name__ == "__main__":
    main()
