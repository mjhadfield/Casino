import tkinter as tk

from ui import game_icons

BG = "#0b0b0b"
BAR_BG = "#111111"
GOLD = "#d4af37"

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
        super().__init__(parent, bg=BG)
        self.app = app

        # --- top bar ---
        top_bar = tk.Frame(self, bg=BAR_BG)
        top_bar.pack(fill="x", side="top")

        tk.Label(
            top_bar, text="\u2660 HADFIELD CASINO \u2663", bg=BAR_BG, fg=GOLD,
            font=("Georgia", 18, "bold"),
        ).pack(side="left", padx=20, pady=14)

        self.balance_btn = tk.Button(
            top_bar, text="Bank Balance: £0.00", bg="#1c1c1c", fg="#4be36b",
            activebackground="#2a2a2a", activeforeground="#4be36b",
            font=("Helvetica", 12, "bold"), relief="flat", padx=14, pady=8,
            cursor="hand2", command=lambda: app.show_frame("finances"),
        )
        self.balance_btn.pack(side="right", padx=(6, 20), pady=14)

        tk.Button(
            top_bar, text="\u2699 Settings", bg="#1c1c1c", fg="#cccccc",
            activebackground="#2a2a2a", activeforeground="#ffffff",
            font=("Helvetica", 12), relief="flat", padx=14, pady=8,
            cursor="hand2", command=lambda: app.show_frame("settings"),
        ).pack(side="right", padx=6, pady=14)

        # --- body ---
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)

        tk.Label(
            body, text="Choose a game", bg=BG, fg="#aaaaaa", font=("Helvetica", 13),
        ).pack(pady=(30, 10))

        grid = tk.Frame(body, bg=BG)
        grid.pack(pady=10)

        for i, (icon, name, subtitle, enabled, frame_name) in enumerate(GAMES):
            row, col = divmod(i, GAMES_PER_ROW)
            command = (lambda f=frame_name: app.show_frame(f)) if (enabled and frame_name) else None
            self._make_game_tile(grid, row, col, icon, name, subtitle, enabled, command=command)

    def _make_game_tile(self, grid, row, col, icon, name, subtitle, enabled, command=None):
        bg = "#15321f" if enabled else "#161616"
        fg = "#f2f2f2" if enabled else "#555555"
        border = GOLD if enabled else "#333333"

        tile = tk.Frame(grid, bg=bg, width=TILE_WIDTH, height=TILE_HEIGHT,
                         highlightbackground=border, highlightthickness=2)
        tile.grid(row=row, column=col, padx=14, pady=14)
        # Contents are placed with pack() -- pack_propagate (not
        # grid_propagate, which only governs *grid*-managed children) is
        # what stops a longer wrapped subtitle from growing this particular
        # tile taller/wider than the fixed size every tile is given above.
        tile.pack_propagate(False)

        if callable(icon):
            # A vector icon (game_icons.draw_*): fixed-size canvas so it's
            # guaranteed the same footprint as every other tile's icon.
            icon_widget = tk.Canvas(tile, width=ICON_CANVAS_SIZE, height=ICON_CANVAS_SIZE,
                                     bg=bg, highlightthickness=0)
            icon(icon_widget, ICON_CANVAS_SIZE / 2, ICON_CANVAS_SIZE / 2, ICON_DRAW_SIZE, fg)
        else:
            icon_widget = tk.Label(tile, text=icon, bg=bg, fg=fg, font=("Helvetica", 36))
        icon_widget.pack(pady=(16, 4))
        name_lbl = tk.Label(tile, text=name, bg=bg, fg=fg, font=("Helvetica", 13, "bold"),
                             wraplength=TILE_TEXT_WRAP, justify="center")
        name_lbl.pack()
        # height=2 reserves the same two-line footprint whether this
        # particular subtitle wraps to one line or two -- otherwise the
        # "Coming soon" tag below would land at a different height on
        # almost every tile depending on how its subtitle happened to wrap.
        sub_lbl = tk.Label(tile, text=subtitle, bg=bg, fg=("#888888" if enabled else "#444444"),
                            font=("Helvetica", 9), wraplength=TILE_TEXT_WRAP, justify="center", height=2)
        sub_lbl.pack(pady=(4, 0))
        status_lbl = tk.Label(tile, text=("" if enabled else "COMING SOON"), bg=bg, fg="#8a7328",
                               font=("Helvetica", 8, "bold"))
        status_lbl.pack(pady=(4, 0))

        if enabled and command:
            for widget in (tile, icon_widget, name_lbl, sub_lbl, status_lbl):
                widget.configure(cursor="hand2")
                widget.bind("<Button-1>", lambda _e: command())

    def on_show(self):
        self.refresh_balance()

    def refresh_balance(self):
        self.balance_btn.configure(text=f"Bank Balance: £{self.app.finance.balance:,.2f}")
