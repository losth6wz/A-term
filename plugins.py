"""A-term plugin loader.

Plugins live in:
    %APPDATA%\\A-term\\plugins\\*.py

Each plugin is a plain Python file.  It may define any combination of:

    COMMANDS : dict[str, callable]
        Maps command names to functions with signature:
            fn(args: list[str]) -> None
        These are injected directly into the shell's builtin table, so the
        user can call them like any other shell command.

    on_startup(ctx) -> None
        Called once when the shell starts, after all builtins are loaded.
        ``ctx`` exposes:
            ctx.builtins  – the live shell builtins dict (mutable)
            ctx.aliases   – the live aliases dict (mutable)
            ctx.env       – os.environ

Example plugin (hello.py):
    def _hello(args):
        print("Hello,", args[0] if args else "world")

    COMMANDS = {"hello": _hello}
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Plugin directory
# ---------------------------------------------------------------------------

_APPDATA = os.environ.get("APPDATA", os.path.expanduser("~"))
_PLUGIN_DIR = Path(_APPDATA) / "A-term" / "plugins"

# Populated by load_plugins(); consumed by aterm plugin list
_loaded: list[dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def plugin_dir() -> Path:
    """Return the plugins directory path (may not exist yet)."""
    return _PLUGIN_DIR


def loaded() -> list[dict[str, Any]]:
    """Return a snapshot of the loaded-plugin registry."""
    return list(_loaded)


class _Ctx:
    """Context object passed to plugin on_startup hooks."""

    def __init__(self, builtins: dict, aliases: dict) -> None:
        self.builtins = builtins
        self.aliases  = aliases
        self.env      = os.environ


def load_plugins(builtins: dict, aliases: dict) -> None:
    """Scan the plugin directory and load every *.py file found.

    Silently creates the directory if it does not exist.
    Errors in individual plugins are captured and stored; they do not
    abort the shell startup.
    """
    _loaded.clear()
    _PLUGIN_DIR.mkdir(parents=True, exist_ok=True)

    for path in sorted(_PLUGIN_DIR.glob("*.py")):
        # Skip private/internal files
        if path.name.startswith("_"):
            continue

        entry: dict[str, Any] = {
            "name":     path.stem,
            "path":     str(path),
            "commands": [],
            "error":    None,
        }

        try:
            spec = importlib.util.spec_from_file_location(
                f"aterm_plugin_{path.stem}", path
            )
            mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
            spec.loader.exec_module(mod)  # type: ignore[union-attr]

            # Inject COMMANDS
            cmds: dict = getattr(mod, "COMMANDS", {})
            for name, fn in cmds.items():
                if callable(fn):
                    builtins[name] = fn
                    entry["commands"].append(name)

            # Call optional startup hook
            startup = getattr(mod, "on_startup", None)
            if callable(startup):
                startup(_Ctx(builtins, aliases))

        except Exception as exc:
            entry["error"] = str(exc)

        _loaded.append(entry)


# ---------------------------------------------------------------------------
# Plugin scaffolding
# ---------------------------------------------------------------------------

_TEMPLATE = '''\
"""%(name)s — A-term plugin.

Commands registered:
%(commands_doc)s
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# on_startup is called once when the shell loads this plugin (optional).
#
# ctx.builtins  – the live shell builtins dict (mutable)
# ctx.aliases   – the live aliases dict (mutable)
# ctx.env       – os.environ
# ---------------------------------------------------------------------------
def on_startup(ctx: object) -> None:
    pass  # remove if not needed


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------

def _cmd_%(name)s(args: list[str]) -> None:
    """Usage: %(name)s [args...]"""
    print("%(name)s: not yet implemented")


# ---------------------------------------------------------------------------
# Command table — maps command names to functions.
# Every function must accept a list[str] of arguments.
# ---------------------------------------------------------------------------

COMMANDS: dict[str, object] = {
    "%(name)s": _cmd_%(name)s,
}
'''


def scaffold(name: str) -> Path:
    """Write a template plugin file.  Returns the created path."""
    _PLUGIN_DIR.mkdir(parents=True, exist_ok=True)
    dest = _PLUGIN_DIR / f"{name}.py"
    if dest.exists():
        raise FileExistsError(f"{dest} already exists")
    commands_doc = f"    {name}  — (describe your command here)"
    dest.write_text(
        _TEMPLATE % {"name": name, "commands_doc": commands_doc},
        encoding="utf-8",
    )
    return dest
