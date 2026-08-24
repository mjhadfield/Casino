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
    (game_icons.draw_blackjack_icon, "Blackjack", "Perfect Pairs & 21+3 side bets",
     False, None),
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


class MainMenuFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.BG)
        self.app = app

        # --- top bar ---
        top_bar = tk.Frame(self, bg=theme.BG_ELEVATED)
        top_bar.pack(fill="x", side="top")

        theme.traffic_lights(top_bar, bg=theme.BG_ELEVATED).pack(side="left", padx=(20, 10), pady=14)
        tk.Label(
            top_bar, text="HADFIELD CASINO", bg=theme.BG_ELEVATED, fg=theme.ACCENT,
            font=theme.font(18, weight="bold"),
        ).pack(side="left")

        # Packed right-to-left (side="right" stacks inward from the right
        # edge, each new one landing left of the previous), so this order --
        # Cashier, then Stats, then Settings -- reads left-to-right on
        # screen as Settings, Stats, Cashier.
        self.balance_btn = tk.Button(
            top_bar, text="Cashier: £0.00", bg=theme.BG_ELEVATED, fg=theme.WIN_COLOR,
            activebackground=theme.ACCENT_DIM_BG_ELEVATED, activeforeground=theme.WIN_COLOR,
            font=theme.font(12, weight="bold"), relief="flat", padx=14, pady=8,
            highlightthickness=1, highlightbackground=theme.BORDER, highlightcolor=theme.ACCENT,
            cursor="hand2", command=lambda: app.show_frame("finances"),
        )
        self.balance_btn.pack(side="right", padx=(6, 20), pady=14)

        tk.Button(
            top_bar, text="\U0001F4CA Stats", bg=theme.BG_ELEVATED, fg=theme.FG_DIM,
            activebackground=theme.BORDER, activeforeground=theme.FG,
            font=theme.font(12), relief="flat", padx=14, pady=8,
            highlightthickness=1, highlightbackground=theme.BORDER, highlightcolor=theme.ACCENT,
            cursor="hand2", command=lambda: app.show_frame("stats"),
        ).pack(side="right", padx=6, pady=14)

        tk.Button(
            top_bar, text="⚙ Settings", bg=theme.BG_ELEVATED, fg=theme.FG_DIM,
            activebackground=theme.BORDER, activeforeground=theme.FG,
            font=theme.font(12), relief="flat", padx=14, pady=8,
            highlightthickness=1, highlightbackground=theme.BORDER, highlightcolor=theme.ACCENT,
            cursor="hand2", command=lambda: app.show_frame("settings"),
        ).pack(side="right", padx=6, pady=14)

        breadcrumb_lbl = theme.breadcrumb(top_bar, "menu", bg=theme.BG_ELEVATED)
        breadcrumb_lbl.pack(side="right", padx=(6, 6), pady=14)

        # --- body ---
        body = tk.Frame(self, bg=theme.BG)
        body.pack(fill="both", expand=True)

        grid = tk.Frame(body, bg=theme.BG)
        grid.pack(pady=30)

        for i, (icon, name, subtitle, enabled, frame_name) in enumerate(GAMES):
            row, col = divmod(i, GAMES_PER_ROW)
            command = (lambda f=frame_name: app.show_frame(f)) if (enabled and frame_name) else None
            self._make_game_tile(grid, row, col, icon, name, subtitle, enabled, command=command)

    def _make_game_tile(self, grid, row, col, icon, name, subtitle, enabled, command=None):
        bg = theme.ACCENT_DIM_BG if enabled else theme.GREY_BTN_BG
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
        if not enabled:
            # A small rounded "SOON" pill, matching the site's .link-btn__tag
            # -- replaces the old plain "COMING SOON" text label.
            pill_canvas = tk.Canvas(tile, width=TILE_TEXT_WRAP, height=20, bg=bg, highlightthickness=0)
            pill_canvas.pack(pady=(6, 0))
            theme.pill(pill_canvas, TILE_TEXT_WRAP / 2, 10, "SOON")
            status_widgets.append(pill_canvas)

        if enabled and command:
            for widget in status_widgets:
                widget.configure(cursor="hand2")
                widget.bind("<Button-1>", lambda _e: command())

    def on_show(self):
        self.refresh_balance()

    def refresh_balance(self):
        self.balance_btn.configure(text=f"Cashier: £{self.app.finance.balance:,.2f}")
