"""PTY backend using pywinpty.

Spawns a shell in a Windows pseudo-console and provides thread-safe
read/write access.  Output is delivered via the *on_data* callback,
which is called from a background daemon thread – connect it to a
Qt signal so the UI update happens on the main thread.
"""

from __future__ import annotations

import os
import sys
import threading
from typing import Callable, List, Optional, Union


def _find_shell() -> list[str]:
    """Return the command list for our custom shell."""
    if getattr(sys, "frozen", False):
        # Frozen app: the shell entrypoint is exposed via a CLI flag.
        return [sys.executable, "--aterm-shell"]

    here = os.path.dirname(os.path.abspath(__file__))
    main_script = os.path.join(here, "main.py")
    return [sys.executable, main_script, "--aterm-shell"]


class PtyBackend:
    """Wraps a ``winpty.PtyProcess`` with a background reader thread."""

    def __init__(self, cols: int = 80, rows: int = 24) -> None:
        self.cols: int = cols
        self.rows: int = rows

        self._proc    = None
        self._thread: Optional[threading.Thread] = None
        self._lock    = threading.Lock()

        # Callbacks – set before calling start()
        self.on_data: Optional[Callable[[str], None]] = None
        self.on_exit: Optional[Callable[[], None]]    = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, shell: Union[str, List[str], None] = None) -> None:
        """Spawn the custom shell in a PTY."""
        from winpty import PtyProcess  # pywinpty ≥ 2.x

        if shell is None:
            cmd = _find_shell()
        elif isinstance(shell, str):
            cmd = [shell]
        else:
            cmd = shell

        self._proc = PtyProcess.spawn(
            cmd,
            dimensions=(self.rows, self.cols),
            env=dict(os.environ),
        )

        self._thread = threading.Thread(
            target=self._read_loop, name="pty-reader", daemon=True
        )
        self._thread.start()

    # Winpty sends these sequences during ConPTY initialisation.
    # We don't support Win32 input mode or focus events, so disable them
    # immediately to ensure normal raw-character keyboard input works.
    _WINPTY_DISABLE: dict = {
        "\x1b[?9001h": "\x1b[?9001l",  # Win32 input mode  → disable
        "\x1b[?1004h": "\x1b[?1004l",  # Focus-event mode  → disable
    }

    def _read_loop(self) -> None:
        """Background thread: read PTY output and forward to *on_data*."""
        while True:
            try:
                data: str = self._proc.read(4096)
            except EOFError:
                break
            except Exception:
                break

            if data:
                # Auto-disable winpty modes we don't support so that
                # ordinary raw-character writes reach the shell's stdin.
                for seq, response in self._WINPTY_DISABLE.items():
                    if seq in data:
                        try:
                            self._proc.write(response)
                        except Exception:
                            pass

                if self.on_data:
                    try:
                        self.on_data(data)
                    except Exception:
                        pass
            else:
                # Empty read usually means the process has exited
                if not self._proc.isalive():
                    break

        if self.on_exit:
            try:
                self.on_exit()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------

    def write(self, data: str) -> None:
        """Send *data* to the PTY (safe to call from any thread)."""
        with self._lock:
            if self._proc is not None and self._proc.isalive():
                try:
                    self._proc.write(data)
                except Exception:
                    pass

    def resize(self, cols: int, rows: int) -> None:
        """Notify the PTY of a terminal resize."""
        self.cols, self.rows = cols, rows
        with self._lock:
            if self._proc is not None and self._proc.isalive():
                try:
                    self._proc.setwinsize(rows, cols)
                except Exception:
                    pass

    def close(self) -> None:
        """Terminate the child process."""
        with self._lock:
            if self._proc is not None:
                try:
                    self._proc.terminate()
                except Exception:
                    pass
                self._proc = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_alive(self) -> bool:
        with self._lock:
            return self._proc is not None and self._proc.isalive()
