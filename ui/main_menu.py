import tkinter as tk

from ui import game_icons, theme

# One row per game tile: (icon, name, subtitle, enabled, frame_name).
# `icon` is either a single glyph string, rendered as text (the way Three
# Card Poker's is -- its icon is kept exactly as it was), or one of
# game_icons.draw_*, rendered as a small vector icon on a fixed-size canvas
# so every tile's icon reads as the same size regardless of what emoji font
# support happens to be installed (see game_icons.py). `frame_name` is
# looked up in app.frames via show_frame when the tile's enabled; leave it
# None for a "Coming soon" placeholder.
#
# To add a new game later: add one row here (and, once it's implemented, an
# icon in game_icons.py and a real frame_name) -- the grid below lays itself
# out automatically, no layout code to touch.
GAMES = [
    ("\U0001F0A1", "Three Card Poker", "Ante, Play, Pair Plus & Prime side bets",
     True, "three_card_poker"),
    (game_icons.draw_blackjack_icon, "Blackjack", "Super Pairs, 21+3, Top 3 & Jackpot side bets",
     True, "blackjack"),
    (game_icons.draw_pai_gow_icon, "Pai Gow Poker", "Fortune Bonus & Pai Gow Insurance",
     False, None),
    (game_icons.draw_mississippi_stud_icon, "Mississippi Stud", "3 Card Bonus side bet",
     False, None),
    (game_icons.draw_baccarat_icon, "Baccarat", "Perfect Pair & Dragon Bonus side bets",
     False, None),
    (game_icons.draw_let_it_ride_icon, "Let It Ride", "3 starter bets -- pull back or let it ride",
     False, None),
    ("?", "Unknown", "<REDACTED>", False, None),
    ("?", "Unknown", "<REDACTED>", False, None),
    ("?", "Unknown", "<REDACTED>", False, None),
]
GAMES_PER_ROW = 3

ICON_CANVAS_SIZE = 64  # fixed footprint every icon (glyph or vector) sits in
ICON_DRAW_SIZE = 44    # the size passed to a vector icon's draw_* function

# Every tile is forced to exactly this size (see _make_game_tile) so a
# longer subtitle on one game can never make its tile taller or wider than
# the rest.
TILE_WIDTH = 220
TILE_HEIGHT = 190
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
            top_bar, text="HADFIELD CASINO", bg=theme.MENU_BG, fg=theme.SECONDARY,
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

        breadcrumb_lbl = theme.breadcrumb(top_bar, "menu", bg=theme.MENU_BG)
        breadcrumb_lbl.pack(side="right", padx=(6, 6), pady=14)

        # A visible grey rule between the top bar and the body -- MENU_BG is
        # light enough that the bar needs its own separator rather than
        # relying on a color difference the way the darker BG screens do.
        tk.Frame(self, bg=theme.MENU_DIVIDER, height=1).pack(fill="x")

        # --- body ---
        body = tk.Frame(self, bg=theme.MENU_BG)
        body.pack(fill="both", expand=True)

        grid = tk.Frame(body, bg=theme.MENU_BG)
        grid.pack(pady=30)

        for i, (icon, name, subtitle, enabled, frame_name) in enumerate(GAMES):
            row, col = divmod(i, GAMES_PER_ROW)
            command = (lambda f=frame_name: app.show_frame(f)) if (enabled and frame_name) else None
            self._make_game_tile(grid, row, col, icon, name, subtitle, enabled, command=command)

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

    def _make_game_tile(self, grid, row, col, icon, name, subtitle, enabled, command=None):
        # theme.BG (the app's near-black, not MENU_BG) -- differentiates a
        # tile from this screen's own lighter MENU_BG page background.
        bg = theme.BG
        fg = theme.FG if enabled else theme.GREY_BTN_TEXT
        sub_fg = theme.FG_DIM if enabled else theme.GREY_BTN_TEXT

        tile = tk.Frame(
            grid, bg=bg, width=TILE_WIDTH, height=TILE_HEIGHT,
            highlightbackground=theme.ACCENT if enabled else bg,
            highlightthickness=2 if enabled else 0,
        )
        tile.grid(row=row, column=col, padx=14, pady=14)
        # Contents are placed with pack() -- pack_propagate (not
        # grid_propagate, which only governs *grid*-managed children) is
        # what stops a longer wrapped subtitle from growing this particular
        # tile taller/wider than the fixed size every tile is given above.
        tile.pack_propagate(False)

        if not enabled:
            # A Frame border can only ever be solid -- the site's dashed
            # "soon" look has to be Canvas-drawn, sized to exactly cover the
            # tile and placed behind everything else (created first, so
            # every later-packed child renders on top of it).
            border_canvas = tk.Canvas(tile, width=TILE_WIDTH, height=TILE_HEIGHT, bg=bg, highlightthickness=0)
            border_canvas.place(x=0, y=0)
            theme.dashed_rect(
                border_canvas, 2, 2, TILE_WIDTH - 2, TILE_HEIGHT - 2, radius=theme.RADIUS,
                outline=theme.GREY_BTN_BORDER, width=1.5, dash=(5, 3), fill="",
            )

        if callable(icon):
            # A vector icon (game_icons.draw_*): fixed-size canvas so it's
            # guaranteed the same footprint as every other tile's icon.
            icon_widget = tk.Canvas(tile, width=ICON_CANVAS_SIZE, height=ICON_CANVAS_SIZE,
                                     bg=bg, highlightthickness=0)
            icon(icon_widget, ICON_CANVAS_SIZE / 2, ICON_CANVAS_SIZE / 2, ICON_DRAW_SIZE, fg)
        else:
            icon_widget = tk.Label(tile, text=icon, bg=bg, fg=fg, font=theme.font(36))
        icon_widget.pack(pady=(16, 4))
        name_lbl = tk.Label(tile, text=name, bg=bg, fg=fg, font=theme.font(13, weight="bold"),
                             wraplength=TILE_TEXT_WRAP, justify="center")
        name_lbl.pack()
        # height=2 reserves the same two-line footprint whether this
        # particular subtitle wraps to one line or two -- otherwise the
        # status tag below would land at a different height on almost every
        # tile depending on how its subtitle happened to wrap.
        sub_lbl = tk.Label(tile, text=subtitle, bg=bg, fg=sub_fg,
                            font=theme.font(9), wraplength=TILE_TEXT_WRAP, justify="center", height=2)
        sub_lbl.pack(pady=(4, 0))

        status_widgets = [tile, icon_widget, name_lbl, sub_lbl]
        # height=24 (not the pill's own ~19px) with the pill centred in it,
        # not flush against the top -- sized exactly to the pill's own
        # height, its outline's bottom edge sat right on (or just past) the
        # canvas's own bottom boundary and got clipped off, invisible
        # against the felt but obvious once PLAY's brighter accent outline
        # made the same clipping show up clearly.
        pill_canvas = tk.Canvas(tile, width=TILE_TEXT_WRAP, height=24, bg=bg, highlightthickness=0)
        pill_canvas.pack(pady=(6, 0))
        if enabled:
            # Same small rounded pill as "SOON" below, just in the tile's
            # own accent colour (matching its highlighted border) rather
            # than the muted "not yet built" grey, and "PLAY" instead.
            theme.pill(pill_canvas, TILE_TEXT_WRAP / 2, 12, "PLAY",
                       fill=theme.ACCENT_DIM_BG, outline=theme.ACCENT, text_fg=theme.ACCENT)
        else:
            # A small rounded "SOON" pill, matching the site's .link-btn__tag
            # -- replaces the old plain "COMING SOON" text label.
            theme.pill(pill_canvas, TILE_TEXT_WRAP / 2, 12, "SOON")
        status_widgets.append(pill_canvas)

        if enabled and command:
            for widget in status_widgets:
                widget.configure(cursor="hand2")
                widget.bind("<Button-1>", lambda _e: command())

    def on_show(self):
        self.refresh_balance()

    def refresh_balance(self):
        self.balance_btn.configure(text=f"Cashier: £{self.app.finance.balance:,.2f}")
