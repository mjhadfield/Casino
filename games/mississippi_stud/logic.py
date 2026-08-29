"""
Mississippi Stud game engine.

This module is intentionally decoupled from the bank balance and the UI:
it deals cards, evaluates hands, and works out how much each bet returns.
The calling UI is responsible for actually debiting/crediting the
FinanceManager based on the RoundResult it gets back -- see
games/three_card_poker/logic.py's own docstring, same convention.

Round shape: an Ante bet deals the player 2 cards (face up) and 3 community
cards (face down, dealt all at once but revealed one at a time). The player
then faces three Fold-or-Bet decisions in turn -- 3rd, 4th, and 5th Street,
each a bet of 1x-3x the Ante -- and each played bet reveals that street's
community card. Folding at any point forfeits the Ante and any street bets
already placed.

Payout rules implemented:
  Main game (Ante + 3rd/4th/5th Street, whichever were actually played):
    the final 5-card hand is the player's 2 cards plus all 3 community
    cards. Every active bet pays the SAME multiplier, looked up once from
    that hand:
      Royal Flush 500:1, Straight Flush 100:1, Four of a Kind 40:1,
      Full House 10:1, Flush 6:1, Straight 4:1, Three of a Kind 3:1,
      Two Pair 2:1, Pair of Jacks or better 1:1, Pair of 6s-10s push,
      anything worse loses.
  3 Card Bonus side bet (own spot -- resolved on the 3 community cards
  alone, independent of the main hand/fold outcome, but only once all 3 are
  actually exposed -- see reveal_remaining_for_bonus()):
      Mini-Royal (A-K-Q suited) 50:1, Straight Flush 40:1,
      Three of a Kind 30:1, Straight 6:1, Flush 3:1, Pair 1:1.
  Jackpot side bet (flat £1, like the other games' own Jackpot side bets --
  shares the same JackpotManager/pool. Resolved on the final 5-card hand,
  but only when the round wasn't folded -- see jackpot_payout()):
      Royal Flush 100% of the jackpot meter, Straight Flush 10% of the
      meter (a partial drawdown, doesn't reset it), Four of a Kind £300,
      Full House £50, Flush £40, Straight £30, Three of a Kind £9.
"""
from typing import Optional

from core.cards import Deck
from core.hand_evaluator import (
    evaluate_five_card_hand,
    evaluate_three_card_hand,
    HandEval,
    # 3-card rank constants -- used only for the 3 Card Bonus side bet,
    # which is evaluated on the 3 community cards alone.
    STRAIGHT_FLUSH,
    THREE_OF_A_KIND,
    STRAIGHT,
    FLUSH,
    PAIR,
    # 5-card rank constants -- used for the main hand and the Jackpot side
    # bet, both evaluated on the player's 2 cards + all 3 community cards.
    FIVE_CARD_STRAIGHT_FLUSH,
    FOUR_OF_A_KIND,
    FULL_HOUSE,
    FIVE_CARD_FLUSH,
    FIVE_CARD_STRAIGHT,
    FIVE_CARD_THREE_OF_A_KIND,
    TWO_PAIR,
    ONE_PAIR,
    FIVE_CARD_HIGH_CARD,
)

# Identifies this game to GameStatsManager (core/game_stats.py) and the
# Stats screen (ui/stats_screen.py) -- see three_card_poker/logic.py's own
# BET_TYPES for the same convention.
GAME_KEY = "mississippi_stud"
GAME_LABEL = "Mississippi Stud"
BET_TYPES = [
    ("ante", "Ante"),
    ("third_street", "3rd Street"),
    ("fourth_street", "4th Street"),
    ("fifth_street", "5th Street"),
    ("bonus", "3 Card Bonus"),
    ("jackpot", "Jackpot"),
]

# Stats screen's "Hands Made" breakdown -- see hand_outcome_label, which
# sorts one round's result into one of these. The Pair tier splits three
# ways (Lose/Push/Win) since evaluate_five_card_hand alone can't tell a
# losing Pair of 5s from a winning Pair of Jacks -- both are just "One Pair".
HAND_OUTCOME_LABELS = [
    "Fold", "Lose", "Push (Pair 6-10)", "Pair (Jacks or better)", "Two Pair",
    "Three of a Kind", "Straight", "Flush", "Full House", "Four of a Kind",
    "Straight Flush", "Royal Flush",
]

# --- Main game paytable -- keyed by 5-card rank value; the Pair tier isn't
# here since it splits three ways by rank (see _final_hand_multiplier), and
# Straight Flush/Royal Flush aren't here since evaluate_five_card_hand folds
# them into one rank value, split apart below by _is_royal.
MAIN_PAYTABLE = {
    FOUR_OF_A_KIND: 40,
    FULL_HOUSE: 10,
    FIVE_CARD_FLUSH: 6,
    FIVE_CARD_STRAIGHT: 4,
    FIVE_CARD_THREE_OF_A_KIND: 3,
    TWO_PAIR: 2,
}
MAIN_PAYTABLE_STRAIGHT_FLUSH = 100
MAIN_PAYTABLE_ROYAL_FLUSH = 500
MAIN_PAYTABLE_PAIR_JACKS_OR_BETTER = 1  
PAIR_JACKS_OR_BETTER_MIN_VALUE = 11 
PAIR_PUSH_MIN_VALUE = 6  

BONUS_PAYTABLE = {
    THREE_OF_A_KIND: 30,
    STRAIGHT: 6,
    FLUSH: 3,
    PAIR: 1,
}
BONUS_PAYTABLE_STRAIGHT_FLUSH = 40
BONUS_PAYTABLE_MINI_ROYAL = 50

# --- Jackpot side bet ---------------------------------------------------
# Always exactly this amount if played -- see ui.py, which enforces it as an
# on/off toggle rather than a stackable chip amount (same convention as
# every other game's own Jackpot side bet).
JACKPOT_BET_AMOUNT = 1.0

JACKPOT_FOUR_OF_A_KIND_PAYOUT = 300
JACKPOT_FULL_HOUSE_PAYOUT = 50
JACKPOT_FLUSH_PAYOUT = 40
JACKPOT_STRAIGHT_PAYOUT = 30
JACKPOT_THREE_OF_A_KIND_PAYOUT = 9
JACKPOT_STRAIGHT_FLUSH_FRACTION = 0.10  # of the current meter -- a partial drawdown, doesn't reset it
# Royal Flush pays 100% of the jackpot meter -- see jackpot_payout().

# Ace-high straight flush -- the top hand at both 5 cards (the main game's
# Royal Flush) and 3 cards (the Bonus bet's Mini-Royal, A-K-Q suited).
_ROYAL_HIGH_CARD = 14


def _is_royal(hand_eval: HandEval) -> bool:
    rank, _, tiebreak = hand_eval
    return rank == FIVE_CARD_STRAIGHT_FLUSH and tiebreak[0] == _ROYAL_HIGH_CARD


def _is_mini_royal(bonus_eval: HandEval) -> bool:
    rank, _, tiebreak = bonus_eval
    return rank == STRAIGHT_FLUSH and tiebreak[0] == _ROYAL_HIGH_CARD


def _final_hand_multiplier(hand_eval: HandEval):
    """Returns (multiplier, outcome) for the final 5-card hand against the
    main paytable -- outcome is one of "win"/"push"/"lose". `multiplier` is
    only meaningful for "win": the value every active bet (Ante + whichever
    of 3rd/4th/5th Street were played) pays at, e.g. 1 for a Pair of Jacks,
    500 for a Royal Flush. It's 0 for both "push" and "lose"."""
    rank, _, tiebreak = hand_eval
    if rank == FIVE_CARD_STRAIGHT_FLUSH:
        return (MAIN_PAYTABLE_ROYAL_FLUSH if _is_royal(hand_eval) else MAIN_PAYTABLE_STRAIGHT_FLUSH), "win"
    if rank == ONE_PAIR:
        pair_value = tiebreak[0]
        if pair_value >= PAIR_JACKS_OR_BETTER_MIN_VALUE:
            return MAIN_PAYTABLE_PAIR_JACKS_OR_BETTER, "win"
        if pair_value >= PAIR_PUSH_MIN_VALUE:
            return 0, "push"
        return 0, "lose"
    if rank in MAIN_PAYTABLE:
        return MAIN_PAYTABLE[rank], "win"
    return 0, "lose"  # High Card


def bonus_multiplier(bonus_eval: HandEval) -> int:
    """Returns the 3 Card Bonus paytable multiplier for `bonus_eval`
    (evaluated on the 3 community cards alone) -- 0 if it doesn't qualify
    (below a Pair)."""
    rank = bonus_eval[0]
    if rank == STRAIGHT_FLUSH:
        return BONUS_PAYTABLE_MINI_ROYAL if _is_mini_royal(bonus_eval) else BONUS_PAYTABLE_STRAIGHT_FLUSH
    return BONUS_PAYTABLE.get(rank, 0)


def jackpot_payout(hand_eval: HandEval, jackpot_amount: float):
    """Returns (payout, hits_full_jackpot, partial_fraction) for the £1
    Jackpot side bet, resolved on the final 5-card hand -- never called for
    a folded round (see MississippiStudGame.settle: a folded hand never
    qualifies for a Jackpot payout, even in the one case where an active
    Bonus bet already forced a full community-card reveal -- that's the
    real house rule, not just a shortcut).

    `hits_full_jackpot` (Royal Flush) means the caller should reset the
    jackpot to its floor (JackpotManager.win()); `partial_fraction`
    (Straight Flush) means the caller should draw the meter down by that
    fraction instead (JackpotManager.set_amount(amount * (1 -
    partial_fraction))) -- mirrors Pai Gow Poker's own Fortune bonus
    partial-drawdown convention. Neither tier's payout is on top of the
    wager being "returned" -- these are flat "for 1" amounts (the source
    rules' own phrasing), same convention as every other game's own Jackpot
    side bet: the £1 wager is simply gone, win or lose."""
    rank = hand_eval[0]
    if rank == FIVE_CARD_STRAIGHT_FLUSH:
        if _is_royal(hand_eval):
            return jackpot_amount, True, 0.0
        return jackpot_amount * JACKPOT_STRAIGHT_FLUSH_FRACTION, False, JACKPOT_STRAIGHT_FLUSH_FRACTION
    if rank == FOUR_OF_A_KIND:
        return JACKPOT_FOUR_OF_A_KIND_PAYOUT, False, 0.0
    if rank == FULL_HOUSE:
        return JACKPOT_FULL_HOUSE_PAYOUT, False, 0.0
    if rank == FIVE_CARD_FLUSH:
        return JACKPOT_FLUSH_PAYOUT, False, 0.0
    if rank == FIVE_CARD_STRAIGHT:
        return JACKPOT_STRAIGHT_PAYOUT, False, 0.0
    if rank == FIVE_CARD_THREE_OF_A_KIND:
        return JACKPOT_THREE_OF_A_KIND_PAYOUT, False, 0.0
    return 0, False, 0.0


def hand_outcome_label(result: "RoundResult") -> str:
    """One of HAND_OUTCOME_LABELS for a resolved round -- used by the Stats
    screen's hand-frequency breakdown."""
    if result.folded:
        return "Fold"
    assert result.final_eval is not None, "hand_outcome_label() called on an unsettled, non-folded round"
    rank, name, tiebreak = result.final_eval
    if rank == FIVE_CARD_STRAIGHT_FLUSH:
        return "Royal Flush" if _is_royal(result.final_eval) else "Straight Flush"
    if rank == ONE_PAIR:
        pair_value = tiebreak[0]
        if pair_value >= PAIR_JACKS_OR_BETTER_MIN_VALUE:
            return "Pair (Jacks or better)"
        if pair_value >= PAIR_PUSH_MIN_VALUE:
            return "Push (Pair 6-10)"
        return "Lose"
    if rank == FIVE_CARD_HIGH_CARD:
        return "Lose"
    return name  # Two Pair / Three of a Kind / Straight / Flush / Full House / Four of a Kind


class RoundResult:
    """Plain data holder describing the outcome of one round."""

    def __init__(self):
        self.player_cards = []       # 2 hole cards, dealt face up
        self.community_cards = []    # 3 cards, dealt all at once but revealed one at a time
        self.revealed_count = 0      # how many of community_cards are currently exposed (0-3)
        self.final_eval: Optional[HandEval] = None  # player_cards + community_cards, once fully revealed and not folded
        self.bonus_eval: Optional[HandEval] = None  # community_cards alone, once fully revealed

        self.folded = False
        self.folded_at_street: Optional[int] = None  # 3, 4, or 5
        self.outcome = ""  # "win" | "push" | "lose" | "fold"

        self.ante_bet = 0.0
        self.third_street_bet = 0.0
        self.fourth_street_bet = 0.0
        self.fifth_street_bet = 0.0
        self.bonus_bet = 0.0
        self.jackpot_bet = 0.0

        self.ante_return = 0.0
        self.third_street_return = 0.0
        self.fourth_street_return = 0.0
        self.fifth_street_return = 0.0
        self.bonus_return = 0.0
        self.jackpot_return = 0.0
        self.jackpot_won = False  # True only for a Royal Flush -- caller must reset the jackpot
        self.jackpot_pool_partial_fraction = 0.0  # >0 only for a Straight Flush -- caller must draw the meter down

        self.total_wagered = 0.0
        self.total_returned = 0.0
        self.net_result = 0.0

        self.summary = ""


class MississippiStudGame:
    """Engine for a single Mississippi Stud table. Create one instance per table."""

    def __init__(self):
        self.deck = Deck()
        self.result: Optional[RoundResult] = None

    def deal(self, ante_bet, bonus_bet=0.0, jackpot_bet=0.0) -> RoundResult:
        """Deals a new round: 2 cards to the player, 3 community cards (dealt
        now, face down, revealed one at a time via bet_street()/
        reveal_remaining_for_bonus()). `ante_bet` must be > 0; `jackpot_bet`
        must be 0 or exactly JACKPOT_BET_AMOUNT."""
        if ante_bet <= 0:
            raise ValueError("An Ante bet is required to play a round.")
        if jackpot_bet not in (0, JACKPOT_BET_AMOUNT):
            raise ValueError(f"The jackpot side bet must be exactly £{JACKPOT_BET_AMOUNT:.0f} if played.")

        self.deck.reset()
        result = RoundResult()
        result.ante_bet = ante_bet
        result.bonus_bet = bonus_bet
        result.jackpot_bet = jackpot_bet
        result.player_cards = self.deck.deal(2)
        result.community_cards = self.deck.deal(3)
        self.result = result
        return result

    def bet_street(self, street: int, multiplier: int) -> RoundResult:
        """Places `multiplier` (1-3) times the Ante on `street` (3, 4, or 5)
        and reveals that street's community card -- the 1st reveal is 3rd
        Street's card, the 2nd is 4th Street's, the 3rd/final is 5th
        Street's, matching community_cards' own left-to-right order."""
        assert self.result is not None, "bet_street() called before deal()"
        result = self.result
        bet_amount = result.ante_bet * multiplier
        if street == 3:
            result.third_street_bet = bet_amount
        elif street == 4:
            result.fourth_street_bet = bet_amount
        elif street == 5:
            result.fifth_street_bet = bet_amount
        else:
            raise ValueError(f"Invalid street: {street}")
        result.revealed_count = street - 2
        return result

    def fold(self, street: int) -> RoundResult:
        """Folds the round at `street` (3, 4, or 5) -- forfeits the Ante and
        any street bets already placed. Does not by itself reveal any
        remaining community cards -- see reveal_remaining_for_bonus()."""
        assert self.result is not None, "fold() called before deal()"
        result = self.result
        result.folded = True
        result.folded_at_street = street
        return result

    def reveal_remaining_for_bonus(self) -> RoundResult:
        """Force-reveals whatever's left of the 3 community cards after a
        fold, purely to settle an active 3 Card Bonus bet (which "remains in
        action until the three community cards are exposed", per the real
        house rule, regardless of the main game's own fold) -- no further
        player decision or street bet involved. A no-op if they're already
        all exposed."""
        assert self.result is not None, "reveal_remaining_for_bonus() called before deal()"
        self.result.revealed_count = 3
        return self.result

    def settle(self, jackpot_amount: float = 0.0) -> RoundResult:
        """Settles the round. `jackpot_amount` is the current jackpot value,
        needed only if the player might have hit a Jackpot-qualifying hand
        -- pass JackpotManager.amount."""
        assert self.result is not None, "settle() called before deal()"
        result = self.result

        total_wagered = (
            result.ante_bet + result.third_street_bet + result.fourth_street_bet
            + result.fifth_street_bet + result.bonus_bet + result.jackpot_bet
        )
        total_returned = 0.0

        # --- 3 Card Bonus: resolved on the 3 community cards alone, whenever
        # they've all actually been exposed -- either the round played all
        # the way to 5th Street, or it folded with the Bonus bet active and
        # reveal_remaining_for_bonus() force-revealed the rest. ---
        if result.bonus_bet > 0 and result.revealed_count == 3:
            result.bonus_eval = evaluate_three_card_hand(result.community_cards)
            multiplier = bonus_multiplier(result.bonus_eval)
            result.bonus_return = result.bonus_bet * (multiplier + 1) if multiplier else 0.0
            total_returned += result.bonus_return

        if result.folded:
            result.outcome = "fold"
            result.summary = "You folded -- the Ante and any street bets are forfeited."
            # Jackpot is never resolved on a folded round -- see
            # jackpot_payout()'s own docstring.
        else:
            assert result.revealed_count == 3, "settle() called before all 3 community cards were revealed"
            result.final_eval = evaluate_five_card_hand(result.player_cards + result.community_cards)
            multiplier, outcome = _final_hand_multiplier(result.final_eval)
            result.outcome = outcome
            if outcome == "win":
                result.ante_return = result.ante_bet * (multiplier + 1)
                result.third_street_return = result.third_street_bet * (multiplier + 1)
                result.fourth_street_return = result.fourth_street_bet * (multiplier + 1)
                result.fifth_street_return = result.fifth_street_bet * (multiplier + 1)
                result.summary = f"{result.final_eval[1]} -- pays {multiplier}:1 on every bet in play!"
            elif outcome == "push":
                result.ante_return = result.ante_bet
                result.third_street_return = result.third_street_bet
                result.fourth_street_return = result.fourth_street_bet
                result.fifth_street_return = result.fifth_street_bet
                result.summary = "Pair of 6s-10s -- a push. Every bet in play is returned."
            else:
                result.summary = "No qualifying hand -- the Ante and street bets are lost."
            total_returned += (
                result.ante_return + result.third_street_return
                + result.fourth_street_return + result.fifth_street_return
            )

            if result.jackpot_bet > 0:
                payout, hits_full_jackpot, partial_fraction = jackpot_payout(result.final_eval, jackpot_amount)
                result.jackpot_return = payout
                result.jackpot_won = hits_full_jackpot
                result.jackpot_pool_partial_fraction = partial_fraction
                total_returned += result.jackpot_return

        result.total_wagered = total_wagered
        result.total_returned = total_returned
        result.net_result = round(total_returned - total_wagered, 2)
        return result
