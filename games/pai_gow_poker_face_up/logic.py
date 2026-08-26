"""
Face Up Pai Gow Poker game engine.

Identical core game to standard Fortune Pai Gow Poker
(games/pai_gow_poker/logic.py -- the deck, Joker rules, hand evaluation,
House Way chart, and the Fortune/Jackpot side bets are all reused as-is,
unchanged, via PaiGowFaceUpGame subclassing PaiGowPokerGame), with three
differences:

  1. The dealer's hand is set by House Way immediately after dealing --
     in fact the base engine's own deal() already does this unconditionally
     for every table. The real "Face Up" difference is purely a UI one:
     the dealer's already-set hand is revealed to the player before they
     arrange their own, rather than staying hidden until Confirm -- see
     games/pai_gow_poker_face_up/ui.py.
  2. If the dealer's House-Way-set hand comes up an "Ace-high Pai Gow" --
     the lowest hand possible: no pair, straight, or flush anywhere across
     all 7 of the dealer's cards, with an Ace as the single highest card
     (see is_ace_high_pai_gow) -- the round ends immediately, right there
     at deal(): the Ante pushes automatically (stake returned), the
     Fortune/Jackpot side bets still pay exactly as normal (they're
     already resolved off the player's own 7 cards, independent of the
     dealer, by this point), and the player never sets a hand at all that
     round.
  3. No commission on the Ante -- a win pays a flat 1:1, no 5% deduction.

Seeing the Dealer's hand up front also means the player can sometimes tell
in advance the round's unwinnable -- so a Fold option (see fold()) lets
them forfeit the Ante immediately rather than bother setting a hand at all;
Fortune/Jackpot still pay as normal either way, same as the automatic push.
"""
from core.hand_evaluator import FIVE_CARD_HIGH_CARD
from games.pai_gow_poker.logic import (
    PaiGowPokerGame,
    RoundResult,
    TWO_CARD_HIGH_CARD,
    best_five_card_eval_with_joker,
    compare_hands,
    evaluate_two_card_hand,
)

GAME_KEY = "pai_gow_poker_face_up"
GAME_LABEL = "Pai Gow Poker (Face Up!)"
BET_TYPES = [
    ("ante", "Ante"),
    ("fortune", "Fortune"),
    ("jackpot", "Jackpot"),
]
HAND_OUTCOME_LABELS = ["Lose", "Push", "Win"]

JACKPOT_BET_AMOUNT = 1.0  # same flat £1 as standard Pai Gow Poker


def is_ace_high_pai_gow(front_eval, back_eval) -> bool:
    """True iff both halves of a set hand are plain High Card -- i.e. the
    whole 7-card hand has no pair, straight, or flush anywhere -- with an
    Ace as the single highest card among them: the traditional "Ace-high
    Pai Gow", the lowest-ranked hand possible in the game. (Since a real
    pair/trips/quads is always kept together as a unit by the House Way
    chart -- see games/pai_gow_poker/logic.py's _house_way_set_by_chart --
    both halves reading as plain High Card is only possible when there's
    truly nothing better anywhere across all 7 cards.)"""
    if front_eval[0] != TWO_CARD_HIGH_CARD or back_eval[0] != FIVE_CARD_HIGH_CARD:
        return False
    return max(front_eval[2][0], back_eval[2][0]) == 14


class FaceUpRoundResult(RoundResult):
    def __init__(self):
        super().__init__()
        # Set as soon as the dealer's hand is dealt (see
        # PaiGowFaceUpGame.deal) -- once True, the round is already fully
        # settled right there: the player never sets a hand at all, and
        # settle() below becomes a no-op. player_front/player_back/
        # player_front_eval/player_back_eval simply stay at RoundResult's
        # own empty/None defaults in that case.
        self.dealer_ace_high_push = False
        # Set by PaiGowFaceUpGame.fold() -- the player's own way to give up
        # once the Dealer's already-revealed hand makes the round look
        # unwinnable, rather than setting a hand anyway. Same
        # player_front/player_back-stay-empty situation as the automatic
        # push above.
        self.folded = False


class PaiGowFaceUpGame(PaiGowPokerGame):
    """Face Up Pai Gow Poker -- see the module docstring for the 3 rule
    differences from its sibling, games.pai_gow_poker.logic.PaiGowPokerGame,
    which this subclasses to reuse everything else unchanged."""

    def _make_result(self) -> RoundResult:
        return FaceUpRoundResult()

    def deal(self, ante_bet, fortune_bet=0.0, jackpot_bet=0.0, jackpot_amount=0.0) -> RoundResult:
        result = super().deal(ante_bet, fortune_bet, jackpot_bet, jackpot_amount)
        assert isinstance(result, FaceUpRoundResult)

        # The dealer's hand is already set (by the base deal() above) --
        # Face Up's own twist is evaluating it immediately, both to reveal
        # it face-up right away and to check the automatic Ace-high-Pai-Gow
        # push below, rather than waiting until settle() the way standard
        # Pai Gow does.
        result.dealer_front_eval = evaluate_two_card_hand(result.dealer_front)
        result.dealer_back_eval = best_five_card_eval_with_joker(result.dealer_back)

        if is_ace_high_pai_gow(result.dealer_front_eval, result.dealer_back_eval):
            result.dealer_ace_high_push = True
            result.outcome = "push"
            result.ante_return = result.ante_bet
            result.summary = (
                "Dealer has an Ace-high Pai Gow -- the lowest possible hand. "
                "The Ante pushes automatically; side bets still pay as normal."
            )
            total_wagered = result.ante_bet + result.fortune_bet + result.jackpot_bet
            total_returned = result.fortune_return + result.jackpot_return + result.ante_return
            result.total_wagered = total_wagered
            result.total_returned = total_returned
            result.net_result = round(total_returned - total_wagered, 2)
        return result

    def fold(self) -> RoundResult:
        """Folds the round -- the player's own way to give up once the
        Dealer's already-revealed hand makes winning look unlikely enough
        not to bother, rather than setting a hand anyway. Forfeits the
        Ante in full, same as losing both hands outright; Fortune/Jackpot
        still pay exactly as normal -- they're resolved off the player's
        own 7 cards independent of the Dealer's, exactly like the
        Ace-high-Pai-Gow automatic push above."""
        result = self.result
        assert isinstance(result, FaceUpRoundResult)
        assert not result.dealer_ace_high_push, \
            "fold() has nothing to do -- the round already auto-resolved at deal()"
        result.folded = True
        result.outcome = "lose"
        result.ante_return = 0.0
        result.summary = "You folded -- the Ante is forfeited. Side bets still pay as normal."
        total_wagered = result.ante_bet + result.fortune_bet + result.jackpot_bet
        total_returned = result.fortune_return + result.jackpot_return + result.ante_return
        result.total_wagered = total_wagered
        result.total_returned = total_returned
        result.net_result = round(total_returned - total_wagered, 2)
        return result

    def settle(self) -> RoundResult:
        """Settles the round once the player's hand has been set -- same as
        the base game's own settle(), minus the 5% Ante commission on a win
        (Face Up Pai Gow charges none). A no-op if the round already ended
        at deal() via the automatic Ace-high-Pai-Gow push above."""
        result = self.result
        assert isinstance(result, FaceUpRoundResult)
        if result.dealer_ace_high_push:
            return result
        assert result.player_front and result.player_back, \
            "settle() called before set_player_hand()"

        result.player_front_eval = evaluate_two_card_hand(result.player_front)
        result.player_back_eval = best_five_card_eval_with_joker(result.player_back)

        # dealer_front_eval/dealer_back_eval are typed Optional on the base
        # RoundResult (only ever populated once settle() itself runs, for
        # standard Pai Gow) -- but deal() above always fills them in
        # unconditionally, well before settle() is ever reachable, so they
        # can't actually still be None here. Asserted, not just assumed, so
        # this stays true even if that ordering ever changes.
        assert result.dealer_front_eval is not None and result.dealer_back_eval is not None
        front_win = compare_hands(result.player_front_eval, result.dealer_front_eval) > 0
        back_win = compare_hands(result.player_back_eval, result.dealer_back_eval) > 0

        total_wagered = result.ante_bet + result.fortune_bet + result.jackpot_bet
        total_returned = result.fortune_return + result.jackpot_return

        if front_win and back_win:
            result.outcome = "win"
            result.ante_return = result.ante_bet * 2  # no commission -- see module docstring
            result.summary = "You win! Ante pays 1:1 (no commission)."
        elif not front_win and not back_win:
            result.outcome = "lose"
            result.summary = "Dealer wins both hands. Ante is lost."
        else:
            result.outcome = "push"
            result.ante_return = result.ante_bet
            result.summary = "Push -- you split the two hands with the dealer. Stake returned."
        total_returned += result.ante_return

        result.total_wagered = total_wagered
        result.total_returned = total_returned
        result.net_result = round(total_returned - total_wagered, 2)
        return result
