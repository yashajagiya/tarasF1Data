import json
import os
import shutil
import subprocess
from datetime import date
import requests
from bs4 import BeautifulSoup

def scrape_f1_qualifying(url, output_file='qualifying_results.json'):
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
        print("Please ensure the URL is accessible or provide a local HTML file.")
        return

    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 1. Extract Race Name / Session
    # Looking for the main H1 tag
    h1_tag = soup.find('h1')
    full_title = h1_tag.get_text(strip=True) if h1_tag else ""
    
    # Example: "FORMULA 1 MOËT & CHANDON BELGIAN GRAND PRIX 2026 - QUALIFYING"
    parts = full_title.split('-')
    race_name = parts[0].strip() if len(parts) > 0 else full_title
    session = parts[-1].strip() if len(parts) > 1 else ""
    
    # Extract Country Name from URL
    url_parts = url.split('/')
    country_name = "Unknown"
    if 'races' in url_parts:
        try:
            races_index = url_parts.index('races')
            # The country name is usually 2 positions after 'races' in the URL 
            country_name = url_parts[races_index + 2].capitalize()
        except Exception:
            pass

    # 2. Extract Date and Circuit Name
    date_text = ""
    circuit_name = ""
    
    if h1_tag:
        # The date and circuit name are typically the first two paragraph tags after the main heading
        p_siblings = h1_tag.find_all_next('p')
        if len(p_siblings) >= 2:
            date_text = p_siblings[0].get_text(strip=True)
            circuit_name = p_siblings[1].get_text(strip=True)

    # 3. Extract Table Data
    table = soup.find('table', class_=lambda c: c and 'Table-module_table' in c)
    results = []
    
    if table:
        tbody = table.find('tbody')
        if tbody:
            rows = tbody.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                # A full qualifying table usually has 8 columns: Pos, No, Driver, Team, Q1, Q2, Q3, Laps
                if len(cols) >= 8:
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
                    q1 = cols[4].get_text(strip=True)
                    q2 = cols[5].get_text(strip=True)
                    q3 = cols[6].get_text(strip=True)
                    laps = cols[7].get_text(strip=True)
                    
                    results.append({
                        "position": position,
                        "driverNumber": driver_number,
                        "driverName": driver_name,
                        "team": team,
                        "q1": q1,
                        "q2": q2,
                        "q3": q3,
                        "laps": laps
                    })

    # Prepare final JSON structure
    scraped_data = {
        "country": country_name,
        "session": session,
        "raceName": race_name,
        "date": date_text,
        "circuitName": circuit_name,
        "results": results
    }

    # Save to JSON file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(scraped_data, f, indent=4, ensure_ascii=False)
        
    print(f"Successfully scraped {len(results)} drivers!")
    print(f"Data saved to {output_file}")

def get_dynamic_url(schedule_file='schedule.json', target_date=None):
    if target_date is None:
        target_date = date.today().isoformat()
        
    script_dir = os.path.dirname(os.path.abspath(__file__))
    schedule_path = os.path.join(script_dir, schedule_file)
        
    try:
        with open(schedule_path, 'r', encoding='utf-8') as f:
            schedule = json.load(f)
            
        for event in schedule:
            qualy_date = event.get('schedule', {}).get('qualy', {}).get('date')
            if qualy_date == target_date:
                event_id = event.get('id')
                url = f"https://www.formula1.com/en/results/2026/races/{event_id}/qualifying"
                print(f"Found event for {target_date}: {url}")
                return url
                
        print(f"No Qualifying session found for date: {target_date}")
        return None
        
    except FileNotFoundError:
        print(f"Error: {schedule_path} not found.")
        return None

def push_to_git(practice_num):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    source_dir = os.path.dirname(script_dir) # e.g., m:\taras\qualifying
    target_repo = os.path.join(os.path.dirname(source_dir), 'tarasF1Data')
    target_dir = os.path.join(target_repo, practice_num)
    
    print(f"Syncing to Git repository: {target_repo}")
    
    # 0. Pull latest changes first
    try:
        subprocess.run(["git", "pull", "--rebase", "origin", "main"], cwd=target_repo, check=True)
    except subprocess.CalledProcessError:
        pass # Ignore if it fails due to no remote or other issues, will catch push errors later

    # 1. Copy the directory to tarasF1Data
    shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)
    
    # 2. Run git commands
    try:
        subprocess.run(["git", "add", practice_num], cwd=target_repo, check=True)
        subprocess.run(["git", "commit", "-m", f"Auto-update {practice_num} JSON data"], cwd=target_repo)
        subprocess.run(["git", "push", "origin", "main"], cwd=target_repo, check=True)
        print("Successfully pushed to GitHub!")
    except subprocess.CalledProcessError as e:
        print(f"Error during git push: {e}")

if __name__ == "__main__":
    target_date = "2026-07-18"  # Hardcoded for Belgium Qualifying test as per your data, change to None for today
    url = get_dynamic_url(schedule_file='schedule.json', target_date=target_date)
    
    if url:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_file = os.path.join(os.path.dirname(script_dir), 'qualifying_results.json')
        scrape_f1_qualifying(url, output_file)
        # Push to github automatically
        push_to_git('qualifying')
