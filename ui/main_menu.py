import tkinter as tk

BG = "#0b0b0b"
BAR_BG = "#111111"
GOLD = "#d4af37"


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

        self._make_game_tile(
            grid, 0, 0, "\U0001F0A1", "Three Card Poker",
            "Ante, Play, Pair Plus & Prime side bets",
            enabled=True, command=lambda: app.show_frame("three_card_poker"),
        )
        self._make_game_tile(grid, 0, 1, "\U0001F3B2", "Blackjack", "Coming soon", enabled=False)
        self._make_game_tile(grid, 0, 2, "\U0001F3A1", "Roulette", "Coming soon", enabled=False)
        self._make_game_tile(grid, 1, 0, "\U0001F004", "Baccarat", "Coming soon", enabled=False)
        self._make_game_tile(grid, 1, 1, "\U0001F3C6", "Jackpots", "Unlocked at milestones", enabled=False)
        self._make_game_tile(grid, 1, 2, "\u2795", "More Tables", "New games added over time", enabled=False)

    def _make_game_tile(self, grid, row, col, icon, name, subtitle, enabled, command=None):
        bg = "#15321f" if enabled else "#161616"
        fg = "#f2f2f2" if enabled else "#555555"
        border = GOLD if enabled else "#333333"

        tile = tk.Frame(grid, bg=bg, width=220, height=170, highlightbackground=border, highlightthickness=2)
        tile.grid(row=row, column=col, padx=14, pady=14)
        tile.grid_propagate(False)

        icon_lbl = tk.Label(tile, text=icon, bg=bg, fg=fg, font=("Helvetica", 36))
        icon_lbl.pack(pady=(18, 4))
        name_lbl = tk.Label(tile, text=name, bg=bg, fg=fg, font=("Helvetica", 13, "bold"),
                             wraplength=190, justify="center")
        name_lbl.pack()
        sub_lbl = tk.Label(tile, text=subtitle, bg=bg, fg=("#888888" if enabled else "#444444"),
                            font=("Helvetica", 9), wraplength=190, justify="center")
        sub_lbl.pack(pady=(4, 0))

        if enabled and command:
            for widget in (tile, icon_lbl, name_lbl, sub_lbl):
                widget.configure(cursor="hand2")
                widget.bind("<Button-1>", lambda _e: command())

    def on_show(self):
        self.refresh_balance()

    def refresh_balance(self):
        self.balance_btn.configure(text=f"Bank Balance: £{self.app.finance.balance:,.2f}")
