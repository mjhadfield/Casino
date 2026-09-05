"""
The game-tile widget (icon + name + subtitle + PLAY/LOCKED/SOON pill,
optionally padlocked) shared by the main menu and any game-family picker
screen (e.g. ui/blackjack_menu.py's Standard/Counting choice) -- pulled out
of ui/main_menu.py's own MainMenuFrame since it never actually depended on
that class (every dependency -- the grid to place into, the app-level
unlock/playable state -- was already passed in as a parameter), matching
ui/chips.py's own "shared function takes the widget explicitly" convention.
"""
import tkinter as tk

from ui import game_icons, theme

ICON_CANVAS_SIZE = 64  # fixed footprint every icon (glyph or vector) sits in
ICON_DRAW_SIZE = 44    # the size passed to a vector icon's draw_* function

# The lock-status badge -- sits in the game *tile's* own top-right corner
PADLOCK_SIZE = 22
PADLOCK_CANVAS = round(PADLOCK_SIZE * 1.5)
PADLOCK_MARGIN = 6

# Every tile is forced to exactly this size (see make_game_tile) so a longer
# subtitle -- or a longer *name* that wraps ("Pai Gow Poker (Face Up!)",
# "Ultimate Texas Hold'em") -- can never make its tile taller or wider than
# the rest.
TILE_WIDTH = 220
TILE_HEIGHT = 214
TILE_TEXT_WRAP = 190


def make_game_tile(grid, row, col, icon, name, subtitle, unlocked, playable, command=None):
    # theme.BG (the app's near-black, not MENU_BG) -- differentiates a tile
    # from a lighter MENU_BG page background; LOCK_BG for a still-locked
    # game instead, its dedicated dark-red tint (see ui/theme.py).
    bg = theme.BG if unlocked else theme.LOCK_BG
    if not unlocked:
        fg, sub_fg = theme.LOCK_FG, theme.LOCK_FG_DIM
    elif playable:
        fg, sub_fg = theme.FG, theme.FG_DIM
    else:
        # Unlocked, but not built yet -- same dim, muted look every "coming
        # soon" placeholder always had.
        fg, sub_fg = theme.GREY_BTN_TEXT, theme.GREY_BTN_TEXT

    tile = tk.Frame(
        grid, bg=bg, width=TILE_WIDTH, height=TILE_HEIGHT,
        highlightbackground=theme.ACCENT if playable else bg,
        highlightthickness=2 if playable else 0,
    )
    tile.grid(row=row, column=col, padx=14, pady=10)
    # Contents are placed with pack() -- pack_propagate (not grid_propagate,
    # which only governs *grid*-managed children) is what stops a longer
    # wrapped subtitle from growing this particular tile taller/wider than
    # the fixed size every tile is given above.
    tile.pack_propagate(False)

    if not playable:
        # A Frame border can only ever be solid -- the site's dashed
        # "soon"/"locked" look has to be Canvas-drawn, sized to exactly
        # cover the tile and placed behind everything else (created first,
        # so every later-packed child renders on top of it).
        border_canvas = tk.Canvas(tile, width=TILE_WIDTH, height=TILE_HEIGHT, bg=bg, highlightthickness=0)
        border_canvas.place(x=0, y=0)
        dash_color = theme.LOCK_BORDER if not unlocked else theme.GREY_BTN_BORDER
        theme.dashed_rect(
            border_canvas, 2, 2, TILE_WIDTH - 2, TILE_HEIGHT - 2, radius=theme.RADIUS,
            outline=dash_color, width=1.5, dash=(5, 3), fill="",
        )

    icon_widget = tk.Canvas(tile, width=ICON_CANVAS_SIZE, height=ICON_CANVAS_SIZE,
                             bg=bg, highlightthickness=0)
    if callable(icon):
        # A vector icon (game_icons.draw_*): fixed-size canvas so it's
        # guaranteed the same footprint as every other tile's icon.
        icon(icon_widget, ICON_CANVAS_SIZE / 2, ICON_CANVAS_SIZE / 2, ICON_DRAW_SIZE, fg)
    else:
        icon_widget.create_text(ICON_CANVAS_SIZE / 2, ICON_CANVAS_SIZE / 2, text=icon,
                                 fill=fg, font=theme.font(36))
    icon_widget.pack(pady=(14, 4))
    # height=2 reserves the same two-line footprint whether this particular
    # name wraps to one line or two -- a plain single-line game name
    # ("Blackjack") and a longer one that wraps ("Pai Gow Poker (Face Up!)")
    # both end up the same tile height.
    name_lbl = tk.Label(tile, text=name, bg=bg, fg=fg, font=theme.font(13, weight="bold"),
                         wraplength=TILE_TEXT_WRAP, justify="center", height=2)
    name_lbl.pack()
    # Same reasoning, for the subtitle underneath.
    sub_lbl = tk.Label(tile, text=subtitle, bg=bg, fg=sub_fg,
                        font=theme.font(9), wraplength=TILE_TEXT_WRAP, justify="center", height=2)
    sub_lbl.pack(pady=(2, 0))

    status_widgets = [tile, icon_widget, name_lbl, sub_lbl]
    pill_canvas = tk.Canvas(tile, width=TILE_TEXT_WRAP, height=24, bg=bg, highlightthickness=0)
    pill_canvas.pack(pady=(6, 0))
    if playable:
        # Same small rounded pill as "SOON" below, just in the tile's own
        # accent colour (matching its highlighted border) rather than the
        # muted "not yet built" grey, and "PLAY" instead.
        theme.pill(pill_canvas, TILE_TEXT_WRAP / 2, 12, "PLAY",
                   fill=theme.ACCENT_DIM_BG, outline=theme.ACCENT, text_fg=theme.ACCENT)
    elif not unlocked:
        theme.pill(pill_canvas, TILE_TEXT_WRAP / 2, 12, "LOCKED",
                   fill=theme.LOCK_BG, outline=theme.LOCK_BORDER, text_fg=theme.LOCK_FG)
    else:
        # A small rounded "SOON" pill, matching the site's .link-btn__tag --
        # replaces the old plain "COMING SOON" text label.
        theme.pill(pill_canvas, TILE_TEXT_WRAP / 2, 12, "SOON")
    status_widgets.append(pill_canvas)

    if not unlocked:
        # Lock-status badge
        padlock_canvas = tk.Canvas(tile, width=PADLOCK_CANVAS, height=PADLOCK_CANVAS, bg=bg, highlightthickness=0)
        padlock_canvas.place(x=TILE_WIDTH - PADLOCK_MARGIN - PADLOCK_CANVAS, y=PADLOCK_MARGIN)
        game_icons.draw_padlock(padlock_canvas, PADLOCK_CANVAS / 2, PADLOCK_CANVAS * 0.6, PADLOCK_SIZE,
                                 theme.LOCK_RED, locked=True)
        status_widgets.append(padlock_canvas)

    if playable and command:
        for widget in status_widgets:
            widget.configure(cursor="hand2")
            widget.bind("<Button-1>", lambda _e: command())
