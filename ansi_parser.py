"""ANSI/VT100 escape sequence parser.

Parses raw PTY output and drives a TerminalBuffer via its public API.
Supports: SGR colours, cursor movement, erase, scroll regions,
alternate screen, save/restore cursor, OSC title (ignored).
"""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    from terminal_buffer import TerminalBuffer


class _State(Enum):
    NORMAL   = auto()
    ESC      = auto()
    CSI      = auto()
    OSC      = auto()
    ESC_HASH = auto()
    CHARSET  = auto()   # ESC ( or ESC ) – skip one char


class AnsiParser:
    """Stateful ANSI/VT-100 parser."""

    def __init__(self) -> None:
        self._state  = _State.NORMAL
        self._params = ""       # CSI parameter bytes
        self._inter  = ""       # CSI intermediate bytes (e.g. '?')
        self._osc    = ""       # OSC string accumulator

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def feed(self, data: str, buf: "TerminalBuffer") -> None:
        """Parse *data* and apply every escape sequence to *buf*."""
        for ch in data:
            self._step(ch, buf)

    # ------------------------------------------------------------------
    # Internal state machine
    # ------------------------------------------------------------------

    def _step(self, ch: str, buf: "TerminalBuffer") -> None:  # noqa: C901
        s = self._state

        if s == _State.NORMAL:
            if   ch == "\x1b":                 self._state = _State.ESC
            elif ch == "\r":                   buf.carriage_return()
            elif ch in "\n\x0b\x0c":           buf.newline()
            elif ch == "\x08":                 buf.backspace()
            elif ch == "\t":                   buf.tab()
            elif ch == "\x07":                 pass   # BEL – ignore
            elif ch in "\x0e\x0f":             pass   # SO/SI – ignore
            elif ch >= "\x20":                 buf.put_char(ch)
            # else: other C0 controls – ignore

        elif s == _State.ESC:
            if   ch == "[":
                self._state  = _State.CSI
                self._params = ""
                self._inter  = ""
            elif ch == "]":
                self._state = _State.OSC
                self._osc   = ""
            elif ch == "#":
                self._state = _State.ESC_HASH
            elif ch in "()*+":
                self._state = _State.CHARSET   # skip designator char
            elif ch == "7":  buf.save_cursor();    self._state = _State.NORMAL
            elif ch == "8":  buf.restore_cursor(); self._state = _State.NORMAL
            elif ch == "c":  buf.reset();          self._state = _State.NORMAL
            elif ch == "D":  buf.index();          self._state = _State.NORMAL
            elif ch == "M":  buf.reverse_index();  self._state = _State.NORMAL
            elif ch == "E":
                buf.carriage_return()
                buf.newline()
                self._state = _State.NORMAL
            else:
                self._state = _State.NORMAL

        elif s == _State.ESC_HASH:
            # ESC # 8 = DECALN (fill with 'E') – we just ignore it
            self._state = _State.NORMAL

        elif s == _State.CHARSET:
            # Charset designation – we ignore the actual designator
            self._state = _State.NORMAL

        elif s == _State.CSI:
            if   "0" <= ch <= "9":   self._params += ch
            elif ch == ";":          self._params += ";"
            elif ch in "?><!=":      self._inter  += ch
            elif "\x40" <= ch <= "\x7e":
                self._dispatch_csi(ch, buf)
                self._state = _State.NORMAL
            # else: other intermediates – accumulate

        elif s == _State.OSC:
            if ch in "\x07\x9c":    # BEL or ST ends OSC
                self._dispatch_osc(self._osc, buf)
                self._state = _State.NORMAL
            elif ch == "\x1b":      # ESC \ (ST)
                self._state = _State.NORMAL
            else:
                self._osc += ch

    # ------------------------------------------------------------------
    # Parameter helpers
    # ------------------------------------------------------------------

    def _p(self, n: int, default: int = 0) -> int:
        """Return the nth semicolon-separated CSI parameter (0-indexed)."""
        parts = self._params.split(";") if self._params else []
        if n < len(parts) and parts[n]:
            try:
                return int(parts[n])
            except ValueError:
                pass
        return default

    def _plist(self, default: int = 0):
        """Return all CSI parameters as a list of ints."""
        parts = self._params.split(";") if self._params else [""]
        result = []
        for part in parts:
            try:
                result.append(int(part) if part else default)
            except ValueError:
                result.append(default)
        return result

    # ------------------------------------------------------------------
    # CSI dispatch
    # ------------------------------------------------------------------

    def _dispatch_csi(self, cmd: str, buf: "TerminalBuffer") -> None:  # noqa: C901
        inter = self._inter

        # ---- Private (DEC) sequences  ESC [ ? … h/l ----
        if "?" in inter:
            for n in self._plist(0):
                if cmd == "h":
                    if   n == 1:    buf.application_cursor_keys = True
                    elif n == 25:   buf.cursor_visible = True
                    elif n in (47, 1047, 1049): buf.enter_alt_screen()
                elif cmd == "l":
                    if   n == 1:    buf.application_cursor_keys = False
                    elif n == 25:   buf.cursor_visible = False
                    elif n in (47, 1047, 1049): buf.exit_alt_screen()
            return

        # ---- Standard sequences ----
        p = self._p   # shorthand

        if   cmd == "A":  buf.cursor_up(max(1, p(0, 1)))
        elif cmd == "B":  buf.cursor_down(max(1, p(0, 1)))
        elif cmd == "C":  buf.cursor_forward(max(1, p(0, 1)))
        elif cmd == "D":  buf.cursor_back(max(1, p(0, 1)))
        elif cmd == "E":
            buf.cursor_down(max(1, p(0, 1)))
            buf.carriage_return()
        elif cmd == "F":
            buf.cursor_up(max(1, p(0, 1)))
            buf.carriage_return()
        elif cmd == "G":
            buf.cursor_col = max(0, min(buf.cols - 1, max(1, p(0, 1)) - 1))
        elif cmd in ("H", "f"):
            buf.cursor_to(max(1, p(0, 1)) - 1, max(1, p(1, 1)) - 1)
        elif cmd == "I":   # Cursor forward tabulation
            for _ in range(max(1, p(0, 1))):
                buf.tab()
        elif cmd == "J":   buf.erase_in_display(p(0, 0))
        elif cmd == "K":   buf.erase_in_line(p(0, 0))
        elif cmd == "L":   buf.insert_lines(max(1, p(0, 1)))
        elif cmd == "M":   buf.delete_lines(max(1, p(0, 1)))
        elif cmd == "P":   buf.delete_chars(max(1, p(0, 1)))
        elif cmd == "S":   buf.scroll_up(max(1, p(0, 1)))
        elif cmd == "T":   buf.scroll_down(max(1, p(0, 1)))
        elif cmd == "X":   buf.erase_chars(max(1, p(0, 1)))
        elif cmd == "@":   buf.insert_chars(max(1, p(0, 1)))
        elif cmd == "Z":   # Cursor backward tabulation
            for _ in range(max(1, p(0, 1))):
                buf.back_tab()
        elif cmd == "d":
            buf.cursor_row = max(0, min(buf.rows - 1, max(1, p(0, 1)) - 1))
        elif cmd == "m":
            self._apply_sgr(self._plist(0), buf)
        elif cmd == "r":
            top = max(1, p(0, 1)) - 1
            bot = (p(1) or buf.rows) - 1
            buf.set_scroll_region(top, bot)
        elif cmd == "s":   buf.save_cursor()
        elif cmd == "u":   buf.restore_cursor()
        elif cmd in ("c", "n", "h", "l"):
            pass   # device attributes / status – terminal responses not needed

    # ------------------------------------------------------------------
    # SGR  (Select Graphic Rendition)
    # ------------------------------------------------------------------

    def _apply_sgr(self, params: list, buf: "TerminalBuffer") -> None:  # noqa: C901
        if not params:
            params = [0]

        i = 0
        while i < len(params):
            n = params[i]
            attrs = buf.current_attrs

            if   n == 0:   attrs.reset()
            elif n == 1:   attrs.bold          = True
            elif n == 2:   attrs.dim           = True
            elif n == 3:   attrs.italic        = True
            elif n == 4:   attrs.underline     = True
            elif n in (5, 6): attrs.blink      = True
            elif n == 7:   attrs.reverse       = True
            elif n == 8:   attrs.hidden        = True
            elif n == 9:   attrs.strikethrough = True
            elif n == 21:  attrs.underline     = True
            elif n == 22:  attrs.bold = attrs.dim = False
            elif n == 23:  attrs.italic        = False
            elif n == 24:  attrs.underline     = False
            elif n == 25:  attrs.blink         = False
            elif n == 27:  attrs.reverse       = False
            elif n == 28:  attrs.hidden        = False
            elif n == 29:  attrs.strikethrough = False
            elif 30 <= n <= 37:  attrs.fg = ANSI_COLORS[n - 30]
            elif n == 38:
                color, skip = _parse_extended_color(params, i + 1)
                if color:
                    attrs.fg = color
                i += skip
            elif n == 39:  attrs.fg = None
            elif 40 <= n <= 47:  attrs.bg = ANSI_COLORS[n - 40]
            elif n == 48:
                color, skip = _parse_extended_color(params, i + 1)
                if color:
                    attrs.bg = color
                i += skip
            elif n == 49:  attrs.bg = None
            elif 90 <= n <= 97:  attrs.fg = ANSI_COLORS[n - 90 + 8]
            elif 100 <= n <= 107: attrs.bg = ANSI_COLORS[n - 100 + 8]

            i += 1

    # ------------------------------------------------------------------
    # OSC dispatch
    # ------------------------------------------------------------------

    def _dispatch_osc(self, osc: str, buf: "TerminalBuffer") -> None:
        # OSC 0 or 2 → set window title.  We store it on the buffer.
        try:
            code_str, _, text = osc.partition(";")
            code = int(code_str)
            if code in (0, 2):
                buf.title = text
        except (ValueError, AttributeError):
            pass


# ---------------------------------------------------------------------------
# Colour tables
# ---------------------------------------------------------------------------

def set_palette(colors: list) -> None:
    """Replace the 16-colour palette in-place (call once after loading config)."""
    for i, rgb in enumerate(colors[:16]):
        ANSI_COLORS[i] = tuple(rgb)


# 16-colour xterm-compatible palette (overridable via set_palette)
ANSI_COLORS: list = [
    # Normal (0–7)
    (  0,   0,   0),   # black
    (170,   0,   0),   # red
    (  0, 170,   0),   # green
    (170, 170,   0),   # yellow
    (  0,   0, 170),   # blue
    (170,   0, 170),   # magenta
    (  0, 170, 170),   # cyan
    (170, 170, 170),   # white (light grey)
    # Bright (8–15)
    ( 85,  85,  85),   # bright black  (dark grey)
    (255,  85,  85),   # bright red
    ( 85, 255,  85),   # bright green
    (255, 255,  85),   # bright yellow
    ( 85,  85, 255),   # bright blue
    (255,  85, 255),   # bright magenta
    ( 85, 255, 255),   # bright cyan
    (255, 255, 255),   # bright white
]


def color_from_256(n: int) -> Tuple[int, int, int]:
    """Map a 256-colour index to an (R, G, B) tuple."""
    if n < 16:
        return ANSI_COLORS[n]
    if n < 232:
        n -= 16
        def _v(i: int) -> int:
            return 0 if i == 0 else 55 + 40 * i
        return (_v(n // 36), _v((n % 36) // 6), _v(n % 6))
    v = 8 + (n - 232) * 10
    return (v, v, v)


def _parse_extended_color(
    params: list, i: int
) -> Tuple[Optional[Tuple[int, int, int]], int]:
    """Parse 38;2;r;g;b or 38;5;n from *params* starting at index *i*.

    Returns (color_or_None, number_of_extra_params_consumed).
    """
    if i >= len(params):
        return None, 0
    mode = params[i]
    if mode == 2 and i + 3 < len(params):
        r, g, b = params[i + 1], params[i + 2], params[i + 3]
        return (r, g, b), 4
    if mode == 5 and i + 1 < len(params):
        return color_from_256(params[i + 1]), 2
    return None, 1   # consume the mode byte even on failure
