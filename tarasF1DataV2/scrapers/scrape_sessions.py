"""
Taras F1 API v2 — Native Weekend Session Scraper
Scrapes live sessions (FP1, FP2, FP3, Qualifying, Sprint Qualy, Sprint Race, Grand Prix)
directly from official Formula 1 timing & classifications.
Saves directly into: tarasF1DataV2/data/sessions/round_{N}.json
"""

import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
V2_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
sys.path.insert(0, V2_ROOT)

from extract_rounds import extract_round_data, extract_all_rounds, load_calendar_master


def scrape_weekend_session(round_num: int, verbose: bool = True):
    """Scrape and save a complete weekend event by round number into data/sessions/"""
    return extract_round_data(round_num, verbose=verbose, export_legacy=False)


def scrape_current_weekend(verbose: bool = True):
    """Automatically find the active or latest race in calendar and scrape it."""
    calendar = load_calendar_master()
    if not calendar:
        print("⚠️ Calendar master not found!")
        return None

    # First round without a winner or the latest completed
    upcoming = [r for r in calendar if not r.get("winner")]
    target = upcoming[0] if upcoming else calendar[-1]
    round_num = target.get("round", 16)
    print(f"🏎️ Scraping current weekend event: Round {round_num} ({target.get('raceName')})...")
    return scrape_weekend_session(round_num, verbose=verbose)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        r_num = int(sys.argv[1])
        scrape_weekend_session(r_num)
    else:
        scrape_current_weekend()
