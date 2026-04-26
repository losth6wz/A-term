"""Terminal view widget (PySide6).

Renders a TerminalBuffer using QPainter and forwards keyboard / mouse
events to a PtyBackend.  All visual and behavioural properties are
driven by the ``CFG`` singleton from config.py.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Dict, Optional, Tuple

from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import (
    QColor, QFont, QFontMetrics, QKeyEvent, QPainter,
    QPaintEvent, QResizeEvent, QWheelEvent, QFocusEvent, QCloseEvent,
)
from PySide6.QtWidgets import QApplication, QWidget

import ansi_parser as _ansi_mod
from ansi_parser import AnsiParser
from config import CFG
from pty_backend import PtyBackend
from terminal_buffer import Cell, TerminalBuffer


# ---------------------------------------------------------------------------
# Keybinding parser
# ---------------------------------------------------------------------------

_KEY_NAMES: Dict[str, Qt.Key] = {
    **{c: getattr(Qt.Key, f"Key_{c}") for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"},
    **{str(n): getattr(Qt.Key, f"Key_{n}") for n in range(10)},
    "Equal":        Qt.Key.Key_Equal,
    "Plus":         Qt.Key.Key_Plus,
    "Minus":        Qt.Key.Key_Minus,
    "Underscore":   Qt.Key.Key_Underscore,
    "Slash":        Qt.Key.Key_Slash,
    "Backslash":    Qt.Key.Key_Backslash,
    "BracketLeft":  Qt.Key.Key_BracketLeft,
    "BracketRight": Qt.Key.Key_BracketRight,
    "Semicolon":    Qt.Key.Key_Semicolon,
    "Apostrophe":   Qt.Key.Key_Apostrophe,
    "Comma":        Qt.Key.Key_Comma,
    "Period":       Qt.Key.Key_Period,
    "Grave":        Qt.Key.Key_QuoteLeft,
    "PageUp":       Qt.Key.Key_PageUp,
    "PageDown":     Qt.Key.Key_PageDown,
    "Home":         Qt.Key.Key_Home,
    "End":          Qt.Key.Key_End,
    "Insert":       Qt.Key.Key_Insert,
    "Delete":       Qt.Key.Key_Delete,
    "Up":           Qt.Key.Key_Up,
    "Down":         Qt.Key.Key_Down,
    "Left":         Qt.Key.Key_Left,
    "Right":        Qt.Key.Key_Right,
    "Space":        Qt.Key.Key_Space,
    "Tab":          Qt.Key.Key_Tab,
    "Return":       Qt.Key.Key_Return,
    "Enter":        Qt.Key.Key_Return,
    "Backspace":    Qt.Key.Key_Backspace,
    "Escape":       Qt.Key.Key_Escape,
    **{f"F{n}": getattr(Qt.Key, f"Key_F{n}") for n in range(1, 13)},
}

_MOD_NAMES: Dict[str, Qt.KeyboardModifier] = {
    "Ctrl":  Qt.KeyboardModifier.ControlModifier,
    "Shift": Qt.KeyboardModifier.ShiftModifier,
    "Alt":   Qt.KeyboardModifier.AltModifier,
    "Meta":  Qt.KeyboardModifier.MetaModifier,
}


def _parse_keybinding(s: str) -> Optional[Tuple]:
    """Parse ``'Ctrl+Shift+C'`` → ``(mods, key)`` or ``None``."""
    if not s.strip():
        return None
    mods = Qt.KeyboardModifier.NoModifier
    key  = None
    for part in s.split("+"):
        part = part.strip()
        if part in _MOD_NAMES:
            mods |= _MOD_NAMES[part]
        elif part in _KEY_NAMES:
            key = _KEY_NAMES[part]
        else:
            return None
    return (mods, key) if key is not None else None


# ---------------------------------------------------------------------------
# VT-100 key maps
# ---------------------------------------------------------------------------

_SPECIAL_KEYS: Dict[Qt.Key, str] = {
    Qt.Key.Key_Return:    "\r",
    Qt.Key.Key_Enter:     "\r",
    Qt.Key.Key_Backspace: "\x7f",
    Qt.Key.Key_Tab:       "\t",
    Qt.Key.Key_Escape:    "\x1b",
    Qt.Key.Key_Delete:    "\x1b[3~",
    Qt.Key.Key_Insert:    "\x1b[2~",
    Qt.Key.Key_Home:      "\x1b[H",
    Qt.Key.Key_End:       "\x1b[F",
    Qt.Key.Key_PageUp:    "\x1b[5~",
    Qt.Key.Key_PageDown:  "\x1b[6~",
    Qt.Key.Key_F1:        "\x1bOP",
    Qt.Key.Key_F2:        "\x1bOQ",
    Qt.Key.Key_F3:        "\x1bOR",
    Qt.Key.Key_F4:        "\x1bOS",
    Qt.Key.Key_F5:        "\x1b[15~",
    Qt.Key.Key_F6:        "\x1b[17~",
    Qt.Key.Key_F7:        "\x1b[18~",
    Qt.Key.Key_F8:        "\x1b[19~",
    Qt.Key.Key_F9:        "\x1b[20~",
    Qt.Key.Key_F10:       "\x1b[21~",
    Qt.Key.Key_F11:       "\x1b[23~",
    Qt.Key.Key_F12:       "\x1b[24~",
}

_ARROW_NORMAL: Dict[Qt.Key, str] = {
    Qt.Key.Key_Up:    "\x1b[A",
    Qt.Key.Key_Down:  "\x1b[B",
    Qt.Key.Key_Right: "\x1b[C",
    Qt.Key.Key_Left:  "\x1b[D",
}

_ARROW_APP: Dict[Qt.Key, str] = {
    Qt.Key.Key_Up:    "\x1bOA",
    Qt.Key.Key_Down:  "\x1bOB",
    Qt.Key.Key_Right: "\x1bOC",
    Qt.Key.Key_Left:  "\x1bOD",
}


# ---------------------------------------------------------------------------
# Style run helper
# ---------------------------------------------------------------------------

def _same_style(a: Cell, b: Cell) -> bool:
    aa, ba = a.attrs, b.attrs
    return (
        aa.fg == ba.fg and aa.bg == ba.bg
        and aa.bold == ba.bold and aa.italic == ba.italic
        and aa.underline == ba.underline and aa.reverse == ba.reverse
        and aa.hidden == ba.hidden and aa.strikethrough == ba.strikethrough
    )


# ---------------------------------------------------------------------------
# TerminalView
# ---------------------------------------------------------------------------

class TerminalView(QWidget):
    """Widget that renders a TerminalBuffer and drives a PtyBackend."""

    _data_arrived = Signal(str)
    _proc_exited  = Signal()
    title_changed = Signal(str)

    def __init__(self, shell=None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        # Apply config palette to ANSI parser before any output is parsed
        _ansi_mod.set_palette(CFG.palette_16())

        # ---- Configurable colours ----
        self._fg_color     = QColor(CFG.fg)
        self._bg_color     = QColor(CFG.bg)
        self._cursor_color = QColor(CFG.cursor_color)
        self._cursor_text  = QColor(CFG.cursor_text_color)

        # ---- Configurable behaviour ----
        self._pad          = CFG.padding
        self._cursor_style = CFG.cursor_style   # "block" | "underline" | "beam"
        self._scroll_speed = CFG.scroll_speed

        # ---- Font ----
        self._font_size_default = CFG.font_size
        self._font_size         = CFG.font_size
        self._font_family       = CFG.font_family
        self._font = self._make_font(self._font_size)
        self._font_cache: Dict[Tuple[bool, bool, bool, bool], QFont] = {}
        self._rebuild_metrics()

        # ---- Initial terminal size ----
        init_cols = max(10, (960 - 2 * self._pad) // self._cell_w)
        init_rows = max(5,  (640 - 2 * self._pad) // self._cell_h)

        # ---- Core objects ----
        self._buffer  = TerminalBuffer(init_cols, init_rows,
                                       max_history=CFG.scrollback_lines)
        self._parser  = AnsiParser()
        self._backend = PtyBackend(init_cols, init_rows)

        self._scroll_offset: int = 0

        # ---- Cursor blink ----
        self._cursor_on = True
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._blink_tick)
        if CFG.cursor_blink:
            self._blink_timer.start(CFG.cursor_blink_rate)

        # ---- Parse keybindings ----
        self._kb: Dict[str, Optional[Tuple]] = {
            name: _parse_keybinding(CFG.keybinding(name))
            for name in (
                "copy", "paste", "increase_font", "decrease_font",
                "reset_font", "scroll_up", "scroll_down",
                "clear_screen", "new_window",
            )
        }

        # ---- Qt widget setup ----
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(200, 100)

        # ---- Wire signals ----
        self._data_arrived.connect(self._on_data_slot)
        self._proc_exited.connect(self._on_exit_slot)

        # ---- Start PTY ----
        self._backend.on_data = lambda d: self._data_arrived.emit(d)
        self._backend.on_exit = lambda: self._proc_exited.emit()
        self._backend.start(shell)

    # ------------------------------------------------------------------
    # Font helpers
    # ------------------------------------------------------------------

    def _make_font(self, size: int) -> QFont:
        f = QFont(self._font_family, size)
        f.setStyleHint(QFont.StyleHint.Monospace)
        return f

    def _rebuild_metrics(self) -> None:
        fm = QFontMetrics(self._font)
        self._cell_w: int = fm.horizontalAdvance("W")
        self._cell_h: int = fm.height()
        self._ascent: int = fm.ascent()
        if hasattr(self, "_font_cache"):
            self._font_cache.clear()

    def _resize_font(self, delta: int) -> None:
        self._font_size = max(6, min(72, self._font_size + delta))
        self._font = self._make_font(self._font_size)
        self._rebuild_metrics()
        self.resizeEvent(None)
        self.update()

    def _get_font(self, bold: bool, italic: bool,
                  underline: bool, strikethrough: bool) -> QFont:
        key = (bold, italic, underline, strikethrough)
        if key not in self._font_cache:
            f = QFont(self._font)
            f.setBold(bold); f.setItalic(italic)
            f.setUnderline(underline); f.setStrikeOut(strikethrough)
            self._font_cache[key] = f
        return self._font_cache[key]

    # ------------------------------------------------------------------
    # Keybinding match
    # ------------------------------------------------------------------

    def _is_kb(self, name: str, mods: Qt.KeyboardModifier,
               key: Qt.Key) -> bool:
        parsed = self._kb.get(name)
        return parsed is not None and parsed == (mods, key)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @Slot(str)
    def _on_data_slot(self, data: str) -> None:
        self._parser.feed(data, self._buffer)
        if self._buffer.title:
            self.title_changed.emit(self._buffer.title)
        self._scroll_offset = 0
        self.update()

    @Slot()
    def _on_exit_slot(self) -> None:
        self._blink_timer.stop()
        self.update()

    @Slot()
    def _blink_tick(self) -> None:
        self._cursor_on = not self._cursor_on
        self.update()

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        buf     = self._buffer
        history = buf.history
        screen  = buf.screen

        all_lines = history + screen
        total     = len(all_lines)
        n_rows    = buf.rows
        start     = max(0, total - n_rows - self._scroll_offset)
        visible   = all_lines[start:start + n_rows]

        pad = self._pad
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._bg_color)

        cw, ch, asc = self._cell_w, self._cell_h, self._ascent

        for row_idx, line in enumerate(visible):
            y     = pad + row_idx * ch
            n_col = min(len(line), buf.cols)
            col   = 0
            while col < n_col:
                run_start = col
                cell0     = line[col]
                col      += 1
                while col < n_col and _same_style(line[col], cell0):
                    col += 1

                run_cells = line[run_start:col]
                attrs     = cell0.attrs

                fg = QColor(*attrs.fg) if attrs.fg else QColor(self._fg_color)
                bg = QColor(*attrs.bg) if attrs.bg else QColor(self._bg_color)

                if attrs.dim:
                    fg = QColor(fg.red() // 2, fg.green() // 2, fg.blue() // 2)
                if attrs.reverse:
                    fg, bg = bg, fg

                run_w = len(run_cells) * cw
                x0    = pad + run_start * cw

                if bg != self._bg_color:
                    painter.fillRect(x0, y, run_w, ch, bg)

                if not attrs.hidden:
                    text = "".join(c.char for c in run_cells)
                    if text.strip():
                        painter.setFont(self._get_font(
                            attrs.bold, attrs.italic,
                            attrs.underline, attrs.strikethrough,
                        ))
                        painter.setPen(fg)
                        painter.drawText(x0, y + asc, text)

        # ---- Cursor ----
        if self._scroll_offset == 0 and buf.cursor_visible \
                and self._cursor_on and self.hasFocus():
            cx    = pad + buf.cursor_col * cw
            cy    = pad + buf.cursor_row * ch
            style = self._cursor_style

            if style == "block":
                painter.fillRect(cx, cy, cw, ch, self._cursor_color)
                if buf.cursor_row < len(screen) \
                        and buf.cursor_col < len(screen[buf.cursor_row]):
                    ch_char = screen[buf.cursor_row][buf.cursor_col].char
                    if ch_char and ch_char != " ":
                        painter.setFont(self._font)
                        painter.setPen(self._cursor_text)
                        painter.drawText(cx, cy + asc, ch_char)
            elif style == "underline":
                bar_h = max(2, ch // 8)
                painter.fillRect(cx, cy + ch - bar_h, cw, bar_h,
                                 self._cursor_color)
            elif style == "beam":
                bar_w = max(2, cw // 6)
                painter.fillRect(cx, cy, bar_w, ch, self._cursor_color)

        painter.end()

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        self._scroll_offset = 0
        self._cursor_on     = True
        if CFG.cursor_blink:
            self._blink_timer.start(CFG.cursor_blink_rate)

        key  = event.key()
        mods = event.modifiers()

        # ---- Config keybindings ----
        if self._is_kb("paste", mods, key):
            text = QApplication.clipboard().text()
            if text:
                self._backend.write(text)
            return
        if self._is_kb("copy", mods, key):
            return  # selection not yet implemented
        if self._is_kb("increase_font", mods, key):
            self._resize_font(+1); return
        if self._is_kb("decrease_font", mods, key):
            self._resize_font(-1); return
        if self._is_kb("reset_font", mods, key):
            self._font_size = self._font_size_default
            self._font = self._make_font(self._font_size)
            self._rebuild_metrics()
            self.resizeEvent(None)
            self.update()
            return
        if self._is_kb("scroll_up", mods, key):
            max_off = len(self._buffer.history)
            self._scroll_offset = min(max_off,
                                      self._scroll_offset + self._buffer.rows)
            self.update(); return
        if self._is_kb("scroll_down", mods, key):
            self._scroll_offset = max(0,
                                      self._scroll_offset - self._buffer.rows)
            self.update(); return
        if self._is_kb("clear_screen", mods, key):
            self._backend.write("\x0c"); return
        if self._is_kb("new_window", mods, key):
            if getattr(sys, "frozen", False):
                cmd = [sys.executable]
            else:
                cmd = [sys.executable,
                       os.path.join(os.path.dirname(__file__), "main.py")]
            subprocess.Popen(
                cmd,
                creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
            )
            return

        # ---- Ctrl+letter → ASCII control ----
        ctrl  = bool(mods & Qt.KeyboardModifier.ControlModifier)
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)

        if ctrl and not shift:
            if Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
                self._backend.write(chr(key - Qt.Key.Key_A + 1)); return
            if key == Qt.Key.Key_BracketLeft:
                self._backend.write("\x1b"); return
            if key == Qt.Key.Key_Backslash:
                self._backend.write("\x1c"); return
            if key == Qt.Key.Key_BracketRight:
                self._backend.write("\x1d"); return
            if key == Qt.Key.Key_6:
                self._backend.write("\x1e"); return

        # ---- Arrow keys ----
        arrow_map = (_ARROW_APP if self._buffer.application_cursor_keys
                     else _ARROW_NORMAL)
        if key in arrow_map:
            self._backend.write(arrow_map[key]); return

        # ---- Special keys ----
        if key in _SPECIAL_KEYS:
            self._backend.write(_SPECIAL_KEYS[key]); return

        # ---- Printable text ----
        text = event.text()
        if text:
            self._backend.write(text)

    # ------------------------------------------------------------------
    # Mouse wheel – scrollback
    # ------------------------------------------------------------------

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        delta   = event.angleDelta().y()
        lines   = (delta // 120) * self._scroll_speed
        max_off = len(self._buffer.history)
        self._scroll_offset = max(0, min(max_off, self._scroll_offset + lines))
        self.update()

    # ------------------------------------------------------------------
    # Resize
    # ------------------------------------------------------------------

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:  # noqa: N802
        if event is not None:
            super().resizeEvent(event)
        usable_w = self.width()  - 2 * self._pad
        usable_h = self.height() - 2 * self._pad
        cols = max(10, usable_w // self._cell_w)
        rows = max(5,  usable_h // self._cell_h)
        if cols != self._buffer.cols or rows != self._buffer.rows:
            self._buffer.resize(cols, rows)
            self._backend.resize(cols, rows)

    # ------------------------------------------------------------------
    # Focus
    # ------------------------------------------------------------------

    def focusInEvent(self, event: QFocusEvent) -> None:  # noqa: N802
        if CFG.cursor_blink:
            self._blink_timer.start(CFG.cursor_blink_rate)
        self.update()

    def focusOutEvent(self, event: QFocusEvent) -> None:  # noqa: N802
        self._cursor_on = True
        self.update()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def shutdown(self) -> None:
        self._blink_timer.stop()
        self._backend.close()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self.shutdown()
        super().closeEvent(event)

