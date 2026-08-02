"""
F1 2026 Team Data Scraper
Fetches all 11 team pages from formula1.com and extracts:
  - Hero: name, team colors
  - 2026 Season: position, points, GP/Sprint stats
  - Team Summary: GP entered, points, highest finish, poles, championships
  - Team Profile: Base, Chief, Chassis, Power Unit
Outputs: teams_data.json
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
import sys
import os

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
    # Name from <h1>
    h1 = soup.find("h1")
    if h1:
        data["hero"]["name"] = h1.get_text(strip=True)
    else:
        data["hero"]["name"] = slug.replace("-", " ").title()

    # Team colors from parent containers with style attributes
    for div in soup.find_all("div", style=True):
        style = div.get("style", "")
        tc_match = re.search(r"--f1-team-colour:\s*(#[0-9a-fA-F]{3,8})", style)
        ac_match = re.search(r"--f1-accessible-colour:\s*(#[0-9a-fA-F]{3,8})", style)
        if tc_match:
            hex_color = tc_match.group(1).lstrip("#")
            # Pad to 6 chars if short-form (e.g. #abc -> aabbcc)
            if len(hex_color) == 3:
                hex_color = "".join(c * 2 for c in hex_color)
            data["hero"]["team_color"] = f"0xFF{hex_color.upper()}"
        if ac_match:
            data["hero"]["accessible_color"] = ac_match.group(1)
        if tc_match or ac_match:
            break

    # ── Team Car Image ────────────────────────────────────────────
    # Look for <img> whose src contains "carright"
    car_img = soup.find("img", src=lambda s: s and "carright" in s.lower())
    if car_img:
        data["hero"]["team_car"] = car_img.get("src", "")
    else:
        # Fallback: look for img with alt matching team name
        team_name = data["hero"].get("name", "")
        car_img = soup.find("img", alt=lambda a: a and team_name.lower() in a.lower() and "logo" not in a.lower())
        if car_img and "formula1.com" in car_img.get("src", ""):
            data["hero"]["team_car"] = car_img.get("src", "")

    # ── Team Logo Image ───────────────────────────────────────────
    # Look for <img> whose src or alt contains "logowhite" or "logolight"
    logo_img = soup.find("img", src=lambda s: s and ("logowhite" in s.lower() or "logolight" in s.lower()))
    if not logo_img:
        logo_img = soup.find("img", alt=lambda a: a and ("logowhite" in a.lower() or "logolight" in a.lower()))
    if logo_img:
        data["hero"]["team_logo"] = logo_img.get("src", "")

    # ── Biography ─────────────────────────────────────────────────
    bio_span = soup.find(
        "span",
        class_=lambda c: c and "typography-module_body-s-bold" in c and "typography-module_md_body-m-bold" in c
    )
    if bio_span:
        data["biography"] = bio_span.get_text(strip=True)

    # ── Statistics – parse all <dl> data grids ────────────────────
    all_sections = soup.find_all(["h2", "h3"])
    for heading in all_sections:
        heading_text = heading.get_text(strip=True).upper()

        # Find the next <dl> siblings/cousins
        parent = heading.find_parent("div", class_=lambda c: c and "flex" in c)
        if not parent:
            parent = heading.parent

        dls = parent.find_all("dl") if parent else []

        for dl in dls:
            items = dl.find_all("div", class_=lambda c: c and "item" in (c or ""))
            if not items:
                # Try direct dt/dd pairs
                dts = dl.find_all("dt")
                dds = dl.find_all("dd")
                for dt_tag, dd_tag in zip(dts, dds):
                    key = dt_tag.get_text(strip=True)
                    val = dd_tag.get_text(strip=True)
                    if "SEASON" in heading_text or "2026" in heading_text:
                        data["season_2026"][key] = val
                    elif "SUMMARY" in heading_text:
                        data["team_summary"][key] = val
                    elif "PROFILE" in heading_text:
                        data["team_profile"][key] = val
            else:
                for item in items:
                    dt = item.find("dt")
                    dd = item.find("dd")
                    if dt and dd:
                        key = dt.get_text(strip=True)
                        value = dd.get_text(strip=True)
                        if "SEASON" in heading_text or "2026" in heading_text:
                            data["season_2026"][key] = value
                        elif "SUMMARY" in heading_text:
                            data["team_summary"][key] = value
                        elif "PROFILE" in heading_text:
                            data["team_profile"][key] = value

    # ── Fallback: if sections missed, grab ALL dt/dd pairs ────────
    if not data["season_2026"] and not data["team_summary"] and not data["team_profile"]:
        all_dls = soup.find_all("dl")
        for dl in all_dls:
            items = dl.find_all("div", class_=lambda c: c and "item" in (c or ""))
            if not items:
                dts = dl.find_all("dt")
                dds = dl.find_all("dd")
                for dt_tag, dd_tag in zip(dts, dds):
                    key = dt_tag.get_text(strip=True)
                    val = dd_tag.get_text(strip=True)
                    
                    key_lower = key.lower()
                    if "position" in key_lower or "points" in key_lower and "team points" not in key_lower or "sprint" in key_lower or "grand prix" in key_lower and "entered" not in key_lower:
                        data["season_2026"][key] = val
                    elif "name" in key_lower or "base" in key_lower or "chief" in key_lower or "chassis" in key_lower or "power unit" in key_lower or "entry" in key_lower:
                        data["team_profile"][key] = val
                    else:
                        data["team_summary"][key] = val
            else:
                for item in items:
                    dt = item.find("dt")
                    dd = item.find("dd")
                    if dt and dd:
                        key = dt.get_text(strip=True)
                        val = dd.get_text(strip=True)
                        
                        key_lower = key.lower()
                        if "position" in key_lower or "points" in key_lower and "team points" not in key_lower or "sprint" in key_lower or "grand prix" in key_lower and "entered" not in key_lower:
                            data["season_2026"][key] = val
                        elif "name" in key_lower or "base" in key_lower or "chief" in key_lower or "chassis" in key_lower or "power unit" in key_lower or "entry" in key_lower:
                            data["team_profile"][key] = val
                        else:
                            data["team_summary"][key] = val

    return data


def scrape_all_teams() -> list:
    """Fetch and parse all 11 team pages."""
    all_teams = []
    total = len(TEAM_SLUGS)

    for i, slug in enumerate(TEAM_SLUGS, 1):
        url = BASE_URL + slug
        print(f"[{i}/{total}] Fetching {slug}...", end=" ", flush=True)

        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            team_data = parse_team_page(resp.text, slug)
            all_teams.append(team_data)
            print(f"OK  {team_data['hero'].get('name', slug)}")
        except requests.RequestException as e:
            print(f"FAIL  ERROR: {e}")
            all_teams.append({"slug": slug, "url": url, "error": str(e)})

        # Be polite – delay between requests
        if i < total:
            time.sleep(5)

    return all_teams


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

    # GitHub Upload
    repo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'tarasF1Data'))
    if os.path.exists(repo_path):
        import shutil
        import subprocess
        
        try:
            # Sync with remote first to avoid push conflicts
            subprocess.run(["git", "pull", "--rebase"], cwd=repo_path, check=True)
            
            file_name = os.path.basename(out_path)
            # Target the f1Info folder inside the repo
            target_dir = os.path.join(repo_path, 'f1Info')
            os.makedirs(target_dir, exist_ok=True)
            dest_path = os.path.join(target_dir, file_name)
            
            shutil.copy2(out_path, dest_path)
            
            # The path relative to the git repo root
            git_file_path = f"f1Info/{file_name}"
            
            status = subprocess.check_output(["git", "status", "--porcelain", git_file_path], cwd=repo_path).decode("utf-8").strip()
            if status:
                print(f"Changes detected in {git_file_path}. Uploading to GitHub...")
                subprocess.run(["git", "add", git_file_path], cwd=repo_path, check=True)
                subprocess.run(["git", "commit", "-m", f"Automated update for {git_file_path}"], cwd=repo_path, check=True)
                subprocess.run(["git", "push"], cwd=repo_path, check=True)
                print(f"Uploaded {git_file_path} to GitHub successfully.")
            else:
                print(f"No changes in {git_file_path}. Skipped GitHub upload.")
        except Exception as e:
            print(f"Error during tarasF1Data GitHub upload: {e}")
    else:
        print(f"Repo path {repo_path} not found. Skipped tarasF1Data GitHub upload.")

    # Main Workspace GitHub Upload (m:\taras)
    workspace_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    try:
        file_name = os.path.basename(out_path)
        git_file_path = f"f1Info/{file_name}"
        
        # Sync with remote first
        subprocess.run(["git", "pull", "--rebase"], cwd=workspace_path, check=True)
        
        status = subprocess.check_output(["git", "status", "--porcelain", git_file_path], cwd=workspace_path).decode("utf-8").strip()
        if status:
            print(f"Changes detected in {git_file_path} (workspace). Uploading to GitHub...")
            subprocess.run(["git", "add", git_file_path], cwd=workspace_path, check=True)
            subprocess.run(["git", "commit", "-m", f"Automated update for {git_file_path}"], cwd=workspace_path, check=True)
            subprocess.run(["git", "push"], cwd=workspace_path, check=True)
            print(f"Uploaded {git_file_path} to workspace GitHub successfully.")
        else:
            print(f"No changes in {git_file_path} (workspace). Skipped GitHub upload.")
    except Exception as e:
        print(f"Error during workspace GitHub upload: {e}")

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
