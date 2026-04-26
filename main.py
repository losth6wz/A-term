"""A-term – a minimal terminal emulator built with PySide6 + pywinpty."""

import os
import sys
from pathlib import Path


def _is_shell_mode(argv: list[str]) -> bool:
    return "--aterm-shell" in argv


if _is_shell_mode(sys.argv):
    from shell import main as _shell_main

    if __name__ == "__main__":
        _shell_main()
        raise SystemExit(0)

from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtGui import QIcon

from config import CFG
from terminal_view import TerminalView
from wt_profile import ensure_windows_terminal_profile


def _resolve_icon_path() -> Path | None:
    """Find an icon path from config or known default locations."""
    candidates: list[Path] = []

    if CFG.window_icon:
        candidates.append(Path(CFG.window_icon).expanduser())

    appdata = Path(os.environ.get("APPDATA", "")).expanduser() / "A-term"

    base = Path(__file__).resolve().parent
    candidates.extend(
        [
            base / "assets" / "icon.ico",
            base / "assets" / "icon.png",
            base / "icon.ico",
            base / "icon.png",
            appdata / "icon.ico",
            appdata / "icon.png",
            appdata / "icon.jpg",
            appdata / "icon.jpeg",
        ]
    )

    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable))

    for c in candidates:
        if c.exists() and c.is_file():
            return c
    return None


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(CFG.window_title)
        self.resize(CFG.window_width, CFG.window_height)
        self.setWindowOpacity(CFG.window_opacity)

        self._view = TerminalView(parent=self)
        self.setCentralWidget(self._view)

        self._view.title_changed.connect(self._on_title_changed)

    def _on_title_changed(self, title: str) -> None:
        if title:
            self.setWindowTitle(f"{CFG.window_title} – {title}")

    def closeEvent(self, event) -> None:  # noqa: N802
        self._view.shutdown()
        super().closeEvent(event)


def main() -> None:
    # Ensure Windows Terminal can discover A-term via profile fragments.
    try:
        ensure_windows_terminal_profile()
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName(CFG.window_title)
    app.setStyle("Fusion")

    icon_path = _resolve_icon_path()
    if icon_path is not None:
        icon = QIcon(str(icon_path))
        if not icon.isNull():
            app.setWindowIcon(icon)

    win = MainWindow()
    if icon_path is not None:
        icon = QIcon(str(icon_path))
        if not icon.isNull():
            win.setWindowIcon(icon)
    win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
 