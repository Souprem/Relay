"""Test-session setup shared by every test module."""

import os

# Typer forces Rich terminal output (ANSI colors, box drawing) when GITHUB_ACTIONS, FORCE_COLOR or
# PY_COLORS is set, which splits the plain strings the CLI tests assert on. Typer reads this at
# import time, so it must be set before any test imports relay.cli.
os.environ["_TYPER_FORCE_DISABLE_TERMINAL"] = "1"
