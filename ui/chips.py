"""
Shared physical-chip rendering -- the classic casino chip palette, the
greedy denomination breakdown, and the on-table chip-stack drawing routine.
Originally built for Three Card Poker; lifted out here so a second game
(Blackjack) can render identical-looking chips without re-implementing this,
and so any future game gets it for free too.

CHIP_DENOMINATIONS is a fixed casino convention -- these colours must never
change once a game has shipped with them, the same way real chip colours
don't change on a casino floor. Nothing in this module is felt/theme-scoped;
every chip looks the same regardless of which table it's sitting on.
"""
import tkinter as tk

from ui import theme

# (denomination, face colour, rim colour).
CHIP_DENOMINATIONS = [
    (1, "#1f6fd6", "#0d3c85"),     # blue
    (5, "#d1362f", "#8f211d"),     # red
    (25, "#1f8a4c", "#125c32"),    # green
    (100, "#1c1c1c", "#000000"),   # black
    (500, "#d6389f", "#8f1f68"),   # pink
]
CHIP_COLORS_BY_VALUE = {value: (face, rim) for value, face, rim in CHIP_DENOMINATIONS}
CHIP_SIZE = 58  # a chip-tray button's on-screen diameter (in px, before the selection ring)

# An on-table chip stack's per-layer radius default -- callers usually pass
# their own max_r (sized to whatever spot the stack sits on), but this is a
# sane fallback.
CHIP_LAYER_MAX_R = 36


def chip_breakdown(amount):
    """Greedy denomination breakdown of `amount` -- e.g. £30 -> [(25, 1), (5, 1)].
    Since £1 chips exist this always accounts for the full amount exactly, and
    it's meant to be recomputed from the total every draw, so e.g. five £1
    chips on a spot render as a single £5 chip once the total reaches £5."""
    breakdown = []
    remaining = amount
    for value, _, _ in sorted(CHIP_DENOMINATIONS, reverse=True):
        if remaining <= 0:
            break
        count, remaining = divmod(remaining, value)
        if count:
            breakdown.append((value, count))
    return breakdown


def draw_chip_stack(canvas, tag, cx, cy, amount, max_r):
    """Draws `amount` as a stack of chip icons on `canvas` (largest
    denomination at the base), each carrying a ×N badge if more than one of
    that chip is on the spot.

    Every chip is always drawn at `max_r` -- a stack needing several
    denominations just grows taller, never shrinks its individual chips to
    fit some notional budget (a large payout could otherwise end up with a
    correctly-sized bottom chip and comically small ones stacked above it).

    `tag` is usually a single string, but a payout animation that needs to
    delete/redraw just the chips on a spot without touching that spot's own
    box+label can pass a (shell_tag, chips_tag) pair instead, so both are
    still there for anything (e.g. tag_lower) that expects the whole spot as
    one unit."""
    tags = (tag,) if isinstance(tag, str) else tuple(tag)
    breakdown = chip_breakdown(amount)  # largest denomination first
    layer_r = max_r
    dy = layer_r * 0.85
    base_cy = cy + dy * (len(breakdown) - 1) / 2
    for i, (value, count) in enumerate(breakdown):
        layer_cy = base_cy - i * dy
        face, rim = CHIP_COLORS_BY_VALUE[value]
        canvas.create_oval(cx - layer_r, layer_cy - layer_r, cx + layer_r, layer_cy + layer_r,
                            fill=face, outline=rim, width=2, tags=tags)
        canvas.create_oval(cx - layer_r + 4, layer_cy - layer_r + 4, cx + layer_r - 4, layer_cy + layer_r - 4,
                            outline="#ffffff", width=1, tags=tags)
        canvas.create_text(cx, layer_cy, text=f"£{value}", fill="#ffffff",
                            font=theme.font(max(7, int(layer_r * 0.38)), weight="bold"), tags=tags)
        if count > 1:
            badge_r = max(7, layer_r * 0.42)
            bx, by = cx + layer_r * 0.62, layer_cy + layer_r * 0.62
            canvas.create_oval(bx - badge_r, by - badge_r, bx + badge_r, by + badge_r,
                                fill=theme.BG_ELEVATED, outline=theme.ACCENT, width=1, tags=tags)
            canvas.create_text(bx, by, text=f"×{count}", fill="#ffffff",
                                font=theme.font(max(7, int(badge_r * 0.85)), weight="bold"), tags=tags)


def draw_chip_face(canvas, cx, cy, value, face, rim, r=None, selected=False):
    """Draws one selectable chip-tray button face, centred at (cx, cy) on
    `canvas` -- the same look every chip-tray chip in the app uses (a ring
    around it when `selected`, a white inner rim, the £value centred).
    Doesn't bind any click handling -- the caller owns that, since what
    "selecting" a chip does differs per game (Three Card Poker just sets
    self.selected_chip; a future game might need something else)."""
    r = r if r is not None else CHIP_SIZE / 2
    if selected:
        canvas.create_oval(cx - r - 4, cy - r - 4, cx + r + 4, cy + r + 4,
                            outline=theme.ACCENT, width=3)
    canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=face, outline=rim, width=3)
    canvas.create_oval(cx - r + 7, cy - r + 7, cx + r - 7, cy + r - 7,
                        outline="#ffffff", width=1)
    canvas.create_text(cx, cy, text=f"£{value}", fill="#ffffff", font=theme.font(10, weight="bold"))
