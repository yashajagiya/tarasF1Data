"""
F1 2026 Driver Data Scraper
Fetches all 22 driver pages from formula1.com and extracts:
  - Hero: name, team, country, number, team colors, images
  - 2026 Season: position, points, GP/Sprint stats
  - Career Stats: GP entered, points, wins, podiums, poles, championships, DNFs
Outputs: drivers_data.json
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

DRIVER_SLUGS = [
    "george-russell",
    "kimi-antonelli",
    "charles-leclerc",
    "lewis-hamilton",
    "lando-norris",
    "oscar-piastri",
    "max-verstappen",
    "isack-hadjar",
    "liam-lawson",
    "arvid-lindblad",
    "pierre-gasly",
    "franco-colapinto",
    "esteban-ocon",
    "oliver-bearman",
    "nico-hulkenberg",
    "gabriel-bortoleto",
    "carlos-sainz",
    "alexander-albon",
    "fernando-alonso",
    "lance-stroll",
    "sergio-perez",
    "valtteri-bottas",
]

BASE_URL = "https://www.formula1.com/en/drivers/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def parse_driver_page(html: str, slug: str) -> dict:
    """Parse a single driver detail page and return structured data."""
    soup = BeautifulSoup(html, "html.parser")
    data = {
        "slug": slug,
        "url": BASE_URL + slug,
        "hero": {},
        "biography": {},
        "season_2026": {},
        "career_stats": {},
    }

    # ── Hero Section ──────────────────────────────────────────────
    # Name from <h1> — direct children only to avoid nested span duplicates
    h1 = soup.find("h1")
    if h1:
        direct_children = h1.find_all("span", recursive=False)
        texts = []
        for child in direct_children:
            t = child.get_text(strip=True)
            if t:
                texts.append(t)
        if len(texts) >= 2:
            data["hero"]["first_name"] = texts[0]
            data["hero"]["last_name"] = texts[1]
        elif len(texts) == 1:
            parts = texts[0].split()
            data["hero"]["first_name"] = parts[0] if parts else ""
            data["hero"]["last_name"] = " ".join(parts[1:]) if len(parts) > 1 else ""

    # Country – look for the Flag <title> or the text next to it
    flag_svg = soup.find("svg", class_=lambda c: c and "CountryFlag" in c)
    if flag_svg:
        title_tag = flag_svg.find("title")
        if title_tag:
            flag_text = title_tag.get_text(strip=True)
            # "Flag of Finland" → "Finland"
            data["hero"]["country"] = flag_text.replace("Flag of ", "")

    # Team & Number from the hero subtitle area
    # They sit in <p> tags with semibold classes near the flag
    hero_container = soup.find(
        "div",
        class_=lambda c: c and "relative" in c and "h-full" in c,
    )
    if hero_container:
        semibold_ps = hero_container.find_all(
            "p",
            class_=lambda c: c and "semibold" in c,
        )
        # Typically: [country_text, team_name, number]
        hero_texts = [p.get_text(strip=True) for p in semibold_ps]
        if len(hero_texts) >= 3:
            data["hero"]["team"] = hero_texts[1]
            data["hero"]["number"] = hero_texts[2]
        elif len(hero_texts) == 2:
            data["hero"]["team"] = hero_texts[0]
            data["hero"]["number"] = hero_texts[1]

    # Team colors from the hero wrapper's CSS custom properties
    hero_wrapper = soup.find(
        "div",
        class_=lambda c: c and "overflow-clip" in c and "bg-[--f1-team-colour]" in c,
    )
    if not hero_wrapper:
        # fallback: look for inline style with --f1-team-colour
        for div in soup.find_all("div", style=True):
            style = div.get("style", "")
            if "--f1-team-colour" in style:
                hero_wrapper = div
                break

    # Parse team colours from parent containers with style attributes
    for div in soup.find_all("div", style=True):
        style = div.get("style", "")
        tc_match = re.search(r"--f1-team-colour:\s*(#[0-9a-fA-F]{3,8})", style)
        ac_match = re.search(r"--f1-accessible-colour:\s*(#[0-9a-fA-F]{3,8})", style)
        if tc_match:
            data["hero"]["team_color"] = tc_match.group(1)
        if ac_match:
            data["hero"]["accessible_color"] = ac_match.group(1)
        if tc_match or ac_match:
            break

    # ── Biography (Date of Birth, Place of Birth, Text, Quote) ────
    for heading in soup.find_all(["h2", "h3"]):
        if "biography" in heading.get_text(strip=True).lower():
            curr = heading
            bio_container = None
            while curr and curr.name != "body":
                if curr.find("dl") and len(curr.find_all("p")) > 2:
                    bio_container = curr
                    break
                curr = curr.parent

            if bio_container:
                for dt in bio_container.find_all("dt"):
                    key = dt.get_text(strip=True)
                    dd = dt.find_next_sibling("dd") or dt.find_next("dd")
                    if dd:
                        data["biography"][key] = dd.get_text(strip=True)
                
                ps = [p.get_text(strip=True) for p in bio_container.find_all("p") if not p.find_parent("dl") and p.get_text(strip=True)]
                if ps:
                    data["biography"]["text"] = ps
            break

    quote_fig = soup.find("figure", class_=lambda c: c and "PullQuote" in (c or ""))
    if not quote_fig:
        bq = soup.find("blockquote")
        if bq:
            quote_fig = bq.find_parent("figure")
    if quote_fig:
        bq = quote_fig.find("blockquote")
        fc = quote_fig.find("figcaption")
        if bq and fc:
            data["biography"]["quote"] = {
                "text": bq.get_text(strip=True),
                "author": fc.get_text(strip=True)
            }

    # ── Statistics – parse all <dl> data grids ────────────────────
    all_sections = soup.find_all("h3")
    for heading in all_sections:
        heading_text = heading.get_text(strip=True).upper()

        # Find the next <dl> siblings/cousins
        parent = heading.find_parent("div", class_=lambda c: c and "flex" in c)
        if not parent:
            parent = heading.parent

        dls = parent.find_all("dl") if parent else []

        for dl in dls:
            items = dl.find_all("div", class_=lambda c: c and "item" in c)
            for item in items:
                dt = item.find("dt")
                dd = item.find("dd")
                if dt and dd:
                    key = dt.get_text(strip=True)
                    value = dd.get_text(strip=True)

                    if "SEASON" in heading_text or "2026" in heading_text:
                        data["season_2026"][key] = value
                    elif "CAREER" in heading_text:
                        data["career_stats"][key] = value

    # ── Fallback: if sections missed, grab ALL dt/dd pairs ────────
    if not data["season_2026"] and not data["career_stats"]:
        all_dls = soup.find_all("dl")
        for dl in all_dls:
            items = dl.find_all("div", class_=lambda c: c and "item" in (c or ""))
            if not items:
                # try direct dt/dd pairs
                dts = dl.find_all("dt")
                dds = dl.find_all("dd")
                for dt_tag, dd_tag in zip(dts, dds):
                    key = dt_tag.get_text(strip=True)
                    val = dd_tag.get_text(strip=True)
                    data["season_2026"][key] = val
            else:
                for item in items:
                    dt = item.find("dt")
                    dd = item.find("dd")
                    if dt and dd:
                        data["season_2026"][dt.get_text(strip=True)] = dd.get_text(strip=True)

    return data


def scrape_all_drivers() -> list:
    """Fetch and parse all 22 driver pages."""
    all_drivers = []
    total = len(DRIVER_SLUGS)

    for i, slug in enumerate(DRIVER_SLUGS, 1):
        url = BASE_URL + slug
        print(f"[{i}/{total}] Fetching {slug}...", end=" ", flush=True)

        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            driver_data = parse_driver_page(resp.text, slug)
            all_drivers.append(driver_data)
            print(
                f"OK  {driver_data['hero'].get('first_name', '?')} "
                f"{driver_data['hero'].get('last_name', '?')} - "
                f"{driver_data['hero'].get('team', '?')}"
            )
        except requests.RequestException as e:
            print(f"FAIL  ERROR: {e}")
            all_drivers.append({"slug": slug, "url": url, "error": str(e)})

        # Be polite – 1.5 s between requests
        if i < total:
            time.sleep(5)

    return all_drivers


def main():
    print("=" * 60)
    print("  F1 2026 Driver Data Scraper")
    print("=" * 60)
    print()

    drivers = scrape_all_drivers()

    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'drivers_data.json'))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(drivers, f, indent=2, ensure_ascii=False)

    print()
    print(f"Done! Saved {len(drivers)} drivers to {out_path}")

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
    print(f"{'#':<4} {'Driver':<25} {'Team':<20} {'Num':<5}")
    print("-" * 60)
    for i, d in enumerate(drivers, 1):
        hero = d.get("hero", {})
        name = f"{hero.get('first_name', '?')} {hero.get('last_name', '?')}"
        team = hero.get("team", "?")
        num = hero.get("number", "?")
        print(f"{i:<4} {name:<25} {team:<20} {num:<5}")
    print("-" * 60)


if __name__ == "__main__":
    main()
