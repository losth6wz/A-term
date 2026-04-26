"""Windows Terminal profile fragment integration for A-term.

This module writes a profile fragment for Windows Terminal so A-term appears
in the dropdown profile list.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


PROFILE_GUID = "{6dbf368f-f8f0-4e0d-87cf-31f2ea86e8a5}"
PROFILE_NAME = "A-term"


def _commandline() -> str:
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable).resolve()}"'

    here = Path(__file__).resolve().parent
    return f'"{Path(sys.executable).resolve()}" "{here / "main.py"}"'


def _icon_path() -> str:
    if getattr(sys, "frozen", False):
        return str(Path(sys.executable).resolve())
    return ""


def _fragment_dirs() -> list[Path]:
    localappdata = os.environ.get("LOCALAPPDATA", "").strip()
    if not localappdata:
        return []

    root = Path(localappdata)
    return [
        root
        / "Packages"
        / "Microsoft.WindowsTerminal_8wekyb3d8bbwe"
        / "LocalState"
        / "fragments"
        / "A-term",
        root
        / "Packages"
        / "Microsoft.WindowsTerminalPreview_8wekyb3d8bbwe"
        / "LocalState"
        / "fragments"
        / "A-term",
        root / "Microsoft" / "Windows Terminal" / "Fragments" / "A-term",
    ]


def ensure_windows_terminal_profile() -> list[Path]:
    """Write/update profile fragment files and return updated file paths."""
    cmd = _commandline()
    icon = _icon_path()

    profile = {
        "guid": PROFILE_GUID,
        "name": PROFILE_NAME,
        "commandline": cmd,
        "hidden": False,
    }
    if icon:
        profile["icon"] = icon

    fragment = {
        "$schema": "https://aka.ms/terminal-profiles-schema",
        "profiles": [profile],
    }

    written: list[Path] = []
    for d in _fragment_dirs():
        d.mkdir(parents=True, exist_ok=True)
        f = d / "A-term.json"
        f.write_text(json.dumps(fragment, indent=2), encoding="utf-8")
        written.append(f)

    return written
