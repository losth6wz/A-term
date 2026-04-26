"""aterm_cmd.py — built-in 'aterm' meta-command for the A-term shell.

Subcommands
-----------
    aterm theme              interactive Vim-style picker (j/k, gg, G, Enter)
  aterm theme <name>       apply a named preset theme directly
  aterm themes             list all available preset themes with swatches
    aterm fetch              neofetch-style system summary
    aterm fetch --image <p>  render an image instead of ASCII logo
  aterm reload             re-exec the shell to pick up new config
  aterm version            print A-term version
  aterm help               print this message
"""

from __future__ import annotations

import os
import platform
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import plugins as _plugins
from config import CFG, CONF_PATH, ensure_conf_file

try:
    from PIL import Image
except Exception:
    Image = None

_CONF_PATH = Path(CONF_PATH)
_VERSION   = "0.1.0"

# ── ANSI helpers ──────────────────────────────────────────────────────────────

RST  = "\x1b[0m"
BOLD = "\x1b[1m"
DIM  = "\x1b[2m"


def _hex_rgb(h: str) -> Tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _fg(r: int, g: int, b: int) -> str:
    return f"\x1b[38;2;{r};{g};{b}m"


def _bg(r: int, g: int, b: int) -> str:
    return f"\x1b[48;2;{r};{g};{b}m"


def _swatch(colors: List[str], n: int = 16) -> str:
    """Return a one-line ANSI strip of n coloured blocks."""
    out: List[str] = []
    for c in colors[:n]:
        try:
            r, g, b = _hex_rgb(c)
            out.append(f"{_bg(r, g, b)}  {RST}")
        except Exception:
            out.append("  ")
    return "".join(out)


def _ansi_len(s: str) -> int:
    """Visible character length of a string that may contain ANSI escapes."""
    return len(re.sub(r"\x1b\[[^m]*m", "", s))


# ── fetch ────────────────────────────────────────────────────────────────────

_FETCH_LOGO: List[str] = [
    f"{_fg(255, 120, 180)}        /\\{RST}",
    f"{_fg(255, 120, 180)}   /\\  /  \\{RST}",
    f"{_fg(255, 145, 198)}  /  \\/ /\\ \\{RST}",
    f"{_fg(255, 170, 214)} / /\\  /__\\ \\{RST}",
    f"{_fg(255, 190, 228)}/_/  \\/    \\_\\{RST}",
    f"{_fg(255, 205, 238)}   A-term console{RST}",
]


def _uptime_text() -> str:
    try:
        import ctypes

        ms = int(ctypes.windll.kernel32.GetTickCount64())
        secs = max(0, ms // 1000)
    except Exception:
        return "unknown"

    days, rem = divmod(secs, 86400)
    hours, rem = divmod(rem, 3600)
    mins, _ = divmod(rem, 60)
    parts: List[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if mins or not parts:
        parts.append(f"{mins}m")
    return " ".join(parts)


def _fetch_info_lines() -> List[str]:
    theme = f"FG {CFG.fg} / BG {CFG.bg}"
    return [
        f"{BOLD}{_fg(255, 170, 214)}{os.environ.get('USERNAME', 'user')}@{platform.node()}{RST}",
        f"{DIM}{'-' * 34}{RST}",
        f"{BOLD}OS{RST}: {platform.system()} {platform.release()}",
        f"{BOLD}Kernel{RST}: {platform.version()}",
        f"{BOLD}Python{RST}: {platform.python_version()}",
        f"{BOLD}A-term{RST}: {_VERSION}",
        f"{BOLD}Uptime{RST}: {_uptime_text()}",
        f"{BOLD}Shell{RST}: A-term custom shell",
        f"{BOLD}Theme{RST}: {theme}",
        f"{BOLD}Plugins{RST}: {len(_plugins.loaded())} loaded",
        f"{BOLD}Config{RST}: {CONF_PATH}",
        f"{BOLD}Time{RST}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        _swatch([CFG.ansi_color_hex(i) for i in range(16)], n=16),
    ]


def _image_to_ansi_lines(path: Path, width: int) -> List[str]:
    if Image is None:
        raise RuntimeError("Image rendering requires Pillow. Install it with: pip install pillow")

    width = max(8, min(120, width))
    with Image.open(path) as img:
        img = img.convert("RGB")
        h = max(2, int((img.height / max(1, img.width)) * width * 2))
        if h % 2:
            h += 1
        img = img.resize((width, h))
        px = img.load()

        lines: List[str] = []
        for y in range(0, h, 2):
            row: List[str] = []
            for x in range(width):
                r1, g1, b1 = px[x, y]
                r2, g2, b2 = px[x, y + 1]
                row.append(f"\x1b[38;2;{r1};{g1};{b1}m\x1b[48;2;{r2};{g2};{b2}m▀")
            row.append(RST)
            lines.append("".join(row))
    return lines


def _print_two_columns(left: List[str], right: List[str], left_width: int = 38) -> None:
    rows = max(len(left), len(right))
    for i in range(rows):
        l = left[i] if i < len(left) else ""
        r = right[i] if i < len(right) else ""
        pad = max(1, left_width - _ansi_len(l))
        print(f"{l}{' ' * pad}{r}")


def _run_fetch(args: List[str]) -> int:
    image_path: Optional[Path] = None
    width = 34

    i = 0
    while i < len(args):
        a = args[i]
        if a in ("--image", "-i"):
            if i + 1 >= len(args):
                print("Usage: aterm fetch [--image <path>] [--width <n>]")
                return 1
            image_path = Path(args[i + 1]).expanduser()
            i += 2
            continue
        if a in ("--width", "-w"):
            if i + 1 >= len(args):
                print("Usage: aterm fetch [--image <path>] [--width <n>]")
                return 1
            try:
                width = int(args[i + 1])
            except ValueError:
                print(f"Invalid width '{args[i + 1]}'.")
                return 1
            i += 2
            continue
        if a in ("--help", "-h"):
            print("Usage: aterm fetch [--image <path>] [--width <n>]")
            return 0

        # Convenience: bare positional path means image path.
        if image_path is None:
            image_path = Path(a).expanduser()
            i += 1
            continue

        print(f"Unknown argument '{a}'.")
        print("Usage: aterm fetch [--image <path>] [--width <n>]")
        return 1

    left = _FETCH_LOGO
    if image_path is not None:
        if not image_path.exists() or not image_path.is_file():
            print(f"Image not found: {image_path}")
            return 1
        try:
            left = _image_to_ansi_lines(image_path, width)
        except Exception as exc:
            print(f"Image render failed: {exc}")
            return 1

    right = _fetch_info_lines()
    _print_two_columns(left, right, left_width=max(38, width + 2))
    return 0


# ── theme parsing ─────────────────────────────────────────────────────────────

_THEME_KEYS: List[str] = (
    ["foreground", "background", "cursor", "cursor_text", "selection_bg"]
    + [f"color{i}" for i in range(16)]
)


def _parse_preset_themes() -> Dict[str, Dict[str, str]]:
    """Parse commented-out preset theme blocks from aterm.conf.

    A block looks like:
        # [Theme Name]
        # foreground = #RRGGBB
        # background = #RRGGBB
        # color0 = #... ; color1 = #... ; ...
    """
    themes: Dict[str, Dict[str, str]] = {}
    current_name: Optional[str] = None
    current_data: Dict[str, str] = {}

    with open(_CONF_PATH, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip()

            m = re.match(r'^#\s*\[(.+?)\]\s*$', line)
            if m:
                if current_name and current_data:
                    themes[current_name] = current_data
                current_name = m.group(1)
                current_data = {}
                continue

            if current_name is None:
                continue

            if line.startswith('#'):
                content = line[1:].strip()
                for part in content.split(';'):
                    part = part.strip()
                    if '=' in part:
                        k, _, v = part.partition('=')
                        k = k.strip().lower()
                        v = v.strip()
                        if k and v:
                            current_data[k] = v
            else:
                # Any non-comment line ends the current block
                if current_name and current_data:
                    themes[current_name] = current_data
                current_name = None
                current_data = {}

    if current_name and current_data:
        themes[current_name] = current_data

    return themes


# ── config writer ─────────────────────────────────────────────────────────────

def _apply_theme(data: Dict[str, str]) -> None:
    """Update [theme] key values in aterm.conf, preserving all formatting."""
    text   = _CONF_PATH.read_text(encoding="utf-8")
    lines  = text.splitlines(keepends=True)
    in_theme = False
    result: List[str] = []

    for line in lines:
        stripped = line.strip()

        sec = re.match(r'^\[(\w+)\]', stripped)
        if sec:
            in_theme = sec.group(1).lower() == "theme"
            result.append(line)
            continue

        if in_theme and not stripped.startswith('#') and '=' in stripped:
            m = re.match(r'^(\s*)([\w]+)(\s*=\s*)([^\s;]+)(.*)', line)
            if m:
                key = m.group(2).lower()
                if key in data:
                    replacement = (
                        f"{m.group(1)}{m.group(2)}{m.group(3)}"
                        f"{data[key]}{m.group(5)}"
                    )
                    if not replacement.endswith('\n'):
                        replacement += '\n'
                    line = replacement

        result.append(line)

    _CONF_PATH.write_text("".join(result), encoding="utf-8")


# ── keyboard reader ───────────────────────────────────────────────────────────

def _read_key() -> str:
    """Read a single keypress and return a semantic string."""
    import msvcrt
    ch = msvcrt.getwch()
    if ch in ('\x00', '\xe0'):
        ch2 = msvcrt.getwch()
        return {
            'H': 'UP',   'P': 'DOWN',
            'K': 'LEFT', 'M': 'RIGHT',
            'G': 'HOME', 'O': 'END',
            'I': 'PGUP', 'Q': 'PGDN',
        }.get(ch2, f'EXT:{ch2}')
    if ch == '\r':   return 'ENTER'
    if ch == '\x1b': return 'ESC'
    if ch == '\x03': return 'CTRL_C'
    return ch


def _clear_lines(n: int) -> None:
    """Move cursor up n lines and erase each one."""
    for _ in range(n):
        sys.stdout.write("\x1b[A\x1b[2K")
    sys.stdout.flush()


# ── interactive theme picker ──────────────────────────────────────────────────

_BOX_W = 58   # inner width of the picker box (excluding border chars)

_C_BORDER = _fg(120, 90, 200)
_C_TITLE  = _fg(220, 175, 255)
_C_SEL    = _fg(100, 255, 150)
_C_DIM    = _fg(120, 120, 140)
_C_NAME   = _fg(240, 240, 255)


def _box_line(content: str, w: int = _BOX_W) -> str:
    """Pad *content* to fill a box row and add border characters."""
    pad = w - _ansi_len(content) - 2   # -2 for the leading space + trailing space
    return f"{_C_BORDER}│{RST} {content}{' ' * max(0, pad)} {_C_BORDER}│{RST}"


def _render_picker(names: List[str], themes: Dict[str, Dict[str, str]], sel: int) -> int:
    """Render the picker and return the number of lines written."""
    W = _BOX_W
    written = 0

    def emit(s: str) -> None:
        nonlocal written
        sys.stdout.write(s + "\n")
        written += 1

    top = f"{_C_BORDER}┌{'─' * W}┐{RST}"
    mid = f"{_C_BORDER}├{'─' * W}┤{RST}"
    bot = f"{_C_BORDER}└{'─' * W}┘{RST}"

    # Header row
    title_s = f"{_C_TITLE}{BOLD}A-term Theme Selector (Vim){RST}"
    hint_s  = f"{_C_DIM}j/k move  gg top  G bottom  Enter apply  q quit{RST}"
    gap     = W - 2 - len("A-term Theme Selector (Vim)") - len("j/k move  gg top  G bottom  Enter apply  q quit")
    header  = f"{title_s}{' ' * max(1, gap)}{hint_s}"

    emit(top)
    emit(_box_line(header))
    emit(mid)

    for i, name in enumerate(names):
        data   = themes[name]
        colors = [data.get(f"color{j}", "#000000") for j in range(16)]
        sw     = _swatch(colors)

        if i == sel:
            bullet = f"{_C_SEL}{BOLD}❯{RST}"
            label  = f"{BOLD}{_C_NAME}{name}{RST}"
        else:
            bullet = " "
            label  = f"{_C_DIM}{name}{RST}"

        name_col = 24
        pad      = max(0, name_col - len(name))
        row      = f"{bullet} {label}{' ' * pad}{sw}"
        emit(_box_line(row))

    emit(bot)
    sys.stdout.flush()
    return written


def _run_theme_picker() -> None:
    themes = _parse_preset_themes()
    if not themes:
        print("No preset themes found in aterm.conf.")
        return

    names = list(themes.keys())
    sel   = 0
    pending_g = False

    lines = _render_picker(names, themes, sel)

    while True:
        key = _read_key()

        if key in ('UP', 'k'):
            pending_g = False
            sel = (sel - 1) % len(names)
        elif key in ('DOWN', 'j'):
            pending_g = False
            sel = (sel + 1) % len(names)
        elif key in ('LEFT', 'h'):
            pending_g = False
            sel = (sel - 1) % len(names)
        elif key in ('RIGHT', 'l'):
            pending_g = False
            sel = (sel + 1) % len(names)
        elif key == 'g':
            if pending_g:
                sel = 0
                pending_g = False
            else:
                pending_g = True
                continue
        elif key == 'G':
            pending_g = False
            sel = len(names) - 1
        elif key == 'HOME':
            pending_g = False
            sel = 0
        elif key == 'END':
            pending_g = False
            sel = len(names) - 1
        elif key == 'ENTER':
            pending_g = False
            name = names[sel]
            _clear_lines(lines)
            _apply_theme(themes[name])
            print(
                f"{_C_SEL}{BOLD}✓{RST} Theme {BOLD}{name}{RST} applied to aterm.conf.\n"
                f"{DIM}  Restart A-term (exit → reopen) to load the new colours.{RST}"
            )
            return
        elif key in ('q', 'Q', 'ESC', 'CTRL_C'):
            pending_g = False
            _clear_lines(lines)
            print(f"{_C_DIM}No theme applied.{RST}")
            return
        else:
            pending_g = False
            continue

        _clear_lines(lines)
        lines = _render_picker(names, themes, sel)


# ── direct theme-by-name ──────────────────────────────────────────────────────

def _run_theme_set(name_arg: str) -> None:
    themes = _parse_preset_themes()

    # Exact match (case-insensitive)
    match: Optional[str] = None
    for n in themes:
        if n.lower() == name_arg.lower():
            match = n
            break

    # Partial match fallback
    if match is None:
        hits = [n for n in themes if name_arg.lower() in n.lower()]
        if len(hits) == 1:
            match = hits[0]
        elif len(hits) > 1:
            print(f"Ambiguous name '{name_arg}'. Matches: {', '.join(hits)}")
            return
        else:
            available = ", ".join(themes.keys())
            print(f"Unknown theme '{name_arg}'.\nAvailable: {available}")
            return

    _apply_theme(themes[match])
    print(
        f"{_C_SEL}{BOLD}✓{RST} Theme {BOLD}{match}{RST} applied to aterm.conf.\n"
        f"{DIM}  Restart A-term (exit → reopen) to load the new colours.{RST}"
    )


# ── list themes ───────────────────────────────────────────────────────────────

def _run_themes_list() -> None:
    themes = _parse_preset_themes()
    if not themes:
        print("No preset themes found in aterm.conf.")
        return

    print(f"\n{BOLD}Available themes:{RST}\n")
    for name, data in themes.items():
        colors = [data.get(f"color{i}", "#000000") for i in range(16)]
        sw     = _swatch(colors)
        fg_hex = data.get("foreground", "#cccccc")
        bg_hex = data.get("background", "#000000")
        try:
            r, g, b = _hex_rgb(fg_hex)
            br, bg_, bb = _hex_rgb(bg_hex)
            label = f"{_bg(br, bg_, bb)}{_fg(r, g, b)} {name:22s} {RST}"
        except Exception:
            label = f" {name:22s} "
        print(f"  {label}  {sw}")
    print()


# ── config command ───────────────────────────────────────────────────────────

def _app_location() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()
    return Path(__file__).resolve().parent


def _run_config(args: List[str]) -> int:
    reset = bool(args and args[0].lower() == "reset")
    path, changed = ensure_conf_file(force_reset=reset)

    if reset:
        print(f"{_C_SEL}{BOLD}✓{RST} Reset config file to defaults.")
    elif changed:
        print(f"{_C_SEL}{BOLD}✓{RST} Created default config file.")
    else:
        print(f"{_C_DIM}Config file already exists.{RST}")

    print(f"Config path: {path}")
    print(f"App location: {_app_location()}")
    return 0


# ── plugin command ──────────────────────────────────────────────────────────

def _run_plugin(args: List[str]) -> int:
    if not args or args[0] in ("list", "ls"):
        items = _plugins.loaded()
        pdir  = _plugins.plugin_dir()
        print(f"\n{BOLD}Plugin directory:{RST} {pdir}\n")
        if not items:
            print(f"  {DIM}No plugins loaded.{RST}")
            print(f"  Drop a .py file in the directory above and restart A-term.")
        else:
            for p in items:
                if p["error"]:
                    tag  = f"\x1b[1;31m✗ {p['error']}{RST}"
                    cmds = ""
                else:
                    tag  = f"\x1b[1;32m✓{RST}"
                    cmds = f"  → {', '.join(p['commands'])}" if p["commands"] else "  (no commands)"
                print(f"  {tag}  {BOLD}{p['name']}{RST}{cmds}")
                print(f"     {DIM}{p['path']}{RST}")
        print()
        return 0

    if args[0] == "dir":
        pdir = _plugins.plugin_dir()
        pdir.mkdir(parents=True, exist_ok=True)
        print(str(pdir))
        # Try to open in Explorer
        try:
            import subprocess
            subprocess.Popen(["explorer", str(pdir)])
        except Exception:
            pass
        return 0

    if args[0] == "new":
        if len(args) < 2:
            print("Usage: aterm plugin new <name>")
            return 1
        name = args[1]
        # Sanitise name
        if not name.replace("_", "").replace("-", "").isalnum():
            print(f"Invalid plugin name '{name}'. Use letters, digits, underscores.")
            return 1
        try:
            dest = _plugins.scaffold(name)
            print(f"{_C_SEL}{BOLD}✓{RST} Created plugin scaffold: {dest}")
            print(f"{DIM}  Edit the file, then run 'aterm reload' to load it.{RST}")
        except FileExistsError as exc:
            print(f"\x1b[1;31m{exc}{RST}")
            return 1
        return 0

    print(f"Unknown plugin subcommand '{args[0]}'. Try: list, dir, new <name>")
    return 1


# ── help ──────────────────────────────────────────────────────────────────────

_HELP = f"""\
{BOLD}aterm{RST} — A-term terminal meta-command

{BOLD}Usage:{RST}
    aterm theme              open interactive Vim-style theme picker
  aterm theme <name>       apply a named preset theme directly
  aterm themes             list all preset themes with colour swatches
    aterm config             create default config if missing and print location
    aterm config reset       reset config file to default values
  aterm plugin list        list loaded plugins and their commands
  aterm plugin dir         open the plugins directory in Explorer
  aterm plugin new <name>  scaffold a new plugin file
    aterm fetch              neofetch-style system summary
    aterm fetch --image <p>  render an image instead of ASCII logo
  aterm reload             re-exec the shell (picks up new aterm.conf)
  aterm version            print A-term version
  aterm help               show this message

{BOLD}Picker keys:{RST}
    j/k or ↑/↓               move selection
    gg / G                   jump to top / bottom
    Enter                    apply selected theme
    q or Esc                 quit without changes

{BOLD}Tip:{RST} you can also edit {_C_DIM}aterm.conf{RST} directly and restart.\
"""


# ── entry point ───────────────────────────────────────────────────────────────

def run(args: List[str]) -> int:
    """Main entry point.  Called from shell.py _BUILTINS["aterm"]."""
    if not args:
        print(_HELP)
        return 0

    sub = args[0].lower()

    if sub == "theme":
        if len(args) > 1:
            _run_theme_set(" ".join(args[1:]))
        else:
            _run_theme_picker()
        return 0

    if sub == "themes":
        _run_themes_list()
        return 0

    if sub == "config":
        return _run_config(args[1:])

    if sub == "reload":
        print(f"{DIM}Re-launching shell…{RST}")
        os.execv(sys.executable, [sys.executable] + sys.argv)
        return 0  # unreachable

    if sub in ("version", "--version", "-v"):
        print(f"A-term {_VERSION}")
        return 0

    if sub == "plugin":
        return _run_plugin(args[1:])

    if sub == "fetch":
        return _run_fetch(args[1:])

    if sub in ("help", "--help", "-h"):
        print(_HELP)
        return 0

    print(f"aterm: unknown subcommand '{args[0]}'. Try 'aterm help'.")
    return 1
