"""
Ultimate Texas Hold'em game engine.

Head-to-head Texas Hold'em against the dealer: the player's 2 hole cards and
the dealer's 2 hole cards share the same 5 community cards, exactly like
real Hold'em (unlike Mississippi Stud or Pai Gow Poker, where each side's
cards are entirely separate). Both hands are independently searched for
their best 5-of-7 combination via _best_hand -- no Joker involved, so this
is a small local helper rather than reusing Pai Gow Poker's own Joker-aware
best_five_of_seven (games/pai_gow_poker/logic.py); this module is kept
isolated from every sibling game, the same as Mississippi Stud was.

Round shape: an Ante bet requires an equal Blind bet alongside it (Trips and
the Jackpot side bet are both optional, independent of it). The player is
dealt 2 cards, the dealer 2 cards, and all 5 community cards, all face down.
The player then faces up to three Bet-or-Check decisions in turn -- pre-flop
(bet 4x or 3x the Ante), post-flop (bet 2x), post-turn (bet 1x, or Fold
instead) -- and whichever point the Play bet actually lands, every
still-hidden community card is revealed immediately afterward, then the
dealer's own 2 cards, and the round settles. Folding (only ever offered at
the final, post-turn decision) forfeits the Ante, Blind, and Trips outright.

Payout rules implemented:
  Main game (Ante, Blind, Play): the player's and dealer's best 5-of-7 hands
  are compared once the river is reached.
    - Dealer qualifies with a Pair or better. If the dealer doesn't qualify,
      the Ante pushes (refunded) regardless of the comparison outcome --
      Play (and Blind) still settle by the actual hand comparison either
      way, since only the Ante is gated by qualification.
    - Player's hand beats a qualifying dealer: Ante and Play both pay 1:1.
    - Player's hand loses: Ante, Play, and Blind are all lost.
    - Tie: Ante, Play, and Blind all push.
    - Blind additionally only ever pays out (per the paytable below) when
      the player's *winning* hand is a Straight or better -- winning with
      anything weaker (Three of a Kind down to High Card) still just pushes
      the Blind bet rather than losing it.
  Trips side bet (own spot, independent of the Ante/Play/Blind outcome --
  resolved on the player's own best 7-card hand once the river is reached;
  never evaluated on a fold, since a fold can only happen before the river):
      Royal Flush 50:1, Straight Flush 40:1, Four of a Kind 20:1,
      Full House 7:1, Flush 6:1, Straight 5:1, Three of a Kind 3:1.
  Jackpot side bet (flat £1, shared JackpotManager pool like every other
  game's own Jackpot side bet -- but a genuinely different 5-card hand from
  every other bet here: the player's 2 hole cards plus the 3-card flop
  ONLY, fixed the moment the flop is revealed and never affected by the
  turn/river or by anything that happens afterwards, except that a fold
  still forfeits any payout outright):
      Royal Flush 100% of the jackpot meter, Straight Flush 10% of the
      meter (a partial drawdown, doesn't reset it), Four of a Kind £300,
      Full House £50, Flush £40, Straight £30, Three of a Kind £9.
"""
from itertools import combinations
from typing import List, Optional

from core.cards import Card, Deck
from core.hand_evaluator import (
    compare_hands,
    evaluate_five_card_hand,
    HandEval,
    FIVE_CARD_HAND_NAMES,
    FIVE_CARD_HIGH_CARD,
    FIVE_CARD_STRAIGHT_FLUSH,
    FOUR_OF_A_KIND,
    FULL_HOUSE,
    FIVE_CARD_FLUSH,
    FIVE_CARD_STRAIGHT,
    FIVE_CARD_THREE_OF_A_KIND,
    ONE_PAIR,
)

GAME_KEY = "ultimate_texas_holdem"
GAME_LABEL = "Ultimate Texas Hold'em"
BET_TYPES = [
    ("ante", "Ante"),
    ("blind", "Blind"),
    ("play", "Play"),
    ("trips", "Trips"),
    ("jackpot", "Jackpot"),
]

# Stats screen's "Hands Made" breakdown -- see hand_outcome_label, which
# sorts one round's result into one of these purely by the player's own
# final hand rank (win/lose/push against the dealer is a separate axis --
# you can win with a Pair just as easily as lose with a Full House).
HAND_OUTCOME_LABELS = (
    ["Fold"] + [FIVE_CARD_HAND_NAMES[rank] for rank in sorted(FIVE_CARD_HAND_NAMES)] + ["Royal Flush"]
)

# --- Trips side bet paytable -- keyed by 5-card rank value; Straight Flush/
# Royal Flush aren't here since evaluate_five_card_hand folds them into one
# rank value, split apart below by _is_royal.
TRIPS_PAYTABLE = {
    FIVE_CARD_THREE_OF_A_KIND: 3,
    FIVE_CARD_STRAIGHT: 5,
    FIVE_CARD_FLUSH: 6,
    FULL_HOUSE: 7,
    FOUR_OF_A_KIND: 20,
}
TRIPS_STRAIGHT_FLUSH = 40
TRIPS_ROYAL_FLUSH = 50

# --- Blind side bet paytable -- only ever consulted once the player's hand
# is already known to have WON (see UltimateTexasHoldemGame.settle); a
# missing rank here (Three of a Kind down to High Card) means "push", not
# "lose" -- that's handled by the caller, not this table.
BLIND_PAYTABLE = {
    FIVE_CARD_STRAIGHT: 1,
    FIVE_CARD_FLUSH: 1.5,
    FULL_HOUSE: 3,
    FOUR_OF_A_KIND: 10,
}
BLIND_STRAIGHT_FLUSH = 50
BLIND_ROYAL_FLUSH = 500

# --- Jackpot side bet -- identical paytable/shape to every other game's own
# Jackpot side bet (see e.g. games/mississippi_stud/logic.py's own).
JACKPOT_BET_AMOUNT = 1.0
JACKPOT_FOUR_OF_A_KIND_PAYOUT = 300
JACKPOT_FULL_HOUSE_PAYOUT = 50
JACKPOT_FLUSH_PAYOUT = 40
JACKPOT_STRAIGHT_PAYOUT = 30
JACKPOT_THREE_OF_A_KIND_PAYOUT = 9
JACKPOT_STRAIGHT_FLUSH_FRACTION = 0.10

_ROYAL_HIGH_CARD = 14


def _is_royal(hand_eval: HandEval) -> bool:
    rank, _, tiebreak = hand_eval
    return rank == FIVE_CARD_STRAIGHT_FLUSH and tiebreak[0] == _ROYAL_HIGH_CARD


def _best_hand(seven_cards):
    """The best-ranked 5-card hand out of all C(7,5)=21 combinations of
    `seven_cards` -- no Joker handling needed (unlike Pai Gow Poker's own
    version of this search), so a plain itertools.combinations sweep is
    all this needs. Returns (HandEval, the winning 5 cards themselves) --
    the UI needs to know which specific cards were actually used, to dim
    the other 2 once a hand's fully revealed."""
    best: Optional[HandEval] = None
    best_cards = None
    for combo in combinations(seven_cards, 5):
        candidate = evaluate_five_card_hand(combo)
        if best is None or compare_hands(candidate, best) > 0:
            best = candidate
            best_cards = list(combo)
    assert best is not None  # combinations(seven_cards, 5) is never empty for 7 cards
    return best, best_cards


def trips_multiplier(hand_eval: HandEval) -> float:
    """Returns the Trips paytable multiplier for `hand_eval` -- 0 if it
    doesn't qualify (below Three of a Kind)."""
    rank = hand_eval[0]
    if rank == FIVE_CARD_STRAIGHT_FLUSH:
        return TRIPS_ROYAL_FLUSH if _is_royal(hand_eval) else TRIPS_STRAIGHT_FLUSH
    return TRIPS_PAYTABLE.get(rank, 0)


def blind_multiplier(hand_eval: HandEval) -> float:
    """Returns the Blind paytable multiplier for `hand_eval` -- 0 if it's
    below a Straight (the caller treats that as "push", not "lose": this is
    only ever consulted once the player is already known to have won the
    hand -- see settle())."""
    rank = hand_eval[0]
    if rank == FIVE_CARD_STRAIGHT_FLUSH:
        return BLIND_ROYAL_FLUSH if _is_royal(hand_eval) else BLIND_STRAIGHT_FLUSH
    return BLIND_PAYTABLE.get(rank, 0)


def jackpot_payout(hand_eval: HandEval, jackpot_amount: float):
    """Returns (payout, hits_full_jackpot, partial_fraction) for the £1
    Jackpot side bet -- resolved on the player's 2 hole cards + the 3-card
    flop ONLY (see UltimateTexasHoldemGame.reveal_flop), never called for a
    folded round. Same flat "for 1"/partial-drawdown convention as every
    other game's own Jackpot side bet -- see e.g.
    games/mississippi_stud/logic.py's own jackpot_payout for the full
    rationale, identical here."""
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
    """One of HAND_OUTCOME_LABELS for a resolved round -- purely the
    player's own final hand rank (win/lose/push against the dealer is a
    separate axis entirely -- see the module docstring)."""
    if result.folded:
        return "Fold"
    assert result.player_eval is not None, "hand_outcome_label() called on an unsettled, non-folded round"
    rank, name, _ = result.player_eval
    if rank == FIVE_CARD_STRAIGHT_FLUSH:
        return "Royal Flush" if _is_royal(result.player_eval) else "Straight Flush"
    return name


class RoundResult:
    """Plain data holder describing the outcome of one round."""

    def __init__(self):
        self.player_cards = []       # 2 hole cards
        self.dealer_cards = []       # 2 hole cards
        self.community_cards = []    # 5 cards, shared by both hands, dealt at once but revealed in stages
        self.revealed_count = 0      # how many of community_cards are currently exposed (0/3/4/5)
        self.dealer_revealed = False

        self.player_eval: Optional[HandEval] = None    # player_cards + community_cards, once the river is reached
        self.dealer_eval: Optional[HandEval] = None    # dealer_cards + community_cards, once the river is reached
        self.jackpot_eval: Optional[HandEval] = None   # player_cards + community_cards[:3] ONLY, fixed at the flop
        self.player_best_cards: Optional[List[Card]] = None  # the 5 actual cards behind player_eval
        self.dealer_best_cards: Optional[List[Card]] = None  # the 5 actual cards behind dealer_eval

        self.folded = False
        self.dealer_qualified = False
        self.outcome = ""  # "win" | "lose" | "push" | "fold" -- the Ante/Play/Blind hand-comparison headline

        self.ante_bet = 0.0
        self.blind_bet = 0.0
        self.play_bet = 0.0
        self.trips_bet = 0.0
        self.jackpot_bet = 0.0

        self.ante_return = 0.0
        self.blind_return = 0.0
        self.play_return = 0.0
        self.trips_return = 0.0
        self.jackpot_return = 0.0
        self.jackpot_won = False
        self.jackpot_pool_partial_fraction = 0.0

        self.total_wagered = 0.0
        self.total_returned = 0.0
        self.net_result = 0.0

        self.summary = ""


class UltimateTexasHoldemGame:
    """Engine for a single Ultimate Texas Hold'em table. Create one instance per table."""

    def __init__(self):
        self.deck = Deck()
        self.result: Optional[RoundResult] = None

    def deal(self, ante_bet, trips_bet=0.0, jackpot_bet=0.0) -> RoundResult:
        """Deals a new round: 2 cards to the player, 2 to the dealer, and
        all 5 community cards -- all face down, revealed via reveal_flop()/
        reveal_turn()/reveal_river(). `ante_bet` must be > 0 (the Blind bet
        is always exactly equal to it -- see the module docstring);
        `jackpot_bet` must be 0 or exactly JACKPOT_BET_AMOUNT."""
        if ante_bet <= 0:
            raise ValueError("An Ante bet is required to play a round.")
        if jackpot_bet not in (0, JACKPOT_BET_AMOUNT):
            raise ValueError(f"The jackpot side bet must be exactly £{JACKPOT_BET_AMOUNT:.0f} if played.")

        self.deck.reset()
        result = RoundResult()
        result.ante_bet = ante_bet
        result.blind_bet = ante_bet
        result.trips_bet = trips_bet
        result.jackpot_bet = jackpot_bet
        result.player_cards = self.deck.deal(2)
        result.dealer_cards = self.deck.deal(2)
        result.community_cards = self.deck.deal(5)
        self.result = result
        return result

    def reveal_flop(self) -> RoundResult:
        """Reveals the first 3 community cards -- and, right here, fixes
        the Jackpot hand forever (player_cards + this flop only, per the
        real house rule -- see jackpot_payout's own docstring): nothing
        that happens on the turn/river ever changes it again."""
        assert self.result is not None, "reveal_flop() called before deal()"
        result = self.result
        result.revealed_count = 3
        result.jackpot_eval, _ = _best_hand(result.player_cards + result.community_cards[:3])
        return result

    def reveal_turn(self) -> RoundResult:
        assert self.result is not None, "reveal_turn() called before deal()"
        self.result.revealed_count = 4
        return self.result

    def reveal_river(self) -> RoundResult:
        assert self.result is not None, "reveal_river() called before deal()"
        self.result.revealed_count = 5
        return self.result

    def bet_play(self, multiplier) -> RoundResult:
        """Places `multiplier` (4, 3, 2, or 1, depending on which decision
        point this is) times the Ante into the Play bet."""
        assert self.result is not None, "bet_play() called before deal()"
        result = self.result
        result.play_bet = result.ante_bet * multiplier
        return result

    def fold(self) -> RoundResult:
        """Folds the round -- only ever a legal decision at the final,
        post-turn stage. Forfeits the Ante, Blind, and Trips outright; no
        further community cards are revealed for the player's own hand."""
        assert self.result is not None, "fold() called before deal()"
        self.result.folded = True
        return self.result

    def settle(self, jackpot_amount: float = 0.0) -> RoundResult:
        """Settles the round. `jackpot_amount` is the current jackpot
        value, needed only if the player might have hit a Jackpot-
        qualifying hand -- pass JackpotManager.amount."""
        assert self.result is not None, "settle() called before deal()"
        result = self.result

        total_wagered = (
            result.ante_bet + result.blind_bet + result.play_bet + result.trips_bet + result.jackpot_bet
        )
        total_returned = 0.0

        if result.folded:
            result.outcome = "fold"
            result.summary = "You folded -- the Ante, Blind and Trips are forfeited."
            # Jackpot is never resolved on a folded round -- "folded hands
            # do not qualify", per the real house rule, even though the
            # flop-only Jackpot hand was already fully known by then.
        else:
            assert result.revealed_count == 5, "settle() called before the river was revealed"
            result.player_eval, result.player_best_cards = _best_hand(result.player_cards + result.community_cards)
            result.dealer_eval, result.dealer_best_cards = _best_hand(result.dealer_cards + result.community_cards)
            result.dealer_qualified = result.dealer_eval[0] >= ONE_PAIR

            comparison = compare_hands(result.player_eval, result.dealer_eval)
            if comparison > 0:
                result.outcome = "win"
            elif comparison < 0:
                result.outcome = "lose"
            else:
                result.outcome = "push"

            # --- Ante: pushes on a non-qualifying dealer regardless of the
            # comparison outcome; otherwise follows it directly. ---
            if not result.dealer_qualified:
                result.ante_return = result.ante_bet
                result.summary = "Dealer doesn't qualify (below a Pair) -- the Ante pushes."
            elif result.outcome == "win":
                result.ante_return = result.ante_bet * 2
                result.summary = "You win! Ante and Play pay 1:1."
            elif result.outcome == "push":
                result.ante_return = result.ante_bet
                result.summary = "Push -- Ante, Play and Blind all push."
            else:
                result.summary = "Dealer's hand wins. Ante, Play and Blind are lost."

            # --- Play: always follows the comparison directly, regardless
            # of dealer qualification -- only the Ante is gated by it. ---
            if result.outcome == "win":
                result.play_return = result.play_bet * 2
            elif result.outcome == "push":
                result.play_return = result.play_bet

            # --- Blind: loses/pushes the same as Play on a loss/push; on a
            # win, pays per the paytable only for a Straight or better --
            # anything weaker just pushes instead. ---
            if result.outcome == "win":
                mult = blind_multiplier(result.player_eval)
                result.blind_return = result.blind_bet * (mult + 1) if mult else result.blind_bet
            elif result.outcome == "push":
                result.blind_return = result.blind_bet

            total_returned += result.ante_return + result.play_return + result.blind_return

            # --- Trips: independent of the Ante/Play/Blind outcome
            # entirely, resolved on the player's own hand alone. ---
            if result.trips_bet > 0:
                mult = trips_multiplier(result.player_eval)
                result.trips_return = result.trips_bet * (mult + 1) if mult else 0.0
                total_returned += result.trips_return

            # --- Jackpot: independent too, resolved on the flop-only hand
            # already fixed back in reveal_flop(). ---
            if result.jackpot_bet > 0:
                assert result.jackpot_eval is not None
                payout, hits_full_jackpot, partial_fraction = jackpot_payout(result.jackpot_eval, jackpot_amount)
                result.jackpot_return = payout
                result.jackpot_won = hits_full_jackpot
                result.jackpot_pool_partial_fraction = partial_fraction
                total_returned += result.jackpot_return

        result.total_wagered = total_wagered
        result.total_returned = total_returned
        result.net_result = round(total_returned - total_wagered, 2)
        return result
