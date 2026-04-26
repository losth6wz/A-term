"""Terminal screen buffer.

Maintains a 2-D grid of Cell objects (the active screen) plus a scrollback
history list.  All cursor and screen-manipulation operations live here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# ---------------------------------------------------------------------------
# Cell attributes
# ---------------------------------------------------------------------------

Color = Tuple[int, int, int]   # (R, G, B)


@dataclass
class TextAttrs:
    bold:          bool                 = False
    dim:           bool                 = False
    italic:        bool                 = False
    underline:     bool                 = False
    blink:         bool                 = False
    reverse:       bool                 = False
    hidden:        bool                 = False
    strikethrough: bool                 = False
    fg:            Optional[Color]      = None   # None → theme default
    bg:            Optional[Color]      = None   # None → theme default

    def reset(self) -> None:
        self.bold = self.dim = self.italic = self.underline = False
        self.blink = self.reverse = self.hidden = self.strikethrough = False
        self.fg = self.bg = None

    def copy(self) -> "TextAttrs":
        return TextAttrs(
            bold=self.bold, dim=self.dim, italic=self.italic,
            underline=self.underline, blink=self.blink,
            reverse=self.reverse, hidden=self.hidden,
            strikethrough=self.strikethrough,
            fg=self.fg, bg=self.bg,
        )


@dataclass
class Cell:
    char:  str       = " "
    attrs: TextAttrs = field(default_factory=TextAttrs)

    def copy(self) -> "Cell":
        return Cell(char=self.char, attrs=self.attrs.copy())


# ---------------------------------------------------------------------------
# Terminal buffer
# ---------------------------------------------------------------------------

class TerminalBuffer:
    """Holds the terminal screen and scrollback history."""

    MAX_HISTORY = 10_000

    def __init__(self, cols: int = 80, rows: int = 24,
                 max_history: int = 10_000) -> None:
        self.cols: int = cols
        self.rows: int = rows
        self.MAX_HISTORY = max_history

        # Cursor
        self.cursor_row: int  = 0
        self.cursor_col: int  = 0
        self.cursor_visible:  bool = True

        # Current drawing attributes
        self.current_attrs: TextAttrs = TextAttrs()

        # Modes
        self.insert_mode:            bool = False
        self.application_cursor_keys: bool = False

        # Scroll region (0-based, inclusive)
        self._scroll_top: int = 0
        self._scroll_bot: int = rows - 1

        # Screens
        self.history: List[List[Cell]] = []
        self.screen:  List[List[Cell]] = self._make_screen(cols, rows)

        # Alternate screen
        self._alt_screen:  Optional[List[List[Cell]]] = None
        self._alt_cursor:  Tuple[int, int]            = (0, 0)
        self._in_alt:      bool                       = False

        # Saved cursor / attrs
        self._saved_cursor: Tuple[int, int] = (0, 0)
        self._saved_attrs:  TextAttrs       = TextAttrs()

        # Window title (updated by OSC sequences)
        self.title: str = ""

    # ------------------------------------------------------------------
    # Screen construction helpers
    # ------------------------------------------------------------------

    def _blank_cell(self) -> Cell:
        """Return a blank cell with the *current* background colour."""
        attrs = TextAttrs(bg=self.current_attrs.bg)
        return Cell(char=" ", attrs=attrs)

    def _make_row(self, cols: int) -> List[Cell]:
        return [Cell() for _ in range(cols)]

    def _make_screen(self, cols: int, rows: int) -> List[List[Cell]]:
        return [self._make_row(cols) for _ in range(rows)]

    # ------------------------------------------------------------------
    # Cursor movement
    # ------------------------------------------------------------------

    def cursor_up(self, n: int) -> None:
        self.cursor_row = max(self._scroll_top, self.cursor_row - n)

    def cursor_down(self, n: int) -> None:
        self.cursor_row = min(self._scroll_bot, self.cursor_row + n)

    def cursor_forward(self, n: int) -> None:
        self.cursor_col = min(self.cols - 1, self.cursor_col + n)

    def cursor_back(self, n: int) -> None:
        self.cursor_col = max(0, self.cursor_col - n)

    def cursor_to(self, row: int, col: int) -> None:
        self.cursor_row = max(0, min(self.rows - 1, row))
        self.cursor_col = max(0, min(self.cols - 1, col))

    def carriage_return(self) -> None:
        self.cursor_col = 0

    def backspace(self) -> None:
        if self.cursor_col > 0:
            self.cursor_col -= 1

    def tab(self) -> None:
        next_stop = ((self.cursor_col // 8) + 1) * 8
        self.cursor_col = min(self.cols - 1, next_stop)

    def back_tab(self) -> None:
        prev_stop = ((self.cursor_col - 1) // 8) * 8
        self.cursor_col = max(0, prev_stop)

    # ------------------------------------------------------------------
    # Newline / index
    # ------------------------------------------------------------------

    def newline(self) -> None:
        """LF: move down, scrolling the scroll region if at the bottom."""
        if self.cursor_row == self._scroll_bot:
            self.scroll_up(1)
        elif self.cursor_row < self.rows - 1:
            self.cursor_row += 1

    def index(self) -> None:
        """ESC D – same as LF but does not move to column 0."""
        self.newline()

    def reverse_index(self) -> None:
        """ESC M – move cursor up, inserting a blank line at top of region."""
        if self.cursor_row == self._scroll_top:
            self.scroll_down(1)
        elif self.cursor_row > 0:
            self.cursor_row -= 1

    # ------------------------------------------------------------------
    # Character output
    # ------------------------------------------------------------------

    def put_char(self, ch: str) -> None:
        """Write *ch* at the cursor position and advance the cursor."""
        if self.cursor_col >= self.cols:
            # Auto-wrap: go to next line
            self.carriage_return()
            self.newline()

        cell = Cell(char=ch, attrs=self.current_attrs.copy())
        if self.insert_mode:
            row = self.screen[self.cursor_row]
            row.insert(self.cursor_col, cell)
            self.screen[self.cursor_row] = row[:self.cols]
        else:
            self.screen[self.cursor_row][self.cursor_col] = cell

        self.cursor_col += 1

    # ------------------------------------------------------------------
    # Scrolling (within scroll region)
    # ------------------------------------------------------------------

    def scroll_up(self, n: int) -> None:
        """Scroll content up *n* lines inside the scroll region."""
        top, bot = self._scroll_top, self._scroll_bot
        for _ in range(n):
            removed = self.screen[top]
            if top == 0 and not self._in_alt:
                self.history.append(removed)
                if len(self.history) > self.MAX_HISTORY:
                    self.history.pop(0)
            self.screen[top:bot + 1] = (
                self.screen[top + 1:bot + 1] + [self._make_row(self.cols)]
            )

    def scroll_down(self, n: int) -> None:
        """Scroll content down *n* lines inside the scroll region."""
        top, bot = self._scroll_top, self._scroll_bot
        for _ in range(n):
            self.screen[top:bot + 1] = (
                [self._make_row(self.cols)] + self.screen[top:bot]
            )

    # ------------------------------------------------------------------
    # Erase operations
    # ------------------------------------------------------------------

    def erase_in_display(self, mode: int) -> None:
        if mode == 0:   # cursor → end
            for c in range(self.cursor_col, self.cols):
                self.screen[self.cursor_row][c] = Cell()
            for r in range(self.cursor_row + 1, self.rows):
                self.screen[r] = self._make_row(self.cols)
        elif mode == 1:  # beginning → cursor
            for r in range(0, self.cursor_row):
                self.screen[r] = self._make_row(self.cols)
            for c in range(0, self.cursor_col + 1):
                self.screen[self.cursor_row][c] = Cell()
        elif mode == 2:  # whole screen
            self.screen = self._make_screen(self.cols, self.rows)
        elif mode == 3:  # whole screen + scrollback
            self.screen  = self._make_screen(self.cols, self.rows)
            self.history.clear()

    def erase_in_line(self, mode: int) -> None:
        if mode == 0:   # cursor → end of line
            for c in range(self.cursor_col, self.cols):
                self.screen[self.cursor_row][c] = Cell()
        elif mode == 1:  # beginning → cursor
            for c in range(0, self.cursor_col + 1):
                self.screen[self.cursor_row][c] = Cell()
        elif mode == 2:  # whole line
            self.screen[self.cursor_row] = self._make_row(self.cols)

    def erase_chars(self, n: int) -> None:
        """ECH – erase *n* characters starting at the cursor (no cursor move)."""
        for i in range(n):
            c = self.cursor_col + i
            if c < self.cols:
                self.screen[self.cursor_row][c] = Cell()

    # ------------------------------------------------------------------
    # Line operations
    # ------------------------------------------------------------------

    def insert_lines(self, n: int) -> None:
        top, bot = self.cursor_row, self._scroll_bot
        n = min(n, bot - top + 1)
        for _ in range(n):
            self.screen[top:bot + 1] = (
                [self._make_row(self.cols)] + self.screen[top:bot]
            )

    def delete_lines(self, n: int) -> None:
        top, bot = self.cursor_row, self._scroll_bot
        n = min(n, bot - top + 1)
        for _ in range(n):
            self.screen[top:bot + 1] = (
                self.screen[top + 1:bot + 1] + [self._make_row(self.cols)]
            )

    # ------------------------------------------------------------------
    # Character-level operations
    # ------------------------------------------------------------------

    def delete_chars(self, n: int) -> None:
        row = self.screen[self.cursor_row]
        col = self.cursor_col
        del row[col:col + n]
        row.extend(Cell() for _ in range(n))
        self.screen[self.cursor_row] = row[:self.cols]

    def insert_chars(self, n: int) -> None:
        row = self.screen[self.cursor_row]
        col = self.cursor_col
        for _ in range(n):
            row.insert(col, Cell())
        self.screen[self.cursor_row] = row[:self.cols]

    # ------------------------------------------------------------------
    # Scroll region
    # ------------------------------------------------------------------

    def set_scroll_region(self, top: int, bot: int) -> None:
        if 0 <= top < bot < self.rows:
            self._scroll_top = top
            self._scroll_bot = bot
        else:
            self._scroll_top = 0
            self._scroll_bot = self.rows - 1
        # DECSTBM moves cursor to home
        self.cursor_row = self.cursor_col = 0

    # ------------------------------------------------------------------
    # Save / restore cursor
    # ------------------------------------------------------------------

    def save_cursor(self) -> None:
        self._saved_cursor = (self.cursor_row, self.cursor_col)
        self._saved_attrs  = self.current_attrs.copy()

    def restore_cursor(self) -> None:
        row, col = self._saved_cursor
        self.cursor_row  = max(0, min(self.rows - 1, row))
        self.cursor_col  = max(0, min(self.cols - 1, col))
        self.current_attrs = self._saved_attrs.copy()

    # ------------------------------------------------------------------
    # Alternate screen
    # ------------------------------------------------------------------

    def enter_alt_screen(self) -> None:
        if not self._in_alt:
            self._alt_screen = [row[:] for row in self.screen]
            self._alt_cursor = (self.cursor_row, self.cursor_col)
            self.screen      = self._make_screen(self.cols, self.rows)
            self.cursor_row  = self.cursor_col = 0
            self._in_alt     = True

    def exit_alt_screen(self) -> None:
        if self._in_alt and self._alt_screen is not None:
            self.screen     = self._alt_screen
            self._alt_screen = None
            self.cursor_row, self.cursor_col = self._alt_cursor
            self._in_alt    = False

    # ------------------------------------------------------------------
    # Full reset
    # ------------------------------------------------------------------

    def reset(self) -> None:
        self.cursor_row = self.cursor_col = 0
        self.cursor_visible  = True
        self.current_attrs   = TextAttrs()
        self.insert_mode     = False
        self.application_cursor_keys = False
        self._scroll_top     = 0
        self._scroll_bot     = self.rows - 1
        self.screen          = self._make_screen(self.cols, self.rows)
        self._in_alt         = False
        self._alt_screen     = None

    # ------------------------------------------------------------------
    # Resize
    # ------------------------------------------------------------------

    def resize(self, cols: int, rows: int) -> None:
        old_cols, old_rows = self.cols, self.rows
        self.cols, self.rows = cols, rows

        # Adjust every row's width
        new_screen: List[List[Cell]] = []
        for row in self.screen:
            if cols > old_cols:
                row = row + [Cell() for _ in range(cols - old_cols)]
            else:
                row = row[:cols]
            new_screen.append(row)

        # Add or remove rows
        while len(new_screen) < rows:
            new_screen.append(self._make_row(cols))
        self.screen = new_screen[:rows]

        # Clamp cursor and scroll region
        self.cursor_row  = min(self.cursor_row,  rows - 1)
        self.cursor_col  = min(self.cursor_col,  cols - 1)
        self._scroll_top = 0
        self._scroll_bot = rows - 1
