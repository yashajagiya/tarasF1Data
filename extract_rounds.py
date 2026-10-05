"""
Root launcher for Taras F1 Historical Rounds Extractor
Delegates directly to tarasF1DataV2/extract_rounds.py
"""

import os
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET_SCRIPT = os.path.join(BASE_DIR, "tarasF1DataV2", "extract_rounds.py")

if __name__ == "__main__":
    if not os.path.exists(TARGET_SCRIPT):
        print(f"Error: Could not find extractor script at {TARGET_SCRIPT}")
        sys.exit(1)
    res = subprocess.run([sys.executable, TARGET_SCRIPT] + sys.argv[1:])
    sys.exit(res.returncode)
