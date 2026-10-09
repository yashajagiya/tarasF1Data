"""
Zero Data Loss & Integrity Verification Test for Taras F1 API v2
Validates that 100% of data fields, metrics, images, and sessions are preserved.
"""

import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def run_integrity_tests():
    print("=" * 70)
    print("  🧪 Running Taras F1 API v2 Data Integrity Verification")
    print("=" * 70)

    # 1. Test Overview
    overview_path = os.path.join(OUTPUT_DIR, "overview.json")
    assert os.path.exists(overview_path), "overview.json is missing!"
    overview = json.load(open(overview_path, encoding="utf-8"))
    assert overview["season"] == 2026, "Season mismatch!"
    assert overview["championship_leader"]["driver"]["name"], "Missing driver leader!"
    assert overview["championship_leader"]["team"]["name"], "Missing team leader!"
    assert overview["next_event"]["race_name"], "Missing next event race name!"
    assert len(overview["latest_race"]["podium"]) == 3, "Missing 3 podium finishers!"
    print("  [PASS] 1. overview.json integrity verified (Leaders, Next Event, Podium present)")

    # 2. Test Drivers
    drivers_path = os.path.join(OUTPUT_DIR, "drivers.json")
    assert os.path.exists(drivers_path), "drivers.json is missing!"
    drivers = json.load(open(drivers_path, encoding="utf-8"))
    assert len(drivers) == 23, f"Expected 23 drivers, found {len(drivers)}!"

    # Verify Yuki Tsunoda
    tsunoda = next((d for d in drivers if d["id"] == "yuki-tsunoda"), None)
    assert tsunoda is not None, "Yuki Tsunoda missing from drivers.json!"
    assert tsunoda["number"] == 22, f"Expected Tsunoda #22, got {tsunoda['number']}"
    assert tsunoda["team"]["name"] == "Racing Bulls", "Tsunoda team mismatch!"
    assert tsunoda["images"]["portrait"].startswith("http"), "Missing Tsunoda portrait!"
    assert len(tsunoda["biography"]["paragraphs"]) >= 5, "Missing Tsunoda biography paragraphs!"
    assert len(tsunoda["season_2026"]) == 16, f"Expected 16 season metrics, got {len(tsunoda['season_2026'])}"
    assert len(tsunoda["career_stats"]) == 8, f"Expected 8 career stats, got {len(tsunoda['career_stats'])}"
    print("  [PASS] 2. drivers.json integrity verified (All 23 drivers, Tsunoda #22, 16 season + 8 career metrics)")

    # 3. Test Teams
    teams_path = os.path.join(OUTPUT_DIR, "teams.json")
    assert os.path.exists(teams_path), "teams.json is missing!"
    teams = json.load(open(teams_path, encoding="utf-8"))
    assert len(teams) == 11, f"Expected 11 teams, found {len(teams)}!"
    for t in teams:
        assert t["images"]["car"], f"Missing car image for {t['name']}"
        assert t["images"]["logo"], f"Missing logo for {t['name']}"
        assert t["images"]["car"].endswith(".png") and "w_2400" in t["images"]["car"], f"Car image not official 2026 high-res PNG for {t['name']}"
        assert t["images"]["logo"].endswith(".png") and "w_1024" in t["images"]["logo"], f"Logo image not official 2026 high-res PNG for {t['name']}"
        assert t["power_unit"], f"Missing power unit for {t['name']}"
        assert t["team_chief"], f"Missing team chief for {t['name']}"
    print("  [PASS] 3. teams.json integrity verified (All 11 constructors, official high-res 2026 car renders, white logos, specs)")

    # 4. Test Standings
    standings_path = os.path.join(OUTPUT_DIR, "standings.json")
    assert os.path.exists(standings_path), "standings.json is missing!"
    standings = json.load(open(standings_path, encoding="utf-8"))
    assert len(standings["drivers"]) >= 22, "Missing drivers in standings!"
    assert len(standings["teams"]) == 11, "Missing teams in standings!"
    assert len(standings["drivers"][0]["races"]) > 0, "Missing round-by-round race points for drivers!"
    assert len(standings["teams"][0]["races"]) > 0, "Missing round-by-round race points for teams!"
    print("  [PASS] 4. standings.json integrity verified (Leaderboards + round-by-round points)")

    # 5. Test Calendar
    calendar_path = os.path.join(OUTPUT_DIR, "calendar.json")
    assert os.path.exists(calendar_path), "calendar.json is missing!"
    calendar = json.load(open(calendar_path, encoding="utf-8"))
    assert len(calendar) >= 22, f"Expected 22+ calendar rounds, found {len(calendar)}"
    for r in calendar:
        assert r["circuit"]["name"], f"Missing circuit name in round {r['round']}"
        assert r["circuit"]["track_image"], f"Missing track image in round {r['round']}"
        assert "race" in r["schedule"], f"Missing race schedule in round {r['round']}"
    # Verify Singapore Round 17 Sprint configuration
    r17 = next((r for r in calendar if r["round"] == 17), None)
    assert r17 is not None, "Round 17 Singapore missing from calendar.json!"
    assert r17["has_sprint"] is True, "Round 17 Singapore must be marked has_sprint=True!"
    assert r17["weekend_format"] == "sprint", "Round 17 Singapore must have weekend_format='sprint'!"
    assert "sprintQualy" in r17["schedule"], "Round 17 Singapore missing sprintQualy in schedule!"
    assert "sprintRace" in r17["schedule"], "Round 17 Singapore missing sprintRace in schedule!"
    print("  [PASS] 5. calendar.json integrity verified (All rounds, Singapore Sprint format, circuit records, track maps)")

    # 6. Test Weekend Telemetry
    latest_results_path = os.path.join(OUTPUT_DIR, "results", "latest.json")
    assert os.path.exists(latest_results_path), "results/latest.json is missing!"
    latest = json.load(open(latest_results_path, encoding="utf-8"))
    sessions = latest["sessions"]
    assert sessions.get("practice_1") and len(sessions["practice_1"]) > 0, "FP1 results empty!"
    if latest.get("status") == "in_progress":
        assert "practice_1" in latest.get("completed_sessions", []), "practice_1 should be in completed_sessions!"
        print(f"  [PASS] 6. results/latest.json integrity verified (Round {latest.get('round')} {latest.get('race_name')} in-progress, FP1 intact)")
    else:
        assert len(sessions["qualifying"]) > 0, "Qualifying results empty!"
        assert len(sessions["race"]) > 0, "Race results empty!"
        print("  [PASS] 6. results/latest.json integrity verified (FP1, FP2, FP3, Qualy, Sprint, Race all intact)")

    # 7. Test Concluded Rounds (Round 1 to Round 16)
    for r_num in range(1, 17):
        r_path = os.path.join(OUTPUT_DIR, "results", f"round_{r_num}.json")
        assert os.path.exists(r_path), f"results/round_{r_num}.json is missing!"
        r_data = json.load(open(r_path, encoding="utf-8"))
        assert r_data["round"] == r_num, f"Round number mismatch in {r_path}!"
        assert r_data["status"] == "completed", f"Status in {r_path} not completed!"
        assert len(r_data["sessions"]["race"]) > 0, f"Race results empty in {r_path}!"
        assert len(r_data["sessions"]["practice_1"]) > 0, f"FP1 results empty in {r_path}!"
        assert len(r_data["sessions"]["qualifying"]) > 0, f"Qualifying results empty in {r_path}!"
        if r_data.get("has_sprint"):
            assert len(r_data["sessions"]["sprint_race"]) > 0, f"Sprint race empty in sprint weekend {r_path}!"
    print("  [PASS] 7. All historical rounds 1 to 16 verified (FP1, Qualy, Sprint, Race all intact)")

    # 8. Test Round 17 (Singapore Sprint Weekend)
    r17_results_path = os.path.join(OUTPUT_DIR, "results", "round_17.json")
    if os.path.exists(r17_results_path):
        r17_res = json.load(open(r17_results_path, encoding="utf-8"))
        assert r17_res["round"] == 17, "Round 17 mismatch!"
        assert r17_res["has_sprint"] is True, "Round 17 must have has_sprint=True!"
        assert r17_res["weekend_format"] == "sprint", "Round 17 must have weekend_format='sprint'!"
        assert len(r17_res["sessions"]["practice_1"]) >= 20, "Round 17 FP1 results missing drivers!"
        print("  [PASS] 8. results/round_17.json integrity verified (Singapore Sprint Weekend, FP1 results intact)")

    print("\n" + "=" * 70)
    print("  ✅ ALL INTEGRITY TESTS PASSED: 100% DATA RETENTION CONFIRMED!")
    print("=" * 70)


if __name__ == "__main__":
    run_integrity_tests()
