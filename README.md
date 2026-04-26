<div align="center">

```
    _        _                     
   / \      | |_ ___ _ __ _ __ ___ 
  / _ \ ____| __/ _ \ '__| '_ ` _ \
 / ___ \_____| ||  __/ |  | | | | | |
/_/   \_\     \__\___|_|  |_| |_| |_|
```

**A custom terminal for Windows. No cmd.exe. No PowerShell UI. Just yours.**

[![Release](https://img.shields.io/github/v/release/losth6wz/A-term?color=%23CC88FF&label=latest&style=flat-square)](https://github.com/losth6wz/A-term/releases/latest)
[![Platform](https://img.shields.io/badge/platform-Windows-5599FF?style=flat-square)](https://github.com/losth6wz/A-term)
[![Python](https://img.shields.io/badge/python-3.10%2B-55FF88?style=flat-square)](https://python.org)
[![License](https://img.shields.io/badge/license-none%20yet-555555?style=flat-square)](#license)

</div>

---

## ▸ What is A-term?

A-term is a fully custom terminal emulator built from scratch in Python. It has its own renderer, its own shell, its own config system, and its own command set. It does not wrap `cmd.exe` or the PowerShell UI — it runs an entirely separate process with its own ANSI/VT pipeline.

---

## ▸ Install

**Download the MSI → double-click → done.**

> [`A-term-Setup.msi` → latest release](https://github.com/losth6wz/A-term/releases/latest)

- Installs `A-term.exe` to `Program Files\A-term`
- No Python required on the target machine
- On first launch, A-term registers itself in **Windows Terminal's profile dropdown** automatically
- Config file is created at `%APPDATA%\A-term\aterm.conf` on first run

---

## ▸ Built-in Commands

| Command | Description |
|---|---|
| `aterm theme` | Vim-style interactive theme picker |
| `aterm theme <name>` | Apply a preset theme directly |
| `aterm themes` | List all themes with colour swatches |
| `aterm config` | Show config path, create defaults if missing |
| `aterm config reset` | Reset config to defaults |
| `aterm fetch` | Neofetch-style system info |
| `aterm fetch --image <path>` | Render image + system info |
| `aterm reload` | Re-launch shell to pick up config changes |
| `aterm version` | Show version |

---

## ▸ Config

Config lives at `%APPDATA%\A-term\aterm.conf` after install.  
Edit it with any text editor to change fonts, colours, keybindings, prompt, and more.

**Override location:**
```powershell
$env:ATERM_CONF = "C:\path\to\my.conf"
```

**Reset to defaults:**
```
aterm config reset
```

**Preset themes** (apply from inside the terminal):
```
aterm theme
```
Includes: Gruvbox Dark · Solarized Dark · Nord · Tokyo Night · Dracula · Catppuccin Mocha

---

## ▸ Plugins

Plugins let you add new shell commands without rebuilding or touching the source.

**Plugin directory:** `%APPDATA%\A-term\plugins\`

Drop any `.py` file there and it is loaded automatically on next shell start. No build step. No restart of the app required beyond `aterm reload`.

| Command | Description |
|---|---|
| `aterm plugin list` | Show all loaded plugins and their commands |
| `aterm plugin dir` | Print (and open) the plugins directory |
| `aterm plugin new <name>` | Scaffold a new plugin with a template |

**Minimal example** (`%APPDATA%\A-term\plugins\hello.py`):

```python
def _hello(args):
    print("Hello,", args[0] if args else "world!")

COMMANDS = {"hello": _hello}
```

After saving, run `aterm reload` — then `hello` is a real shell command.

**Full plugin interface:**

```python
# on_startup is optional — called once when the shell loads the plugin
def on_startup(ctx):
    ctx.builtins["my_cmd"] = my_cmd   # register commands programmatically
    ctx.aliases["alias"]   = "my_cmd" # register aliases
    ctx.env["MY_VAR"]      = "value"  # set environment variables

def my_cmd(args: list[str]) -> None:
    ...

COMMANDS = {"my_cmd": my_cmd}
```

---

## ▸ Running from Source

```powershell
git clone https://github.com/losth6wz/A-term
cd A-term
python -m venv .venv
.venv\Scripts\python.exe -m pip install PySide6 pywinpty
.venv\Scripts\python.exe main.py
```

---

<details>
<summary><b>▸ For Nerds — Internals & Architecture</b></summary>

### Module Map

| File | Role |
|---|---|
| `main.py` | GUI entry point, window setup, shell mode flag |
| `terminal_view.py` | QWidget renderer, input handling, font/cursor logic |
| `terminal_buffer.py` | Screen model — 2D cell grid, scrollback, attributes |
| `ansi_parser.py` | Stateful VT100/ANSI parser — CSI, OSC, SGR, DEC |
| `pty_backend.py` | pywinpty wrapper, background reader thread |
| `shell.py` | Custom interactive shell, built-ins, alias expansion |
| `aterm_cmd.py` | `aterm` meta-command dispatcher and TUI components |
| `config.py` | INI config loader, typed accessors, defaults, bootstrap |
| `wt_profile.py` | Windows Terminal profile fragment writer |

### ANSI / VT Pipeline

- SGR: full 16-colour, 256-colour (`38;5;n`), and truecolor (`38;2;r;g;b`) support
- CSI: cursor movement (A–H, f), erase (J, K), insert/delete chars/lines (L, M, P, @)
- DEC private: `?25h/l` cursor visibility, `?1049h/l` alternate screen
- OSC: title changes via `0` and `2`
- Palette overridable at runtime from `aterm.conf` theme values

### Render Loop

```
PTY output
    └─► AnsiParser.feed()
            └─► TerminalBuffer ops (put_char, cursor_*, erase_*, scroll_*)
                    └─► TerminalView.paintEvent() → QPainter → screen
```

### Config Resolution Order

```
ATERM_CONF env var
    └─► %APPDATA%\A-term\aterm.conf
            └─► local aterm.conf  (dev fallback)
```

</details>

---

## ▸ License

No license has been added yet. Contributions and forks welcome — add a `LICENSE` file if you redistribute.
