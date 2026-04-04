from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT_STR = str(REPO_ROOT)
if REPO_ROOT_STR not in sys.path:
    sys.path.insert(0, REPO_ROOT_STR)

SCRIPTS_ROOT = REPO_ROOT / "scripts"
SCRIPTS_ROOT_STR = str(SCRIPTS_ROOT)
if SCRIPTS_ROOT_STR not in sys.path:
    sys.path.insert(0, SCRIPTS_ROOT_STR)
