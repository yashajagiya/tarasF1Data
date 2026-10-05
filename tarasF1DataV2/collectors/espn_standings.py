"""
ESPN Standings Collector (V2)
Fetches raw standings from the ESPN F1 API and normalizes them
against the master drivers registry. Zero Git commands, pure data function.
"""

import json
import os
import re
import ssl
import unicodedata
import urllib.request

API_URL = "https://site.api.espn.com/apis/v2/sports/racing/f1/standings"

OFFICIAL_TEAM_NAMES = {
    "Red Bull": "Red Bull Racing",
    "Haas": "Haas F1 Team",
}


def _normalize(s):
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("utf-8")
    return re.sub(r"[^a-z0-9]", "", s.lower())


def fetch_espn_raw_data():
    """Fetch raw standings JSON from ESPN."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(
        API_URL,
        headers={
            "User-Agent": "curl/8.4.0",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
        },
    )
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_drivers_lookup(registry_path=None):
    """Load driver registry lookup dictionary keyed by normalized name and acronym."""
    if registry_path is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        registry_path = os.path.join(base_dir, "..", "data", "drivers_registry.json")

    lookup = {}
    if os.path.exists(registry_path):
        with open(registry_path, "r", encoding="utf-8") as f:
            registry = json.load(f)
            for d in registry:
                norm_full = _normalize(d.get("full_name", ""))
                norm_last = _normalize(d.get("last_name", ""))
                code = d.get("code", "").upper()
                slug = d.get("slug", "")

                lookup[norm_full] = d
                if norm_last and norm_last not in lookup:
                    lookup[norm_last] = d
                if code:
                    lookup[code] = d
                if slug:
                    lookup[slug] = d
    return lookup


def parse_standings(raw_data, drivers_lookup=None):
    """
    Parse both Driver and Constructor standings from ESPN response.
    Returns:
      {
        "season": int,
        "drivers": [...],
        "teams": [...]
      }
    """
    if drivers_lookup is None:
        drivers_lookup = load_drivers_lookup()

    children = raw_data.get("children", [])
    if len(children) < 2:
        return {"season": 2026, "drivers": [], "teams": []}

    driver_child = children[0].get("standings", {})
    team_child = children[1].get("standings", {})
    season_val = driver_child.get("season", 2026)
    try:
        season = int(season_val)
    except Exception:
        season = 2026

    # 1. Driver Standings
    driver_entries = []
    for entry in driver_child.get("entries", []):
        athlete = entry.get("athlete", {})
        stats = entry.get("stats", [])

        # Stats lookup
        stats_map = {s.get("type"): s for s in stats if s.get("type")}
        rank_val = stats_map.get("rank", {}).get("value", 0)
        pts_val = stats_map.get("points", {}).get("value", 0.0)

        # Clean integer or float points
        points = int(pts_val) if float(pts_val).is_integer() else round(float(pts_val), 1)

        raw_name = athlete.get("displayName", athlete.get("name", ""))
        short_name = athlete.get("shortName", "")
        flag = athlete.get("flag", {})
        nationality = flag.get("alt", athlete.get("nationality", ""))

        norm_name = _normalize(raw_name)
        matched = drivers_lookup.get(norm_name)

        driver_number = matched.get("number") if matched else None
        team_name = matched.get("team") if matched else ""
        acronym = matched.get("code") if matched else ""
        driver_id = matched.get("slug") if matched else norm_name

        # Per-race points
        races = []
        round_num = 1
        for s in stats:
            stype = s.get("type", "")
            if stype in ("rank", "points", "overall"):
                continue
            played = bool(s.get("played", False))
            r_pts_val = s.get("value", 0.0)
            r_pts = int(r_pts_val) if float(r_pts_val).is_integer() else round(float(r_pts_val), 1)
            display_val = s.get("displayValue", "")

            races.append({
                "round": round_num,
                "race_code": s.get("name", ""),
                "race_name": s.get("displayName", ""),
                "played": played,
                "points": r_pts if played else 0,
                "display_value": display_val if played else ""
            })
            round_num += 1

        driver_entries.append({
            "rank": int(rank_val),
            "driver_id": driver_id,
            "driver_number": driver_number,
            "name": raw_name,
            "short_name": short_name,
            "code": acronym,
            "team_name": team_name,
            "nationality": nationality,
            "points": points,
            "races": races
        })

    # Sort drivers by rank
    driver_entries.sort(key=lambda x: x["rank"])

    # 2. Team (Constructor) Standings
    team_entries = []
    for entry in team_child.get("entries", []):
        team = entry.get("team", {})
        stats = entry.get("stats", [])

        stats_map = {s.get("type"): s for s in stats if s.get("type")}
        rank_val = stats_map.get("rank", {}).get("value", 0)
        pts_val = stats_map.get("points", {}).get("value", 0.0)
        points = int(pts_val) if float(pts_val).is_integer() else round(float(pts_val), 1)

        raw_team_name = team.get("displayName", team.get("name", ""))
        team_name = OFFICIAL_TEAM_NAMES.get(raw_team_name, raw_team_name)
        team_id = _normalize(team_name)

        races = []
        round_num = 1
        for s in stats:
            stype = s.get("type", "")
            if stype in ("rank", "points", "overall"):
                continue
            played = bool(s.get("played", False))
            r_pts_val = s.get("value", 0.0)
            r_pts = int(r_pts_val) if float(r_pts_val).is_integer() else round(float(r_pts_val), 1)

            races.append({
                "round": round_num,
                "race_code": s.get("name", ""),
                "race_name": s.get("displayName", ""),
                "played": played,
                "points": r_pts if played else 0,
                "display_value": s.get("displayValue", "") if played else ""
            })
            round_num += 1

        team_entries.append({
            "rank": int(rank_val),
            "team_id": team_id,
            "team_name": team_name,
            "points": points,
            "races": races
        })

    team_entries.sort(key=lambda x: x["rank"])

    return {
        "season": season,
        "drivers": driver_entries,
        "teams": team_entries
    }


if __name__ == "__main__":
    raw = fetch_espn_raw_data()
    data = parse_standings(raw)
    print(f"Parsed {len(data['drivers'])} drivers and {len(data['teams'])} teams.")
    print("Driver Leader:", data["drivers"][0]["name"], f"({data['drivers'][0]['points']} pts)")
    print("Team Leader:", data["teams"][0]["team_name"], f"({data['teams'][0]['points']} pts)")
