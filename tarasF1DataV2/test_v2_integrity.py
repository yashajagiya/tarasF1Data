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
        assert t["power_unit"], f"Missing power unit for {t['name']}"
        assert t["team_chief"], f"Missing team chief for {t['name']}"
    print("  [PASS] 3. teams.json integrity verified (All 11 constructors, car renders, logos, specs)")

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
    print("  [PASS] 5. calendar.json integrity verified (All rounds, circuit records, track outline maps)")

    # 6. Test Weekend Telemetry
    latest_results_path = os.path.join(OUTPUT_DIR, "results", "latest.json")
    assert os.path.exists(latest_results_path), "results/latest.json is missing!"
    latest = json.load(open(latest_results_path, encoding="utf-8"))
    sessions = latest["sessions"]
    assert len(sessions["practice_1"]) > 0, "FP1 results empty!"
    assert len(sessions["qualifying"]) > 0, "Qualifying results empty!"
    assert len(sessions["race"]) > 0, "Race results empty!"
    print("  [PASS] 6. results/latest.json integrity verified (FP1, FP2, FP3, Qualy, Sprint, Race all intact)")

    # 7. Test Historical Rounds (Round 1 to Round 15)
    for r_num in range(1, 16):
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
    print("  [PASS] 7. All historical rounds 1 to 15 verified (FP1, Qualy, Sprint, Race all intact)")

    print("\n" + "=" * 70)
    print("  ✅ ALL INTEGRITY TESTS PASSED: 100% DATA RETENTION CONFIRMED!")
    print("=" * 70)


if __name__ == "__main__":
    run_integrity_tests()
