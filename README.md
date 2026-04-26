# A-term

A custom terminal emulator for Windows built with Python, PySide6, and pywinpty.

## Features

- Custom terminal UI (not cmd.exe or powershell UI)
- Built-in custom shell
- ANSI / VT100 parsing
- Config-driven behavior via aterm.conf
- Vim-style theme picker: `aterm theme`
- Theme list and direct apply: `aterm themes`, `aterm theme <name>`
- Config bootstrap command: `aterm config`
- Config reset command: `aterm config reset`
- PyInstaller packaging support
- Inno Setup installer script included

## Project Structure

- main.py: GUI app entrypoint
- shell.py: custom shell process
- terminal_view.py: rendering and input
- terminal_buffer.py: screen buffer + scrollback
- ansi_parser.py: ANSI/VT parser
- pty_backend.py: pywinpty wrapper
- config.py: config loading + defaults
- aterm.conf: editable defaults template
- aterm_cmd.py: built-in `aterm` command
- installer/A-term.iss: Inno Setup installer recipe
- build_installer.ps1: one-command build script for exe + installer

## Run From Source

1. Create and activate a virtual environment
2. Install dependencies
3. Launch app

Windows example:

- .venv\Scripts\python.exe -m pip install PySide6 pywinpty
- .venv\Scripts\python.exe main.py

## Config File Location

At runtime, config is resolved in this order:

1. ATERM_CONF environment variable path
2. %APPDATA%\A-term\aterm.conf
3. Local project aterm.conf (development fallback)

Use `aterm config` to create default config if missing.

## Build EXE

- .venv\Scripts\python.exe -m pip install pyinstaller
- .venv\Scripts\python.exe -m PyInstaller --noconfirm --windowed --name A-term main.py

Output:

- dist\A-term\A-term.exe

## Build Installer

Prerequisite: Inno Setup 6 installed.

Run:

- powershell -ExecutionPolicy Bypass -File .\build_installer.ps1

Installer output:

- dist-installer\A-term-Setup.exe

## Windows Terminal Profile

Add a profile in Windows Terminal settings JSON that points to your built exe.

Example commandline:

- C:\Users\PC\A-term\dist\A-term\A-term.exe

## License

No license file has been added yet.
If you want this repo to be open-source, add a LICENSE file (MIT is a common choice).
