"""Offline research: replay the live strategy over history and compare exit policies.

Run from the repo root, e.g. `python -m research.run research/experiments/baseline.json`.
Nothing here places orders or writes the live ledger.
"""

import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
for _path in (REPO_ROOT, os.path.join(REPO_ROOT, 'src')):
    if _path not in sys.path:
        sys.path.insert(0, _path)
