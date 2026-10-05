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


def load_all_known_sessions(repo_dir=None):
    """
    Separates weekend sessions by circuit/event so that races are not mixed up.
    Returns:
      {
        "round_16": { ... Sepang sessions (FP1-FP3, Qualy, Race) ... },
        "round_14": { ... Zandvoort sessions (Sprint Qualy, Sprint Race) ... }
      }
    """
    if repo_dir is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.abspath(os.path.join(base_dir, "..", "..")),
            os.path.abspath(os.path.join(base_dir, "..")),
            os.path.abspath(os.path.join(base_dir, "..", "..", "tarasF1Data")),
        ]
        repo_dir = next((p for p in candidates if os.path.exists(os.path.join(p, "practice1"))), candidates[0])

    fp1_data = _safe_load_json(os.path.join(repo_dir, "practice1", "fp1_extracted.json"))
    fp2_data = _safe_load_json(os.path.join(repo_dir, "practice2", "fp2_extracted.json"))
    fp3_data = _safe_load_json(os.path.join(repo_dir, "practice3", "fp3_extracted.json"))
    qualy_data = _safe_load_json(os.path.join(repo_dir, "qualifying", "qualifying_results.json"))
    sq_data = _safe_load_json(os.path.join(repo_dir, "sprint-quly", "sprint_quly_result.json"))
    sr_data = _safe_load_json(os.path.join(repo_dir, "sprint-race", "sprint_race_result.json"))
    race_data = _safe_load_json(os.path.join(repo_dir, "race-result", "race_results.json"))

    events = {}

    # Event 1: Sepang / Bahrain GP (Round 16) - Conventional weekend
    sepang_meta = race_data or qualy_data or fp1_data or {}
    events["round_16"] = {
        "round": 16,
        "race_name": sepang_meta.get("raceName", "FORMULA 1 GULF AIR BAHRAIN GRAND PRIX IN MALAYSIA 2026"),
        "country": sepang_meta.get("country", "Bahrain"),
        "circuit_id": sepang_meta.get("circuitId", "sepang"),
        "circuit_name": sepang_meta.get("circuitName", "Sepang International Circuit, Kuala Lumpur"),
        "date_range": sepang_meta.get("date", "02 - 04 Oct 2026"),
        "weekend_format": "conventional",
        "has_sprint": False,
        "sessions": {
            "practice_1": clean_practice((fp1_data or {}).get("results", [])),
            "practice_2": clean_practice((fp2_data or {}).get("results", [])),
            "practice_3": clean_practice((fp3_data or {}).get("results", [])),
            "qualifying": clean_qualifying((qualy_data or {}).get("results", [])),
            "sprint_qualifying": None,
            "sprint_race": None,
            "race": clean_race((race_data or {}).get("results", []))
        }
    }

    # Event 2: Zandvoort / Dutch GP (Round 14) - Sprint weekend
    if sq_data or sr_data:
        zand_meta = sr_data or sq_data or {}
        events["round_14"] = {
            "round": 14,
            "race_name": zand_meta.get("raceName", "FORMULA 1 HEINEKEN DUTCH GRAND PRIX 2026"),
            "country": zand_meta.get("country", "Netherlands"),
            "circuit_id": zand_meta.get("circuitId", "zandvoort"),
            "circuit_name": zand_meta.get("circuitName", "Circuit Zandvoort, Zandvoort"),
            "date_range": zand_meta.get("date", "21 - 23 Aug 2026"),
            "weekend_format": "sprint",
            "has_sprint": True,
            "sessions": {
                "practice_1": None,
                "practice_2": None,
                "practice_3": None,
                "qualifying": None,
                "sprint_qualifying": clean_sprint_qualifying((sq_data or {}).get("results", [])),
                "sprint_race": clean_race((sr_data or {}).get("results", [])),
                "race": None
            }
        }

    return events


if __name__ == "__main__":
    evs = load_all_known_sessions()
    for k, v in evs.items():
        print(f"Loaded {k}: {v['race_name']} (Format: {v['weekend_format']})")
        for s, rows in v["sessions"].items():
            if rows is not None:
                print(f"  - {s}: {len(rows)} entries")
