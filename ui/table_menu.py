"""
Generic table-picker screen -- shown between the main menu and an actual
game table whenever a game has more than one TABLE (different rules, e.g.
Blackjack's 3:2/6:5 payout, or a different dealer-visibility gimmick like
Pai Gow Poker's Face Up table; eventually different table min/max bets
too). Extracted from what was a Blackjack-only ui/blackjack_menu.py once a
second game (Pai Gow Poker) needed the exact same screen shape -- a game's
own picker is now just a ~15-line subclass declaring GAME_TITLE/BREADCRUMB/
TILES (see ui/blackjack_menu.py, ui/pai_gow_poker_menu.py), not a copy of
this whole file.

Same top-bar shell every game screen uses (Menu button, title, breadcrumb --
not MainMenuFrame's own heavier top bar with Cashier/Stats/Settings, since
this isn't the main menu), holding a small row of tiles built with the same
ui/game_tile.py tile widget the main menu itself uses.

Adding a new table to an existing game is just one more row in that game's
own TILES list (a default lock state in core/unlocks.py's DEFAULT_UNLOCKS,
and once it's implemented, a real frame_name) -- no layout code to touch,
same promise ui/main_menu.py's own GAMES list already makes for a whole new
game.
"""
import tkinter as tk

from core import achievements_data
from ui import dialogs, game_tile, theme


class TableMenuFrame(tk.Frame):
    # Set by a subclass -- see ui/blackjack_menu.py/ui/pai_gow_poker_menu.py.
    GAME_TITLE: str = ""   # e.g. "Blackjack" -- shown in the top bar
    BREADCRUMB: str = ""   # e.g. "blackjack_menu" -- shown in the breadcrumb
    # (icon, name, subtitle, game_key, frame_name) rows, same 5-tuple shape
    # ui/main_menu.py's own GAMES list uses, laid out as one row instead of
    # a whole grid.
    TILES: list = []

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
        tk.Label(top_bar, text=self.GAME_TITLE, bg=theme.BG_ELEVATED, fg=theme.ACCENT,
                 font=theme.font(16, weight="bold")).pack(side="left", padx=10)
        theme.breadcrumb(top_bar, self.BREADCRUMB, bg=theme.BG_ELEVATED,
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
        for col, (icon, name, subtitle, game_key, frame_name) in enumerate(self.TILES):
            unlocked = self.app.unlocks.is_unlocked(game_key)
            playable = unlocked and frame_name is not None
            command = (lambda f=frame_name: self.app.show_frame(f)) if playable else None
            game_tile.make_game_tile(
                self.tile_grid, 0, col, icon, name, subtitle, unlocked, playable, command=command,
                # A sub-table (unlike a main-menu GAMES row) can only ever
                # be earned, never bought early -- see the plan's decision
                # #4 -- so a locked one gets the same explanatory hover
                # tooltip but a plain "must be earned" info click instead
                # of a Crowns purchase prompt.
                tooltip_text=(lambda gk=game_key: self._lock_tooltip(gk)) if not unlocked else None,
                locked_command=(lambda gk=game_key, n=name: self._on_locked_tile_click(gk, n)) if not unlocked else None,
            )

    def _lock_tooltip(self, game_key):
        achievement = achievements_data.UNLOCK_SOURCE.get(game_key)
        return f"Requires: {achievement.name}" if achievement else None

    def _on_locked_tile_click(self, game_key, name):
        achievement = achievements_data.UNLOCK_SOURCE.get(game_key)
        requirement = f" Requires: {achievement.name}." if achievement else ""
        dialogs.info(
            self, "$ unlock --locked",
            f"{name} can only be earned through play, not bought early.{requirement}",
        )

    def on_show(self):
        # A table's lock state can change on the Settings screen (or by
        # earning its achievement) in between visits -- rebuild fresh every
        # time this screen is shown, same reasoning as MainMenuFrame's own
        # on_show.
        self._build_tiles()
