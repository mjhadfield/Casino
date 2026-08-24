"""
Central style tokens for the whole app -- colors, fonts, and a handful of
small Canvas-drawing helpers -- mirroring the "terminal window" aesthetic of
the user's own website (dark background, mint-green monospace accent,
traffic-light window chrome, dashed "soon" borders). Every UI file imports
from here instead of hardcoding its own hex literals/font tuples, so the
whole app's look lives in one place.

What deliberately does NOT live here, and why:
  - CHIP_DENOMINATIONS (games/three_card_poker/ui.py) -- the physical poker
    chip colours (blue/red/green/black/pink) are a fixed casino convention,
    not a display token, and must never change with a restyle.
  - TABLE_THEMES (core/settings.py) -- the poker table's felt/trim is its own
    per-table choice (Settings' theme picker), intentionally independent of
    this module's one fixed global accent -- see that module's docstring.
  - Real playing-card colours (ui/card_widgets.py's draw_card) -- a card
    should look like a card, not like terminal text.
  - The jackpot meter's red LED digits (ui/jackpot_display.py) -- kept as a
    deliberate "arcade jackpot" accent that pops against this palette rather
    than blending into it.
"""
import tkinter as tk
import tkinter.font as tkfont

# ---------------------------------------------------------------------- colors
BG = "#06080a"
BG_ELEVATED = "#0c1210"   # top bars, chip-tray plaques, panel backgrounds
FG = "#e7f3ee"
FG_DIM = "#78897f"
ACCENT = "#35e0a0"        # the one fixed global accent -- every screen but the
                           # poker table's own felt (which stays theme-driven)
WARN = "#ff9f40"
BORDER = "#1c2622"
BORDER_SOFT = "#141b18"
GREY_BTN_BG = "#0e1311"
GREY_BTN_BORDER = "#232c27"
GREY_BTN_TEXT = "#4c5850"
RADIUS = 10

# A warm secondary accent, used sparingly and only where something needs to
# stand out from the cool mint primary -- the Main Menu's own branding/nav
# highlights (see ui/main_menu.py), not a general-purpose token reached for
# everywhere else.
SECONDARY = "#d4af37"

# The Main Menu's own page background -- lifted straight from the terminal
# background on the user's website, distinct from (and lighter than) BG,
# which every other screen still uses. Scoped to ui/main_menu.py only.
MENU_BG = "#141917"

# Win / lose / push -- the one 3-way mapping used everywhere a result (a bet,
# a hand, a round) is colored: finances, stats, the poker result/payout panel.
WIN_COLOR = ACCENT
LOSE_COLOR = "#ff5f56"     # the same red the site uses for invalid fields,
                           # so "red" reads as one consistent signal
PUSH_COLOR = WARN


def lerp_color(c1, c2, t):
    """Blends two "#rrggbb" colours -- t=0 -> c1, t=1 -> c2."""
    t = max(0.0, min(1.0, t))
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    return f"#{round(r1 + (r2 - r1) * t):02x}{round(g1 + (g2 - g1) * t):02x}{round(b1 + (b2 - b1) * t):02x}"


# Tk widget colors are flat -- there's no alpha channel on a Label/Frame/
# Canvas fill -- so the site's semi-transparent "accent-dim"/"warn-dim" tints
# become pre-blended flat hex, one variant per background they actually sit
# on (a blend baked for one backdrop looks wrong composited over another).
ACCENT_DIM_BG = lerp_color(BG, ACCENT, 0.12)
ACCENT_DIM_BG_ELEVATED = lerp_color(BG_ELEVATED, ACCENT, 0.14)
WARN_DIM_BG = lerp_color(BG, WARN, 0.12)
LOSE_DIM_BG = lerp_color(BG, LOSE_COLOR, 0.12)
LOSE_DIM_BG_ELEVATED = lerp_color(BG_ELEVATED, LOSE_COLOR, 0.14)
SECONDARY_DIM_MENU_BG = lerp_color(MENU_BG, SECONDARY, 0.16)

# A visible neutral-grey rule for separators against MENU_BG -- BORDER/
# BORDER_SOFT are calibrated for the near-black BG and read as almost
# invisible against the lighter MENU_BG, so this is its own, brighter token.
MENU_DIVIDER = lerp_color(MENU_BG, "#ffffff", 0.15)

# ---------------------------------------------------------------------- fonts
_FONT_FAMILY = None  # resolved lazily -- tkinter.font.families() needs a live
                      # root window, so this can't run at import time; the
                      # first widget built after CasinoApp.__init__ triggers it.
_FALLBACK_CHAIN = ("JetBrains Mono", "DejaVu Sans Mono", "Courier New")


def mono_family():
    global _FONT_FAMILY
    if _FONT_FAMILY is None:
        available = set(tkfont.families())
        _FONT_FAMILY = next((f for f in _FALLBACK_CHAIN if f in available), "Courier")
    return _FONT_FAMILY


def font(size, weight="normal", slant="roman"):
    style = tuple(s for s in (weight if weight != "normal" else None,
                               slant if slant != "roman" else None) if s)
    return (mono_family(), size, *style)


# ---------------------------------------------------------------------- drawing helpers
def rounded_rect(canvas, x1, y1, x2, y2, radius=RADIUS, **kwargs):
    points = [
        x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
        x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
        x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


def dashed_rect(canvas, x1, y1, x2, y2, radius=RADIUS, dash=(4, 2), **kwargs):
    """Same rounded shape as rounded_rect, dashed -- Tk Frames/Buttons have no
    dashed-border option at all, so anywhere the site's dashed "soon" look is
    needed, it has to be drawn on a Canvas."""
    return rounded_rect(canvas, x1, y1, x2, y2, radius=radius, dash=dash, **kwargs)


def pill(canvas, cx, cy, text, fill=GREY_BTN_BG, outline=GREY_BTN_BORDER,
         text_fg=GREY_BTN_TEXT, pad_x=8, pad_y=3, dash=None, font_size=8):
    """A fully-rounded pill (radius = half height) sized to fit `text`,
    centred at (cx, cy) -- used for the "SOON" tag and similar small badges."""
    text_id = canvas.create_text(cx, cy, text=text, fill=text_fg, font=font(font_size, weight="bold"))
    x1, y1, x2, y2 = canvas.bbox(text_id)
    x1, y1, x2, y2 = x1 - pad_x, y1 - pad_y, x2 + pad_x, y2 + pad_y
    height = y2 - y1
    if dash:
        shape_id = dashed_rect(canvas, x1, y1, x2, y2, radius=height / 2, dash=dash, fill=fill, outline=outline)
    else:
        shape_id = rounded_rect(canvas, x1, y1, x2, y2, radius=height / 2, fill=fill, outline=outline)
    canvas.tag_raise(text_id, shape_id)
    return shape_id, text_id


def outlined_glyph(canvas, cx, cy, text, size, fill, outline, outline_width=1, weight="bold"):
    """A single character with a solid fill and a colored outline -- Tk canvas
    text only ever takes one fill color, so the outline is faked by drawing
    the glyph several times at small offsets in `outline`, then once more
    dead-center in `fill` on top. Good enough at icon sizes (a handful of px
    of offset); not meant for large display type."""
    f = font(size, weight=weight)
    for dx in (-outline_width, 0, outline_width):
        for dy in (-outline_width, 0, outline_width):
            if dx or dy:
                canvas.create_text(cx + dx, cy + dy, text=text, font=f, fill=outline)
    canvas.create_text(cx, cy, text=text, font=f, fill=fill)


def breadcrumb(parent, path, bg, host="hadfield-casino"):
    """A dim shell-prompt-style breadcrumb label, e.g.
    "player@hadfield-casino:~/cashier" -- the site's own top-bar signature."""
    text = f"player@{host}:~/{path}"
    return tk.Label(parent, text=text, bg=bg, fg=FG_DIM, font=font(9))


def recessed_panel(canvas, x1, y1, x2, y2, title=None, title_font_size=12,
                    fill=BG_ELEVATED, outline=ACCENT, inner_outline=BORDER):
    """The "recessed double-border panel" look used for the poker table's
    paytable and round-result panels: an outer accent-bordered rect, a
    dimmer inner rule 5px in, and an optional centered title along the top.
    Both call sites drew this by hand as 3 nearly-identical lines; this is
    the one shared version."""
    canvas.create_rectangle(x1 + 3, y1 + 3, x2 - 3, y2 - 3, fill=fill, outline=outline, width=2)
    canvas.create_rectangle(x1 + 8, y1 + 8, x2 - 8, y2 - 8, outline=inner_outline, width=1)
    if title:
        canvas.create_text((x1 + x2) / 2, y1 + 22, text=title, fill=outline,
                            font=font(title_font_size, weight="bold"))
