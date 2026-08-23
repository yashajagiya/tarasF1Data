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
import shutil
import subprocess
from datetime import datetime

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
            hex_color = tc_match.group(1).lstrip("#")
            if len(hex_color) == 3:
                hex_color = "".join(c * 2 for c in hex_color)
            data["hero"]["team_color"] = f"0xFF{hex_color.upper()}"
        if ac_match:
            data["hero"]["accessible_color"] = ac_match.group(1)
        if tc_match or ac_match:
            break

    # ── Driver Image ──────────────────────────────────────────────
    # Look for <img> whose src contains the driver's slug identifier + "right.webp"
    # e.g. "2026mercedesgeorus01right.webp" for george-russell
    driver_img = None
    for img in soup.find_all("img", src=True):
        src = img.get("src", "").lower()
        if "right.webp" in src and "/common/f1/" in src and "carright" not in src and "logo" not in src:
            driver_img = img
            break
    if driver_img:
        data["hero"]["driver_image"] = driver_img.get("src", "")

    # ── Driver Number Logo ────────────────────────────────────────
    # The number logo is set via mask-image CSS on a <div> with "numberwhite" in the URL
    for div in soup.find_all("div", style=True):
        style = div.get("style", "")
        num_match = re.search(r'mask-image:\s*url\(["\']?(.*?numberwhite[^"\')\s]*)["\']?\)', style)
        if num_match:
            data["hero"]["driver_number_logo"] = num_match.group(1)
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

def find_target_repo(script_path):
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


def push_f1info_to_git(out_path, info_type="driver"):
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
    push_f1info_to_git(out_path, info_type="drivers")

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
