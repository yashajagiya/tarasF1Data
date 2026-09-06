"""
F1 2026 Driver Data Scraper
Fetches all 22 driver pages from formula1.com and extracts:
  - Hero: name, acronym, driver_id, team, country, number, team colors, cutout images, number logos
  - 2026 Season: position, points, GP/Sprint stats (16 metrics)
  - Career Stats: GP entered, points, wins, podiums, poles, championships, DNFs (8 metrics)
  - Biography: Date of Birth, Place of Birth, story paragraphs, pull quote
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

KNOWN_ACRONYMS = {
    "george-russell": "RUS",
    "kimi-antonelli": "ANT",
    "charles-leclerc": "LEC",
    "lewis-hamilton": "HAM",
    "lando-norris": "NOR",
    "oscar-piastri": "PIA",
    "max-verstappen": "VER",
    "isack-hadjar": "HAD",
    "liam-lawson": "LAW",
    "arvid-lindblad": "LIN",
    "pierre-gasly": "GAS",
    "franco-colapinto": "COL",
    "esteban-ocon": "OCO",
    "oliver-bearman": "BEA",
    "nico-hulkenberg": "HUL",
    "gabriel-bortoleto": "BOR",
    "carlos-sainz": "SAI",
    "alexander-albon": "ALB",
    "fernando-alonso": "ALO",
    "lance-stroll": "STR",
    "sergio-perez": "PER",
    "valtteri-bottas": "BOT",
}

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

    # ── Driver ID & Acronym ──────────────────────────────────────
    driver_id = None
    for a in soup.find_all("a", href=True):
        m = re.search(r'/drivers/([A-Z0-9]+)/', a['href'])
        if m:
            driver_id = m.group(1)
            break

    acronym = KNOWN_ACRONYMS.get(slug, "")
    if not acronym and driver_id and len(driver_id) >= 6:
        acronym = driver_id[3:6]

    # ── Hero Section ──────────────────────────────────────────────
    # Name from <h1>
    h1 = soup.find("h1")
    first_name, last_name = "", ""
    if h1:
        direct_spans = h1.find_all("span", recursive=False)
        texts = [s.get_text(strip=True) for s in direct_spans if s.get_text(strip=True)]
        if len(texts) >= 2:
            first_name = texts[0]
            last_name = texts[1]
        elif len(texts) == 1:
            parts = texts[0].split()
            first_name = parts[0] if parts else ""
            last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

    data["hero"]["first_name"] = first_name
    data["hero"]["last_name"] = last_name
    data["hero"]["name_acronym"] = acronym
    if driver_id:
        data["hero"]["driver_id"] = driver_id

    # Hero container with Country, Team, Number
    hero_container = soup.find(
        "div",
        class_=lambda c: c and "relative" in c and "h-full" in c,
    )
    country = ""
    team = ""
    number = ""

    if hero_container:
        semibold_ps = hero_container.find_all("p", class_=lambda c: c and "semibold" in c)
        hero_texts = [p.get_text(strip=True) for p in semibold_ps if p.get_text(strip=True)]
        if len(hero_texts) >= 3:
            country = hero_texts[0]
            team = hero_texts[1]
            number = hero_texts[2]
        elif len(hero_texts) == 2:
            team = hero_texts[0]
            number = hero_texts[1]

    # Fallback for country from Flag <title>
    if not country:
        flag_svg = soup.find("svg", class_=lambda c: c and "CountryFlag" in c)
        if flag_svg:
            title_tag = flag_svg.find("title")
            if title_tag:
                country = title_tag.get_text(strip=True).replace("Flag of ", "")

    # Fallback for team from page title: "George Russell - F1 Driver for Mercedes"
    if not team and soup.title and " - F1 Driver for " in soup.title.string:
        team = soup.title.string.split(" - F1 Driver for ")[-1].strip()

    data["hero"]["country"] = country
    data["hero"]["team"] = team
    data["hero"]["number"] = number

    # Team colors: search style attributes and HTML for CSS custom properties
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

    # HTML string regex fallback
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

    # ── Driver Image ──────────────────────────────────────────────
    driver_img = None
    for img in soup.find_all("img", src=True):
        src = img.get("src", "").lower()
        if "right.webp" in src and "/common/f1/" in src and "carright" not in src and "logo" not in src:
            driver_img = img
            break
    if not driver_img:
        clean_id = (driver_id or "").lower()
        for img in soup.find_all("img", src=True):
            src = img.get("src", "").lower()
            if clean_id and clean_id in src and "logo" not in src and "car" not in src:
                driver_img = img
                break

    if driver_img:
        data["hero"]["driver_image"] = driver_img.get("src", "")

    # ── Driver Number Logo ────────────────────────────────────────
    for div in soup.find_all(style=True):
        style = div.get("style", "")
        num_match = re.search(r'mask-image:\s*url\(["\']?(.*?numberwhite[^"\')\s]*)["\']?\)', style)
        if num_match:
            data["hero"]["driver_number_logo"] = num_match.group(1)
            break
    if "driver_number_logo" not in data["hero"]:
        num_match = re.search(r'https://media\.formula1\.com/[^"\'\s)]*?numberwhite[^"\'\s)]*\.webp', html)
        if num_match:
            data["hero"]["driver_number_logo"] = num_match.group(0)

    # ── Biography (Date of Birth, Place of Birth, Text, Quote) ────
    bio_sec = soup.find("div", id="biography")
    if not bio_sec:
        for heading in soup.find_all(["h2", "h3"]):
            if "biography" in heading.get_text(strip=True).lower():
                bio_sec = heading.find_parent("div", class_=lambda c: c and "link-target" in c) or heading.parent
                break

    if bio_sec:
        for dt in bio_sec.find_all("dt"):
            key = dt.get_text(strip=True)
            dd = dt.find_next_sibling("dd") or dt.find_next("dd")
            if dd:
                data["biography"][key] = dd.get_text(strip=True)

        ps = [
            p.get_text(strip=True) for p in bio_sec.find_all("p")
            if not p.find_parent("dl") and not p.find_parent("figure") and p.get_text(strip=True)
        ]
        if ps:
            data["biography"]["text"] = ps

    # PullQuote
    quote_fig = soup.find("figure", class_=lambda c: c and "PullQuote" in (c or ""))
    if not quote_fig:
        bq = soup.find("blockquote")
        if bq:
            quote_fig = bq.find_parent("figure") or bq
    if quote_fig:
        bq = quote_fig.find("blockquote") if quote_fig.name != "blockquote" else quote_fig
        fc = quote_fig.find("figcaption") if hasattr(quote_fig, "find") else None
        if bq:
            q_text = bq.get_text(strip=True)
            q_author = fc.get_text(strip=True) if fc else ""
            if q_text:
                data["biography"]["quote"] = {
                    "text": q_text,
                    "author": q_author
                }

    # ── Statistics – parse all <dl> data grids ────────────────────
    stats_sec = soup.find("div", id="statistics") or soup
    for heading in stats_sec.find_all(["h2", "h3"]):
        heading_text = heading.get_text(strip=True).upper()
        parent = heading.find_parent("div", class_=lambda c: c and "flex" in c) or heading.parent
        dls = parent.find_all("dl") if parent else []

        for dl in dls:
            items = dl.find_all("div", class_=lambda c: c and "item" in c)
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
                elif "CAREER" in heading_text:
                    data["career_stats"][key] = val

    # Fallback if statistics were missed
    if not data["season_2026"] and not data["career_stats"]:
        for dl in soup.find_all("dl"):
            for dt, dd in zip(dl.find_all("dt"), dl.find_all("dd")):
                key = dt.get_text(strip=True)
                val = dd.get_text(strip=True)
                if key in ["Grands Prix Entered", "Career Points", "Highest Race Finish", "Podiums", "Highest Grid Position", "Pole Positions", "World Championships"]:
                    data["career_stats"][key] = val
                else:
                    data["season_2026"][key] = val

    return data


def scrape_all_drivers() -> list:
    """Fetch and parse all 22 driver pages with connection pooling and retries."""
    all_drivers = []
    total = len(DRIVER_SLUGS)

    session = requests.Session()
    session.headers.update(HEADERS)

    for i, slug in enumerate(DRIVER_SLUGS, 1):
        url = BASE_URL + slug
        print(f"[{i:2d}/{total}] Fetching {slug}...", end=" ", flush=True)

        driver_data = None
        last_error = None

        for attempt in range(1, 4):
            try:
                resp = session.get(url, timeout=25)
                resp.encoding = "utf-8"
                resp.raise_for_status()
                driver_data = parse_driver_page(resp.text, slug)
                break
            except requests.RequestException as e:
                last_error = e
                if attempt < 3:
                    time.sleep(2 * attempt)

        if driver_data:
            all_drivers.append(driver_data)
            hero = driver_data.get("hero", {})
            name = f"{hero.get('first_name', '?')} {hero.get('last_name', '?')}"
            acronym = hero.get("name_acronym", "")
            team = hero.get("team", "?")
            num = hero.get("number", "?")
            print(f"OK  {name:<22} ({acronym}) | #{num:<2} | {team}")
        else:
            print(f"FAIL  ERROR: {last_error}")
            all_drivers.append({"slug": slug, "url": url, "error": str(last_error)})

        # Polite delay between requests
        if i < total:
            time.sleep(1.5)

    return all_drivers


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


def push_f1info_to_git(out_path, info_type="drivers"):
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

    # Also sync to root workspace drivers_data.json if it exists
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
    print("  F1 2026 Driver Data Scraper")
    print("=" * 60)
    print()

    drivers = scrape_all_drivers()

    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'drivers_data.json'))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(drivers, f, indent=2, ensure_ascii=False)

    print()
    print(f"Done! Saved {len(drivers)} drivers to {out_path}")

    # GitHub Upload & sync
    push_f1info_to_git(out_path, info_type="drivers")

    # Quick summary
    print()
    print("-" * 65)
    print(f"{'#':<4} {'Driver':<23} {'TLA':<5} {'Team':<20} {'Num':<5}")
    print("-" * 65)
    for i, d in enumerate(drivers, 1):
        hero = d.get("hero", {})
        name = f"{hero.get('first_name', '?')} {hero.get('last_name', '?')}"
        tla = hero.get("name_acronym", "?")
        team = hero.get("team", "?")
        num = hero.get("number", "?")
        print(f"{i:<4} {name:<23} {tla:<5} {team:<20} {num:<5}")
    print("-" * 65)


if __name__ == "__main__":
    main()
