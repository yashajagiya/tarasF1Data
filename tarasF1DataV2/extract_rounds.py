"""
Formula 1 Historical & Past Rounds Data Extractor
Extracts complete session data (FP1, FP2, FP3, Qualifying, Sprint Qualifying, Sprint Race, Grand Prix)
for old rounds (e.g. Round 15 down to Round 1) directly from Formula 1 official results,
structuring them into clean, standardized Taras F1 API v2 payloads with 100% data fidelity.
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
import requests
from bs4 import BeautifulSoup

# Setup paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
SESSIONS_DIR = os.path.join(DATA_DIR, "sessions")
OUTPUT_RESULTS_DIR = os.path.join(BASE_DIR, "output", "results")
PUBLIC_V2_RESULTS_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "v2", "results"))
ROOT_REPO_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Formula 1 Web Mappings for 2026 Season
# Maps round number to F1 website race ID and slug
F1_WEB_ROUNDS = {
    1: {"f1_id": "1279", "slug": "australia"},
    2: {"f1_id": "1280", "slug": "china"},
    3: {"f1_id": "1281", "slug": "japan"},
    4: {"f1_id": "1284", "slug": "miami"},
    5: {"f1_id": "1285", "slug": "canada"},
    6: {"f1_id": "1286", "slug": "monaco"},
    7: {"f1_id": "1287", "slug": "barcelona-catalunya"},
    8: {"f1_id": "1288", "slug": "austria"},
    9: {"f1_id": "1289", "slug": "great-britain"},
    10: {"f1_id": "1290", "slug": "belgium"},
    11: {"f1_id": "1291", "slug": "hungary"},
    12: {"f1_id": "1292", "slug": "netherlands"},
    13: {"f1_id": "1293", "slug": "italy"},
    14: {"f1_id": "1294", "slug": "spain"},
    15: {"f1_id": "1295", "slug": "azerbaijan"},
    16: {"f1_id": "1308", "slug": "bahrain"},
    17: {"f1_id": "1296", "slug": "singapore"},
    18: {"f1_id": "1297", "slug": "united-states"},
    19: {"f1_id": "1298", "slug": "mexico"},
    20: {"f1_id": "1299", "slug": "brazil"},
    21: {"f1_id": "1300", "slug": "las-vegas"},
    22: {"f1_id": "1301", "slug": "qatar"},
    23: {"f1_id": "1302", "slug": "abu-dhabi"},
}


def load_calendar_master():
    cal_path = os.path.join(DATA_DIR, "calendar_master.json")
    if os.path.exists(cal_path):
        try:
            with open(cal_path, "r", encoding="utf-8") as f:
                return json.load(f).get("races", [])
        except Exception as e:
            print(f"  ⚠️ Error loading calendar_master.json: {e}")
    return []


def load_drivers_lookup():
    reg_path = os.path.join(DATA_DIR, "drivers_registry.json")
    lookup_by_num = {}
    lookup_by_name = {}
    if os.path.exists(reg_path):
        try:
            with open(reg_path, "r", encoding="utf-8") as f:
                reg = json.load(f)
                for d in reg:
                    num = d.get("number")
                    name = d.get("full_name")
                    code = d.get("code")
                    team = d.get("team")
                    info = {"number": num, "name": name, "code": code, "team": team}
                    if num is not None:
                        lookup_by_num[int(num)] = info
                    if name:
                        lookup_by_name[name.lower()] = info
        except Exception as e:
            print(f"  ⚠️ Error loading drivers_registry.json: {e}")
    return lookup_by_num, lookup_by_name


def clean_str(val):
    if val is None:
        return ""
    return re.sub(r"\s+", " ", str(val)).strip()


def parse_driver_cell(driver_col, lookup_by_num=None, fallback_num=None):
    """
    Extracts driver full name and 3-letter code from table cell.
    Formula 1 uses responsive spans:
      - max-lg:hidden: First Name (e.g. 'George')
      - max-md:hidden: Last Name (e.g. 'Russell')
      - md:hidden: Short 3-letter code (e.g. 'RUS')
    """
    first_span = driver_col.find("span", class_="max-lg:hidden")
    last_span = driver_col.find("span", class_="max-md:hidden")
    code_span = driver_col.find("span", class_="md:hidden")

    code = clean_str(code_span.text) if code_span else ""
    if first_span and last_span:
        name = f"{clean_str(first_span.text)} {clean_str(last_span.text)}"
    else:
        raw = clean_str(driver_col.get_text())
        if code and raw.endswith(code):
            raw = raw[:-len(code)].strip()
        name = raw

    # Cross-reference with registry if number is available
    if lookup_by_num and fallback_num is not None:
        try:
            num_int = int(fallback_num)
            if num_int in lookup_by_num:
                reg_driver = lookup_by_num[num_int]
                if not code:
                    code = reg_driver.get("code", "")
                if not name or len(name) < 3:
                    name = reg_driver.get("name", name)
        except Exception:
            pass

    return name, code


def scrape_f1_session_table(url, session_name="session", retries=3):
    """
    Scrapes an individual session results table from Formula1.com.
    Returns: (rows, page_title, date_text, circuit_text)
    """
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 404:
                return None, "", "", ""
            if resp.status_code != 200:
                time.sleep(1.0)
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            h1 = soup.find("h1")
            title = clean_str(h1.text) if h1 else ""

            date_text = ""
            circuit_text = ""
            if h1:
                p_siblings = h1.find_all_next("p")
                if len(p_siblings) >= 2:
                    date_text = clean_str(p_siblings[0].text)
                    circuit_text = clean_str(p_siblings[1].text)

            table = soup.find("table")
            if not table or not table.find("tbody"):
                return [], title, date_text, circuit_text

            rows = []
            for tr in table.find("tbody").find_all("tr"):
                cols = tr.find_all("td")
                if cols:
                    rows.append(cols)
            return rows, title, date_text, circuit_text
        except Exception as e:
            if attempt == retries:
                print(f"      ⚠️ Failed fetching {session_name} ({url}): {e}")
            time.sleep(1.0)

    return None, "", "", ""


def parse_practice_session(cols_list, lookup_by_num=None):
    results = []
    for cols in cols_list:
        if len(cols) < 6:
            continue
        pos = clean_str(cols[0].text)
        num = clean_str(cols[1].text)
        name, code = parse_driver_cell(cols[2], lookup_by_num, num)
        team = clean_str(cols[3].text)
        time_gap = clean_str(cols[4].text)
        laps = clean_str(cols[5].text)

        results.append({
            "position": int(pos) if pos.isdigit() else pos,
            "driver_number": int(num) if num.isdigit() else num,
            "driver_name": name,
            "driver_code": code,
            "team": team,
            "time_or_gap": time_gap,
            "laps": int(laps) if laps.isdigit() else laps,
        })
    return results


def parse_qualifying_session(cols_list, is_sprint=False, lookup_by_num=None):
    results = []
    for cols in cols_list:
        if len(cols) < 8:
            continue
        pos = clean_str(cols[0].text)
        num = clean_str(cols[1].text)
        name, _ = parse_driver_cell(cols[2], lookup_by_num, num)
        team = clean_str(cols[3].text)
        q1 = clean_str(cols[4].text)
        q2 = clean_str(cols[5].text)
        q3 = clean_str(cols[6].text)
        laps = clean_str(cols[7].text)

        if is_sprint:
            entry = {
                "position": int(pos) if pos.isdigit() else pos,
                "driver_number": int(num) if num.isdigit() else num,
                "driver_name": name,
                "team": team,
                "sq1": q1,
                "sq2": q2,
                "sq3": q3,
                "laps": int(laps) if laps.isdigit() else laps,
            }
        else:
            entry = {
                "position": int(pos) if pos.isdigit() else pos,
                "driver_number": int(num) if num.isdigit() else num,
                "driver_name": name,
                "team": team,
                "q1": q1,
                "q2": q2,
                "q3": q3,
                "laps": int(laps) if laps.isdigit() else laps,
            }
        results.append(entry)
    return results


def parse_race_session(cols_list, lookup_by_num=None):
    results = []
    for cols in cols_list:
        if len(cols) < 7:
            continue
        pos = clean_str(cols[0].text)
        num = clean_str(cols[1].text)
        name, _ = parse_driver_cell(cols[2], lookup_by_num, num)
        team = clean_str(cols[3].text)
        laps = clean_str(cols[4].text)
        time_ret = clean_str(cols[5].text)
        pts = clean_str(cols[6].text)

        parsed_pts = int(pts) if pts.isdigit() else (float(pts) if pts.replace(".", "", 1).isdigit() else pts)
        results.append({
            "position": int(pos) if pos.isdigit() else pos,
            "driver_number": int(num) if num.isdigit() else num,
            "driver_name": name,
            "team": team,
            "laps": int(laps) if laps.isdigit() else laps,
            "time_or_retired": time_ret,
            "points": parsed_pts,
        })
    return results


def extract_single_round(round_num, cal_race, lookup_by_num, verbose=True):
    """
    Extracts all weekend sessions for a specific round from Formula 1 website,
    formatting it into the standardized Taras F1 API v2 payload.
    """
    web_info = F1_WEB_ROUNDS.get(round_num)
    if not web_info:
        print(f"  ❌ No web mapping found for Round {round_num}")
        return None

    f1_id = web_info["f1_id"]
    slug = web_info["slug"]
    base_url = f"https://www.formula1.com/en/results/2026/races/{f1_id}/{slug}"

    circuit_data = cal_race.get("circuit", {})
    sched_data = cal_race.get("schedule", {})

    has_sprint = bool("sprintQualy" in sched_data or "sprintRace" in sched_data)
    weekend_format = "sprint" if has_sprint else "conventional"

    race_name = cal_race.get("raceName") or f"Formula 1 Grand Prix Round {round_num}"
    circuit_id = circuit_data.get("circuitId", slug)
    circuit_name = circuit_data.get("circuitName", "Unknown Circuit")
    country = circuit_data.get("country", "")

    if verbose:
        print(f"\n🏎️  Extracting Round {round_num:02d}: {race_name} [{weekend_format.upper()}]")
        print(f"   URL: {base_url}")

    sessions = {
        "practice_1": None,
        "practice_2": None,
        "practice_3": None,
        "qualifying": None,
        "sprint_qualifying": None,
        "sprint_race": None,
        "race": None,
    }

    date_range_detected = ""
    circuit_detected = ""

    # 1. Practice 1
    fp1_cols, _, d_text, c_text = scrape_f1_session_table(f"{base_url}/practice/1", "FP1")
    if fp1_cols:
        sessions["practice_1"] = parse_practice_session(fp1_cols, lookup_by_num)
        if verbose:
            print(f"   ✓ FP1:               {len(sessions['practice_1'])} drivers")
    if d_text and not date_range_detected:
        date_range_detected = d_text
    if c_text and not circuit_detected:
        circuit_detected = c_text

    # 2. Sprint Qualifying & Sprint Race (if sprint weekend)
    if has_sprint:
        sq_cols, _, _, _ = scrape_f1_session_table(f"{base_url}/sprint-qualifying", "Sprint Qualy")
        if sq_cols:
            sessions["sprint_qualifying"] = parse_qualifying_session(sq_cols, is_sprint=True, lookup_by_num=lookup_by_num)
            if verbose:
                print(f"   ✓ Sprint Qualifying: {len(sessions['sprint_qualifying'])} drivers")

        sr_cols, _, _, _ = scrape_f1_session_table(f"{base_url}/sprint-results", "Sprint Race")
        if sr_cols:
            sessions["sprint_race"] = parse_race_session(sr_cols, lookup_by_num)
            if verbose:
                print(f"   ✓ Sprint Race:       {len(sessions['sprint_race'])} drivers")
    else:
        # FP2 & FP3 (if conventional weekend)
        fp2_cols, _, _, _ = scrape_f1_session_table(f"{base_url}/practice/2", "FP2")
        if fp2_cols:
            sessions["practice_2"] = parse_practice_session(fp2_cols, lookup_by_num)
            if verbose:
                print(f"   ✓ FP2:               {len(sessions['practice_2'])} drivers")

        fp3_cols, _, _, _ = scrape_f1_session_table(f"{base_url}/practice/3", "FP3")
        if fp3_cols:
            sessions["practice_3"] = parse_practice_session(fp3_cols, lookup_by_num)
            if verbose:
                print(f"   ✓ FP3:               {len(sessions['practice_3'])} drivers")

    # 3. Qualifying
    q_cols, _, _, _ = scrape_f1_session_table(f"{base_url}/qualifying", "Qualifying")
    if q_cols:
        sessions["qualifying"] = parse_qualifying_session(q_cols, is_sprint=False, lookup_by_num=lookup_by_num)
        if verbose:
            print(f"   ✓ Qualifying:        {len(sessions['qualifying'])} drivers")

    # 4. Sunday Grand Prix Race Result
    r_cols, r_title, r_date, r_circ = scrape_f1_session_table(f"{base_url}/race-result", "Race Result")
    if r_cols:
        sessions["race"] = parse_race_session(r_cols, lookup_by_num)
        if verbose:
            winner = sessions["race"][0]["driver_name"] if sessions["race"] else "Unknown"
            print(f"   ✓ Grand Prix Race:   {len(sessions['race'])} drivers (Winner: {winner})")
    if r_date and not date_range_detected:
        date_range_detected = r_date
    if r_circ and not circuit_detected:
        circuit_detected = r_circ

    # Session completion status
    expected = (
        ["practice_1", "sprint_qualifying", "sprint_race", "qualifying", "race"]
        if has_sprint else
        ["practice_1", "practice_2", "practice_3", "qualifying", "race"]
    )
    completed = [k for k, v in sessions.items() if v is not None and len(v) > 0]
    upcoming = [k for k in expected if sessions.get(k) is None or len(sessions.get(k) or []) == 0]

    has_race = bool(sessions.get("race") and len(sessions["race"]) > 0)
    if has_race:
        status = "completed"
    elif completed:
        status = "in_progress"
    else:
        status = "upcoming"

    # Assemble complete round payload
    round_payload = {
        "round": round_num,
        "race_name": race_name,
        "country": country,
        "circuit_id": circuit_id,
        "circuit_name": circuit_detected or circuit_name,
        "date_range": date_range_detected,
        "status": status,
        "weekend_format": weekend_format,
        "has_sprint": has_sprint,
        "completed_sessions": completed,
        "upcoming_sessions": upcoming,
        "sessions": sessions,
    }

    return round_payload


def save_round_payload(round_payload, save_individual_files=True):
    """
    Saves the extracted round to:
    1. tarasF1DataV2/data/sessions/round_{N}.json (master storage)
    2. tarasF1DataV2/output/results/round_{N}.json (output API)
    3. v2/results/round_{N}.json (GitHub Pages sync)
    4. Optional: tarasF1DataV2/data/sessions/round_{N}/ individual files
    """
    r_num = round_payload["round"]
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    os.makedirs(OUTPUT_RESULTS_DIR, exist_ok=True)
    os.makedirs(PUBLIC_V2_RESULTS_DIR, exist_ok=True)

    filename = f"round_{r_num}.json"

    # 1. Master storage
    master_path = os.path.join(SESSIONS_DIR, filename)
    with open(master_path, "w", encoding="utf-8") as f:
        json.dump(round_payload, f, indent=2, ensure_ascii=False)

    # 2. Output results
    output_path = os.path.join(OUTPUT_RESULTS_DIR, filename)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(round_payload, f, indent=2, ensure_ascii=False)

    # 3. Public v2 results
    public_path = os.path.join(PUBLIC_V2_RESULTS_DIR, filename)
    with open(public_path, "w", encoding="utf-8") as f:
        json.dump(round_payload, f, indent=2, ensure_ascii=False)

    # 4. Optional individual session files in round folder
    if save_individual_files:
        round_dir = os.path.join(SESSIONS_DIR, f"round_{r_num}")
        os.makedirs(round_dir, exist_ok=True)
        for s_key, s_data in round_payload["sessions"].items():
            if s_data is not None:
                s_path = os.path.join(round_dir, f"{s_key}.json")
                with open(s_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "round": r_num,
                        "session": s_key,
                        "race_name": round_payload["race_name"],
                        "circuit_name": round_payload["circuit_name"],
                        "circuit_id": round_payload["circuit_id"],
                        "date": round_payload["date_range"],
                        "results": s_data
                    }, f, indent=2, ensure_ascii=False)

    file_size_kb = round(os.path.getsize(master_path) / 1024, 1)
    return master_path, file_size_kb


def export_round_to_legacy_directories(round_payload):
    """
    Exports a round's session files into the root legacy folders
    (practice1/fp1_extracted.json, race-result/race_results.json, etc.)
    for testing or legacy scraper compatibility.
    """
    r_num = round_payload["round"]
    s = round_payload["sessions"]
    r_name = round_payload["race_name"]
    c_name = round_payload["circuit_name"]
    c_id = round_payload["circuit_id"]
    d_range = round_payload["date_range"]
    country = round_payload["country"]

    mappings = [
        ("practice_1", "practice1", "fp1_extracted.json"),
        ("practice_2", "practice2", "fp2_extracted.json"),
        ("practice_3", "practice3", "fp3_extracted.json"),
        ("qualifying", "qualifying", "qualifying_results.json"),
        ("sprint_qualifying", "sprint-quly", "sprint_quly_result.json"),
        ("sprint_race", "sprint-race", "sprint_race_result.json"),
        ("race", "race-result", "race_results.json"),
    ]

    print(f"\n[Legacy Export] Exporting Round {r_num} to root session directories...")
    for s_key, folder, out_file in mappings:
        rows = s.get(s_key)
        if rows is None:
            continue
        dest_dir = os.path.join(ROOT_REPO_DIR, folder)
        if os.path.exists(dest_dir):
            payload = {
                "country": country,
                "session": s_key.upper().replace("_", " "),
                "raceName": f"{r_name} - {s_key.upper()}".upper(),
                "date": d_range,
                "circuitName": c_name,
                "circuitId": c_id,
                "results": rows,
            }
            target_path = os.path.join(dest_dir, out_file)
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=4, ensure_ascii=False)
            print(f"   ✓ Updated {folder}/{out_file} ({len(rows)} entries)")


def extract_past_rounds(rounds_to_extract, force=False, save_individual=True, verbose=True):
    """
    Extracts a list of rounds (e.g. [15, 14, 13, ..., 1]).
    Skips already extracted rounds unless force=True.
    """
    cal_races = load_calendar_master()
    cal_by_round = {r.get("round"): r for r in cal_races if r.get("round")}
    lookup_by_num, _ = load_drivers_lookup()

    extracted_count = 0
    skipped_count = 0
    summary = []

    print("=" * 75)
    print("  🏎️  Taras F1 Historical Rounds Data Extractor")
    print(f"  Target Rounds: {rounds_to_extract}")
    print("=" * 75)

    for r_num in rounds_to_extract:
        master_file = os.path.join(SESSIONS_DIR, f"round_{r_num}.json")
        if os.path.exists(master_file) and not force:
            try:
                with open(master_file, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                has_race = bool(existing.get("sessions", {}).get("race"))
                if has_race:
                    if verbose:
                        print(f"  ⚡ Round {r_num:02d} already extracted in {os.path.basename(master_file)} (Use --force to re-scrape)")
                    summary.append({
                        "round": r_num,
                        "name": existing.get("race_name", ""),
                        "winner": (existing.get("sessions", {}).get("race", [{}])[0].get("driver_name", "")),
                        "status": "cached",
                    })
                    skipped_count += 1
                    continue
            except Exception:
                pass

        cal_race = cal_by_round.get(r_num, {})
        payload = extract_single_round(r_num, cal_race, lookup_by_num, verbose=verbose)
        if not payload:
            continue

        master_path, size_kb = save_round_payload(payload, save_individual_files=save_individual)
        winner = payload["sessions"]["race"][0]["driver_name"] if payload["sessions"].get("race") else "N/A"
        summary.append({
            "round": r_num,
            "name": payload["race_name"],
            "winner": winner,
            "status": f"extracted ({size_kb} KB)",
        })
        extracted_count += 1
        time.sleep(0.5)  # Respectful throttle

    print("\n" + "=" * 75)
    print("  🏁 Extraction Summary:")
    print(f"  • Extracted: {extracted_count} rounds")
    print(f"  • Cached/Skipped: {skipped_count} rounds")
    print("-" * 75)
    print(f"  {'Round':<7} | {'Status':<18} | {'Winner':<22} | {'Grand Prix'}")
    print("-" * 75)
    for s in summary:
        print(f"  Round {s['round']:<2} | {s['status']:<18} | {s['winner']:<22} | {s['name']}")
    print("=" * 75)

    return extracted_count


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Extract Formula 1 historical round data (15 down to 1) into Taras F1 API v2"
    )
    parser.add_argument(
        "--rounds", "-r",
        type=str,
        default="",
        help="Comma-separated round numbers to extract (e.g. '15,14,13' or '1,2,3')",
    )
    parser.add_argument(
        "--round",
        type=int,
        default=None,
        help="Extract a single round (e.g. --round 15)",
    )
    parser.add_argument(
        "--from",
        dest="from_round",
        type=int,
        default=None,
        help="Start round in range (e.g. --from 15)",
    )
    parser.add_argument(
        "--to",
        dest="to_round",
        type=int,
        default=None,
        help="End round in range (e.g. --to 1)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Extract all concluded rounds (Round 1 to Round 16)",
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force re-scraping even if round is already cached",
    )
    parser.add_argument(
        "--build", "-b",
        action="store_true",
        help="Automatically run build.py to update the complete V2 API after extraction",
    )
    parser.add_argument(
        "--set-active",
        type=int,
        default=None,
        help="Copy extracted round files to legacy root directories (e.g. --set-active 15)",
    )
    return parser.parse_args()


def main():
    args = parse_arguments()

    # Determine rounds to extract
    if args.round is not None:
        target_rounds = [args.round]
    elif args.rounds:
        target_rounds = [int(x.strip()) for x in args.rounds.split(",") if x.strip().isdigit()]
    elif args.from_round is not None and args.to_round is not None:
        step = -1 if args.from_round > args.to_round else 1
        target_rounds = list(range(args.from_round, args.to_round + step, step))
    elif args.all:
        target_rounds = list(range(1, 17))
    else:
        # Default: extract old rounds 15 down to 1 (as requested by user)
        target_rounds = list(range(15, 0, -1))

    extract_past_rounds(target_rounds, force=args.force)

    # Optional set-active / legacy export
    if args.set_active:
        active_file = os.path.join(SESSIONS_DIR, f"round_{args.set_active}.json")
        if os.path.exists(active_file):
            with open(active_file, "r", encoding="utf-8") as f:
                payload = json.load(f)
            export_round_to_legacy_directories(payload)
        else:
            print(f"  ⚠️ Cannot set active: {active_file} not found.")

    # Optional trigger build.py
    if args.build:
        print("\n[Build] Running Master Build Engine...")
        import subprocess
        build_script = os.path.join(BASE_DIR, "build.py")
        subprocess.run([sys.executable, build_script], cwd=BASE_DIR, check=True)


if __name__ == "__main__":
    main()
