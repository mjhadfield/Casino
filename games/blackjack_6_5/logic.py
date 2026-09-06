"""
Blackjack (6:5) -- identical rules/engine to standard Blackjack
(games/blackjack/logic.py's BlackjackGame, subclassed here as
BlackjackSixFiveGame to reuse everything else unchanged), with one rule-
level difference: a natural Blackjack pays 6:5 instead of the standard
game's 3:2 -- a well-known real-world "worse for the player" table variant,
often paired with a lower table minimum. See BlackjackGame's own
BLACKJACK_PAYOUT_MULTIPLIER docstring for why this is a plain class-
attribute override rather than a second copy of _settle_hand.

No GAME_KEY/GAME_LABEL of its own -- like blackjack_count, this variant
deliberately shares standard Blackjack's own GAME_KEY ("blackjack") rather
than getting a distinct one, so its bets/hands/achievements feed the same
GameStatsManager bucket and the same single "Blackjack" section on the
Stats screen instead of a second, near-identical one of its own -- see
games/blackjack_6_5/ui.py's BlackjackSixFiveFrame, which deliberately
doesn't override GAME_KEY either.
"""
from games.blackjack.logic import BlackjackGame

BLACKJACK_PAYOUT_MULTIPLIER = 1.2  # 6:5, instead of the base game's 3:2 (1.5)


class BlackjackSixFiveGame(BlackjackGame):
    BLACKJACK_PAYOUT_MULTIPLIER = BLACKJACK_PAYOUT_MULTIPLIER
