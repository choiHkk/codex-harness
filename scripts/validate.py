#!/usr/bin/env python3
"""Repository entry point for the installable harness validator."""

from pathlib import Path
import runpy
import sys

directory = Path(__file__).resolve().parents[1] / ".agents/skills/harness/scripts"
sys.path.insert(0, str(directory))
runpy.run_path(str(directory / "validate.py"), run_name="__main__")
