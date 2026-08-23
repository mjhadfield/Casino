"""
Three Card Poker game engine (UK casino payout rules).

This module is intentionally decoupled from the bank balance and the UI:
it deals cards, evaluates hands, and works out how much each bet returns.
The calling UI is responsible for actually debiting/crediting the
FinanceManager based on the RoundResult it gets back. That keeps the game
rules testable in isolation and keeps FinanceManager reusable for any
future game in the library.

Payout rules implemented:
  Main game (Ante & Play):
    - Player beats dealer (dealer qualifies): Ante 1:1, Play 1:1
    - Dealer doesn't qualify (below Queen-high): Ante 1:1, Play pushes
    - Dealer beats player: Ante and Play both lost
    - Tie: both push
  Ante Bonus (paid regardless of dealer's hand, forfeited on fold):
    - Straight Flush 5:1, Three of a Kind 4:1, Straight 1:1
  Pair Plus side bet (resolved on the player's hand alone, unaffected by fold):
    - Pair 1:1, Flush 4:1, Straight 6:1, Three of a Kind 33:1, Straight Flush 35:1
  Prime side bet (UK variation, suit-colour based, unaffected by fold):
    - All 3 player cards same colour: 3:1
    - All 6 cards (player + dealer) same colour: 4:1 (supersedes the 3:1)
  Jackpot side bet (flat £1, unaffected by fold, like Pair Plus/Prime -- paid
  regardless of the main game's outcome since it's resolved on the player's
  own 3 cards alone):
    - Straight: £6
    - Three of a Kind: £60
    - Straight Flush (not Ace-high): £100
    - Royal Flush (Q-K-A suited), not spades: £500
    - Royal Flush, spades: 100% of the current jackpot -- which then resets
      to its floor (see core/jackpot.py)
"""
from typing import Optional

from core.cards import Deck, Suit
from core.hand_evaluator import (
    evaluate_three_card_hand,
    compare_hands,
    dealer_qualifies,
    HandEval,
    STRAIGHT_FLUSH,
    THREE_OF_A_KIND,
    STRAIGHT,
)

ANTE_BONUS_MULTIPLIERS = {
    STRAIGHT_FLUSH: 5,
    THREE_OF_A_KIND: 4,
    STRAIGHT: 1,
}

PAIR_PLUS_MULTIPLIERS = {
    "Pair": 1,
    "Flush": 4,
    "Straight": 6,
    "Three of a Kind": 33,
    "Straight Flush": 35,
}

PRIME_SAME_COLOUR_3_MULTIPLIER = 3
PRIME_SAME_COLOUR_6_MULTIPLIER = 4

# --- Jackpot side bet ---------------------------------------------------
# Always exactly this amount if played -- see ui.py, which enforces it as an
# on/off toggle rather than a stackable chip amount.
JACKPOT_BET_AMOUNT = 1.0

JACKPOT_STRAIGHT_PAYOUT = 6
JACKPOT_THREE_OF_A_KIND_PAYOUT = 60
JACKPOT_STRAIGHT_FLUSH_PAYOUT = 100    # Straight Flush, excluding the Ace-high "Royal"
JACKPOT_ROYAL_NON_SPADES_PAYOUT = 500  # Ace-high straight flush (Q-K-A suited), any suit but spades
# Ace-high straight flush in spades pays 100% of the jackpot -- see jackpot_payout().

# Ace-high straight flush == Q-K-A suited, the top hand in 3-card poker.
_ROYAL_HIGH_CARD = 14


def _is_royal(player_eval: HandEval) -> bool:
    rank, _, tiebreak = player_eval
    return rank == STRAIGHT_FLUSH and tiebreak[0] == _ROYAL_HIGH_CARD


def jackpot_payout(player_eval: HandEval, player_cards, jackpot_amount):
    """Returns (payout, hits_jackpot) for the £1 jackpot side bet, resolved
    on the player's final 3-card hand alone -- unaffected by fold, like Pair
    Plus/Prime. `hits_jackpot` is True only for a spades Royal Flush, which
    pays `jackpot_amount` in full; the caller is responsible for resetting
    the jackpot afterwards (see JackpotManager.win)."""
    rank = player_eval[0]
    if rank == STRAIGHT_FLUSH:
        if _is_royal(player_eval):
            if player_cards[0].suit == Suit.SPADES:  # a flush, so any one card's suit says it all
                return jackpot_amount, True
            return JACKPOT_ROYAL_NON_SPADES_PAYOUT, False
        return JACKPOT_STRAIGHT_FLUSH_PAYOUT, False
    if rank == THREE_OF_A_KIND:
        return JACKPOT_THREE_OF_A_KIND_PAYOUT, False
    if rank == STRAIGHT:
        return JACKPOT_STRAIGHT_PAYOUT, False
    return 0, False


class RoundResult:
    """Plain data holder describing the outcome of one round."""

    def __init__(self):
        self.player_cards = []
        self.dealer_cards = []
        self.player_eval: Optional[HandEval] = None
        self.dealer_eval: Optional[HandEval] = None

        self.folded = False
        self.dealer_qualified = False
        self.outcome = ""  # "win" | "lose" | "push" | "dealer_no_qualify" | "fold"

        self.ante_bet = 0.0
        self.play_bet = 0.0
        self.pair_plus_bet = 0.0
        self.prime_bet = 0.0
        self.jackpot_bet = 0.0

        self.ante_return = 0.0
        self.play_return = 0.0
        self.ante_bonus_return = 0.0
        self.pair_plus_return = 0.0
        self.prime_return = 0.0
        self.jackpot_return = 0.0
        self.jackpot_won = False  # True only for the spades Royal Flush -- caller must reset the jackpot

        self.total_wagered = 0.0
        self.total_returned = 0.0
        self.net_result = 0.0

        self.summary = ""


class ThreeCardPokerGame:
    """Engine for a single Three Card Poker table. Create one instance per table."""

    def __init__(self):
        self.deck = Deck()
        self.result: Optional[RoundResult] = None

    def play_round(self, ante, pair_plus=0, prime=0, jackpot=0):
        """Deals a new round. `ante` must be > 0; `jackpot` must be 0 or
        exactly JACKPOT_BET_AMOUNT. Returns the in-progress RoundResult
        (dealer's hand is dealt but the round isn't settled until resolve() is called)."""
        if ante <= 0:
            raise ValueError("An Ante bet is required to play a round.")
        if jackpot not in (0, JACKPOT_BET_AMOUNT):
            raise ValueError(f"The jackpot side bet must be exactly £{JACKPOT_BET_AMOUNT:.0f} if played.")

        self.deck.reset()
        result = RoundResult()
        result.ante_bet = ante
        result.pair_plus_bet = pair_plus
        result.prime_bet = prime
        result.jackpot_bet = jackpot

        result.player_cards = self.deck.deal(3)
        result.dealer_cards = self.deck.deal(3)
        result.player_eval = evaluate_three_card_hand(result.player_cards)
        result.dealer_eval = evaluate_three_card_hand(result.dealer_cards)

        self.result = result
        return result

    def resolve(self, folded: bool, jackpot_amount: float = 0.0) -> RoundResult:
        """Settles the round given the player's Play/Fold decision.
        When playing, the Play bet is assumed equal to the Ante bet (standard
        rule). `jackpot_amount` is the current jackpot value, needed only if
        the player might have hit the spades Royal Flush -- pass
        JackpotManager.amount."""
        assert self.result is not None, "resolve() called before play_round()"
        result = self.result
        # play_round() always sets both evals right before setting self.result,
        # so by construction they're never still None here.
        assert result.player_eval is not None and result.dealer_eval is not None
        result.folded = folded
        result.play_bet = 0.0 if folded else result.ante_bet
        result.dealer_qualified = dealer_qualifies(result.dealer_eval)

        total_wagered = result.ante_bet + result.play_bet + result.pair_plus_bet + result.prime_bet + result.jackpot_bet
        total_returned = 0.0

        # --- Jackpot: resolved on the player's hand alone, regardless of fold ---
        if result.jackpot_bet > 0:
            result.jackpot_return, result.jackpot_won = jackpot_payout(
                result.player_eval, result.player_cards, jackpot_amount
            )
            total_returned += result.jackpot_return

        # --- Pair Plus: resolved on the player's hand alone, regardless of fold ---
        if result.pair_plus_bet > 0:
            hand_name = result.player_eval[1]
            multiplier = PAIR_PLUS_MULTIPLIERS.get(hand_name, 0)
            result.pair_plus_return = result.pair_plus_bet * (multiplier + 1) if multiplier else 0.0
            total_returned += result.pair_plus_return

        # --- Prime (UK): suit-colour side bet, regardless of fold ---
        if result.prime_bet > 0:
            player_colours = {c.color for c in result.player_cards}
            all_colours = {c.color for c in (result.player_cards + result.dealer_cards)}
            if len(all_colours) == 1:
                result.prime_return = result.prime_bet * (PRIME_SAME_COLOUR_6_MULTIPLIER + 1)
            elif len(player_colours) == 1:
                result.prime_return = result.prime_bet * (PRIME_SAME_COLOUR_3_MULTIPLIER + 1)
            else:
                result.prime_return = 0.0
            total_returned += result.prime_return

        # --- Ante Bonus: paid regardless of dealer's hand, forfeited if the player folds ---
        if not folded:
            player_rank = result.player_eval[0]
            multiplier = ANTE_BONUS_MULTIPLIERS.get(player_rank, 0)
            if multiplier:
                result.ante_bonus_return = result.ante_bet * multiplier
                total_returned += result.ante_bonus_return

        # --- Main Ante / Play resolution ---
        if folded:
            result.outcome = "fold"
            result.summary = "You folded and forfeited your Ante."
        elif not result.dealer_qualified:
            result.outcome = "dealer_no_qualify"
            result.ante_return = result.ante_bet * 2  # stake back + 1:1
            result.play_return = result.play_bet       # push, stake returned
            total_returned += result.ante_return + result.play_return
            result.summary = "Dealer doesn't qualify (below Queen-high). Ante pays 1:1, Play pushes."
        else:
            comparison = compare_hands(result.player_eval, result.dealer_eval)
            if comparison > 0:
                result.outcome = "win"
                result.ante_return = result.ante_bet * 2
                result.play_return = result.play_bet * 2
                total_returned += result.ante_return + result.play_return
                result.summary = "You beat the dealer! Ante and Play both pay 1:1."
            elif comparison < 0:
                result.outcome = "lose"
                result.summary = "Dealer's hand wins. Ante and Play are lost."
            else:
                result.outcome = "push"
                result.ante_return = result.ante_bet
                result.play_return = result.play_bet
                total_returned += result.ante_return + result.play_return
                result.summary = "Push! Hands are equal, stakes returned."

        result.total_wagered = total_wagered
        result.total_returned = total_returned
        result.net_result = round(total_returned - total_wagered, 2)
        return result
