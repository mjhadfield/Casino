"""
Hadfield Casino
=================
A small, extensible casino games library. New games can be dropped in
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
from core.players import PlayerManager
from core.settings import SettingsManager
from core.unlocks import UnlocksManager
from ui import theme
from ui.logon_screen import LogonFrame
from ui.main_menu import MainMenuFrame
from ui.finances_screen import FinancesFrame
from ui.settings_screen import SettingsFrame
from ui.stats_screen import StatsFrame
from games.three_card_poker.ui import ThreeCardPokerFrame
from games.blackjack.ui import BlackjackFrame
from games.pai_gow_poker.ui import PaiGowPokerFrame
from games.pai_gow_poker_face_up.ui import PaiGowPokerFaceUpFrame
from games.mississippi_stud.ui import MississippiStudFrame
from games.ultimate_texas_holdem.ui import UltimateTexasHoldemFrame
from games.let_it_ride.ui import LetItRideFrame
from games.high_card_flush.ui import HighCardFlushFrame
from games.baccarat.ui import BaccaratFrame

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(APP_DIR, "data")
# jackpot.json and players.json are the only save files that live at the
# top level of data/ -- everything else (balance, stats, settings, unlocks,
# each game's bet-tray state) is per-player, resolved inside
# CasinoApp.start_session once a profile has actually been chosen.
JACKPOT_SAVE_PATH = os.path.join(DATA_DIR, "jackpot.json")
PLAYERS_SAVE_PATH = os.path.join(DATA_DIR, "players.json")

APP_TITLE = "Hadfield Casino"


class CasinoApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.withdraw()
        self.title(APP_TITLE)
        self.geometry("1200x820")
        self.resizable(False, False)
        self.configure(bg=theme.BG)

        self.data_dir = DATA_DIR
        self.admin_unlocked = False
        self.players = PlayerManager(PLAYERS_SAVE_PATH)
        self.current_player = None

        # None until the first start_session() runs -- every game screen
        # reads these lazily off self.app.<manager> at call time (never
        # caches them at construction), so they genuinely don't need to
        # exist until a player has actually been chosen.
        self.finance = None
        self.settings = None
        self.jackpot = None
        self.game_stats = None
        self.unlocks = None

        # Per-player state, built once per slug the first time that player
        # is ever selected this run and kept alive for the rest of the
        # process -- switching back to them later (see the "Player Screen"
        # button on Settings) just re-points the live self.<manager>
        # attributes and self.frames at their cached entry below, rather
        # than reloading from disk or rebuilding any widget. See
        # start_session's docstring for why frames in particular can't just
        # be handed a different player and carry on.
        self.sessions = {}  # slug -> {"player_dir", "settings", "finance", "game_stats", "unlocks", "frames"}

        self.container = tk.Frame(self, bg=theme.BG)
        self.container.pack(fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        # The logon/player-select screen is itself a persistent, permanent
        # frame -- not torn down once a session starts -- so switching
        # players (or, later, character creation/a bonus store reached from
        # the same screen) just means navigating back to it like any other
        # screen, via self.show_frame("logon").
        self.frames = {}
        logon = LogonFrame(parent=self.container, app=self)
        self.frames["logon"] = logon
        logon.grid(row=0, column=0, sticky="nsew")

        # Legacy-save migration, if this install needs it, happens as a
        # flat inline form built directly into LogonFrame's own body (see
        # ui/logon_screen.py's _build_welcome_form) rather than anything
        # triggered from here -- it's just what the logon screen renders
        # instead of the roster the first time it's shown, same as any
        # other state that screen can be in.
        self.show_frame("logon")
        self.deiconify()

    def start_session(self, slug):
        """Called by LogonFrame once a player has been picked or just
        created -- either the very first login of the process, or a
        mid-session switch back to (or onto) a player via Settings' "Player
        Screen" button.

        The first time a given slug is seen, this builds that player's 5
        managers and all 13 game/menu frames, exactly as it always has, and
        caches them in self.sessions[slug]. On every later call for a slug
        already in that cache, no manager is reloaded and no frame is
        rebuilt -- table felt colour, the breadcrumb's player name, and
        every jackpot-listener binding are all baked in once at
        frame-construction time (see each frame's own _build_ui), so
        reusing the same already-built widgets is what keeps them correct
        across a switch, rather than a live in-place refresh of 13 screens'
        worth of widgets. The one manager that's a genuine exception is the
        jackpot: it's shared by every player, so it's built once ever (the
        very first session of the process, whoever that is) and simply
        never touched again here."""
        # Withdraw for the duration of any frame construction below, same
        # reasoning as __init__'s own withdraw/deiconify bracket: several
        # screens call update_idletasks() while building (to measure a chip
        # tray's real size), which forces Tk to paint whatever's currently
        # topmost in the grid stack -- without this, the window visibly
        # cycles through several game screens before landing on the menu.
        # A cache hit doesn't build anything, so this ends up a same-frame
        # withdraw+deiconify (imperceptible) rather than a real hide.
        self.withdraw()

        player = self.players.get(slug)
        self.current_player = player
        self.players.touch_last_played(slug)

        if slug not in self.sessions:
            # Always resolved from the fixed top-level DATA_DIR, never from
            # self.data_dir -- self.data_dir tracks whichever player is
            # *currently* active and gets reassigned below, so resolving a
            # new player's directory from it would nest a second player's
            # files inside the previously active one's folder.
            player_dir = self.players.player_dir(slug, DATA_DIR)
            os.makedirs(player_dir, exist_ok=True)

            settings = SettingsManager(os.path.join(player_dir, "settings.json"))
            finance = FinanceManager(os.path.join(player_dir, "finances.json"))
            game_stats = GameStatsManager(os.path.join(player_dir, "game_stats.json"))
            unlocks = UnlocksManager(os.path.join(player_dir, "unlocks.json"))

            # Swap the live pointers in *before* building any frame --
            # every frame reads self.app.<manager> during its own
            # construction (breadcrumb text, table felt colour, tile
            # unlock colours, the jackpot listener binding below).
            self.settings = settings
            self.finance = finance
            self.game_stats = game_stats
            self.unlocks = unlocks
            self.data_dir = player_dir

            if self.jackpot is None:
                # jackpot.json stays at the top level, shared by every
                # player -- built once ever, on whichever session starts
                # first; see core/jackpot.py's docstring for why it reads
                # its growth rate off self.settings (i.e. live off
                # whichever player is currently active) rather than the
                # SettingsManager instance that happened to exist here.
                self.jackpot = JackpotManager(JACKPOT_SAVE_PATH, self)
                self.jackpot.start()

            frames = {}
            for frame_class, name in (
                (MainMenuFrame, "menu"),
                (FinancesFrame, "finances"),
                (StatsFrame, "stats"),
                (SettingsFrame, "settings"),
                (ThreeCardPokerFrame, "three_card_poker"),
                (BlackjackFrame, "blackjack"),
                (PaiGowPokerFrame, "pai_gow_poker"),
                (PaiGowPokerFaceUpFrame, "pai_gow_poker_face_up"),
                (MississippiStudFrame, "mississippi_stud"),
                (UltimateTexasHoldemFrame, "ultimate_texas_holdem"),
                (LetItRideFrame, "let_it_ride"),
                (HighCardFlushFrame, "high_card_flush"),
                (BaccaratFrame, "baccarat"),
            ):
                frame = frame_class(parent=self.container, app=self)
                frames[name] = frame
                frame.grid(row=0, column=0, sticky="nsew")

            self.sessions[slug] = {
                "player_dir": player_dir,
                "settings": settings,
                "finance": finance,
                "game_stats": game_stats,
                "unlocks": unlocks,
                "frames": frames,
            }
        else:
            session = self.sessions[slug]
            self.settings = session["settings"]
            self.finance = session["finance"]
            self.game_stats = session["game_stats"]
            self.unlocks = session["unlocks"]
            self.data_dir = session["player_dir"]

        # self.frames always means "logon, plus whichever player is
        # currently active's own 13 frames" -- reassigned wholesale here
        # rather than merged in place, so a stale entry from a previously
        # active player can never leak through under the same name.
        self.frames = {"logon": self.frames["logon"], **self.sessions[slug]["frames"]}

        self.show_frame("menu")
        self.deiconify()

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
    # Legacy-save migration (if needed) now happens inside CasinoApp itself
    # -- see __init__'s _offer_legacy_migration -- since it needs a live
    # window to prompt for a name, which doesn't exist yet at this point.
    app = CasinoApp()
    app.mainloop()


if __name__ == "__main__":
    main()
