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

from ui import game_icons, theme, tooltip

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


def make_game_tile(grid, row, col, icon, name, subtitle, unlocked, playable, command=None, border_color=None,
                    subtitle_font_size=9, subtitle_lines=2, pill_label="PLAY",
                    tooltip_text=None, locked_command=None, disabled_pill_label=None):
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

    # border_color overrides the usual mint ACCENT border/pill for a tile
    # that isn't a locked/unlocked GAME at all (see ui/main_menu.py's own
    # Crowns Store tile, always playable, gold instead) -- every other
    # tile leaves this None and gets the ordinary ACCENT treatment.
    accent = border_color or theme.ACCENT

    tile = tk.Frame(
        grid, bg=bg, width=TILE_WIDTH, height=TILE_HEIGHT,
        highlightbackground=accent if playable else bg,
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
    # Same reasoning, for the subtitle underneath. subtitle_font_size/
    # subtitle_lines only ever move off their defaults (9pt, 2 lines) for a
    # tile whose copy genuinely can't fit two lines at the normal size
    # within the fixed width every tile shares (see ui/main_menu.py's own
    # Crowns Store tile, whose description is a full sentence plus a live
    # balance figure, needing 3 lines at a smaller size) -- every other
    # caller leaves both at their defaults and looks exactly as before.
    sub_lbl = tk.Label(tile, text=subtitle, bg=bg, fg=sub_fg, font=theme.font(subtitle_font_size),
                        wraplength=TILE_TEXT_WRAP, justify="center", height=subtitle_lines)
    sub_lbl.pack(pady=(2, 0))

    status_widgets = [tile, icon_widget, name_lbl, sub_lbl]
    pill_canvas = tk.Canvas(tile, width=TILE_TEXT_WRAP, height=24, bg=bg, highlightthickness=0)
    pill_canvas.pack(pady=(6, 0))
    if playable:
        # Same small rounded pill as "SOON" below, just in the tile's own
        # accent colour (matching its highlighted border) rather than the
        # muted "not yet built" grey, and pill_label ("PLAY" for every
        # actual game; ui/main_menu.py's Crowns Store tile is the one
        # exception, "OPEN" instead -- it isn't a game to "play").
        theme.pill(pill_canvas, TILE_TEXT_WRAP / 2, 12, pill_label,
                   fill=theme.lerp_color(theme.BG, accent, 0.12), outline=accent, text_fg=accent)
    elif not unlocked:
        theme.pill(pill_canvas, TILE_TEXT_WRAP / 2, 12, "LOCKED",
                   fill=theme.LOCK_BG, outline=theme.LOCK_BORDER, text_fg=theme.LOCK_FG)
    else:
        # A small rounded "SOON" pill, matching the site's .link-btn__tag --
        # replaces the old plain "COMING SOON" text label. disabled_pill_label
        # overrides this default only for a tile that's unlocked-but-inert
        # for a reason OTHER than "not built yet" (ui/main_menu.py's own
        # Crowns Store tile shows "N/A" here for a Sandbox player, whose
        # achievements are switched off entirely).
        theme.pill(pill_canvas, TILE_TEXT_WRAP / 2, 12, disabled_pill_label or "SOON")
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
    elif not unlocked and locked_command:
        # A locked tile's own click handler -- ui/main_menu.py's top-level
        # game tiles offer an early-unlock-for-Crowns prompt here;
        # ui/table_menu.py's sub-table tiles pass a plain "must be earned"
        # info dialog instead (see decision #4 in the plan -- only
        # main-menu-tile games can be bought early).
        for widget in status_widgets:
            widget.configure(cursor="hand2")
            widget.bind("<Button-1>", lambda _e: locked_command())

    if tooltip_text is not None:
        # The whole status_widgets group (the outer tile Frame plus every
        # child drawn on top of it) is treated as ONE hoverable region --
        # see ui/tooltip.py's own attach(): shown once centred on the tile
        # (status_widgets[0] is always the outer Frame, spanning the
        # tile's full size) regardless of which child widget triggered it,
        # and only hidden once the mouse has left the tile entirely, not
        # every time it crosses from one child widget to another.
        tooltip.attach(status_widgets, tooltip_text)
