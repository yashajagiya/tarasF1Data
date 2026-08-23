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
from datetime import datetime

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
        "fastestLapDriverId": circuit_raw.get("fastestLapDriverId"),
        "fastestLapTeamId": circuit_raw.get("fastestLapTeamId"),
        "fastestLapYear": circuit_raw.get("fastestLapYear"),
    }

    # ── Winner ───────────────────────────────────────────────────
    winner_raw = race.get("winner")
    team_raw = race.get("teamWinner")
    winner = None
    if winner_raw:
        number = winner_raw.get("number", "")
        name = winner_raw.get("name", "")
        surname = winner_raw.get("surname", "")
        full_name = f"{name} {surname}".strip()
        winner = {
            "drivernumber": number,
            "fullName": full_name,
            "teamWinner": team_raw.get("teamName") if team_raw else None
        }

    return {
        "raceId": race.get("raceId"),
        "raceName": race.get("raceName"),
        "round": race.get("round"),
        "laps": race.get("laps"),
        "schedule": schedule,
        "circuit": circuit,
        "winner": winner,
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
                "drivernumber": int(p1.get("driverNumber", 0)),
                "fullName": p1.get("driverName", ""),
                "teamWinner": p1.get("team", ""),
            },
        }
        print(f"OK  ({data.get('raceName', circuit_id)} -> #{result['winner']['drivernumber']} {result['winner']['fullName']})")
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
        
        # Patch in track image and GP name inside circuit
        circuit_id = extracted.get("circuit", {}).get("circuitId")
        img_data = images_mapping.get(circuit_id, {})
        extracted["circuit"]["trackImage"] = img_data.get("trackImage")
        extracted["circuit"]["gpName"] = img_data.get("gpName")
        
        races.append(extracted)

    # ── Patch missing winners from GitHub race result ────────────
    latest = fetch_latest_result()
    patched_circuit = None
    if latest:
        for race in races:
            circuit_id = race.get("circuit", {}).get("circuitId")
            if circuit_id == latest["circuitId"] and race["winner"] is None:
                race["winner"] = latest["winner"]
                patched_circuit = circuit_id
                print(f"  >> Patched R{race['round']} ({race['raceName']}) with GitHub result")

    # ── Log all races ────────────────────────────────────────────
    print()
    for extracted in races:
        winner_info = ""
        if extracted["winner"]:
            w = extracted["winner"]
            tw = w.get("teamWinner") or "TBD"
            src = " [GitHub]" if extracted.get("circuit", {}).get("circuitId") == patched_circuit else ""
            winner_info = f" | Winner: #{w.get('drivernumber', '')} {w.get('fullName', '')} ({tw}){src}"
        else:
            winner_info = " | TBD"

        print(f"  R{extracted['round']:>2}: {extracted['raceName']}{winner_info}")

    return {
        "season": season,
        "championship": {
            "championshipId": championship.get("championshipId"),
            "championshipName": championship.get("championshipName"),
            "year": championship.get("year")
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

def find_target_repo(script_path):
    current = os.path.abspath(script_path)
    candidates = []
    while True:
        parent = os.path.dirname(current)
        if parent == current:
            break
        nested = os.path.join(current, 'tarasF1Data')
        if os.path.isdir(nested) and os.path.isdir(os.path.join(nested, '.git')):
            candidates.append(nested)
        if os.path.isdir(os.path.join(current, '.git')):
            candidates.append(current)
        current = parent
    
    for cand in candidates:
        try:
            out = subprocess.check_output(['git', 'remote', '-v'], cwd=cand, text=True)
            if 'tarasf1data' in out.lower():
                return cand
        except Exception:
            pass
    return candidates[0] if candidates else None


def push_f1info_to_git(out_path, info_type="races"):
    target_repo = find_target_repo(__file__)
    if not target_repo or not os.path.isdir(target_repo):
        print(f"Error: Target git repository not found for {out_path}.")
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_name = os.path.basename(out_path)
    target_dir = os.path.join(target_repo, 'f1Info')
    os.makedirs(target_dir, exist_ok=True)
    dest_path = os.path.join(target_dir, file_name)

    if os.path.abspath(out_path) != os.path.abspath(dest_path):
        shutil.copy2(out_path, dest_path)

    git_file_path = f"f1Info/{file_name}"
    print(f"Syncing {git_file_path} to Git repository: {target_repo}")

    try:
        # Pull latest changes first
        subprocess.run(["git", "pull", "--rebase", "--autostash", "origin", "main"], cwd=target_repo, check=False)

        # Stage the file and folder
        subprocess.run(["git", "add", "f1Info"], cwd=target_repo, check=True)

        # Check for staged changes
        result = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=target_repo, capture_output=True)
        if result.returncode != 0:
            commit_msg = f"Auto-update {info_type} data — {now}"
            subprocess.run(["git", "commit", "-m", commit_msg], cwd=target_repo, check=True)
            print(f"Committed changes: {commit_msg}")
        else:
            commit_msg = f"Auto-update {info_type} data (verified) — {now}"
            subprocess.run(["git", "commit", "--allow-empty", "-m", commit_msg], cwd=target_repo, check=True)
            print(f"Committed (no data changes): {commit_msg}")

        # Push to origin main
        push_res = subprocess.run(["git", "push", "origin", "main"], cwd=target_repo, capture_output=True, text=True)
        if push_res.returncode == 0:
            print(f"Uploaded {git_file_path} to GitHub successfully.")
        else:
            subprocess.run(["git", "pull", "--rebase", "--autostash", "origin", "main"], cwd=target_repo, check=False)
            retry = subprocess.run(["git", "push", "origin", "main"], cwd=target_repo, capture_output=True, text=True)
            if retry.returncode == 0:
                print(f"Uploaded {git_file_path} to GitHub successfully on retry.")
            else:
                print(f"Git push error: {retry.stderr or retry.stdout}")
    except Exception as e:
        print(f"Error during GitHub upload: {e}")


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

    # GitHub Upload
    push_f1info_to_git(out_path, info_type="races")

    # Quick summary
    print()
    print("-" * 80)
    print(f"{'R#':<4} {'Race':<50} {'Winner':<25}")
    print("-" * 80)
    for r in result["races"]:
        rnd = f"R{r['round']}"
        name = r["raceName"][:48]
        if r["winner"]:
            w = f"#{r['winner'].get('drivernumber', '')} {r['winner'].get('fullName', '')}"
        else:
            w = "TBD"
        print(f"{rnd:<4} {name:<50} {w:<25}")
    print("-" * 80)


if __name__ == "__main__":
    main()
