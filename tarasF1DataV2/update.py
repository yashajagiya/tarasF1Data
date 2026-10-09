"""
Taras F1 API v2 — Master Update & Deployment Pipeline
One-command orchestration to:
1. Scrape current or specified race weekend sessions from Formula 1
2. Build all V2 REST endpoints (overview, drivers, teams, standings, calendar, results)
3. Synchronize to public v2 directories for GitHub Pages
4. Run 100% data integrity & zero-loss tests
5. Auto-commit and push updates to both GitHub repositories (Taras and tarasF1Data)
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
sys.path.insert(0, BASE_DIR)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def run_pipeline(round_num=None, skip_scrape=False, skip_push=False, force=False):
    print("=" * 75)
    print("  🚀 TARAS F1 API v2 — MASTER UPDATE & DEPLOYMENT PIPELINE")
    print("=" * 75)

    # Step 1: Scrape weekend session
    if not skip_scrape:
        print("\n[Step 1/4] Scraping Formula 1 session classifications...")
        from scrapers.scrape_sessions import scrape_weekend_session, scrape_current_weekend
        if round_num:
            print(f"  • Target: Round {round_num}")
            scrape_weekend_session(round_num, verbose=True)
        else:
            print("  • Target: Auto-detecting current/upcoming race weekend...")
            scrape_current_weekend(verbose=True)
    else:
        print("\n[Step 1/4] Scraping skipped (--skip-scrape).")

    # Step 2: Build V2 API
    print("\n[Step 2/4] Building Taras F1 API v2 endpoints...")
    from build import build_v2_api
    build_v2_api()

    # Step 3: Run Data Integrity Verification
    print("\n[Step 3/4] Verifying data integrity and zero data loss...")
    from test_v2_integrity import run_integrity_tests
    run_integrity_tests()

    # Step 4: Commit and Push to GitHub
    if not skip_push:
        print("\n[Step 4/4] Committing & pushing to GitHub (Edge CDN Deployment)...")
        from build import git_commit_and_push
        git_commit_and_push(ROOT_DIR)
    else:
        print("\n[Step 4/4] Git push skipped (--no-push).")

    print("\n" + "=" * 75)
    print("  ✅ PIPELINE COMPLETE: Taras F1 API v2 is live & up to date!")
    print("=" * 75)


def parse_args():
    parser = argparse.ArgumentParser(description="Taras F1 API v2 Master Pipeline")
    parser.add_argument("--round", "-r", type=int, default=None, help="Specific round to scrape (e.g. --round 17)")
    parser.add_argument("--skip-scrape", action="store_true", help="Skip web scraping and build from current data")
    parser.add_argument("--no-push", action="store_true", help="Build locally without pushing to GitHub")
    parser.add_argument("--force", "-f", action="store_true", help="Force re-scraping existing rounds")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_pipeline(
        round_num=args.round,
        skip_scrape=args.skip_scrape,
        skip_push=args.no_push,
        force=args.force,
    )
