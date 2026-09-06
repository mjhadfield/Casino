"""
Blackjack (6:5) table screen. Subclasses games.blackjack.ui.BlackjackFrame --
every betting/animation/payout/paytable/rules mechanism is reused unchanged.
Only what's genuinely different is overridden here: the game engine
(BlackjackSixFiveGame instead of BlackjackGame, via _make_game, paying 6:5
on a natural instead of 3:2), the paytable/rules display label that mirrors
it (BLACKJACK_PAYOUT_LABEL), and a distinct save file/top-bar title/
breadcrumb -- the same minimal-override shape
games/blackjack_count/ui.py's BlackjackCountFrame already established for
its own variant.
"""
from games.blackjack.ui import BlackjackFrame
from games.blackjack_6_5.logic import BlackjackSixFiveGame

STATE_FILENAME = "blackjack_6_5_state.json"


class BlackjackSixFiveFrame(BlackjackFrame):
    STATE_FILENAME = STATE_FILENAME
    # GAME_KEY is inherited from BlackjackFrame ("blackjack") rather than
    # overridden -- see games/blackjack_6_5/logic.py's own docstring: this
    # is a different TABLE, not a different GAME, as far as
    # GameStatsManager/the Stats screen/achievements are concerned.
    GAME_TITLE = "Blackjack (6:5)"
    BREADCRUMB = "blackjack_6_5"
    BLACKJACK_PAYOUT_LABEL = "6:5"

    def _make_game(self):
        return BlackjackSixFiveGame()
