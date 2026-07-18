import json
import urllib.request
from bs4 import BeautifulSoup

def extract_fp1_data(url, output_file='fp1_extracted.json'):
    print(f"Fetching data from {url}...\n")
    
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8')
    except Exception as e:
        print(f"Error fetching data: {e}")
        return

    soup = BeautifulSoup(html, 'html.parser')
    
    extracted_data = {}
    
    # Extract Race Name
    h1 = soup.find('h1')
    extracted_data['raceName'] = h1.text.strip() if h1 else 'Unknown Race'
    
    # Extract Race Date and Circuit
    # Targeting the general display classes to extract date and circuit since they don't have unique IDs
    date_p = soup.find('p', class_='typography-module_display-s-bold__Vxu9c')
    extracted_data['raceDate'] = date_p.text.strip() if date_p else 'Unknown Date'
    
    circuit_p = soup.find('p', class_='typography-module_body-xs-semibold__Fyfwn')
    extracted_data['circuitName'] = circuit_p.text.strip() if circuit_p else 'Unknown Circuit'
    
    extracted_data['results'] = []
    
    # Extract table rows
    tbody = soup.find('tbody', class_='Table-module_tbody__KEiSx')
    if tbody:
        for row in tbody.find_all('tr'):
            cols = row.find_all('td')
            if len(cols) >= 6:
                # Driver name extraction
                driver_cell = cols[2]
                first_name_span = driver_cell.find('span', class_='max-lg:hidden')
                last_name_span = driver_cell.find('span', class_='max-md:hidden')
                short_name_span = driver_cell.find('span', class_='md:hidden')
                
                first_name = first_name_span.text.strip() if first_name_span else ''
                last_name = last_name_span.text.strip() if last_name_span else ''
                short_name = short_name_span.text.strip() if short_name_span else ''
                
                full_name = f"{first_name} {last_name}".strip()
                if not full_name:
                     # Fallback if specific spans aren't found
                     full_name = driver_cell.text.strip().replace('\xa0', ' ')
                
                team_cell = cols[3]
                team_logo = team_cell.find('span', class_='TeamLogo-module_teamlogo__lA3j1')
                # Remove logo text if it exists inside the cell to only get the team name
                team_name = team_cell.text.replace(team_logo.text if team_logo else '', '').strip() if team_cell else ''

                result = {
                    "position": cols[0].text.strip(),
                    "number": cols[1].text.strip(),
                    "driver": full_name,
                    "shortName": short_name,
                    "team": team_name,
                    "timeOrGap": cols[4].text.strip(),
                    "laps": cols[5].text.strip()
                }
                extracted_data['results'].append(result)
                
    # Save to JSON file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(extracted_data, f, indent=4, ensure_ascii=False)
        
    print(f"Extracted data successfully saved to '{output_file}'!")

import os
import shutil
import subprocess
from datetime import date

def get_dynamic_url(schedule_file='schedule.json', target_date=None):
    if target_date is None:
        target_date = date.today().isoformat()
        
    script_dir = os.path.dirname(os.path.abspath(__file__))
    schedule_path = os.path.join(script_dir, schedule_file)
        
    try:
        with open(schedule_path, 'r', encoding='utf-8') as f:
            schedule = json.load(f)
            
        for event in schedule:
            fp1_date = event.get('schedule', {}).get('fp1', {}).get('date')
            if fp1_date == target_date:
                event_id = event.get('id')
                url = f"https://www.formula1.com/en/results/2026/races/{event_id}/practice/1"
                print(f"Found event for {target_date}: {url}")
                return url
                
        print(f"No FP1 session found for date: {target_date}")
        return None
        
    except FileNotFoundError:
        print(f"Error: {schedule_path} not found.")
        return None

def push_to_git(practice_num):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    source_dir = os.path.dirname(script_dir) # e.g., m:\taras\practice1
    target_repo = os.path.join(os.path.dirname(source_dir), 'tarasF1Data')
    target_dir = os.path.join(target_repo, practice_num)
    
    print(f"Syncing to Git repository: {target_repo}")
    
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
    # You can change target_date to a specific date string like "2026-10-09" for Singapore
    target_date = "2026-07-17"  # Hardcoded for Belgium test as per your data, change to None for today
    url = get_dynamic_url(schedule_file='schedule.json', target_date=target_date)
    
    if url:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_file = os.path.join(os.path.dirname(script_dir), 'fp1_extracted.json')
        extract_fp1_data(url, output_file)
        # Push to github automatically
        push_to_git('practice1')
