"""
Let It Ride game engine.

Three equal starter bets ("bet1", "bet2", and an always-in-play "ante" spot,
rendered on screen as "1", "2", and "£" respectively) plus three fully
independent optional side bets (Bonus, 3 Card, Jackpot). The player is dealt
3 cards; the dealer is dealt 2 cards face down -- these act as "community"
cards shared with the player's own hand (a single-player app, so there's no
other seat to share them with; they simply complete the player's own final
5-card hand alongside their own 3). The player faces two Pull Back-or-Let It
Ride decisions in turn: right after seeing their own 3 cards (governs bet1),
then again after the first community card is revealed (governs bet2). The
"ante" spot never gets a decision -- it always plays. Whichever spots are
still active once the second community card is revealed settle against the
final 5-card hand (3 player + 2 community).

Payout rules implemented:
  Base wager (ante, plus bet1/bet2 if not pulled back): qualifies with a Pair
  of Tens or better -- any hand ranked above a single pair automatically
  qualifies regardless of specific ranks (Two Pair always qualifies); a
  single pair below Tens, or a worse hand, loses outright with no push.
  Every still-active spot pays independently at the Basic Game Payout odds
  on a qualifying hand.

  Bonus side bet (flat £1, always resolves regardless of what happened
  to bet1/bet2): same final 5-card hand. Requires Three of a Kind or better
  -- Two Pair, which *does* qualify the base wager, still loses the Bonus.

  3 Card side bet (variable, always resolves independently): judged on the
  player's own 3 cards only, no community cards. Requires a Pair or better.
  Alternative A gives A-K-Q suited ("Mini Royal") no separate tier -- it's
  just paid as a Straight Flush.

  Jackpot side bet (flat £1, shared JackpotManager pool like every other
  game's own Jackpot side bet): same final 5-card hand as the base wager and
  Bonus -- unlike Ultimate Texas Hold'em's own Jackpot, nothing here is
  frozen early; it's judged at final settlement like everything else.
      Royal Flush 100% of the jackpot meter, Straight Flush 10% of the meter
      (a partial drawdown, doesn't reset it), Four of a Kind £300, Full
      House £50, Flush £40, Straight £30, Three of a Kind
      £9.
"""
from typing import List, Optional

from core.cards import Card, Deck
from core.hand_evaluator import (
    evaluate_five_card_hand,
    evaluate_three_card_hand,
    HandEval,
    FIVE_CARD_STRAIGHT_FLUSH,
    FOUR_OF_A_KIND,
    FULL_HOUSE,
    FIVE_CARD_FLUSH,
    FIVE_CARD_STRAIGHT,
    FIVE_CARD_THREE_OF_A_KIND,
    TWO_PAIR,
    ONE_PAIR,
    STRAIGHT_FLUSH,
    THREE_OF_A_KIND,
    STRAIGHT,
    FLUSH,
    PAIR,
)

GAME_KEY = "let_it_ride"
GAME_LABEL = "Let It Ride"
BET_TYPES = [
    ("bet1", "Bet 1"),
    ("bet2", "Bet 2"),
    ("ante", "£ Bet"),
    ("bonus", "Bonus"),
    ("three_card", "3 Card Bonus"),
    ("jackpot", "Jackpot"),
]

# Stats screen's "Hands Made" breakdown -- see hand_outcome_label, which
# sorts one round's result purely by the strength of the final 5-card hand.
# A pair below Tens and a plain High Card are both lumped as "No Qualifying
# Hand" -- from the base wager's point of view they're the same outcome.
HAND_OUTCOME_LABELS = [
    "No Qualifying Hand", "Pair of Tens or Better", "Two Pair", "Three of a Kind",
    "Straight", "Flush", "Full House", "Four of a Kind", "Straight Flush", "Royal Flush",
]

_TIER_TO_OUTCOME_LABEL = {
    "high_card": "No Qualifying Hand", "low_pair": "No Qualifying Hand",
    "pair_tens_or_better": "Pair of Tens or Better", "two_pair": "Two Pair",
    "three_of_a_kind": "Three of a Kind", "straight": "Straight", "flush": "Flush",
    "full_house": "Full House", "four_of_a_kind": "Four of a Kind",
    "straight_flush": "Straight Flush", "royal_flush": "Royal Flush",
}

# --- Basic Game Payout -- Alternative A (X:1). Applies independently to
# every base spot (ante/bet1/bet2) still in play. Tiers not present here
# ("low_pair", "high_card") don't qualify -- the spot simply loses.
BASIC_GAME_PAYOUT = {
    "royal_flush": 500, "straight_flush": 100, "four_of_a_kind": 25, "full_house": 15,
    "flush": 10, "straight": 5, "three_of_a_kind": 3, "two_pair": 2, "pair_tens_or_better": 1,
}

# --- Bonus side bet -- Alternative A (X:1, flat £1, 5-card hand). Two
# Pair and below lose -- note this qualification line sits *above* the base
# wager's own (Pair of Tens), so a Two Pair hand wins the base wager but
# still loses the Bonus.
BONUS_PAYOUT = {
    "royal_flush": 10000, "straight_flush": 2000, "four_of_a_kind": 400, "full_house": 200,
    "flush": 50, "straight": 25, "three_of_a_kind": 5,
}

# --- 3 Card side bet -- Alternative A (X:1, player's own 3 cards only).
# High Card loses. A-K-Q suited ("Mini Royal") gets no separate tier under
# Alternative A -- it just falls out of _three_card_tier as "straight_flush"
# like any other straight flush.
THREE_CARD_BONUS_PAYOUT = {
    "straight_flush": 40, "three_of_a_kind": 30, "straight": 6, "flush": 4, "pair": 1,
}

# --- Bonus side bet is locked at a flat £1, same as Jackpot below -- kept as
# its own named constant (rather than reusing JACKPOT_BET_AMOUNT) so the two
# unrelated £1 side bets don't read as if one were defined in terms of the
# other.
BONUS_BET_AMOUNT = 1.0

# --- Jackpot side bet -- identical paytable/shape to Ultimate Texas Hold'em's
# own Jackpot side bet (games/ultimate_texas_holdem/logic.py), confirmed
# against the same source document; each game keeps its own copy of these
# numbers rather than sharing code, per this app's isolation convention.
JACKPOT_BET_AMOUNT = 1.0
JACKPOT_FOUR_OF_A_KIND_PAYOUT = 300
JACKPOT_FULL_HOUSE_PAYOUT = 50
JACKPOT_FLUSH_PAYOUT = 40
JACKPOT_STRAIGHT_PAYOUT = 30
JACKPOT_THREE_OF_A_KIND_PAYOUT = 9
JACKPOT_STRAIGHT_FLUSH_FRACTION = 0.10
JACKPOT_TIER_PAYOUTS = {
    "four_of_a_kind": JACKPOT_FOUR_OF_A_KIND_PAYOUT,
    "full_house": JACKPOT_FULL_HOUSE_PAYOUT,
    "flush": JACKPOT_FLUSH_PAYOUT,
    "straight": JACKPOT_STRAIGHT_PAYOUT,
    "three_of_a_kind": JACKPOT_THREE_OF_A_KIND_PAYOUT,
}


def _five_card_tier(hand_eval: HandEval) -> str:
    """Classifies a 5-card HandEval into this game's own tier vocabulary --
    used to index every paytable dict above."""
    rank, _, tiebreak = hand_eval
    if rank == FIVE_CARD_STRAIGHT_FLUSH:
        return "royal_flush" if tiebreak[0] == 14 else "straight_flush"
    if rank == FOUR_OF_A_KIND:
        return "four_of_a_kind"
    if rank == FULL_HOUSE:
        return "full_house"
    if rank == FIVE_CARD_FLUSH:
        return "flush"
    if rank == FIVE_CARD_STRAIGHT:
        return "straight"
    if rank == FIVE_CARD_THREE_OF_A_KIND:
        return "three_of_a_kind"
    if rank == TWO_PAIR:
        return "two_pair"
    if rank == ONE_PAIR:
        return "pair_tens_or_better" if tiebreak[0] >= 10 else "low_pair"
    return "high_card"


def _three_card_tier(hand_eval: HandEval) -> str:
    rank, _, _ = hand_eval
    return {
        STRAIGHT_FLUSH: "straight_flush",
        THREE_OF_A_KIND: "three_of_a_kind",
        STRAIGHT: "straight",
        FLUSH: "flush",
        PAIR: "pair",
    }.get(rank, "high_card")


def jackpot_payout(tier: str, jackpot_amount: float):
    """Returns (payout, hits_full_jackpot, partial_fraction) for the £1
    Jackpot side bet, given the final 5-card tier (the same tier the base
    wager and Bonus are judged against -- nothing here is frozen early)."""
    if tier == "royal_flush":
        return jackpot_amount, True, 0.0
    if tier == "straight_flush":
        return jackpot_amount * JACKPOT_STRAIGHT_FLUSH_FRACTION, False, JACKPOT_STRAIGHT_FLUSH_FRACTION
    if tier in JACKPOT_TIER_PAYOUTS:
        return JACKPOT_TIER_PAYOUTS[tier], False, 0.0
    return 0, False, 0.0


def hand_outcome_label(result: "RoundResult") -> str:
    assert result.five_card_tier is not None, "hand_outcome_label() called on an unsettled round"
    return _TIER_TO_OUTCOME_LABEL[result.five_card_tier]


def total_upfront_cost(bet_unit, bonus_bet=0.0, three_card_bet=0.0, jackpot_bet=0.0) -> float:
    """The full cost to deal a round: 3 equal base spots plus whichever
    optional side bets are placed. Plain affordability check -- no extra
    multiplier quirk needed beyond what the three-equal-bets mechanic
    already implies."""
    return 3 * bet_unit + bonus_bet + three_card_bet + jackpot_bet


def _build_summary(result: "RoundResult") -> str:
    tier_label = _TIER_TO_OUTCOME_LABEL[result.five_card_tier]
    if not result.qualified:
        return f"{tier_label} -- below a Pair of Tens, the base bet(s) still in play are lost."
    mult = BASIC_GAME_PAYOUT[result.five_card_tier]
    return f"{tier_label} -- the base bet(s) still in play pay {mult}:1."


class RoundResult:
    """Plain data holder describing the outcome of one round."""

    def __init__(self):
        self.player_cards: List[Card] = []       # 3 cards
        self.community_cards: List[Card] = []    # 2 cards, dealt face down, revealed one at a time
        self.revealed_count = 0                  # how many of community_cards are currently exposed (0/1/2)

        self.bet_unit = 0.0
        self.decision1: Optional[str] = None     # "let_it_ride" | "pull_back"
        self.decision2: Optional[str] = None
        self.bet1_active = True
        self.bet2_active = True

        self.ante_bet = 0.0                      # the always-in-play "£" spot
        self.bet1_bet = 0.0
        self.bet2_bet = 0.0
        self.ante_return = 0.0
        self.bet1_return = 0.0
        self.bet2_return = 0.0

        self.bonus_bet = 0.0
        self.bonus_return = 0.0
        self.three_card_bet = 0.0
        self.three_card_return = 0.0
        self.jackpot_bet = 0.0
        self.jackpot_return = 0.0
        self.jackpot_won = False
        self.jackpot_pool_partial_fraction = 0.0

        self.five_card_tier: Optional[str] = None
        self.three_card_tier: Optional[str] = None
        self.qualified = False

        self.total_wagered = 0.0
        self.total_returned = 0.0
        self.net_result = 0.0

        self.summary = ""


class LetItRideGame:
    """Engine for a single Let It Ride table. Create one instance per table."""

    def __init__(self):
        self.deck = Deck()
        self.result: Optional[RoundResult] = None

    def deal(self, bet_unit, bonus_bet=0.0, three_card_bet=0.0, jackpot_bet=0.0) -> RoundResult:
        """Deals a new round: 3 cards to the player, 2 to the dealer (the
        shared community cards) -- all face down, revealed via
        reveal_first_card()/reveal_second_card(). `bet_unit` must be > 0
        (all three base spots start equal -- see the module docstring);
        `jackpot_bet` must be 0 or exactly JACKPOT_BET_AMOUNT."""
        if bet_unit <= 0:
            raise ValueError("A base bet is required to play a round.")
        if bonus_bet not in (0, BONUS_BET_AMOUNT):
            raise ValueError(f"The bonus side bet must be exactly £{BONUS_BET_AMOUNT:.0f} if played.")
        if jackpot_bet not in (0, JACKPOT_BET_AMOUNT):
            raise ValueError(f"The jackpot side bet must be exactly £{JACKPOT_BET_AMOUNT:.0f} if played.")

        self.deck.reset()
        result = RoundResult()
        result.bet_unit = bet_unit
        result.ante_bet = bet_unit
        result.bet1_bet = bet_unit
        result.bet2_bet = bet_unit
        result.bonus_bet = bonus_bet
        result.three_card_bet = three_card_bet
        result.jackpot_bet = jackpot_bet
        result.player_cards = self.deck.deal(3)
        result.community_cards = self.deck.deal(2)
        result.total_wagered = total_upfront_cost(bet_unit, bonus_bet, three_card_bet, jackpot_bet)
        self.result = result
        return result

    def decide_bet1(self, let_it_ride: bool) -> float:
        """The first decision, made right after the player sees their own 3
        cards, before any community card is revealed. Returns the refund
        amount (0.0 if let_it_ride)."""
        assert self.result is not None, "decide_bet1() called before deal()"
        result = self.result
        if let_it_ride:
            result.decision1 = "let_it_ride"
            return 0.0
        result.decision1 = "pull_back"
        result.bet1_active = False
        result.bet1_return = result.bet1_bet
        return result.bet1_bet

    def decide_bet2(self, let_it_ride: bool) -> float:
        """The second decision, made after the first community card is
        revealed. Returns the refund amount (0.0 if let_it_ride)."""
        assert self.result is not None, "decide_bet2() called before deal()"
        result = self.result
        if let_it_ride:
            result.decision2 = "let_it_ride"
            return 0.0
        result.decision2 = "pull_back"
        result.bet2_active = False
        result.bet2_return = result.bet2_bet
        return result.bet2_bet

    def reveal_first_card(self) -> RoundResult:
        assert self.result is not None, "reveal_first_card() called before deal()"
        self.result.revealed_count = 1
        return self.result

    def reveal_second_card(self) -> RoundResult:
        assert self.result is not None, "reveal_second_card() called before deal()"
        self.result.revealed_count = 2
        return self.result

    def settle(self, jackpot_amount: float = 0.0) -> RoundResult:
        """Settles the round. `jackpot_amount` is the current jackpot value,
        needed only if the Jackpot side bet was placed -- pass
        JackpotManager.amount."""
        assert self.result is not None, "settle() called before deal()"
        assert self.result.revealed_count == 2, "settle() called before the second community card was revealed"
        result = self.result

        # The final hand's tier is computed exactly once here and reused for
        # the base wager, Bonus, and Jackpot alike -- deliberately no "freeze
        # at an earlier point" branch anywhere, unlike Ultimate Texas
        # Hold'em's own Jackpot-frozen-at-the-flop quirk, which doesn't
        # apply to this game.
        final_hand = result.player_cards + result.community_cards
        tier = _five_card_tier(evaluate_five_card_hand(final_hand))
        result.five_card_tier = tier
        result.qualified = tier in BASIC_GAME_PAYOUT

        def basic_return(bet):
            mult = BASIC_GAME_PAYOUT.get(tier)
            return bet * (mult + 1) if mult else 0.0

        result.ante_return = basic_return(result.ante_bet)
        if result.bet1_active:
            result.bet1_return = basic_return(result.bet1_bet)
        if result.bet2_active:
            result.bet2_return = basic_return(result.bet2_bet)

        # --- Bonus: independent of the base wager's own outcome, and of
        # bet1/bet2's own pull-back decisions -- always resolves. ---
        if result.bonus_bet > 0:
            mult = BONUS_PAYOUT.get(tier)
            result.bonus_return = result.bonus_bet * (mult + 1) if mult else 0.0

        # --- 3 Card: independent too, judged on the player's own 3 cards
        # alone -- no community cards involved. ---
        if result.three_card_bet > 0:
            three_tier = _three_card_tier(evaluate_three_card_hand(result.player_cards))
            result.three_card_tier = three_tier
            mult = THREE_CARD_BONUS_PAYOUT.get(three_tier)
            result.three_card_return = result.three_card_bet * (mult + 1) if mult else 0.0

        # --- Jackpot: independent too, resolved on the same final tier as
        # the base wager (no early freeze -- see the module docstring). ---
        if result.jackpot_bet > 0:
            payout, hits_full_jackpot, partial_fraction = jackpot_payout(tier, jackpot_amount)
            result.jackpot_return = payout
            result.jackpot_won = hits_full_jackpot
            result.jackpot_pool_partial_fraction = partial_fraction

        result.total_returned = (
            result.ante_return + result.bet1_return + result.bet2_return
            + result.bonus_return + result.three_card_return + result.jackpot_return
        )
        result.net_result = round(result.total_returned - result.total_wagered, 2)
        result.summary = _build_summary(result)
        return result
