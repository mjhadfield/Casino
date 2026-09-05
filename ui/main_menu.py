import tkinter as tk

from ui import game_icons, game_tile, theme

# One row per game tile: (icon, name, subtitle, game_key, frame_name).
# `icon` is either a single glyph string, rendered as text (supported, but
# no current row actually uses one -- every game now has its own themed
# game_icons.draw_* vector icon instead), or one of game_icons.draw_*,
# rendered as a small vector icon on a fixed-size canvas so every tile's
# icon reads as the same size regardless of what emoji font support
# happens to be installed (see game_icons.py). `game_key` is looked
# up in app.unlocks (core/unlocks.py) to decide whether this tile is drawn
# in its normal colours or recoloured red as still-locked (see
# ui/game_tile.py's make_game_tile) -- either way its real icon/name/
# subtitle are shown.
# `frame_name` is looked up in app.frames via show_frame once a game is both
# unlocked and actually implemented; leave it None for a "Coming soon"
# placeholder that just isn't built yet.
#
# To add a new game later: add one row here (a default lock state in
# core/unlocks.py's DEFAULT_UNLOCKS, and once it's implemented, an icon in
# game_icons.py and a real frame_name) -- the grid below lays itself out
# automatically, no layout code to touch.

VERSION = "1.8.0"

GAMES = [
    (game_icons.draw_three_card_poker_icon, "Three Card Poker", "Ante, Play, Pair Plus & Prime side bets",
     "three_card_poker", "three_card_poker"),
    (game_icons.draw_blackjack_icon, "Blackjack", "Super Pairs, 21+3, Top 3 & Jackpot side bets",
     "blackjack", "blackjack_menu"),
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
        # very little vertical slack to begin with (see ui/game_tile.py's
        # make_game_tile and its own TILE_HEIGHT comment).
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
            game_tile.make_game_tile(self.tile_grid, row, col, icon, name, subtitle, unlocked, playable, command=command)

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

    def on_show(self):
        self.refresh_balance()
        self._build_tiles()

    def refresh_balance(self):
        self.balance_btn.configure(text=f"Cashier: £{self.app.finance.balance:,.2f}")
