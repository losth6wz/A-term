"""Configuration loader for A-term.

Reads ``aterm.conf`` (INI format) from the same directory.
Every option falls back to a built-in default when missing or blank.
Access configuration through the module-level ``CFG`` singleton.
"""

from __future__ import annotations

import configparser
import os
import shutil
from typing import Dict, List, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
_LOCAL_CONF_PATH = os.path.join(_HERE, "aterm.conf")

_FALLBACK_CONF_TEXT = """# Auto-generated default A-term configuration\n\
[window]\n\
title = A-term\n\
width = 960\n\
height = 640\n\
opacity = 1.0\n\
padding = 6\n\
\n\
[font]\n\
family = Consolas\n\
size = 11\n\
\n\
[cursor]\n\
style = block\n\
blink = true\n\
blink_rate = 500\n\
\n\
[scrollback]\n\
lines = 10000\n\
scroll_speed = 3\n\
\n\
[theme]\n\
foreground = #CCCCCC\n\
background = #0C0C0C\n\
cursor = #FFFFFF\n\
cursor_text = #0C0C0C\n\
selection_bg = #264F78\n\
selection_fg =\n\
color0 = #000000\n\
color1 = #AA0000\n\
color2 = #00AA00\n\
color3 = #AAAA00\n\
color4 = #0000AA\n\
color5 = #AA00AA\n\
color6 = #00AAAA\n\
color7 = #AAAAAA\n\
color8 = #555555\n\
color9 = #FF5555\n\
color10 = #55FF55\n\
color11 = #FFFF55\n\
color12 = #5555FF\n\
color13 = #FF55FF\n\
color14 = #55FFFF\n\
color15 = #FFFFFF\n\
\n\
[shell]\n\
banner = true\n\
history_size = 1000\n\
tab_width = 8\n\
startup_cmd =\n\
\n\
[prompt]\n\
format = {bold}{fg:#CC88FF}{user}{reset} {bold}{fg:#5599FF}{cwd_short}{reset}{git_branch} {bold}{fg:#55FF88}>{reset} \n\
show_git = true\n\
git_dirty_symbol = *\n\
separator =\n\
\n\
[aliases]\n\
ll = ls\n\
la = ls\n\
py = python\n\
cls = clear\n\
\n\
[env]\n\
\n\
[keybindings]\n\
copy = Ctrl+Shift+C\n\
paste = Ctrl+Shift+V\n\
increase_font = Ctrl+Equal\n\
decrease_font = Ctrl+Minus\n\
reset_font = Ctrl+0\n\
scroll_up = Shift+PageUp\n\
scroll_down = Shift+PageDown\n\
clear_screen = Ctrl+L\n\
new_window = Ctrl+Shift+N\n"""


def _resolve_conf_path() -> str:
    """Return the writable config path used by A-term.

    Priority:
      1) ATERM_CONF (explicit override)
            2) %APPDATA%\\A-term\\aterm.conf
      3) local project path (development fallback)
    """
    override = os.environ.get("ATERM_CONF", "").strip()
    if override:
        return os.path.abspath(os.path.expanduser(override))

    appdata = os.environ.get("APPDATA", "").strip()
    if appdata:
        return os.path.join(appdata, "A-term", "aterm.conf")

    return _LOCAL_CONF_PATH


CONF_PATH = _resolve_conf_path()


def ensure_conf_file(force_reset: bool = False) -> tuple[str, bool]:
    """Ensure a config file exists and return (path, created_or_reset)."""
    parent = os.path.dirname(CONF_PATH)
    if parent:
        os.makedirs(parent, exist_ok=True)

    if (not force_reset) and os.path.exists(CONF_PATH):
        return CONF_PATH, False

    if os.path.exists(_LOCAL_CONF_PATH):
        shutil.copyfile(_LOCAL_CONF_PATH, CONF_PATH)
        return CONF_PATH, True

    # Final fallback for packaged builds where source aterm.conf is not present.
    with open(CONF_PATH, "w", encoding="utf-8") as f:
        f.write(_FALLBACK_CONF_TEXT)

    return CONF_PATH, True


def _ensure_conf_exists() -> None:
    """Compatibility wrapper for existing internal callsites."""
    ensure_conf_file(force_reset=False)

# ---------------------------------------------------------------------------
# Built-in defaults (mirror the comments in aterm.conf)
# ---------------------------------------------------------------------------

_DEFAULTS: Dict[str, str] = {
    # [window]
    "window.title":   "A-term",
    "window.width":   "960",
    "window.height":  "640",
    "window.opacity": "1.0",
    "window.padding": "4",
    # [font]
    "font.family": "Consolas",
    "font.size":   "11",
    # [cursor]
    "cursor.style":      "block",
    "cursor.blink":      "true",
    "cursor.blink_rate": "500",
    # [scrollback]
    "scrollback.lines":        "10000",
    "scrollback.scroll_speed": "3",
    # [theme]
    "theme.foreground":   "#CCCCCC",
    "theme.background":   "#0C0C0C",
    "theme.cursor":       "#FFFFFF",
    "theme.cursor_text":  "#0C0C0C",
    "theme.selection_bg": "#264F78",
    "theme.selection_fg": "",
    # ANSI 16-colour palette
    "theme.color0":  "#000000",
    "theme.color1":  "#AA0000",
    "theme.color2":  "#00AA00",
    "theme.color3":  "#AAAA00",
    "theme.color4":  "#0000AA",
    "theme.color5":  "#AA00AA",
    "theme.color6":  "#00AAAA",
    "theme.color7":  "#AAAAAA",
    "theme.color8":  "#555555",
    "theme.color9":  "#FF5555",
    "theme.color10": "#55FF55",
    "theme.color11": "#FFFF55",
    "theme.color12": "#5555FF",
    "theme.color13": "#FF55FF",
    "theme.color14": "#55FFFF",
    "theme.color15": "#FFFFFF",
    # [shell]
    "shell.banner":       "true",
    "shell.history_size": "1000",
    "shell.tab_width":    "8",
    "shell.startup_cmd":  "",
    # [prompt]
    "prompt.format":
        "{bold}{fg:#CC88FF}{user}{reset}"
        " {bold}{fg:#5599FF}{cwd_short}{reset}"
        "{git_branch}"
        " {bold}{fg:#55FF88}>{reset} ",
    "prompt.show_git":         "true",
    "prompt.git_dirty_symbol": "*",
    "prompt.separator":        "",
    # [keybindings]
    "keybindings.copy":          "Ctrl+Shift+C",
    "keybindings.paste":         "Ctrl+Shift+V",
    "keybindings.increase_font": "Ctrl+Equal",
    "keybindings.decrease_font": "Ctrl+Minus",
    "keybindings.reset_font":    "Ctrl+0",
    "keybindings.scroll_up":     "Shift+PageUp",
    "keybindings.scroll_down":   "Shift+PageDown",
    "keybindings.clear_screen":  "Ctrl+L",
    "keybindings.new_window":    "Ctrl+Shift+N",
}


# ---------------------------------------------------------------------------
# Helper – hex #RRGGBB → (R, G, B)
# ---------------------------------------------------------------------------

def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = h[0] * 2 + h[1] * 2 + h[2] * 2
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


# ---------------------------------------------------------------------------
# Config class
# ---------------------------------------------------------------------------

class Config:
    """Parsed A-term configuration."""

    def __init__(self) -> None:
        self._load()

    def _load(self) -> None:
        _ensure_conf_exists()
        self._cp = configparser.ConfigParser(
            interpolation=None, allow_no_value=True
        )
        self._cp.read(CONF_PATH, encoding="utf-8")

    def reload(self) -> None:
        """Re-read aterm.conf from disk."""
        self._load()

    # ------------------------------------------------------------------
    # Internal getters
    # ------------------------------------------------------------------

    def _raw(self, section: str, key: str) -> str:
        default = _DEFAULTS.get(f"{section}.{key}", "")
        try:
            v = self._cp.get(section, key)
            return (v or "").strip() or default
        except (configparser.NoSectionError, configparser.NoOptionError):
            return default

    def _str(self, section: str, key: str, fallback: str = "") -> str:
        v = self._raw(section, key)
        return v if v else fallback

    def _int(self, section: str, key: str) -> int:
        try:
            return int(self._raw(section, key))
        except (ValueError, TypeError):
            return int(_DEFAULTS.get(f"{section}.{key}", "0"))

    def _float(self, section: str, key: str) -> float:
        try:
            return float(self._raw(section, key))
        except (ValueError, TypeError):
            return float(_DEFAULTS.get(f"{section}.{key}", "0.0"))

    def _bool(self, section: str, key: str) -> bool:
        return self._raw(section, key).lower() in ("1", "true", "yes", "on")

    # ------------------------------------------------------------------
    # [window]
    # ------------------------------------------------------------------

    @property
    def window_title(self) -> str:
        return self._str("window", "title", "A-term")

    @property
    def window_width(self) -> int:
        return max(200, self._int("window", "width"))

    @property
    def window_height(self) -> int:
        return max(100, self._int("window", "height"))

    @property
    def window_opacity(self) -> float:
        return max(0.1, min(1.0, self._float("window", "opacity")))

    @property
    def padding(self) -> int:
        return max(0, self._int("window", "padding"))

    # ------------------------------------------------------------------
    # [font]
    # ------------------------------------------------------------------

    @property
    def font_family(self) -> str:
        return self._str("font", "family", "Consolas")

    @property
    def font_size(self) -> int:
        return max(6, self._int("font", "size"))

    # ------------------------------------------------------------------
    # [cursor]
    # ------------------------------------------------------------------

    @property
    def cursor_style(self) -> str:
        s = self._str("cursor", "style", "block").lower()
        return s if s in ("block", "underline", "beam") else "block"

    @property
    def cursor_blink(self) -> bool:
        return self._bool("cursor", "blink")

    @property
    def cursor_blink_rate(self) -> int:
        return max(100, self._int("cursor", "blink_rate"))

    # ------------------------------------------------------------------
    # [scrollback]
    # ------------------------------------------------------------------

    @property
    def scrollback_lines(self) -> int:
        return max(100, self._int("scrollback", "lines"))

    @property
    def scroll_speed(self) -> int:
        return max(1, self._int("scrollback", "scroll_speed"))

    # ------------------------------------------------------------------
    # [theme]
    # ------------------------------------------------------------------

    @property
    def fg(self) -> str:
        return self._str("theme", "foreground", "#CCCCCC")

    @property
    def bg(self) -> str:
        return self._str("theme", "background", "#0C0C0C")

    @property
    def cursor_color(self) -> str:
        return self._str("theme", "cursor", "#FFFFFF")

    @property
    def cursor_text_color(self) -> str:
        return self._str("theme", "cursor_text", "#0C0C0C")

    @property
    def selection_bg(self) -> str:
        return self._str("theme", "selection_bg", "#264F78")

    @property
    def selection_fg(self) -> str:
        return self._str("theme", "selection_fg", "")

    def ansi_color_hex(self, n: int) -> str:
        """Return hex colour string for ANSI index 0–15."""
        return self._str("theme", f"color{n}",
                         _DEFAULTS.get(f"theme.color{n}", "#000000"))

    def palette_16(self) -> List[Tuple[int, int, int]]:
        """Return the 16-colour palette as (R,G,B) tuples."""
        out = []
        for i in range(16):
            try:
                out.append(hex_to_rgb(self.ansi_color_hex(i)))
            except Exception:
                out.append(hex_to_rgb(_DEFAULTS.get(f"theme.color{i}", "#000000")))
        return out

    # ------------------------------------------------------------------
    # [shell]
    # ------------------------------------------------------------------

    @property
    def shell_banner(self) -> bool:
        return self._bool("shell", "banner")

    @property
    def shell_history_size(self) -> int:
        return max(0, self._int("shell", "history_size"))

    @property
    def shell_tab_width(self) -> int:
        return max(1, self._int("shell", "tab_width"))

    @property
    def shell_startup_cmd(self) -> str:
        return self._str("shell", "startup_cmd", "")

    # ------------------------------------------------------------------
    # [prompt]
    # ------------------------------------------------------------------

    @property
    def prompt_format(self) -> str:
        return self._str(
            "prompt", "format",
            _DEFAULTS["prompt.format"],
        )

    @property
    def prompt_show_git(self) -> bool:
        return self._bool("prompt", "show_git")

    @property
    def prompt_git_dirty(self) -> str:
        return self._str("prompt", "git_dirty_symbol", "*")

    @property
    def prompt_separator(self) -> str:
        return self._str("prompt", "separator", "")

    # ------------------------------------------------------------------
    # [aliases]
    # ------------------------------------------------------------------

    def aliases(self) -> Dict[str, str]:
        """Return alias_name → expanded_command dict."""
        result: Dict[str, str] = {}
        if self._cp.has_section("aliases"):
            for key, value in self._cp.items("aliases"):
                if value:
                    result[key.strip()] = value.strip()
        return result

    # ------------------------------------------------------------------
    # [env]
    # ------------------------------------------------------------------

    def extra_env(self) -> Dict[str, str]:
        """Return extra environment variables to inject into the shell."""
        result: Dict[str, str] = {}
        if self._cp.has_section("env"):
            for key, value in self._cp.items("env"):
                if value:
                    result[key.strip().upper()] = value.strip()
        return result

    # ------------------------------------------------------------------
    # [keybindings]
    # ------------------------------------------------------------------

    def keybinding(self, name: str) -> str:
        """Return the keybinding string for *name*, e.g. ``'Ctrl+Shift+C'``."""
        return self._str(
            "keybindings", name,
            _DEFAULTS.get(f"keybindings.{name}", ""),
        )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

CFG = Config()
