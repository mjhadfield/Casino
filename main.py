"""
Hadfield Casino
=================
A small, extensible casino games library. Currently ships Three Card Poker;
built so future games (Blackjack, Roulette, Baccarat, ...) can be dropped in
as another entry in games/ plus a UI frame, reusing the same core deck,
hand-evaluation, finance, and settings modules.

Run with:  python3 main.py
Requires only the Python standard library (tkinter).
"""
import os
import sys
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.finances import FinanceManager
from core.game_stats import GameStatsManager
from core.jackpot import JackpotManager
from core.settings import SettingsManager
from core.unlocks import UnlocksManager
from ui import theme
from ui.main_menu import MainMenuFrame
from ui.finances_screen import FinancesFrame
from ui.settings_screen import SettingsFrame
from ui.stats_screen import StatsFrame
from games.three_card_poker.ui import ThreeCardPokerFrame
from games.blackjack.ui import BlackjackFrame
from games.pai_gow_poker.ui import PaiGowPokerFrame

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(APP_DIR, "data")
FINANCE_SAVE_PATH = os.path.join(DATA_DIR, "finances.json")
SETTINGS_SAVE_PATH = os.path.join(DATA_DIR, "settings.json")
JACKPOT_SAVE_PATH = os.path.join(DATA_DIR, "jackpot.json")
GAME_STATS_SAVE_PATH = os.path.join(DATA_DIR, "game_stats.json")
UNLOCKS_SAVE_PATH = os.path.join(DATA_DIR, "unlocks.json")

APP_TITLE = "Hadfield Casino"


class CasinoApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1200x820")
        # Fixed-size window -- no drag-to-resize, no maximize -- rather than
        # a minsize floor: this is headed for a static-size embed in a
        # webpage, so a resizable window isn't a real requirement here.
        self.resizable(False, False)
        self.configure(bg=theme.BG)

        self.data_dir = DATA_DIR
        # Whole-app-session admin gate (see ui/dialogs.py's
        # ensure_admin_unlocked) -- entering the password once, anywhere it's
        # asked for, unlocks every admin section for the rest of this run.
        self.admin_unlocked = False
        self.finance = FinanceManager(FINANCE_SAVE_PATH)
        self.settings = SettingsManager(SETTINGS_SAVE_PATH)
        self.jackpot = JackpotManager(JACKPOT_SAVE_PATH, self.settings)
        self.game_stats = GameStatsManager(GAME_STATS_SAVE_PATH)
        self.unlocks = UnlocksManager(UNLOCKS_SAVE_PATH)
        # Grows for as long as the app is open, independent of which screen
        # is showing -- started here rather than by any one game's frame.
        self.jackpot.start(self)

        container = tk.Frame(self, bg=theme.BG)
        container.pack(fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        for frame_class, name in (
            (MainMenuFrame, "menu"),
            (FinancesFrame, "finances"),
            (StatsFrame, "stats"),
            (SettingsFrame, "settings"),
            (ThreeCardPokerFrame, "three_card_poker"),
            (BlackjackFrame, "blackjack"),
            (PaiGowPokerFrame, "pai_gow_poker"),
        ):
            frame = frame_class(parent=container, app=self)
            self.frames[name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame("menu")

    def show_frame(self, name):
        frame = self.frames[name]
        if hasattr(frame, "on_show"):
            frame.on_show()
        frame.tkraise()

    def on_balance_changed(self):
        """Called by any screen that changes the balance/stats, so the menu
        and finances screen stay in sync without polling."""
        self.frames["menu"].refresh_balance()
        self.frames["finances"].refresh()


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    app = CasinoApp()
    app.mainloop()


if __name__ == "__main__":
    main()
