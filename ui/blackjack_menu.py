"""
The Blackjack picker screen -- shown between the main menu and an actual
Blackjack table now that there are two variants (Standard, Counting).
Same top-bar shell every game screen uses (Menu button, title, breadcrumb --
not MainMenuFrame's own heavier top bar with Cashier/Stats/Settings, since
this isn't the main menu), holding a small 2-tile row built with the same
ui/game_tile.py tile widget the main menu itself uses.
"""
import tkinter as tk

from ui import game_icons, game_tile, theme

# (icon, name, subtitle, game_key, frame_name) -- same 5-tuple shape as
# ui/main_menu.py's own GAMES rows, just laid out as one row of 2 instead of
# a whole grid. Both tiles reuse Blackjack's existing icon unchanged (no
# variant-specific icon was asked for -- an easy swap later if wanted).
TILES = [
    (game_icons.draw_blackjack_icon, "Standard", "Super Pairs, 21+3, Top 3 & Jackpot side bets",
     "blackjack", "blackjack"),
    (game_icons.draw_blackjack_icon, "Counting", "8 deck shoe with visible count",
     "blackjack_count", "blackjack_count"),
]


class BlackjackMenuFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.BG)
        self.app = app

        top_bar = tk.Frame(self, bg=theme.BG_ELEVATED)
        top_bar.pack(fill="x")
        tk.Button(
            top_bar, text="← Menu", bg=theme.BG_ELEVATED, fg=theme.FG_DIM, relief="flat",
            font=theme.font(11), padx=12, pady=6, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.BORDER, highlightcolor=theme.ACCENT,
            command=lambda: self.app.show_frame("menu"),
        ).pack(side="left", padx=(20, 10), pady=10)
        tk.Label(top_bar, text="Blackjack", bg=theme.BG_ELEVATED, fg=theme.ACCENT,
                 font=theme.font(16, weight="bold")).pack(side="left", padx=10)
        theme.breadcrumb(top_bar, "blackjack_menu", bg=theme.BG_ELEVATED,
                          player=self.app.current_player["name"]).pack(side="right", padx=(6, 6))

        body = tk.Frame(self, bg=theme.BG)
        body.pack(fill="both", expand=True)
        tk.Label(body, text="Choose a table", bg=theme.BG, fg=theme.FG_DIM,
                 font=theme.font(12)).pack(pady=(60, 0))

        self.tile_grid = tk.Frame(body, bg=theme.BG)
        self.tile_grid.pack(pady=(20, 10))
        self._build_tiles()

    def _build_tiles(self):
        for child in self.tile_grid.winfo_children():
            child.destroy()
        for col, (icon, name, subtitle, game_key, frame_name) in enumerate(TILES):
            unlocked = self.app.unlocks.is_unlocked(game_key)
            playable = unlocked and frame_name is not None
            command = (lambda f=frame_name: self.app.show_frame(f)) if playable else None
            game_tile.make_game_tile(self.tile_grid, 0, col, icon, name, subtitle, unlocked, playable,
                                      command=command)

    def on_show(self):
        # A game's lock state can change on the Settings screen in between
        # visits -- rebuild fresh every time this screen is shown, same
        # reasoning as MainMenuFrame's own on_show.
        self._build_tiles()
