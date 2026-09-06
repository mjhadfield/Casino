"""
Central style tokens for the whole app -- colors, fonts, and a handful of
small Canvas-drawing helpers -- mirroring the "terminal window" aesthetic of
the user's own website (dark background, mint-green monospace accent,
traffic-light window chrome, dashed "soon" borders). Every UI file imports
from here instead of hardcoding its own hex literals/font tuples, so the
whole app's look lives in one place.

BG/BG_ELEVATED/MENU_BG/BORDER/BORDER_SOFT/ACCENT are no longer one fixed
palette -- they're the app's CURRENT theme (core/themes.py's THEMES/
PREMIUM_THEMES catalog), swappable at runtime via set_active_theme() below.
"Terminal" (core/themes.py) is what these six were always hardcoded to, and
stays the default. FG/FG_DIM/WARN/SECONDARY/the lock-red palette stay
theme-INVARIANT on purpose (see core/themes.py's own docstring) -- neutral
ink/signal colours, not brand colours, defined once here and never per-theme.

Because every UI file was already written as `theme.BG`-style module-
attribute reads (not function calls), changing the active theme means two
things have to happen together: these globals get reassigned (so anything
built AFTER the change picks up the new values automatically), AND every
already-built widget gets walked and repainted (since nothing re-reads
theme.BG after construction) -- see retheme_widget_tree() below, and
main.py's CasinoApp.apply_global_theme() which drives the whole thing.

What deliberately does NOT live here, and why:
  - CHIP_DENOMINATIONS (games/three_card_poker/ui.py) -- the physical poker
    chip colours (blue/red/green/black/pink) are a fixed casino convention,
    not a display token, and must never change with a restyle.
  - The THEMES/PREMIUM_THEMES catalog itself (core/themes.py) -- core/ has
    to stay framework-agnostic (no tkinter import), so the actual palette
    DATA lives there; this module only ever holds the CURRENT one.
  - Real playing-card colours (ui/card_widgets.py's draw_card) -- a card
    should look like a card, not like terminal text.
  - The jackpot meter's red LED digits (ui/jackpot_display.py) -- kept as a
    deliberate "arcade jackpot" accent that pops against this palette rather
    than blending into it.
"""
import tkinter as tk
import tkinter.font as tkfont

# ---------------------------------------------------------------------- colors
# The six theme-driven tokens -- these start as "Terminal"'s own values
# (core/themes.py) and are reassigned in place by set_active_theme() below;
# every other module reads them as a plain attribute (`theme.BG`), so this
# assignment is what a freshly-BUILT widget picks up automatically, while
# retheme_widget_tree() is what repaints an ALREADY-built one.
BG = "#06080a"
BG_ELEVATED = "#0c1210"   # top bars, chip-tray plaques, panel backgrounds
ACCENT = "#35e0a0"        # the active theme's own accent
BORDER = "#1c2622"
BORDER_SOFT = "#141b18"
# The Main Menu's own page background -- lifted straight from the terminal
# background on the user's website, distinct from (and lighter than) BG,
# which every other screen still uses. Scoped to ui/main_menu.py only.
MENU_BG = "#141917"

# Theme-invariant from here down -- fixed regardless of the active theme,
# see this module's own docstring for why.
FG = "#e7f3ee"
FG_DIM = "#78897f"
WARN = "#ff9f40"
GREY_BTN_BG = "#0e1311"
GREY_BTN_BORDER = "#232c27"
GREY_BTN_TEXT = "#4c5850"
RADIUS = 10

# A warm secondary accent, used sparingly and only where something needs to
# stand out from the cool mint primary -- the Main Menu's own branding/nav
# highlights (see ui/main_menu.py), not a general-purpose token reached for
# everywhere else.
SECONDARY = "#d4af37"

# Win / lose / push -- the one 3-way mapping used everywhere a result (a bet,
# a hand, a round) is colored: finances, stats, the poker result/payout panel.
# WIN_COLOR tracks the active theme's own ACCENT (recomputed alongside it,
# see _recompute_derived below) rather than being a separate frozen copy.
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
# All of the below are DERIVED from the six theme-driven tokens above (plus
# the fixed WARN/LOSE_COLOR/SECONDARY/LOCK_RED/LOCK_DARK_RED) -- computed
# once here at import time, and again by _recompute_derived() whenever
# set_active_theme() swaps the theme.
ACCENT_DIM_BG = lerp_color(BG, ACCENT, 0.12)
ACCENT_DIM_BG_ELEVATED = lerp_color(BG_ELEVATED, ACCENT, 0.14)
WARN_DIM_BG = lerp_color(BG, WARN, 0.12)
LOSE_DIM_BG = lerp_color(BG, LOSE_COLOR, 0.12)
LOSE_DIM_BG_ELEVATED = lerp_color(BG_ELEVATED, LOSE_COLOR, 0.14)
SECONDARY_DIM_MENU_BG = lerp_color(MENU_BG, SECONDARY, 0.16)
# The gold-tinted fill behind a "+N Crowns" pill badge drawn on a
# BG_ELEVATED surface (the achievement banner, achievement cards) -- same
# formula as ACCENT_DIM_BG_ELEVATED just above, in SECONDARY's own gold.
SECONDARY_DIM_BG_ELEVATED = lerp_color(BG_ELEVATED, SECONDARY, 0.14)

# A visible neutral-grey rule for separators against MENU_BG -- BORDER/
# BORDER_SOFT are calibrated for the near-black BG and read as almost
# invisible against the lighter MENU_BG, so this is its own, brighter token.
MENU_DIVIDER = lerp_color(MENU_BG, "#ffffff", 0.15)

# Locked-game tile styling (ui/main_menu.py, core/unlocks.py) -- LOCK_RED/
# LOCK_DARK_RED are fixed signal colours (see module docstring); the rest
# are BG-derived tints, so they're recomputed per-theme too.
LOCK_RED = "#c23b3b"
LOCK_DARK_RED = "#5B1313"
LOCK_BORDER = lerp_color(BG, LOCK_RED, 0.55)
LOCK_BG = lerp_color(BG, LOCK_RED, 0.05)
LOCK_FG = lerp_color(BG, LOCK_DARK_RED, 0.75)
LOCK_FG_DIM = lerp_color(BG, LOCK_RED, 0.55)

# Every module-level name whose value can change when the active theme
# changes -- the six base tokens plus every derived blend above. Read by
# set_active_theme() to snapshot "before" values and write "after" ones;
# listed by name (not value) since several of these legitimately share a
# value at any one time (e.g. WIN_COLOR == ACCENT).
_THEME_DRIVEN_NAMES = (
    "BG", "BG_ELEVATED", "ACCENT", "BORDER", "BORDER_SOFT", "MENU_BG",
    "WIN_COLOR",
    "ACCENT_DIM_BG", "ACCENT_DIM_BG_ELEVATED", "WARN_DIM_BG",
    "LOSE_DIM_BG", "LOSE_DIM_BG_ELEVATED",
    "SECONDARY_DIM_MENU_BG", "SECONDARY_DIM_BG_ELEVATED", "MENU_DIVIDER",
    "LOCK_BORDER", "LOCK_BG", "LOCK_FG", "LOCK_FG_DIM",
)


def _recompute_derived():
    """Re-runs every lerp_color() blend above off the CURRENT BG/BG_ELEVATED
    /ACCENT/MENU_BG globals -- called once at import (identical output to
    the literal computation above) and again by set_active_theme() any time
    those six change."""
    global ACCENT_DIM_BG, ACCENT_DIM_BG_ELEVATED, WARN_DIM_BG
    global LOSE_DIM_BG, LOSE_DIM_BG_ELEVATED
    global SECONDARY_DIM_MENU_BG, SECONDARY_DIM_BG_ELEVATED, MENU_DIVIDER
    global LOCK_BORDER, LOCK_BG, LOCK_FG, LOCK_FG_DIM, WIN_COLOR
    WIN_COLOR = ACCENT
    ACCENT_DIM_BG = lerp_color(BG, ACCENT, 0.12)
    ACCENT_DIM_BG_ELEVATED = lerp_color(BG_ELEVATED, ACCENT, 0.14)
    WARN_DIM_BG = lerp_color(BG, WARN, 0.12)
    LOSE_DIM_BG = lerp_color(BG, LOSE_COLOR, 0.12)
    LOSE_DIM_BG_ELEVATED = lerp_color(BG_ELEVATED, LOSE_COLOR, 0.14)
    SECONDARY_DIM_MENU_BG = lerp_color(MENU_BG, SECONDARY, 0.16)
    SECONDARY_DIM_BG_ELEVATED = lerp_color(BG_ELEVATED, SECONDARY, 0.14)
    MENU_DIVIDER = lerp_color(MENU_BG, "#ffffff", 0.15)
    LOCK_BORDER = lerp_color(BG, LOCK_RED, 0.55)
    LOCK_BG = lerp_color(BG, LOCK_RED, 0.05)
    LOCK_FG = lerp_color(BG, LOCK_DARK_RED, 0.75)
    LOCK_FG_DIM = lerp_color(BG, LOCK_RED, 0.55)


def set_active_theme(palette):
    """Swaps the active theme -- `palette` is one core/themes.py entry
    (THEMES/PREMIUM_THEMES value; resolve() already handles fallback).
    Reassigns the six base tokens, recomputes every derived blend, and
    returns a {old_hex: new_hex} map of every token that actually changed
    (base + derived) for retheme_widget_tree() to apply to already-built
    widgets. Pairs where old == new are skipped, so re-applying the theme
    that's already active returns an empty map and is a cheap no-op for
    the caller."""
    global BG, BG_ELEVATED, ACCENT, BORDER, BORDER_SOFT, MENU_BG
    before = {name: globals()[name] for name in _THEME_DRIVEN_NAMES}
    BG = palette["bg"]
    BG_ELEVATED = palette["bg_elevated"]
    ACCENT = palette["accent"]
    BORDER = palette["border"]
    BORDER_SOFT = palette["border_soft"]
    MENU_BG = palette["menu_bg"]
    _recompute_derived()
    color_map = {}
    for name in _THEME_DRIVEN_NAMES:
        old, new = before[name], globals()[name]
        if old != new:
            color_map[old] = new
    return color_map


# Every Tk widget option that can hold one of the colors above -- checked
# (defensively, via cget/TclError, since not every widget class supports
# every one of these) by retheme_widget_tree() below.
_RETHEME_OPTIONS = (
    "bg", "fg", "highlightbackground", "highlightcolor", "insertbackground",
    "activebackground", "activeforeground", "selectcolor", "troughcolor",
    "disabledforeground",
)


def retheme_widget_tree(widget, color_map):
    """Recursively repaints an already-built widget tree in place -- for
    every option in _RETHEME_OPTIONS, swaps it to color_map's new value if
    its current value is one of color_map's old ones. Generalizes the
    single-color, bg-only `_retheme_widget` every game table already has
    for its own felt (see e.g. games/blackjack/ui.py) to the whole app-wide
    chrome palette above; the two operate on disjoint sets of colors (felt
    vs. chrome) so a table's own felt walk and this one compose safely.
    A no-op (returns immediately) for an empty color_map."""
    if not color_map:
        return
    for option in _RETHEME_OPTIONS:
        try:
            current = widget.cget(option)
        except tk.TclError:
            continue
        new = color_map.get(current)
        if new is not None:
            try:
                widget.configure(**{option: new})
            except tk.TclError:
                pass
    for child in widget.winfo_children():
        retheme_widget_tree(child, color_map)

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


def diamond(canvas, cx, cy, r, **kwargs):
    """A diamond (rotated square) centred at (cx, cy), its 4 points r away
    from centre -- used for Mississippi Stud's "3 Card Bonus" bet spot, the
    first bet spot in the app that isn't a circle or rounded rect."""
    points = [cx, cy - r, cx + r, cy, cx, cy + r, cx - r, cy]
    return canvas.create_polygon(points, **kwargs)


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


def outlined_glyph(canvas, cx, cy, text, size, fill, outline, outline_width=1, weight="bold", tags=()):
    """A single character (or short word) with a solid fill and a colored
    outline -- Tk canvas text only ever takes one fill color, so the outline
    is faked by drawing the glyph several times at small offsets in
    `outline`, then once more dead-center in `fill` on top. Good enough at
    icon sizes (a handful of px of offset); not meant for large display type."""
    f = font(size, weight=weight)
    for dx in (-outline_width, 0, outline_width):
        for dy in (-outline_width, 0, outline_width):
            if dx or dy:
                canvas.create_text(cx + dx, cy + dy, text=text, font=f, fill=outline, tags=tags)
    canvas.create_text(cx, cy, text=text, font=f, fill=fill, tags=tags)


def breadcrumb(parent, path, bg, host="hadfield-casino", player="player"):
    """A dim shell-prompt-style breadcrumb label, e.g.
    "mike@hadfield-casino:~/cashier" -- the site's own top-bar signature.
    `player` defaults to the literal word "player" so a call site built
    before a profile exists (ui/logon_screen.py) still renders sensibly;
    every screen built after login passes its actual player's name (see
    CasinoApp.start_session in main.py). Read live at construction time,
    not refreshed afterwards -- a mid-session rename wouldn't update an
    already-built screen's banner until relaunch, the same pre-existing
    limitation Settings' table-theme picker has (see core/settings.py)."""
    text = f"{player}@{host}:~/{path}"
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
