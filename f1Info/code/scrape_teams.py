"""
F1 2026 Team Data Scraper
Fetches all 11 team pages from formula1.com and extracts:
  - Hero: name, team colors, team car cutout, team logo
  - 2026 Season: position, points, GP/Sprint stats (16 metrics)
  - Team Summary: GP entered, points, highest finish, poles, championships (7 metrics)
  - Team Profile: Base, Chief, Chassis, Power Unit, etc. (8 metrics)
  - Biography: team story / history summary
Outputs: teams_data.json
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
import sys
import os
import shutil
import subprocess
from datetime import datetime

# Fix Windows console encoding
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

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

# Canonical 2026 High-Resolution Assets for All 11 Teams (White logos & car cutouts)
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
    """Return official team assets (car render, white logo, color) instead of scraping from the website."""
    if slug in OFFICIAL_TEAM_ASSETS:
        return OFFICIAL_TEAM_ASSETS[slug]

    norm = (team_name or "").lower().replace(" ", "").replace("-", "")
    for s, asset in OFFICIAL_TEAM_ASSETS.items():
        if asset["team_name"].lower().replace(" ", "").replace("-", "") in norm or s.replace("-", "") in norm:
            return asset
    return None


def parse_team_page(html: str, slug: str) -> dict:
    """Parse a single team detail page and return structured data."""
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

    # ── Hero Section ──────────────────────────────────────────────
    h1 = soup.find("h1")
    if h1:
        data["hero"]["name"] = h1.get_text(strip=True)
    else:
        data["hero"]["name"] = slug.replace("-", " ").title()

    # Team colors: search style attributes and raw HTML for CSS custom properties
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

    # ── Team Car & Logo Images (Official 2026 High-Res Assets) ─────
    # Instead of pulling low-res / fallback assets from website, always use official links for V2 API
    asset = get_official_team_asset(slug, data["hero"].get("name", ""))
    if asset:
        data["hero"]["team_car"] = asset["team_car"]
        data["hero"]["team_logo"] = asset["team_logo"]
        if asset.get("team_color"):
            data["hero"]["team_color"] = asset["team_color"]
    else:
        # Fallback to website HTML if team is unrecognized
        car_img = soup.find("img", src=lambda s: s and "carright" in s.lower())
        if car_img:
            data["hero"]["team_car"] = car_img.get("src", "")
        else:
            team_name = data["hero"].get("name", "")
            car_img = soup.find("img", alt=lambda a: a and team_name.lower() in a.lower() and "logo" not in a.lower())
            if car_img and "formula1.com" in car_img.get("src", ""):
                data["hero"]["team_car"] = car_img.get("src", "")

        logo_img = soup.find("img", src=lambda s: s and ("logowhite" in s.lower() or "logolight" in s.lower()))
        if not logo_img:
            logo_img = soup.find("img", alt=lambda a: a and ("logowhite" in a.lower() or "logolight" in a.lower()))
        if not logo_img:
            for img in soup.find_all("img", src=True):
                src = img.get("src", "").lower()
                if "/logo/" in src or ("logo" in src and "f1" in src):
                    logo_img = img
                    break
        if logo_img:
            data["hero"]["team_logo"] = logo_img.get("src", "")

    # ── Biography ─────────────────────────────────────────────────
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

    # ── Statistics & Profile – parse all <dl> data grids ──────────
    all_sections = soup.find_all(["h2", "h3"])
    for heading in all_sections:
        heading_text = heading.get_text(strip=True).upper()
        parent = heading.find_parent("div", class_=lambda c: c and "flex" in c) or heading.parent
        dls = parent.find_all("dl") if parent else []

        for dl in dls:
            items = dl.find_all("div", class_=lambda c: c and "item" in (c or ""))
            if not items:
                dts = dl.find_all("dt")
                dds = dl.find_all("dd")
                pairs = list(zip(dts, dds))
            else:
                pairs = []
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

    # Fallback: if sections missed, categorize all dt/dd pairs
    if not data["season_2026"] and not data["team_summary"] and not data["team_profile"]:
        all_dls = soup.find_all("dl")
        for dl in all_dls:
            for dt, dd in zip(dl.find_all("dt"), dl.find_all("dd")):
                key = dt.get_text(strip=True)
                val = dd.get_text(strip=True)
                key_lower = key.lower()
                if "position" in key_lower or ("points" in key_lower and "team points" not in key_lower) or "sprint" in key_lower or ("grand prix" in key_lower and "entered" not in key_lower):
                    data["season_2026"][key] = val
                elif any(w in key_lower for w in ["name", "base", "chief", "chassis", "power unit", "entry"]):
                    data["team_profile"][key] = val
                else:
                    data["team_summary"][key] = val

    return data


def scrape_all_teams() -> list:
    """Fetch and parse all 11 team pages with connection pooling and retries."""
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
            name = team_data['hero'].get('name', slug)
            base = team_data.get('team_profile', {}).get('Base', '?')
            print(f"OK  {name:<22} | {base}")
        else:
            print(f"FAIL  ERROR: {last_error}")
            all_teams.append({"slug": slug, "url": url, "error": str(last_error)})

        # Polite delay between requests
        if i < total:
            time.sleep(1.5)

    return all_teams


def find_target_repo(script_path):
    """Locate the target tarasF1Data git repository."""
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


def push_f1info_to_git(out_path, info_type="teams"):
    """Sync and commit generated JSON to target Git repository."""
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

    # Also sync to root workspace file if it exists
    workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    root_json = os.path.join(workspace_root, file_name)
    if os.path.exists(root_json) and os.path.abspath(root_json) != os.path.abspath(out_path):
        shutil.copy2(out_path, root_json)

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
    print("  F1 2026 Team Data Scraper")
    print("=" * 60)
    print()

    teams = scrape_all_teams()

    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'teams_data.json'))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(teams, f, indent=2, ensure_ascii=False)

    print()
    print(f"Done! Saved {len(teams)} teams to {out_path}")

    # Synchronize to V2 master teams_registry.json
    script_dir = os.path.dirname(os.path.abspath(__file__))
    v2_registry_candidates = [
        os.path.abspath(os.path.join(script_dir, '..', '..', '..', 'tarasF1DataV2', 'data', 'teams_registry.json')),
        os.path.abspath(os.path.join(script_dir, '..', '..', 'tarasF1DataV2', 'data', 'teams_registry.json')),
        os.path.abspath(os.path.join(script_dir, '..', '..', '..', 'tarasF1Data', 'tarasF1DataV2', 'data', 'teams_registry.json')),
    ]
    for v2_path in v2_registry_candidates:
        if os.path.exists(os.path.dirname(v2_path)):
            with open(v2_path, "w", encoding="utf-8") as f:
                json.dump(teams, f, indent=2, ensure_ascii=False)
            print(f"Synced team data to V2 master registry: {v2_path}")

    # GitHub Upload & sync
    push_f1info_to_git(out_path, info_type="teams")

    # Quick summary
    print()
    print("-" * 60)
    print(f"{'#':<4} {'Team Name':<35} {'Base'}")
    print("-" * 60)
    for i, t in enumerate(teams, 1):
        hero = t.get("hero", {})
        profile = t.get("team_profile", {})
        name = hero.get("name", t.get("slug", "?"))
        base = profile.get("Base", "?")
        print(f"{i:<4} {name:<35} {base}")
    print("-" * 60)


if __name__ == "__main__":
    main()
