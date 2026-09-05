"""
Blackjack (Counting) -- identical rules/engine to standard Blackjack
(games/blackjack/logic.py's BlackjackGame, subclassed here as
BlackjackCountGame to reuse everything else unchanged), with one engine-
level difference: the 8-deck shoe is NOT reshuffled every round. It's dealt
down until RESHUFFLE_PENETRATION of it has been dealt, then reshuffled --
see _reshuffle_shoe_if_needed, overriding BlackjackGame's own hook.

The running Hi-Lo count itself isn't tracked here -- it's a display concern,
not a rules concern, and it needs to grow in step with cards actually
becoming visible on screen, which the engine has no notion of (it deals
every card into play well before the UI's own reveal animation for it has
played out). See games/blackjack_count/ui.py's BlackjackCountFrame,
specifically BlackjackFrame._on_card_revealed. What this class DOES expose
is just_reshuffled, so the UI's own count knows when to reset without
independently re-deriving the penetration threshold itself.
"""
from games.blackjack.logic import BlackjackGame

# No GAME_KEY/GAME_LABEL/BET_TYPES/HAND_OUTCOME_LABELS here, unlike every
# other game's own logic.py -- this variant deliberately shares standard
# Blackjack's own GAME_KEY ("blackjack") rather than getting a distinct one,
# so its bets/hands feed the same GameStatsManager bucket and the same
# single "Blackjack" section on the Stats screen instead of a second,
# near-identical one of its own -- see games/blackjack_count/ui.py's
# BlackjackCountFrame, which deliberately doesn't override GAME_KEY either.

# Reshuffle once this fraction of the 416-card (8-deck) shoe has been dealt
# -- 0.75 -> 312 dealt, 104 remaining (~2 decks), comfortably more than any
# single round (even 2 boxes with several splits) could ever consume, so the
# shoe is always reshuffled well before it could run out mid-round.
RESHUFFLE_PENETRATION = 0.75


class BlackjackCountGame(BlackjackGame):
    def __init__(self):
        super().__init__()
        # Set True by _reshuffle_shoe_if_needed exactly when a reshuffle
        # actually happens (and left False otherwise) -- checked, and
        # cleared, by BlackjackCountFrame._on_card_revealed so the UI's own
        # displayed count resets in step with the shoe, without the UI
        # needing to know anything about RESHUFFLE_PENETRATION itself.
        self.just_reshuffled = False

    def _reshuffle_shoe_if_needed(self):
        total = self.shoe.num_decks * 52
        dealt = total - self.shoe.cards_remaining()
        self.just_reshuffled = dealt / total >= RESHUFFLE_PENETRATION
        if self.just_reshuffled:
            self.shoe.reset()
