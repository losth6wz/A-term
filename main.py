"""A-term – a minimal terminal emulator built with PySide6 + pywinpty."""

import sys


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
    app = QApplication(sys.argv)
    app.setApplicationName(CFG.window_title)
    app.setStyle("Fusion")

    win = MainWindow()
    win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
 