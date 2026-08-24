"""
Reusable "progressive jackpot" meter widget.

A mechanical-odometer style money display. The pennies (the 2 digits after
the decimal point) roll smoothly and continuously as the value grows --
that's what makes a slow rate of increase (Three Card Poker's jackpot grows
at only ~£0.01/second by default) actually read as motion. The whole-pound
digits instead sit still and flick over the instant they change, like a real
odometer's carry -- a pound digit only ever moves at the moment it's meant
to display a different number, so it never sits there looking mid-roll/
misaligned the way continuously rolling all seven digits would.

Not tied to Three Card Poker or to core.jackpot.JackpotManager -- it just
renders whatever float it's given via set_value(), so any future game with
its own progressive jackpot can reuse it.
"""
import math
import tkinter as tk

from ui import theme

REEL_DIGIT_WIDTH = 20
REEL_DIGIT_HEIGHT = 32
# Not resolved at import time -- theme.font() needs a live Tk root, which
# doesn't exist yet when this module is first imported (see _reel_font()).
# Deliberately NOT reskinned to the mint accent -- this red "LED" look is a
# signature "arcade jackpot" accent that's meant to pop against the new
# terminal palette rather than blend into it. Leave it red.
REEL_BG = "#0a0a0a"           # recessed "LED window" look, independent of the felt theme
REEL_FG = "#ff4136"           # classic red jackpot-meter digits

INTEGER_DIGITS = 5   # fixed so the ceiling (£50,000.00) never needs more room
DECIMAL_DIGITS = 2


def _reel_font():
    return theme.font(18, weight="bold")


class _DigitReel(tk.Canvas):
    """One digit. In `rolling` mode it draws the current digit and the one
    after it stacked vertically, offset by the fractional part of a
    continuous "wheel position" -- the canvas's own bounds clip whichever
    one is mid-scroll, like a physical odometer wheel actually turning.
    Otherwise it just shows a single static digit that flicks straight to
    the next one the instant it changes, with no in-between frames."""

    def __init__(self, parent, rolling=True):
        super().__init__(parent, width=REEL_DIGIT_WIDTH, height=REEL_DIGIT_HEIGHT,
                          bg=REEL_BG, highlightthickness=0)
        self.rolling = rolling
        self._last_key = None
        self._font = _reel_font()
        self.set_wheel_position(0.0)

    def set_wheel_position(self, w):
        """`w`: a continuous value whose integer part mod 10 is the digit
        currently showing. In `rolling` mode, its fractional part is how far
        it's rolled towards the next one (0 = resting on the digit, ->1 =
        about to land on the next); ignored otherwise -- a non-rolling reel
        only ever shows whole digits."""
        w = w % 10
        digit = int(w)
        frac = (w - digit) if self.rolling else 0.0
        key = round(w, 3) if self.rolling else digit
        if key == self._last_key:
            return
        self._last_key = key
        self.delete("all")
        cy = REEL_DIGIT_HEIGHT / 2
        dy = frac * REEL_DIGIT_HEIGHT
        self.create_text(REEL_DIGIT_WIDTH / 2, cy - dy, text=str(digit),
                          fill=REEL_FG, font=self._font)
        if frac:
            self.create_text(REEL_DIGIT_WIDTH / 2, cy - dy + REEL_DIGIT_HEIGHT, text=str((digit + 1) % 10),
                              fill=REEL_FG, font=self._font)


class JackpotDisplay(tk.Frame):
    """A framed jackpot meter: header, a row of rolling digit reels formatted
    as money (e.g. £05,000.00 up to £50,000.00), and an optional payout
    table underneath describing what wins it.

    `rows`: optional list of (label, value_text) pairs rendered below the
    meter, e.g. [("Straight", "£6"), ("Royal Flush (♠)", "JACKPOT!")] --
    value_text is shown as-is, so the caller controls its formatting.
    `highlight_row`: index into `rows` to draw in the jackpot accent colour
    instead of plain text, for the one row that actually wins the jackpot.
    """

    def __init__(self, parent, title="PROGRESSIVE JACKPOT", rows=None, highlight_row=None,
                 panel_bg=theme.BG_ELEVATED, border=theme.ACCENT):
        super().__init__(parent, bg=panel_bg, highlightbackground=border, highlightthickness=1)
        reel_font = _reel_font()

        tk.Label(self, text=title, bg=panel_bg, fg=border,
                 font=theme.font(12, weight="bold")).pack(pady=(10, 6))

        meter = tk.Frame(self, bg=REEL_BG, highlightbackground="#3a1010", highlightthickness=2)
        meter.pack(padx=14)
        reel_row = tk.Frame(meter, bg=REEL_BG)
        reel_row.pack(padx=8, pady=6)

        tk.Label(reel_row, text="£", bg=REEL_BG, fg=REEL_FG, font=reel_font).pack(side="left")
        self._int_reels = []
        for i in range(INTEGER_DIGITS):
            if i == INTEGER_DIGITS - 3:  # thousands separator, e.g. "50,000"
                tk.Label(reel_row, text=",", bg=REEL_BG, fg=REEL_FG, font=reel_font).pack(side="left")
            reel = _DigitReel(reel_row, rolling=False)  # whole pounds: static, flicks over on carry
            reel.pack(side="left")
            self._int_reels.append(reel)
        tk.Label(reel_row, text=".", bg=REEL_BG, fg=REEL_FG, font=reel_font).pack(side="left")
        self._dec_reels = [_DigitReel(reel_row, rolling=True) for _ in range(DECIMAL_DIGITS)]  # pennies: rolls
        for reel in self._dec_reels:
            reel.pack(side="left")

        if rows:
            tk.Frame(self, bg=border, height=1).pack(fill="x", padx=14, pady=(12, 8))
            table = tk.Frame(self, bg=panel_bg)
            table.pack(fill="x", padx=16, pady=(0, 12))
            for i, (label, value_text) in enumerate(rows):
                fg = REEL_FG if i == highlight_row else theme.FG
                font = theme.font(9, weight="bold") if i == highlight_row else theme.font(9)
                row = tk.Frame(table, bg=panel_bg)
                row.pack(fill="x", pady=2)
                tk.Label(row, text=label, bg=panel_bg, fg=fg, font=font, anchor="w").pack(side="left")
                tk.Label(row, text=value_text, bg=panel_bg, fg=fg, font=font, anchor="e").pack(side="right")

    def set_value(self, amount):
        """`amount`: a float in pounds (sub-penny precision is fine and is
        what makes the pennies reels visibly roll). Whole-pound reels flick
        to their digit the moment it changes; the two pennies reels get the
        full continuous wheel position."""
        pence = amount * 100.0  # place-value math in pence avoids dividing by <1 place values
        # Whole pounds flick over only once pence has actually crossed a
        # penny boundary (floor, not round-to-nearest -- rounding 99.9p up
        # to 100p would flick the pound digit a fraction of a second before
        # the pennies reels actually reach "00", which looks like a glitch).
        # The tiny epsilon guards only against float noise landing just
        # below an exact boundary (e.g. 500099.99999999994 instead of
        # 500100); it's far too small to affect a real, still-short reading.
        whole_pence = math.floor(pence + 1e-6)
        for i, reel in enumerate(self._int_reels):
            place_pence = 10 ** (INTEGER_DIGITS - 1 - i + 2)
            reel.set_wheel_position(whole_pence // place_pence)
        for i, reel in enumerate(self._dec_reels):
            place_pence = 10 ** (1 - i)
            reel.set_wheel_position(pence / place_pence)
