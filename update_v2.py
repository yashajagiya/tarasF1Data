"""
Root Launcher for Taras F1 API v2 Master Pipeline
Delegates directly to tarasF1DataV2/update.py
"""

import os
import subprocess
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT_PATH = os.path.join(BASE_DIR, "tarasF1DataV2", "update.py")

if __name__ == "__main__":
    if not os.path.exists(SCRIPT_PATH):
        print(f"Error: Could not find update pipeline at {SCRIPT_PATH}")
        sys.exit(1)
    res = subprocess.run([sys.executable, SCRIPT_PATH] + sys.argv[1:])
    sys.exit(res.returncode)
