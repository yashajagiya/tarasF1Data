import json
import os
import shutil
import subprocess
from datetime import date, datetime
import requests
from bs4 import BeautifulSoup

def scrape_f1_sprint_race(url, output_file='sprint_race_result.json', circuit_id=None, event_info=None):
    print(f"Fetching data from {url}...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    # We add a try-except to handle potential connection errors
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        html_content = response.text
    except Exception as e:
        print(f"Error fetching the URL: {e}")
        if event_info:
            print("Using fallback event metadata from schedule.")
            country_name = event_info.get('f1siteracename', 'Unknown').replace('-', ' ').title()
            scraped_data = {
                "country": country_name,
                "session": "SPRINT",
                "raceName": event_info.get('raceName', 'Unknown Race').upper(),
                "date": event_info.get('raceDate', 'Unknown Date'),
                "circuitName": event_info.get('circuit', {}).get('circuitName', 'Unknown Circuit'),
                "circuitId": circuit_id or event_info.get('circuit', {}).get('circuitId', 'unknown'),
                "results": []
            }
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(scraped_data, f, indent=4, ensure_ascii=False)
            print(f"Fallback data successfully saved to '{output_file}'!")
            return True
        print("Please ensure the URL is accessible or provide a local HTML file.")
        return False

    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 1. Extract Race Name / Session
    # Looking for the main H1 tag
    h1_tag = soup.find('h1')
    full_title = h1_tag.get_text(strip=True) if h1_tag else ""
    
    # Example: "FORMULA 1 MOËT & CHANDON BELGIAN GRAND PRIX 2026 - SPRINT"
    parts = full_title.split('-')
    race_name = parts[0].strip() if len(parts) > 0 and parts[0].strip() else ""
    session = parts[-1].strip() if len(parts) > 1 and parts[-1].strip() else "SPRINT"
    if not race_name and event_info and event_info.get('raceName'):
        race_name = event_info.get('raceName')
        
    # Extract Country Name from URL
    url_parts = url.split('/')
    country_name = "Unknown"
    if 'races' in url_parts:
        try:
            races_index = url_parts.index('races')
            # The country name is usually 2 positions after 'races' in the URL 
            country_name = url_parts[races_index + 2].replace('-', ' ').title()
        except Exception:
            pass
    if country_name == "Unknown" and event_info and event_info.get('f1siteracename'):
        country_name = event_info.get('f1siteracename').replace('-', ' ').title()

    # 2. Extract Date and Circuit Name
    date_text = ""
    circuit_name = ""
    
    if h1_tag:
        # The date and circuit name are typically the first two paragraph tags after the main heading
        p_siblings = h1_tag.find_all_next('p')
        if len(p_siblings) >= 2:
            date_text = p_siblings[0].get_text(strip=True)
            circuit_name = p_siblings[1].get_text(strip=True)

    if not date_text and event_info and event_info.get('raceDate'):
        date_text = event_info.get('raceDate')
    if not circuit_name and event_info and event_info.get('circuit', {}).get('circuitName'):
        circuit_name = event_info.get('circuit', {}).get('circuitName')

    # 3. Extract Table Data
    table = soup.find('table', class_=lambda c: c and 'Table-module_table' in c)
    results = []
    
    if table:
        tbody = table.find('tbody')
        if tbody:
            rows = tbody.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                # A sprint race result table usually has 7 columns: Pos, No, Driver, Team, Laps, Time / Retired, Pts.
                if len(cols) >= 7:
                    position = cols[0].get_text(strip=True)
                    driver_number = cols[1].get_text(strip=True)
                    
                    # Extract Driver Name cleanly (skipping the TLA like 'VER' at the end)
                    driver_col = cols[2]
                    driver_name = ""
                    # The name is often split into first and last name spans
                    spans = driver_col.find_all('span', class_=lambda c: c and ('max-lg:hidden' in c or 'max-md:hidden' in c))
                    if len(spans) >= 2:
                        driver_name = f"{spans[0].get_text(strip=True)} {spans[1].get_text(strip=True)}"
                    else:
                        # Fallback if the spans aren't structured exactly like that
                        driver_name = driver_col.get_text(strip=True)
                        
                    team = cols[3].get_text(strip=True)
                    laps = cols[4].get_text(strip=True)
                    time_or_retired = cols[5].get_text(strip=True)
                    pts = cols[6].get_text(strip=True)
                    
                    results.append({
                        "position": position,
                        "driverNumber": driver_number,
                        "driverName": driver_name,
                        "team": team,
                        "laps": laps,
                        "timeOrRetired": time_or_retired,
                        "points": pts
                    })

    if len(results) == 0:
        print(f"No sprint race results available yet at {url} (session may not have concluded or results are not yet published). Saving session details with empty results.")


    scraped_data = {
        "country": country_name,
        "session": session,
        "raceName": race_name,
        "date": date_text,
        "circuitName": circuit_name,
        "circuitId": circuit_id if circuit_id else "unknown",
        "results": results
    }

    # Save to JSON file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(scraped_data, f, indent=4, ensure_ascii=False)
        
    print(f"Successfully scraped {len(results)} drivers!")
    print(f"Data saved to {output_file}")
    return True

def get_dynamic_url(schedule_file='schedule.json', target_date=None):
    """
    Dynamically builds the sprint-results URL by checking schedule.json.
    Only returns a URL if the race weekend has a sprint (sprintRace date is not null).
    Finds the active race weekend's sprint or the most recent sprint race session on or before target_date.
    """
    if target_date is None:
        target_date = date.today().isoformat()
        
    script_dir = os.path.dirname(os.path.abspath(__file__))
    schedule_path = os.path.join(script_dir, schedule_file)
        
    try:
        with open(schedule_path, 'r', encoding='utf-8') as f:
            schedule = json.load(f)
        
        # 1. Check for active race weekend having Sprint Race
        for event in schedule:
            sched = event.get('schedule', {})
            sprint_race_date = sched.get('sprintRace', {}).get('date')
            race_info = sched.get('race')
            race_date = race_info.get('date') if race_info else None
            session_dates = [v.get('date') for v in sched.values() if isinstance(v, dict) and v.get('date')]
            if session_dates and race_date and sprint_race_date:
                min_date = min(session_dates)
                if min_date <= target_date <= race_date:
                    event_id = event.get('id')
                    circuit_id = event.get('circuit', {}).get('circuitId', 'unknown')
                    country_name = event.get('f1siteracename', 'unknown')
                    url = f"https://www.formula1.com/en/results/2026/races/{event_id}/sprint-results"
                    print(f"Found active race weekend Sprint Race session ({sprint_race_date}): {url}")
                    return url, circuit_id, event

        # 2. Otherwise find the most recent sprint race session that is on or before target_date
        best_match = None
        best_date = None
        
        for event in schedule:
            sprint_race_date = event.get('schedule', {}).get('sprintRace', {}).get('date')
            
            # Skip events that don't have a sprint (sprintRace date is null)
            if not sprint_race_date:
                continue
                
            if sprint_race_date <= target_date:
                if best_date is None or sprint_race_date > best_date:
                    best_date = sprint_race_date
                    best_match = event
        
        if best_match:
            event_id = best_match.get('id')
            circuit_id = best_match.get('circuit', {}).get('circuitId', 'unknown')
            country_name = best_match.get('f1siteracename', 'unknown')
            url = f"https://www.formula1.com/en/results/2026/races/{event_id}/sprint-results"
            print(f"Found latest Sprint Race session ({best_date}): {url}")
            print(f"  Race: {best_match.get('raceName')}")
            print(f"  Country: {country_name}")
            return url, circuit_id, best_match
                
        print(f"No Sprint Race session found on or before: {target_date}")
        print("(Only sprint weekends have sprint races - most races don't have sprints)")
        return None, None, None
        
    except FileNotFoundError:
        print(f"Error: {schedule_path} not found.")
        return None, None, None

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

def push_to_git(practice_num):
    target_repo = find_target_repo(__file__)
    if not target_repo or not os.path.isdir(target_repo):
        print("Error: Target git repository 'tarasF1Data' not found.")
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    source_dir = os.path.dirname(script_dir) # e.g., .../sprint-race
    target_dir = os.path.join(target_repo, practice_num)
    
    print(f"Syncing to Git repository: {target_repo}")
    
    # 0. Pull latest changes first
    try:
        subprocess.run(["git", "pull", "--rebase", "--autostash", "origin", "main"], cwd=target_repo, check=False)
    except Exception:
        pass

    # 1. Copy the directory to tarasF1Data if not already in target_repo
    if os.path.abspath(source_dir) != os.path.abspath(target_dir):
        shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)
    
    # 2. Also ensure root workspace has the directory updated
    parent_dir = os.path.dirname(target_repo)
    parent_practice_dir = os.path.join(parent_dir, practice_num)
    if os.path.isdir(parent_practice_dir) and os.path.abspath(parent_practice_dir) != os.path.abspath(target_dir):
        shutil.copytree(target_dir, parent_practice_dir, dirs_exist_ok=True)
    
    # 3. Run git commands
    try:
        subprocess.run(["git", "add", practice_num], cwd=target_repo, check=True)
        
        # Check if there are any changes staged for commit
        result = subprocess.run(["git", "diff", "--cached", "--quiet", practice_num], cwd=target_repo, capture_output=True)
        if result.returncode != 0:
            commit_msg = f"Auto-update {practice_num} JSON data — {now}"
            subprocess.run(["git", "commit", "-m", commit_msg], cwd=target_repo, check=True)
            print(f"Committed changes: {commit_msg}")
        else:
            commit_msg = f"Auto-update {practice_num} JSON data (verified) — {now}"
            subprocess.run(["git", "commit", "--allow-empty", "-m", commit_msg], cwd=target_repo, check=True)
            print(f"Committed (no data changes): {commit_msg}")
            
        push_res = subprocess.run(["git", "push", "origin", "main"], cwd=target_repo, capture_output=True, text=True)
        if push_res.returncode == 0:
            print("Successfully pushed to GitHub!")
        else:
            subprocess.run(["git", "pull", "--rebase", "--autostash", "origin", "main"], cwd=target_repo, check=False)
            retry = subprocess.run(["git", "push", "origin", "main"], cwd=target_repo, capture_output=True, text=True)
            if retry.returncode == 0:
                print("Successfully pushed to GitHub on retry!")
            else:
                print(f"Error during git push: {retry.stderr or retry.stdout}")
    except subprocess.CalledProcessError as e:
        print(f"Error during git push: {e}")

if __name__ == "__main__":
    target_date = None  # Uses today's date automatically to find the correct event
    url, circuit_id, event = get_dynamic_url(schedule_file='schedule.json', target_date=target_date)
    
    if url:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_file = os.path.join(os.path.dirname(script_dir), 'sprint_race_result.json')
        success = scrape_f1_sprint_race(url, output_file, circuit_id=circuit_id, event_info=event)
        # Push to github automatically if scraping succeeded
        if success:
            push_to_git('sprint-race')
    else:
        print("No sprint race data to scrape for the current race weekend.")
