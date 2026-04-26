"""A-term custom shell.

This is the interactive shell process that runs inside the PTY.
It is intentionally standalone — no MS shell involvement at all.
"""

from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import sys
from typing import Any

import aterm_cmd as _aterm_cmd_mod
import plugins as _plugins

from config import CFG


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_last_status: int = 0   # exit code of the last command


def _git_branch() -> str:
    """Return ' (branch[*])' if inside a git repo, else empty string."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=1,
        )
        branch = result.stdout.strip()
        if not branch or branch == "HEAD":
            return ""
        dirty = ""
        if CFG.prompt_git_dirty:
            d = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True, text=True, timeout=1,
            )
            dirty = CFG.prompt_git_dirty if d.stdout.strip() else ""
        return f" ({branch}{dirty})"
    except Exception:
        return ""


_TOKEN_RE = re.compile(r"\{(fg|bg):#([0-9A-Fa-f]{6})\}|\{([^}]+)\}")


def _render_prompt(fmt: str) -> str:
    """Expand format tokens to ANSI escape codes."""
    cwd  = os.getcwd().replace("\\", "/")
    home = os.path.expanduser("~").replace("\\", "/")
    cwd_short = ("~" + cwd[len(home):]) if cwd.lower().startswith(home.lower()) else cwd
    user = os.environ.get("USERNAME", os.environ.get("USER", "user"))
    host = socket.gethostname()
    git  = _git_branch() if CFG.prompt_show_git else ""
    status_str = (
        f"\x1b[1;32m{_last_status}\x1b[0m"
        if _last_status == 0
        else f"\x1b[1;31m{_last_status}\x1b[0m"
    )

    simple = {
        "user":      user,
        "host":      host,
        "cwd":       cwd,
        "cwd_short": cwd_short,
        "git_branch": git,
        "status":    status_str,
        "sep":       CFG.prompt_separator,
        "newline":   "\n",
        "bold":      "\x1b[1m",
        "dim":       "\x1b[2m",
        "italic":    "\x1b[3m",
        "underline": "\x1b[4m",
        "reset":     "\x1b[0m",
    }

    def _replace(m: re.Match) -> str:
        if m.group(1) == "fg":
            r, g, b = int(m.group(2)[0:2], 16), int(m.group(2)[2:4], 16), int(m.group(2)[4:6], 16)
            return f"\x1b[38;2;{r};{g};{b}m"
        if m.group(1) == "bg":
            r, g, b = int(m.group(2)[0:2], 16), int(m.group(2)[2:4], 16), int(m.group(2)[4:6], 16)
            return f"\x1b[48;2;{r};{g};{b}m"
        token = m.group(3)
        return simple.get(token, m.group(0))

    return _TOKEN_RE.sub(_replace, fmt)


def _prompt() -> str:
    return _render_prompt(CFG.prompt_format)


# ---------------------------------------------------------------------------
# Built-in commands
# ---------------------------------------------------------------------------

_history: list[str] = []
_ALIASES: dict[str, str] = {}


class _NullWriter:
    """Writable stream fallback used when no real stdout/stderr exists."""

    def write(self, _text: str) -> int:
        return 0

    def flush(self) -> None:
        return


class _NullReader:
    """Readable stream fallback used when no real stdin exists."""

    def readline(self) -> str:
        return ""


def _prepare_output_stream(stream: Any, fd: int) -> Any:
    """Return a line-buffered text stream, even in windowed/frozen builds."""
    if stream is not None:
        try:
            return os.fdopen(os.dup(stream.fileno()), "w", buffering=1, encoding="utf-8", errors="replace")
        except Exception:
            return stream

    fallback_std = sys.__stdout__ if fd == 1 else sys.__stderr__
    if fallback_std is not None:
        try:
            return os.fdopen(os.dup(fallback_std.fileno()), "w", buffering=1, encoding="utf-8", errors="replace")
        except Exception:
            return fallback_std

    try:
        return os.fdopen(os.dup(fd), "w", buffering=1, encoding="utf-8", errors="replace")
    except Exception:
        return _NullWriter()


def _prepare_input_stream(stream: Any) -> Any:
    """Return a valid readable stream; fallback to fd 0 then a null reader."""
    if stream is not None:
        return stream

    if sys.__stdin__ is not None:
        try:
            return os.fdopen(os.dup(sys.__stdin__.fileno()), "r", buffering=1, encoding="utf-8", errors="replace")
        except Exception:
            return sys.__stdin__

    try:
        return os.fdopen(os.dup(0), "r", buffering=1, encoding="utf-8", errors="replace")
    except Exception:
        return _NullReader()


def _builtin_cd(args: list[str]) -> None:
    target = args[0] if args else os.path.expanduser("~")
    target = os.path.expandvars(os.path.expanduser(target))
    try:
        os.chdir(target)
    except FileNotFoundError:
        _err(f"cd: {target}: no such directory")
    except NotADirectoryError:
        _err(f"cd: {target}: not a directory")
    except PermissionError:
        _err(f"cd: {target}: permission denied")


def _builtin_ls(args: list[str]) -> None:
    path = args[0] if args else "."
    try:
        entries = sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name.lower()))
    except (FileNotFoundError, NotADirectoryError, PermissionError) as exc:
        _err(f"ls: {exc}")
        return

    items = []
    for entry in entries:
        name = entry.name
        if entry.is_dir():
            items.append(f"\x1b[1;34m{name}/\x1b[0m")
        elif entry.is_symlink():
            items.append(f"\x1b[1;36m{name}\x1b[0m")
        elif os.access(entry.path, os.X_OK):
            items.append(f"\x1b[1;32m{name}\x1b[0m")
        else:
            items.append(name)

    # Print in columns
    if not items:
        return
    plain = [os.scandir.__class__.__name__]  # just for width ref
    max_len = max(len(e.name) for e in entries) + 2
    cols = max(1, 80 // max_len)
    for i, item in enumerate(items):
        end = "\n" if (i + 1) % cols == 0 or i == len(items) - 1 else "  "
        sys.stdout.write(item + end)
    sys.stdout.flush()


def _builtin_pwd(_args: list[str]) -> None:
    print(os.getcwd().replace("\\", "/"))


def _builtin_echo(args: list[str]) -> None:
    print(" ".join(args))


def _builtin_clear(_args: list[str]) -> None:
    sys.stdout.write("\x1b[2J\x1b[H")
    sys.stdout.flush()


def _builtin_history(_args: list[str]) -> None:
    for i, cmd in enumerate(_history, 1):
        print(f"  {i:4}  {cmd}")


def _builtin_env(args: list[str]) -> None:
    if args:
        # env VAR=VALUE cmd …
        # simple: just print if only VAR given
        for a in args:
            if "=" in a:
                k, _, v = a.partition("=")
                os.environ[k] = v
            else:
                print(os.environ.get(a, ""))
    else:
        for k, v in sorted(os.environ.items()):
            print(f"{k}={v}")


def _builtin_which(args: list[str]) -> None:
    for name in args:
        path = shutil.which(name)
        if path:
            print(path)
        else:
            _err(f"which: {name}: not found")


def _builtin_mkdir(args: list[str]) -> None:
    for d in args:
        try:
            os.makedirs(d, exist_ok=True)
        except OSError as exc:
            _err(f"mkdir: {exc}")


def _builtin_rmdir(args: list[str]) -> None:
    for d in args:
        try:
            os.rmdir(d)
        except OSError as exc:
            _err(f"rmdir: {exc}")


def _builtin_rm(args: list[str]) -> None:
    recursive = "-r" in args or "-rf" in args or "-fr" in args
    targets   = [a for a in args if not a.startswith("-")]
    import shutil as _sh
    for t in targets:
        try:
            if os.path.isdir(t):
                if recursive:
                    _sh.rmtree(t)
                else:
                    _err(f"rm: {t}: is a directory (use -r)")
            else:
                os.remove(t)
        except OSError as exc:
            _err(f"rm: {exc}")


def _builtin_cp(args: list[str]) -> None:
    import shutil as _sh
    if len(args) < 2:
        _err("cp: usage: cp <src> <dst>"); return
    try:
        _sh.copy2(args[0], args[1])
    except OSError as exc:
        _err(f"cp: {exc}")


def _builtin_mv(args: list[str]) -> None:
    import shutil as _sh
    if len(args) < 2:
        _err("mv: usage: mv <src> <dst>"); return
    try:
        _sh.move(args[0], args[1])
    except OSError as exc:
        _err(f"mv: {exc}")


def _builtin_cat(args: list[str]) -> None:
    for path in args:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                sys.stdout.write(f.read())
        except OSError as exc:
            _err(f"cat: {exc}")
    sys.stdout.flush()


def _builtin_exit(args: list[str]) -> None:
    code = int(args[0]) if args and args[0].isdigit() else 0
    sys.exit(code)


def _builtin_help(_args: list[str]) -> None:
    print(
        "\x1b[1;35mA-term shell built-ins\x1b[0m\n"
        "  cd [dir]          change directory\n"
        "  ls [dir]          list files\n"
        "  pwd               print working directory\n"
        "  echo [text]       print text\n"
        "  cat <file>        print file contents\n"
        "  cp <src> <dst>    copy file\n"
        "  mv <src> <dst>    move/rename\n"
        "  mkdir <dir>       create directory\n"
        "  rmdir <dir>       remove empty directory\n"
        "  rm [-r] <path>    remove file or directory\n"
        "  env [VAR[=VAL]]   show/set environment variables\n"
        "  which <cmd>       locate a command\n"
        "  history           show command history\n"
        "  clear / cls       clear screen\n"
        "  help              show this message\n"
        "  exit [code]       exit the shell\n"
        "\nAny other input is run as an external executable.\n"
        "\n\x1b[1;35mPlugins\x1b[0m\n"
        "  Drop a .py file in %APPDATA%\\A-term\\plugins\\\n"
        "  It is loaded automatically on next shell start.\n"
        "  Run 'aterm plugin list' to see loaded plugins.\n"
        "  Run 'aterm plugin new <name>' to scaffold a new one."
    )


_BUILTINS = {
    "cd":      _builtin_cd,
    "ls":      _builtin_ls,
    "dir":     _builtin_ls,
    "pwd":     _builtin_pwd,
    "echo":    _builtin_echo,
    "clear":   _builtin_clear,
    "cls":     _builtin_clear,
    "history": _builtin_history,
    "env":     _builtin_env,
    "set":     _builtin_env,
    "which":   _builtin_which,
    "where":   _builtin_which,
    "mkdir":   _builtin_mkdir,
    "rmdir":   _builtin_rmdir,
    "rm":      _builtin_rm,
    "del":     _builtin_rm,
    "cp":      _builtin_cp,
    "copy":    _builtin_cp,
    "mv":      _builtin_mv,
    "move":    _builtin_mv,
    "cat":     _builtin_cat,
    "type":    _builtin_cat,
    "help":    _builtin_help,
    "exit":    _builtin_exit,
    "quit":    _builtin_exit,
    "aterm":   lambda args: _aterm_cmd_mod.run(args),
}


# ---------------------------------------------------------------------------
# External command execution
# ---------------------------------------------------------------------------

def _run_external(parts: list[str]) -> int:
    """Run an external command; return its exit code."""
    exe = shutil.which(parts[0])
    if exe is None:
        _err(f"{parts[0]}: command not found")
        return 127
    try:
        result = subprocess.run([exe] + parts[1:], env=os.environ)
        return result.returncode
    except KeyboardInterrupt:
        print()
        return 130
    except OSError as exc:
        _err(f"{parts[0]}: {exc}")
        return 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _err(msg: str) -> None:
    text = f"\x1b[1;31m{msg}\x1b[0m\n"
    stream = getattr(sys, "stderr", None) or getattr(sys, "stdout", None)
    if stream is None:
        return
    try:
        stream.write(text)
        stream.flush()
    except Exception:
        return


def _parse(line: str) -> list[str]:
    """Very simple tokeniser: handles single/double quotes and $VAR expansion."""
    tokens: list[str] = []
    current = ""
    i, n = 0, len(line)
    while i < n:
        ch = line[i]
        if ch in (" ", "\t"):
            if current:
                tokens.append(current)
                current = ""
        elif ch == "'":
            i += 1
            while i < n and line[i] != "'":
                current += line[i]
                i += 1
        elif ch == '"':
            i += 1
            while i < n and line[i] != '"':
                if line[i] == "$" and i + 1 < n:
                    i += 1
                    var, i = _read_var(line, i)
                    current += os.environ.get(var, "")
                    continue
                current += line[i]
                i += 1
        elif ch == "$":
            i += 1
            var, i = _read_var(line, i)
            current += os.environ.get(var, "")
            continue
        elif ch == "#":
            break   # comment
        else:
            current += ch
        i += 1
    if current:
        tokens.append(current)
    return tokens


def _read_var(line: str, i: int):
    """Read a variable name starting at i; return (name, new_i)."""
    start = i
    while i < len(line) and (line[i].isalnum() or line[i] == "_"):
        i += 1
    return line[start:i], i


# ---------------------------------------------------------------------------
# REPL
# ---------------------------------------------------------------------------

def main() -> None:
    global _last_status

    # Make stdio robust in --windowed/frozen builds where streams may be None.
    sys.stdin = _prepare_input_stream(sys.stdin)
    sys.stdout = _prepare_output_stream(sys.stdout, 1)
    sys.stderr = _prepare_output_stream(sys.stderr, 2)

    # Apply extra environment variables from config
    for k, v in CFG.extra_env().items():
        os.environ[k] = v

    # Load aliases from config
    global _ALIASES
    _ALIASES = CFG.aliases()

    # Load plugins — must happen before the REPL so user commands are available
    _plugins.load_plugins(_BUILTINS, _ALIASES)

    if CFG.shell_banner:
        print(
            "\x1b[1;35m"
            "    _        _                     \n"
            "   / \\      | |_ ___ _ __ _ __ ___  \n"
            "  / _ \\ ____| __/ _ \\ '__| '_ ` _ \\ \n"
            " / ___ \\_____| ||  __/ |  | | | | | |\n"
            "/_/   \\_\\     \\__\\___|_|  |_| |_| |_|\x1b[0m\n"
            "\n"
            "\x1b[90mType \x1b[1;32mhelp\x1b[0;90m for built-in commands."
            "  Type \x1b[1;32mexit\x1b[0;90m to quit.\x1b[0m\n"
        )

    # Run startup command if configured
    startup = CFG.shell_startup_cmd.strip()
    if startup:
        parts = _parse(startup)
        if parts:
            _last_status = _dispatch(parts)

    history_size = CFG.shell_history_size

    while True:
        try:
            sys.stdout.write(_prompt())
            sys.stdout.flush()
            try:
                line = sys.stdin.readline()
            except KeyboardInterrupt:
                sys.stdout.write("\n")
                continue

            if not line:   # EOF
                break

            line = line.rstrip("\r\n")
            if not line.strip():
                continue

            _history.append(line)
            if history_size and len(_history) > history_size:
                _history.pop(0)

            parts = _parse(line.strip())
            if parts:
                _last_status = _dispatch(parts)

        except SystemExit as exc:
            sys.exit(exc.code)
        except Exception as exc:
            _err(f"shell: {exc}")


def _dispatch(parts: list[str]) -> int:
    """Expand aliases then run built-in or external command."""
    # Alias expansion (single level)
    if parts[0] in _ALIASES:
        expanded = _parse(_ALIASES[parts[0]])
        if expanded:
            parts = expanded + parts[1:]

    cmd  = parts[0].lower()
    args = parts[1:]

    if cmd in _BUILTINS:
        try:
            _BUILTINS[cmd](args)
            return 0
        except SystemExit:
            raise
        except Exception as exc:
            _err(str(exc))
            return 1
    else:
        return _run_external(parts)


if __name__ == "__main__":
    main()
