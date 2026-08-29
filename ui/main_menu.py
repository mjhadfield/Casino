import tkinter as tk

from ui import game_icons, theme

# One row per game tile: (icon, name, subtitle, game_key, frame_name).
# `icon` is either a single glyph string, rendered as text (supported, but
# no current row actually uses one -- every game now has its own themed
# game_icons.draw_* vector icon instead), or one of game_icons.draw_*,
# rendered as a small vector icon on a fixed-size canvas so every tile's
# icon reads as the same size regardless of what emoji font support
# happens to be installed (see game_icons.py). `game_key` is looked
# up in app.unlocks (core/unlocks.py) to decide whether this tile is drawn
# in its normal colours or recoloured red as still-locked (see
# _make_game_tile) -- either way its real icon/name/subtitle are shown.
# `frame_name` is looked up in app.frames via show_frame once a game is both
# unlocked and actually implemented; leave it None for a "Coming soon"
# placeholder that just isn't built yet.
#
# To add a new game later: add one row here (a default lock state in
# core/unlocks.py's DEFAULT_UNLOCKS, and once it's implemented, an icon in
# game_icons.py and a real frame_name) -- the grid below lays itself out
# automatically, no layout code to touch.

VERSION = "1.7.2"

GAMES = [
    (game_icons.draw_three_card_poker_icon, "Three Card Poker", "Ante, Play, Pair Plus & Prime side bets",
     "three_card_poker", "three_card_poker"),
    (game_icons.draw_blackjack_icon, "Blackjack", "Super Pairs, 21+3, Top 3 & Jackpot side bets",
     "blackjack", "blackjack"),
    (game_icons.draw_pai_gow_icon, "Pai Gow Poker", "'Fortune' variant, with face down dealer hand.",
     "pai_gow_poker", "pai_gow_poker"),
    (game_icons.draw_pai_gow_face_up_icon, "Pai Gow Poker\n(Face Up!)",
     "Dealer plays face up, with no commission.", "pai_gow_poker_face_up", "pai_gow_poker_face_up"),
    (game_icons.draw_mississippi_stud_icon, "Mississippi Stud", "3 Card Bonus side bet",
     "mississippi_stud", "mississippi_stud"),
    (game_icons.draw_ultimate_texas_holdem_icon, "Ultimate Texas Hold'em",
     "Trips bonus, Progressive Jackpot", "ultimate_texas_holdem", "ultimate_texas_holdem"),
    (game_icons.draw_baccarat_icon, "Baccarat", "Dragon Bonus & 5 Treasures side bets",
     "baccarat", "baccarat"),
    (game_icons.draw_let_it_ride_icon, "Let It Ride", "3 starter bets -- pull back or let it ride",
     "let_it_ride", "let_it_ride"),
    (game_icons.draw_high_card_flush_icon, "High Card Flush",
     "Flush bonus, Straight bonus", "high_card_flush", "high_card_flush"),
]
GAMES_PER_ROW = 3

ICON_CANVAS_SIZE = 64  # fixed footprint every icon (glyph or vector) sits in
ICON_DRAW_SIZE = 44    # the size passed to a vector icon's draw_* function

# The lock-status badge -- sits in the game *tile's* own top-right corner
PADLOCK_SIZE = 22
PADLOCK_CANVAS = round(PADLOCK_SIZE * 1.5)
PADLOCK_MARGIN = 6

# Every tile is forced to exactly this size (see _make_game_tile) so a
# longer subtitle -- or, since some of these full game names now run long
# enough to wrap ("Pai Gow Poker (Face Up!)", "Ultimate Texas Hold'em") --
# a longer *name* can never make its tile taller or wider than the rest.
TILE_WIDTH = 220
TILE_HEIGHT = 214
TILE_TEXT_WRAP = 190


SPADE_CANVAS_SIZE = 28  # fixed footprint for the title's flanking spade accents


class MainMenuFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.MENU_BG)
        self.app = app

        # --- top bar --- MENU_BG throughout, not theme.BG_ELEVATED -- this
        # screen alone uses the lighter "terminal" background (see
        # ui/theme.py's MENU_BG docstring); every other screen's top bar
        # still uses the app-wide BG_ELEVATED.
        top_bar = tk.Frame(self, bg=theme.MENU_BG)
        top_bar.pack(fill="x", side="top")

        self._make_spade(top_bar).pack(side="left", padx=(20, 8), pady=14)
        tk.Label(
            top_bar, text=f"HADFIELD CASINO v{VERSION}", bg=theme.MENU_BG, fg=theme.SECONDARY,
            font=theme.font(18, weight="bold"),
        ).pack(side="left")
        self._make_spade(top_bar).pack(side="left", padx=(8, 0), pady=14)

        # Packed right-to-left (side="right" stacks inward from the right
        # edge, each new one landing left of the previous), so this order --
        # Cashier, then Stats, then Settings -- reads left-to-right on
        # screen as Settings, Stats, Cashier.
        self.balance_btn = tk.Button(
            top_bar, text="Cashier: £0.00", bg=theme.MENU_BG, fg=theme.WIN_COLOR,
            activebackground=theme.ACCENT_DIM_BG_ELEVATED, activeforeground=theme.WIN_COLOR,
            font=theme.font(12, weight="bold"), relief="flat", padx=14, pady=8,
            highlightthickness=1, highlightbackground=theme.BORDER, highlightcolor=theme.ACCENT,
            cursor="hand2", command=lambda: app.show_frame("finances"),
        )
        self.balance_btn.pack(side="right", padx=(6, 20), pady=14)

        # Stats/Settings get the SECONDARY (gold) treatment rather than
        # ACCENT -- a second, warmer highlight so the top bar isn't just the
        # one mint accent everywhere; Cashier already pops on its own via
        # WIN_COLOR since it's showing money.
        tk.Button(
            top_bar, text="\U0001F4CA Stats", bg=theme.MENU_BG, fg=theme.SECONDARY,
            activebackground=theme.SECONDARY_DIM_MENU_BG, activeforeground=theme.SECONDARY,
            font=theme.font(12), relief="flat", padx=14, pady=8,
            highlightthickness=1, highlightbackground=theme.SECONDARY, highlightcolor=theme.SECONDARY,
            cursor="hand2", command=lambda: app.show_frame("stats"),
        ).pack(side="right", padx=6, pady=14)

        tk.Button(
            top_bar, text="⚙ Settings", bg=theme.MENU_BG, fg=theme.SECONDARY,
            activebackground=theme.SECONDARY_DIM_MENU_BG, activeforeground=theme.SECONDARY,
            font=theme.font(12), relief="flat", padx=14, pady=8,
            highlightthickness=1, highlightbackground=theme.SECONDARY, highlightcolor=theme.SECONDARY,
            cursor="hand2", command=lambda: app.show_frame("settings"),
        ).pack(side="right", padx=6, pady=14)

        breadcrumb_lbl = theme.breadcrumb(top_bar, "menu", bg=theme.MENU_BG,
                                           player=app.current_player["name"])
        breadcrumb_lbl.pack(side="right", padx=(6, 6), pady=14)

        # A visible grey rule between the top bar and the body -- MENU_BG is
        # light enough that the bar needs its own separator rather than
        # relying on a color difference the way the darker BG screens do.
        tk.Frame(self, bg=theme.MENU_DIVIDER, height=1).pack(fill="x")

        # --- body ---
        body = tk.Frame(self, bg=theme.MENU_BG)
        body.pack(fill="both", expand=True)

        # Built empty here; _build_tiles (called once now, and again every
        # time this screen is shown -- see on_show) populates it fresh each
        # time, since a game's lock state can change on the Settings screen
        # in between visits and a tile's look needs to catch up to that.
        # pady is intentionally tight -- with 3 rows of taller (2-line-name-
        # reserving) tiles below, this window's fixed 820px height leaves
        # very little vertical slack to begin with (see _make_game_tile and
        # TILE_HEIGHT's own comment).
        self.tile_grid = tk.Frame(body, bg=theme.MENU_BG)
        self.tile_grid.pack(pady=(16, 10))
        self._build_tiles()

    def _build_tiles(self):
        for child in self.tile_grid.winfo_children():
            child.destroy()
        for i, (icon, name, subtitle, game_key, frame_name) in enumerate(GAMES):
            row, col = divmod(i, GAMES_PER_ROW)
            unlocked = self.app.unlocks.is_unlocked(game_key)
            playable = unlocked and frame_name is not None
            command = (lambda f=frame_name: self.app.show_frame(f)) if playable else None
            self._make_game_tile(self.tile_grid, row, col, icon, name, subtitle, unlocked, playable, command=command)

    def _make_spade(self, parent):
        """A small black-fill, mint-outline spade -- a purely decorative
        accent flanking the "HADFIELD CASINO" title, replacing the traffic-
        light dots that used to sit there (see ui/theme.py's outlined_glyph;
        plain Tk text can't have a two-tone fill/outline on its own)."""
        canvas = tk.Canvas(parent, width=SPADE_CANVAS_SIZE, height=SPADE_CANVAS_SIZE,
                            bg=theme.MENU_BG, highlightthickness=0)
        theme.outlined_glyph(canvas, SPADE_CANVAS_SIZE / 2, SPADE_CANVAS_SIZE / 2, "♠",
                              size=22, fill="#000000", outline=theme.ACCENT)
        return canvas

    def _make_game_tile(self, grid, row, col, icon, name, subtitle, unlocked, playable, command=None):
        # theme.BG (the app's near-black, not MENU_BG) -- differentiates a
        # tile from this screen's own lighter MENU_BG page background;
        # LOCK_BG for a still-locked game instead, its dedicated dark-red
        # tint (see ui/theme.py).
        bg = theme.BG if unlocked else theme.LOCK_BG
        if not unlocked:
            fg, sub_fg = theme.LOCK_FG, theme.LOCK_FG_DIM
        elif playable:
            fg, sub_fg = theme.FG, theme.FG_DIM
        else:
            # Unlocked, but not built yet (e.g. Mississippi Stud) -- same
            # dim, muted look the old "coming soon" placeholders always had.
            fg, sub_fg = theme.GREY_BTN_TEXT, theme.GREY_BTN_TEXT

        tile = tk.Frame(
            grid, bg=bg, width=TILE_WIDTH, height=TILE_HEIGHT,
            highlightbackground=theme.ACCENT if playable else bg,
            highlightthickness=2 if playable else 0,
        )
        tile.grid(row=row, column=col, padx=14, pady=10)
        # Contents are placed with pack() -- pack_propagate (not
        # grid_propagate, which only governs *grid*-managed children) is
        # what stops a longer wrapped subtitle from growing this particular
        # tile taller/wider than the fixed size every tile is given above.
        tile.pack_propagate(False)

        if not playable:
            # A Frame border can only ever be solid -- the site's dashed
            # "soon"/"locked" look has to be Canvas-drawn, sized to exactly
            # cover the tile and placed behind everything else (created
            # first, so every later-packed child renders on top of it).
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
        # height=2 reserves the same two-line footprint whether this
        # particular name wraps to one line or two -- a plain single-line
        # game name ("Blackjack") and a longer one that wraps ("Pai Gow
        # Poker (Face Up!)"
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
            # Same small rounded pill as "SOON" below, just in the tile's
            # own accent colour (matching its highlighted border) rather
            # than the muted "not yet built" grey, and "PLAY" instead.
            theme.pill(pill_canvas, TILE_TEXT_WRAP / 2, 12, "PLAY",
                       fill=theme.ACCENT_DIM_BG, outline=theme.ACCENT, text_fg=theme.ACCENT)
        elif not unlocked:
            theme.pill(pill_canvas, TILE_TEXT_WRAP / 2, 12, "LOCKED",
                       fill=theme.LOCK_BG, outline=theme.LOCK_BORDER, text_fg=theme.LOCK_FG)
        else:
            # A small rounded "SOON" pill, matching the site's .link-btn__tag
            # -- replaces the old plain "COMING SOON" text label.
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

    def on_show(self):
        self.refresh_balance()
        self._build_tiles()

    def refresh_balance(self):
        self.balance_btn.configure(text=f"Cashier: £{self.app.finance.balance:,.2f}")
