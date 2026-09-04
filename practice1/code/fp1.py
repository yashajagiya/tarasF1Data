import json
import os
import shutil
import subprocess
import urllib.request
from datetime import date, datetime
from bs4 import BeautifulSoup

def extract_fp1_data(url, output_file='fp1_extracted.json', circuit_id=None, event_info=None):
    print(f"Fetching data from {url}...\n")
    
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8')
    except Exception as e:
        print(f"Error fetching data from {url}: {e}")
        if event_info:
            print("Using fallback event metadata from schedule.")
            extracted_data = {
                "raceName": f"{event_info.get('raceName', 'Unknown Race')} - PRACTICE 1".upper(),
                "raceDate": event_info.get('raceDate', 'Unknown Date'),
                "circuitName": event_info.get('circuit', {}).get('circuitName', 'Unknown Circuit'),
                "circuitId": circuit_id or event_info.get('circuit', {}).get('circuitId', 'unknown'),
                "results": []
            }
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(extracted_data, f, indent=4, ensure_ascii=False)
            print(f"Fallback data successfully saved to '{output_file}'!")
            return True
        return False

    soup = BeautifulSoup(html, 'html.parser')
    
    extracted_data = {}
    
    # Extract Race Name
    h1 = soup.find('h1')
    if h1:
        extracted_data['raceName'] = h1.text.strip()
    elif event_info and event_info.get('raceName'):
        extracted_data['raceName'] = f"{event_info.get('raceName')} - PRACTICE 1".upper()
    else:
        extracted_data['raceName'] = 'Unknown Race'
    
    # Extract Race Date and Circuit
    date_p = soup.find('p', class_='typography-module_display-s-bold__Vxu9c')
    if date_p:
        extracted_data['raceDate'] = date_p.text.strip()
    elif event_info and event_info.get('raceDate'):
        extracted_data['raceDate'] = event_info.get('raceDate')
    else:
        extracted_data['raceDate'] = 'Unknown Date'
    
    circuit_p = soup.find('p', class_='typography-module_body-xs-semibold__Fyfwn')
    if circuit_p:
        extracted_data['circuitName'] = circuit_p.text.strip()
    elif event_info and event_info.get('circuit', {}).get('circuitName'):
        extracted_data['circuitName'] = event_info.get('circuit', {}).get('circuitName')
    else:
        extracted_data['circuitName'] = 'Unknown Circuit'
    
    if circuit_id:
        extracted_data['circuitId'] = circuit_id
    elif event_info and event_info.get('circuit', {}).get('circuitId'):
        extracted_data['circuitId'] = event_info.get('circuit', {}).get('circuitId')
    
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

    if len(extracted_data['results']) == 0:
        print(f"No FP1 results available yet at {url} (session may not have concluded or results are not yet published). Saving session details with empty results.")
                
    # Save to JSON file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(extracted_data, f, indent=4, ensure_ascii=False)
        
    print(f"Extracted data successfully saved to '{output_file}'!")
    return True

def get_dynamic_url(schedule_file='schedule.json', target_date=None):
    if target_date is None:
        target_date = date.today().isoformat()
        
    script_dir = os.path.dirname(os.path.abspath(__file__))
    schedule_path = os.path.join(script_dir, schedule_file)
        
    try:
        with open(schedule_path, 'r', encoding='utf-8') as f:
            schedule = json.load(f)
        
        # Find the most recent session that is on or before target_date
        best_match = None
        best_date = None
        
        for event in schedule:
            fp1_date = event.get('schedule', {}).get('fp1', {}).get('date')
            if fp1_date and fp1_date <= target_date:
                if best_date is None or fp1_date > best_date:
                    best_date = fp1_date
                    best_match = event
        
        if best_match:
            event_id = best_match.get('id')
            circuit_id = best_match.get('circuit', {}).get('circuitId', 'unknown')
            url = f"https://www.formula1.com/en/results/2026/races/{event_id}/practice/1"
            print(f"Found latest FP1 session ({best_date}): {url}")
            return url, circuit_id, best_match
                
        print(f"No FP1 session found on or before: {target_date}")
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
    source_dir = os.path.dirname(script_dir) # e.g., .../practice1
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
    url, circuit_id, event_info = get_dynamic_url(schedule_file='schedule.json', target_date=target_date)
    
    if url:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_file = os.path.join(os.path.dirname(script_dir), 'fp1_extracted.json')
        success = extract_fp1_data(url, output_file, circuit_id=circuit_id, event_info=event_info)
        # Push to github automatically if extraction succeeded
        if success:
            push_to_git('practice1')
