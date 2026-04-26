# A-term

A custom terminal application for Windows with its own UI, shell, and ANSI pipeline.

## Why A-term

- Not a themed wrapper over cmd.exe or powershell UI
- Custom renderer and input handling in PySide6
- Custom shell process with A-term-specific commands
- Fast theme switching and deep config control

## Highlights

- VT100 / ANSI parser
- Scrollback buffer with style attributes
- Vim-style theme selector via `aterm theme`
- Config bootstrap and reset via `aterm config` and `aterm config reset`
- Automatic Windows Terminal profile fragment registration on launch
- MSI packaging workflow (WiX Toolset)

## Quick Start (Source)

```powershell
.venv\Scripts\python.exe -m pip install PySide6 pywinpty
.venv\Scripts\python.exe main.py
```

## Config Location and Behavior

Runtime config path priority:

1. `ATERM_CONF`
2. `%APPDATA%\\A-term\\aterm.conf`
3. local `aterm.conf` (dev fallback)

Notes:

- `aterm config` creates a default config if missing
- `aterm config reset` rewrites defaults

## Build EXE + MSI

Prerequisites for building installer artifacts:

- Python virtual environment (`.venv`)
- .NET SDK (for WiX CLI)

Build command:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_msi.ps1
```

Outputs:

- `dist\A-term\A-term.exe`
- `dist-installer\A-term-Setup.msi`

## For Nerds

### Architecture

- `main.py`: GUI startup, window creation, shell mode entrypoint
- `terminal_view.py`: terminal widget, painting, keyboard/mouse behavior
- `terminal_buffer.py`: screen model, attributes, cursor, scrollback
- `ansi_parser.py`: CSI/OSC/SGR parser and state machine
- `pty_backend.py`: pywinpty wrapper and reader thread
- `shell.py`: custom command dispatcher and built-ins
- `aterm_cmd.py`: `aterm` meta-command (`theme`, `themes`, `config`, etc.)
- `config.py`: typed INI access + defaults + config bootstrap
- `wt_profile.py`: Windows Terminal profile fragment writer

### ANSI / VT Notes

- Supports SGR color/attributes including 256-color and truecolor modes
- Handles cursor movement, erase operations, insert/delete chars/lines
- Supports title changes via OSC and alternate screen modes
- Palette can be replaced at runtime from config theme values

### Render / Data Flow

1. PTY emits output from shell process
2. Parser converts byte stream into terminal operations
3. Buffer applies operations and stores styled cells
4. View paints visible rows and cursor

## Repository Layout

- `installer/A-term.wxs`: WiX source for MSI package
- `build_msi.ps1`: one-command EXE + MSI build script

## License

No license file is included yet.
If you want open-source distribution, add a `LICENSE` file (MIT is a common choice).
