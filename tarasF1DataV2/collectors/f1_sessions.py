"""
Formula 1 Weekend Sessions Collector (V2)
Gathers and consolidates session results (FP1, FP2, FP3, Qualifying, Sprint Qualy, Sprint Race, Grand Prix)
into clean, strictly-typed weekend payloads without losing any data points.
"""

import json
import os


def _safe_load_json(file_path):
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def clean_practice(results):
    if not results:
        return []
    rows = []
    for r in results:
        num = r.get("number", r.get("driverNumber", ""))
        pos = r.get("position", "")
        driver = r.get("driver", r.get("driverName", ""))
        short = r.get("shortName", "")
        team = r.get("team", "")
        time_gap = r.get("timeOrGap", "")
        laps = r.get("laps", "")

        rows.append({
            "position": int(pos) if str(pos).isdigit() else pos,
            "driver_number": int(num) if str(num).isdigit() else num,
            "driver_name": driver,
            "driver_code": short,
            "team": team,
            "time_or_gap": time_gap,
            "laps": int(laps) if str(laps).isdigit() else laps
        })
    return rows


def clean_qualifying(results):
    if not results:
        return []
    rows = []
    for r in results:
        num = r.get("driverNumber", r.get("number", ""))
        pos = r.get("position", "")
        driver = r.get("driverName", r.get("driver", ""))
        team = r.get("team", "")
        q1 = r.get("q1", r.get("sq1", ""))
        q2 = r.get("q2", r.get("sq2", ""))
        q3 = r.get("q3", r.get("sq3", ""))
        laps = r.get("laps", "")

        entry = {
            "position": int(pos) if str(pos).isdigit() else pos,
            "driver_number": int(num) if str(num).isdigit() else num,
            "driver_name": driver,
            "team": team,
            "q1": q1,
            "q2": q2,
            "q3": q3,
            "laps": int(laps) if str(laps).isdigit() else laps
        }
        rows.append(entry)
    return rows


def clean_sprint_qualifying(results):
    if not results:
        return []
    rows = []
    for r in results:
        num = r.get("driverNumber", r.get("number", ""))
        pos = r.get("position", "")
        driver = r.get("driverName", r.get("driver", ""))
        team = r.get("team", "")
        sq1 = r.get("sq1", r.get("q1", ""))
        sq2 = r.get("sq2", r.get("q2", ""))
        sq3 = r.get("sq3", r.get("q3", ""))
        laps = r.get("laps", "")

        rows.append({
            "position": int(pos) if str(pos).isdigit() else pos,
            "driver_number": int(num) if str(num).isdigit() else num,
            "driver_name": driver,
            "team": team,
            "sq1": sq1,
            "sq2": sq2,
            "sq3": sq3,
            "laps": int(laps) if str(laps).isdigit() else laps
        })
    return rows


def clean_race(results):
    if not results:
        return []
    rows = []
    for r in results:
        num = r.get("driverNumber", r.get("number", ""))
        pos = r.get("position", "")
        driver = r.get("driverName", r.get("driver", ""))
        team = r.get("team", "")
        laps = r.get("laps", "")
        time_ret = r.get("timeOrRetired", "")
        pts = r.get("points", "")

        rows.append({
            "position": int(pos) if str(pos).isdigit() else pos,
            "driver_number": int(num) if str(num).isdigit() else num,
            "driver_name": driver,
            "team": team,
            "laps": int(laps) if str(laps).isdigit() else laps,
            "time_or_retired": time_ret,
            "points": int(pts) if str(pts).isdigit() else (float(pts) if str(pts).replace(".", "").isdigit() else pts)
        })
    return rows


def _load_calendar(base_dir=None):
    if base_dir is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base_dir, "..", "data", "calendar_master.json"),
        os.path.join(base_dir, "data", "calendar_master.json"),
        os.path.join(base_dir, "..", "..", "tarasF1DataV2", "data", "calendar_master.json"),
        os.path.join(base_dir, "..", "..", "tarasF1Data", "tarasF1DataV2", "data", "calendar_master.json"),
    ]
    cal_file = next((p for p in candidates if os.path.exists(p)), None)
    if cal_file:
        try:
            with open(cal_file, "r", encoding="utf-8") as f:
                return json.load(f).get("races", [])
        except Exception:
            return []
    return []


def _match_round_for_session(raw, calendar_races):
    circuit_id = (raw.get("circuitId") or "").strip().lower()
    race_name = (raw.get("raceName") or "").strip().lower()
    date_str = (raw.get("raceDate") or raw.get("date") or "").strip().lower()

    # 1. Match by exact circuitId
    if circuit_id:
        for r in calendar_races:
            c = r.get("circuit", {}).get("circuitId", "").lower()
            if c == circuit_id:
                return r.get("round"), r

    # 2. Match by key tokens in circuitId or raceName
    tokens = [circuit_id] if circuit_id else []
    for word in ["sepang", "zandvoort", "singapore", "marina_bay", "bahrain", "monza", "silverstone", "austin", "vegas", "monaco", "spa", "shanghai", "suzuka", "albert_park", "baku"]:
        if word in circuit_id or word in race_name:
            tokens.append(word)

    for token in tokens:
        for r in calendar_races:
            c = r.get("circuit", {}).get("circuitId", "").lower()
            rn = r.get("raceName", "").lower()
            if token in c or token in rn:
                return r.get("round"), r

    # Fallback to Sepang / Round 16 if "bahrain" or "sepang"
    if "sepang" in circuit_id or "bahrain" in race_name:
        for r in calendar_races:
            if r.get("round") == 16:
                return 16, r

    # Fallback: if Dutch / Zandvoort
    if "zandvoort" in circuit_id or "dutch" in race_name:
        for r in calendar_races:
            if r.get("round") in (12, 14):
                return r.get("round"), r

    return None, None


def load_all_known_sessions(repo_dir=None):
    """
    Intelligently groups session results (FP1, FP2, FP3, Qualifying, Sprint Qualy, Sprint Race, Grand Prix)
    by circuit and round. Handles live, in-progress race weekends:
    - On Friday: FP1 / FP2 results are populated; unrun sessions (FP3, Qualy, Race) are strictly null.
    - On Saturday: FP3 / Qualy (or Sprint) are populated; Race remains null.
    - On Sunday: Grand Prix results & points are populated; status transitions to 'completed'.
    Never leaks stale data from previous races into the active weekend.
    """
    if repo_dir is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.abspath(os.path.join(base_dir, "..", "..")),
            os.path.abspath(os.path.join(base_dir, "..")),
            os.path.abspath(os.path.join(base_dir, "..", "..", "tarasF1Data")),
        ]
        repo_dir = next((p for p in candidates if os.path.exists(os.path.join(p, "practice1"))), candidates[0])

    calendar_races = _load_calendar()

    # Define all 7 session files and their cleaners
    session_defs = [
        ("practice_1", os.path.join(repo_dir, "practice1", "fp1_extracted.json"), clean_practice),
        ("practice_2", os.path.join(repo_dir, "practice2", "fp2_extracted.json"), clean_practice),
        ("practice_3", os.path.join(repo_dir, "practice3", "fp3_extracted.json"), clean_practice),
        ("qualifying", os.path.join(repo_dir, "qualifying", "qualifying_results.json"), clean_qualifying),
        ("sprint_qualifying", os.path.join(repo_dir, "sprint-quly", "sprint_quly_result.json"), clean_sprint_qualifying),
        ("sprint_race", os.path.join(repo_dir, "sprint-race", "sprint_race_result.json"), clean_race),
        ("race", os.path.join(repo_dir, "race-result", "race_results.json"), clean_race),
    ]

    # Collect sessions grouped by round number
    round_buckets = {}  # round_num: {"cal_entry": ..., "meta": ..., "sessions": {}}

    for session_key, file_path, cleaner_fn in session_defs:
        data = _safe_load_json(file_path)
        if not data:
            continue

        raw_results = data.get("results", [])
        # Only associate if results is a non-empty list of driver classifications
        if not raw_results or not isinstance(raw_results, list) or len(raw_results) == 0:
            continue

        round_num, cal_entry = _match_round_for_session(data, calendar_races)
        if round_num is None:
            # Fallback to round 16 if no round matched
            round_num = 16

        if round_num not in round_buckets:
            round_buckets[round_num] = {
                "cal_entry": cal_entry or {},
                "meta": data,
                "sessions": {}
            }

        cleaned = cleaner_fn(raw_results)
        round_buckets[round_num]["sessions"][session_key] = cleaned

    # Find the maximum completed round (where Sunday race has occurred)
    max_completed_round = 0
    for r_num, bucket in round_buckets.items():
        r_race = bucket["sessions"].get("race")
        if r_race and isinstance(r_race, list) and len(r_race) > 0:
            if r_num > max_completed_round:
                max_completed_round = r_num

    events = {}

    # Build standardized event payload for every detected round
    for r_num, bucket in round_buckets.items():
        cal = bucket["cal_entry"]
        meta = bucket["meta"]
        s_data = bucket["sessions"]
        circuit = cal.get("circuit", {})

        race_name = cal.get("raceName") or meta.get("raceName", f"Formula 1 Grand Prix Round {r_num}")
        circuit_id = circuit.get("circuitId") or meta.get("circuitId", "unknown")
        circuit_name = circuit.get("circuitName") or meta.get("circuitName", "Unknown Circuit")
        country = circuit.get("country") or meta.get("country", "")
        date_range = meta.get("date") or meta.get("raceDate") or meta.get("race_date") or ""

        # Determine if sprint weekend
        sched = cal.get("schedule", {})
        has_sprint = bool("sprintQualy" in sched or "sprintRace" in sched or "sprint_qualifying" in s_data or "sprint_race" in s_data)
        weekend_format = "sprint" if has_sprint else "conventional"

        expected_sessions = (
            ["practice_1", "sprint_qualifying", "sprint_race", "qualifying", "race"]
            if has_sprint else
            ["practice_1", "practice_2", "practice_3", "qualifying", "race"]
        )

        # Build clean sessions dictionary: populated if run, strictly None if unrun
        sessions_dict = {
            "practice_1": s_data.get("practice_1"),
            "practice_2": s_data.get("practice_2"),
            "practice_3": s_data.get("practice_3") if not has_sprint else None,
            "qualifying": s_data.get("qualifying"),
            "sprint_qualifying": s_data.get("sprint_qualifying") if has_sprint else None,
            "sprint_race": s_data.get("sprint_race") if has_sprint else None,
            "race": s_data.get("race")
        }

        # Status determination:
        # A round is in_progress ONLY if it's the current/future active round and race hasn't concluded yet.
        has_race = bool(sessions_dict.get("race") and len(sessions_dict["race"]) > 0)
        has_any = any(v is not None and len(v) > 0 for v in sessions_dict.values())

        if has_race:
            status = "completed"
        elif r_num < max_completed_round:
            # Past round archived
            status = "completed"
        elif has_any:
            status = "in_progress"
        else:
            status = "upcoming"

        completed = [k for k, v in sessions_dict.items() if v is not None and len(v) > 0]
        upcoming = [k for k in expected_sessions if sessions_dict.get(k) is None]

        event_obj = {
            "round": r_num,
            "race_name": race_name,
            "country": country,
            "circuit_id": circuit_id,
            "circuit_name": circuit_name,
            "date_range": date_range,
            "status": status,
            "weekend_format": weekend_format,
            "has_sprint": has_sprint,
            "completed_sessions": completed,
            "upcoming_sessions": upcoming,
            "sessions": sessions_dict
        }

        events[f"round_{r_num}"] = event_obj

        # Provide round_14 alias if round 12 is Zandvoort for backward compatibility
        if circuit_id == "zandvoort" and f"round_14" not in events:
            events["round_14"] = dict(event_obj)
            events["round_14"]["round"] = 14

    return events


def get_latest_weekend_event(events):
    """
    Selects the most appropriate weekend for results/latest.json:
    1. If any round is currently 'in_progress' (e.g. Friday FP1/FP2 or Saturday Qualy), that is the active latest!
    2. Otherwise, returns the latest 'completed' round with the highest round number.
    3. Fallback to round_16.
    """
    if not events:
        return {}

    # Check for live in-progress round
    for k, ev in events.items():
        if ev.get("status") == "in_progress":
            return ev

    # Highest completed round
    completed_events = [ev for ev in events.values() if ev.get("status") == "completed"]
    if completed_events:
        completed_events.sort(key=lambda e: e.get("round", 0))
        return completed_events[-1]

    # Fallback to round_16 or first available
    return events.get("round_16") or next(iter(events.values()))


if __name__ == "__main__":
    evs = load_all_known_sessions()
    latest = get_latest_weekend_event(evs)
    print(f"Latest Active Weekend: Round {latest.get('round')} - {latest.get('race_name')} [{latest.get('status')}]")
    print(f"Completed sessions: {latest.get('completed_sessions')}")
    print(f"Upcoming sessions:  {latest.get('upcoming_sessions')}")

