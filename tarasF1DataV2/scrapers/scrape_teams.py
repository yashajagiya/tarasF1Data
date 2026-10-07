"""
Taras F1 API v2 — Native Team Scraper
Fetches all 11 constructor pages from formula1.com and extracts:
  - Hero: name, official colors, 2026 high-resolution car cutout, 2026 white logo
  - 2026 Season: position, points, GP/Sprint stats (16 metrics)
  - Team Summary: GP entered, points, highest finish, poles, championships (7 metrics)
  - Team Profile: Base, Chief, Chassis, Power Unit, etc. (8 metrics)
  - Biography: team story / history summary
Directly updates: tarasF1DataV2/data/teams_registry.json
"""

import json
import os
import re
import sys
import time
import requests
from bs4 import BeautifulSoup

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "data"))

TEAM_SLUGS = [
    "mercedes",
    "ferrari",
    "mclaren",
    "red-bull-racing",
    "racing-bulls",
    "alpine",
    "haas",
    "audi",
    "williams",
    "aston-martin",
    "cadillac",
]

BASE_URL = "https://www.formula1.com/en/teams/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Canonical 2026 High-Resolution Assets for All 11 Teams
OFFICIAL_TEAM_ASSETS = {
    "mercedes": {
        "team_name": "Mercedes",
        "team_color": "0xFF27F4D2",
        "team_logo": "https://media.formula1.com/image/upload/c_fit,w_1024/e_sharpen:100/q_auto:best/v1740000001/common/f1/2026/mercedes/2026mercedeslogowhite.png",
        "team_car": "https://media.formula1.com/image/upload/c_fit,w_2400,h_1200/q_auto:best/d_common:f1:2026:fallback:car:2026fallbackcarright.webp/v1740000001/common/f1/2026/mercedes/2026mercedescarright.png",
    },
    "ferrari": {
        "team_name": "Ferrari",
        "team_color": "0xFFE8002D",
        "team_logo": "https://media.formula1.com/image/upload/c_fit,w_1024/e_sharpen:100/q_auto:best/v1740000001/common/f1/2026/ferrari/2026ferrarilogowhite.png",
        "team_car": "https://media.formula1.com/image/upload/c_fit,w_2400,h_1200/q_auto:best/d_common:f1:2026:fallback:car:2026fallbackcarright.webp/v1740000001/common/f1/2026/ferrari/2026ferraricarright.png",
    },
    "mclaren": {
        "team_name": "McLaren",
        "team_color": "0xFFFF8000",
        "team_logo": "https://media.formula1.com/image/upload/c_fit,w_1024/e_sharpen:100/q_auto:best/v1740000001/common/f1/2026/mclaren/2026mclarenlogowhite.png",
        "team_car": "https://media.formula1.com/image/upload/c_fit,w_2400,h_1200/q_auto:best/d_common:f1:2026:fallback:car:2026fallbackcarright.webp/v1740000001/common/f1/2026/mclaren/2026mclarencarright.png",
    },
    "red-bull-racing": {
        "team_name": "Red Bull",
        "team_color": "0xFF3671C6",
        "team_logo": "https://media.formula1.com/image/upload/c_fit,w_1024/e_sharpen:100/q_auto:best/v1740000001/common/f1/2026/redbullracing/2026redbullracinglogowhite.png",
        "team_car": "https://media.formula1.com/image/upload/c_fit,w_2400,h_1200/q_auto:best/d_common:f1:2026:fallback:car:2026fallbackcarright.webp/v1740000001/common/f1/2026/redbullracing/2026redbullracingcarright.png",
    },
    "alpine": {
        "team_name": "Alpine",
        "team_color": "0xFF00A1E8",
        "team_logo": "https://media.formula1.com/image/upload/c_fit,w_1024/e_sharpen:100/q_auto:best/v1740000001/common/f1/2026/alpine/2026alpinelogowhite.png",
        "team_car": "https://media.formula1.com/image/upload/c_fit,w_2400,h_1200/q_auto:best/d_common:f1:2026:fallback:car:2026fallbackcarright.webp/v1740000001/common/f1/2026/alpine/2026alpinecarright.png",
    },
    "racing-bulls": {
        "team_name": "Racing Bulls",
        "team_color": "0xFF6692FF",
        "team_logo": "https://media.formula1.com/image/upload/c_fit,w_1024/e_sharpen:100/q_auto:best/v1740000001/common/f1/2026/racingbulls/2026racingbullslogowhite.png",
        "team_car": "https://media.formula1.com/image/upload/c_fit,w_2400,h_1200/q_auto:best/d_common:f1:2026:fallback:car:2026fallbackcarright.webp/v1740000001/common/f1/2026/racingbulls/2026racingbullscarright.png",
    },
    "haas": {
        "team_name": "Haas",
        "team_color": "0xFFDEE1E2",
        "team_logo": "https://media.formula1.com/image/upload/c_fit,w_1024/e_sharpen:100/q_auto:best/v1740000001/common/f1/2026/haasf1team/2026haasf1teamlogowhite.png",
        "team_car": "https://media.formula1.com/image/upload/c_fit,w_2400,h_1200/q_auto:best/d_common:f1:2026:fallback:car:2026fallbackcarright.webp/v1740000001/common/f1/2026/haasf1team/2026haasf1teamcarright.png",
    },
    "williams": {
        "team_name": "Williams",
        "team_color": "0xFF1868DB",
        "team_logo": "https://media.formula1.com/image/upload/c_fit,w_1024/e_sharpen:100/q_auto:best/v1740000001/common/f1/2026/williams/2026williamslogowhite.png",
        "team_car": "https://media.formula1.com/image/upload/c_fit,w_2400,h_1200/q_auto:best/d_common:f1:2026:fallback:car:2026fallbackcarright.webp/v1740000001/common/f1/2026/williams/2026williamscarright.png",
    },
    "audi": {
        "team_name": "Audi",
        "team_color": "0xFFFF2D00",
        "team_logo": "https://media.formula1.com/image/upload/c_fit,w_1024/e_sharpen:100/q_auto:best/v1740000001/common/f1/2026/audi/2026audilogowhite.png",
        "team_car": "https://media.formula1.com/image/upload/c_fit,w_2400,h_1200/q_auto:best/d_common:f1:2026:fallback:car:2026fallbackcarright.webp/v1740000001/common/f1/2026/audi/2026audicarright.png",
    },
    "aston-martin": {
        "team_name": "Aston Martin",
        "team_color": "0xFF229971",
        "team_logo": "https://media.formula1.com/image/upload/c_fit,w_1024/e_sharpen:100/q_auto:best/v1740000001/common/f1/2026/astonmartin/2026astonmartinlogowhite.png",
        "team_car": "https://media.formula1.com/image/upload/c_fit,w_2400,h_1200/q_auto:best/d_common:f1:2026:fallback:car:2026fallbackcarright.webp/v1740000001/common/f1/2026/astonmartin/2026astonmartincarright.png",
    },
    "cadillac": {
        "team_name": "Cadillac",
        "team_color": "0xFFAAAAAD",
        "team_logo": "https://media.formula1.com/image/upload/c_fit,w_1024/e_sharpen:100/q_auto:best/v1740000001/common/f1/2026/cadillac/2026cadillaclogowhite.png",
        "team_car": "https://media.formula1.com/image/upload/c_fit,w_2400,h_1200/q_auto:best/d_common:f1:2026:fallback:car:2026fallbackcarright.webp/v1740000001/common/f1/2026/cadillac/2026cadillaccarright.png",
    },
}


def get_official_team_asset(slug: str, team_name: str = "") -> dict:
    if slug in OFFICIAL_TEAM_ASSETS:
        return OFFICIAL_TEAM_ASSETS[slug]
    norm = (team_name or "").lower().replace(" ", "").replace("-", "")
    for s, asset in OFFICIAL_TEAM_ASSETS.items():
        if asset["team_name"].lower().replace(" ", "").replace("-", "") in norm or s.replace("-", "") in norm:
            return asset
    return None


def parse_team_page(html: str, slug: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    data = {
        "slug": slug,
        "url": BASE_URL + slug,
        "hero": {},
        "biography": "",
        "season_2026": {},
        "team_summary": {},
        "team_profile": {},
    }

    h1 = soup.find("h1")
    if h1:
        data["hero"]["name"] = h1.get_text(strip=True)
    else:
        data["hero"]["name"] = slug.replace("-", " ").title()

    tc_found, ac_found = None, None
    for div in soup.find_all(style=True):
        style = div.get("style", "")
        if not tc_found:
            tc_match = re.search(r"--f1-team-colour:\s*(#[0-9a-fA-F]{3,8})", style)
            if tc_match:
                hex_color = tc_match.group(1).lstrip("#")
                if len(hex_color) == 3:
                    hex_color = "".join(c * 2 for c in hex_color)
                tc_found = f"0xFF{hex_color.upper()}"
        if not ac_found:
            ac_match = re.search(r"--f1-accessible-colour:\s*(#[0-9a-fA-F]{3,8})", style)
            if ac_match:
                ac_found = ac_match.group(1)
        if tc_found and ac_found:
            break

    if not tc_found:
        tc_match = re.search(r"--f1-team-colour:\s*(#[0-9a-fA-F]{3,8})", html)
        if tc_match:
            hex_color = tc_match.group(1).lstrip("#")
            if len(hex_color) == 3:
                hex_color = "".join(c * 2 for c in hex_color)
            tc_found = f"0xFF{hex_color.upper()}"
    if not ac_found:
        ac_match = re.search(r"--f1-accessible-colour:\s*(#[0-9a-fA-F]{3,8})", html)
        if ac_match:
            ac_found = ac_match.group(1)

    if tc_found:
        data["hero"]["team_color"] = tc_found
    if ac_found:
        data["hero"]["accessible_color"] = ac_found

    # Canonical high-res assets
    asset = get_official_team_asset(slug, data["hero"].get("name", ""))
    if asset:
        data["hero"]["team_car"] = asset["team_car"]
        data["hero"]["team_logo"] = asset["team_logo"]
        if asset.get("team_color"):
            data["hero"]["team_color"] = asset["team_color"]

    # Biography
    profile_sec = soup.find(id="profile")
    if profile_sec:
        first_p = profile_sec.find("p")
        if first_p and len(first_p.get_text(strip=True)) > 40:
            data["biography"] = first_p.get_text(strip=True)

    if not data["biography"]:
        bio_span = soup.find(
            lambda tag: tag.name in ["p", "span"] and tag.get("class") and any("body" in c and "bold" in c for c in tag.get("class"))
        )
        if bio_span and len(bio_span.get_text(strip=True)) > 40:
            data["biography"] = bio_span.get_text(strip=True)

    # Statistics & Profile
    all_sections = soup.find_all(["h2", "h3"])
    for heading in all_sections:
        heading_text = heading.get_text(strip=True).upper()
        parent = heading.find_parent("div", class_=lambda c: c and "flex" in c) or heading.parent
        dls = parent.find_all("dl") if parent else []

        for dl in dls:
            items = dl.find_all("div", class_=lambda c: c and "item" in (c or ""))
            pairs = []
            if not items:
                pairs = list(zip(dl.find_all("dt"), dl.find_all("dd")))
            else:
                for item in items:
                    dt = item.find("dt")
                    dd = item.find("dd")
                    if dt and dd:
                        pairs.append((dt, dd))

            for dt, dd in pairs:
                key = dt.get_text(strip=True)
                val = dd.get_text(strip=True)
                if "SEASON" in heading_text or "2026" in heading_text:
                    data["season_2026"][key] = val
                elif "SUMMARY" in heading_text:
                    data["team_summary"][key] = val
                elif "PROFILE" in heading_text:
                    data["team_profile"][key] = val

    return data


def scrape_all_teams() -> list:
    all_teams = []
    total = len(TEAM_SLUGS)
    session = requests.Session()
    session.headers.update(HEADERS)

    for i, slug in enumerate(TEAM_SLUGS, 1):
        url = BASE_URL + slug
        print(f"[{i:2d}/{total}] Fetching {slug}...", end=" ", flush=True)

        team_data = None
        last_error = None
        for attempt in range(1, 4):
            try:
                resp = session.get(url, timeout=25)
                resp.encoding = "utf-8"
                resp.raise_for_status()
                team_data = parse_team_page(resp.text, slug)
                break
            except requests.RequestException as e:
                last_error = e
                if attempt < 3:
                    time.sleep(2 * attempt)

        if team_data:
            all_teams.append(team_data)
            name = team_data["hero"].get("name", slug)
            base = team_data.get("team_profile", {}).get("Base", "?")
            print(f"OK  {name:<22} | {base}")
        else:
            print(f"FAIL  ERROR: {last_error}")
            all_teams.append({"slug": slug, "url": url, "error": str(last_error)})

        if i < total:
            time.sleep(1.5)

    return all_teams


def main():
    print("=" * 60)
    print("  🏎️  Taras F1 API v2 — Team Scraper")
    print("=" * 60)

    teams = scrape_all_teams()
    out_path = os.path.join(DATA_DIR, "teams_registry.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(teams, f, indent=2, ensure_ascii=False)

    print(f"\nDone! Saved {len(teams)} teams to {out_path}")

    # Optional legacy sync to v1 if it exists
    legacy_path = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "v1", "f1Info", "teams_data.json"))
    if os.path.exists(os.path.dirname(legacy_path)):
        try:
            with open(legacy_path, "w", encoding="utf-8") as f:
                json.dump(teams, f, indent=2, ensure_ascii=False)
            print(f"Synced copy to legacy path: {legacy_path}")
        except Exception:
            pass


if __name__ == "__main__":
    main()
