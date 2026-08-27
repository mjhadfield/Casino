"""
High Card Flush game engine.

Not a poker game at all -- there are no hand *categories* (pair, straight,
full house, ...). A hand's rank is purely "how many cards of one suit do you
hold": find whichever suit has the most cards in your 7-card hand -- that's
your "flush" -- and compare two hands first by that count (longer always
wins outright, regardless of rank), then, if counts tie, by the flush
cards' ranks descending until a difference is found. Identical count and
ranks all the way down is a push. A "straight flush" (consecutive ranks
within the suit) has no bearing on this comparison at all -- it only
matters for the separate Straight Flush bonus bet below.

Round shape: an Ante bet (plus optional Flush/Straight Flush/Jackpot side
bets, all independent of the Ante/Raise outcome and of folding). Player and
dealer are each dealt 7 cards face down. The player examines their own 7
cards and either Folds (forfeiting the Ante) or Raises -- normally exactly
1x the Ante, but a player whose own true flush is 5+ cards may optionally
raise up to 2x (5-flush) or 3x (6- or 7-flush).

Payout rules implemented:
  Main game (Ante, Raise): the dealer needs a flush of 3+ cards topped by a
  9 or better to qualify (any 4+ card flush always qualifies too, since
  count alone already beats a bare 3-card threshold).
    - Dealer doesn't qualify: Ante pays 1:1, Raise pushes.
    - Dealer qualifies: win pays both 1:1, loss loses both, tie pushes both.
  Flush bonus (independent of Ante/Raise/fold, judged on the player's own
  true best flush): 7-card 250:1, 6-card 100:1, 5-card 10:1, 4-card 1:1.
  Straight Flush bonus (independent too, judged on the player's own longest
  consecutive-rank same-suit run, Ace high or low): 7-card 500:1, 6-card
  200:1, 5-card 100:1, 4-card 60:1, 3-card 8:1.
  Jackpot side bet (flat £1, shared JackpotManager pool like every other
  game's own Jackpot side bet, independent of fold): judged on the
  player's own STRAIGHT flush length -- not the plain flush every other
  bet here uses -- so it only ever pays on a genuine straight flush:
  7-card 100% of the jackpot meter (resets it), 6-card 50% of the meter
  (a partial drawdown, doesn't reset it), 5-card £250, 4-card £50,
  3-card £5.
"""
from collections import defaultdict
from typing import List, Optional, Tuple

from core.cards import Card, Deck, Suit

GAME_KEY = "high_card_flush"
GAME_LABEL = "High Card Flush"
BET_TYPES = [
    ("ante", "Ante"),
    ("raise", "Raise"),
    ("flush", "Flush"),
    ("straight_flush", "Straight Flush"),
    ("jackpot", "Jackpot"),
]

# Stats screen's "Hands Made" breakdown -- purely the player's own flush
# length (2 is the theoretical floor -- 7 cards across 4 suits always
# leaves some suit with 2+ by pigeonhole -- lumped into "No Flush" since
# it's below even the dealer's own minimum qualifying threshold).
HAND_OUTCOME_LABELS = [
    "Fold", "No Flush", "3-Card Flush", "4-Card Flush",
    "5-Card Flush", "6-Card Flush", "7-Card Flush",
]

# --- Flush bonus -- X:1, judged on the player's own true best flush.
FLUSH_BONUS_PAYTABLE = {7: 250, 6: 100, 5: 10, 4: 1}

# --- Straight Flush bonus -- X:1, judged on the player's own longest
# consecutive-rank same-suit run (Ace high or low).
STRAIGHT_FLUSH_BONUS_PAYTABLE = {7: 500, 6: 200, 5: 100, 4: 60, 3: 8}

# --- Jackpot -- flat £1, shared progressive pool.
JACKPOT_BET_AMOUNT = 1.0
JACKPOT_FULL_METER_COUNT = 7   # pays 100% of the meter, resets it
JACKPOT_HALF_METER_COUNT = 6   # pays 50% of the meter, partial drawdown
JACKPOT_FLAT_PAYOUTS = {5: 250.0, 4: 50.0, 3: 5.0}

# --- Dealer qualification: a flush of 3+ cards topped by a 9 or better --
# any 4+ card flush already exceeds this regardless of rank, since count
# alone always wins outright in this game's own comparison.
DEALER_QUALIFY_MIN_COUNT = 3
DEALER_QUALIFY_MIN_TOP_VALUE = 9


def _best_flush(cards: List[Card]) -> Tuple[int, Tuple[int, ...], List[Card]]:
    """(count, descending_value_tuple, cards) for the best same-suit group
    in `cards`. Tuple comparison on (count, values) does exactly this
    game's own tie-break chain (longer wins outright; else highest card,
    then next, ...) with no extra code."""
    by_suit = defaultdict(list)
    for c in cards:
        by_suit[c.suit].append(c)
    best_key: Tuple[int, Tuple[int, ...]] = (-1, ())
    best_cards: List[Card] = []
    for suited in by_suit.values():
        ordered = sorted(suited, key=lambda c: c.value, reverse=True)
        key = (len(ordered), tuple(c.value for c in ordered))
        if key > best_key:
            best_key, best_cards = key, ordered
    return best_key[0], best_key[1], best_cards


def _best_straight_flush(cards: List[Card]) -> Tuple[int, List[Card]]:
    """Longest run of consecutive same-suit ranks (Ace may shadow as a low
    1 to catch a wheel, A-2-3-4-5). Only LENGTH matters for the Straight
    Flush bonus paytable -- no rank tie-break needed here at all, unlike
    _best_flush's own Ante/Raise comparison."""
    best_len = 0
    best_cards: List[Card] = []
    for suit in Suit:
        by_value = {c.value: c for c in cards if c.suit == suit}
        if not by_value:
            continue
        candidates = set(by_value)
        if 14 in candidates:
            candidates.add(1)  # ace-low shadow
        vals = sorted(candidates)
        run = [vals[0]]
        runs = [run]
        for v in vals[1:]:
            if v == run[-1] + 1:
                run.append(v)
            else:
                run = [v]
                runs.append(run)
        for run in runs:
            if len(run) > best_len:
                best_len = len(run)
                best_cards = [by_value[14] if v == 1 else by_value[v] for v in run]
    return best_len, best_cards


def dealer_qualifies(count: int, top_value: int) -> bool:
    if count > DEALER_QUALIFY_MIN_COUNT:
        return True   # any 4+ card flush always exceeds the bare 3-card threshold
    return count == DEALER_QUALIFY_MIN_COUNT and top_value >= DEALER_QUALIFY_MIN_TOP_VALUE


def max_raise_multiplier(flush_count: int) -> int:
    """The highest Raise multiplier a player with a flush this long is
    allowed to choose -- shared by the engine's own validation and the
    UI's Stage 2 button set, so the two can never drift apart."""
    if flush_count >= 6:
        return 3
    if flush_count == 5:
        return 2
    return 1


def jackpot_payout(count: int, jackpot_amount: float):
    """Returns (payout, hits_full_jackpot, partial_fraction) for the £1
    Jackpot side bet, given the player's own true flush length."""
    if count >= JACKPOT_FULL_METER_COUNT:
        return jackpot_amount, True, 0.0
    if count == JACKPOT_HALF_METER_COUNT:
        return jackpot_amount * 0.5, False, 0.5
    if count in JACKPOT_FLAT_PAYOUTS:
        return JACKPOT_FLAT_PAYOUTS[count], False, 0.0
    return 0.0, False, 0.0


def hand_outcome_label(result: "RoundResult") -> str:
    if result.folded:
        return "Fold"
    count = result.player_flush_count
    if count <= 2:
        return "No Flush"
    return f"{count}-Card Flush"


def auto_place(cards: List[Card]) -> List[Card]:
    """The cards behind the player's own true best flush -- the exact same
    group `settle()` itself pays out on, so Auto Place is always "correct"
    by construction. A pure function, decoupled from any engine/round
    state, callable directly by the UI's Auto Place button."""
    return _best_flush(cards)[2]


class RoundResult:
    """Plain data holder describing the outcome of one round."""

    def __init__(self):
        self.player_cards: List[Card] = []   # 7 cards
        self.dealer_cards: List[Card] = []   # 7 cards

        # The player's own flush/straight-flush are known the moment the
        # cards are dealt -- computed immediately in deal(), not settle(),
        # since the UI's Stage 2 Raise buttons need this before settle()
        # is ever called.
        self.player_flush_count = 0
        self.player_flush_values: Tuple[int, ...] = ()
        self.player_flush_cards: List[Card] = []
        self.player_straight_flush_count = 0
        self.player_straight_flush_cards: List[Card] = []

        # The dealer's own hand stays "hidden" (unset) until settle(),
        # same as every other game's own dealer hand.
        self.dealer_flush_count = 0
        self.dealer_flush_values: Tuple[int, ...] = ()
        self.dealer_flush_cards: List[Card] = []
        self.dealer_qualified = False

        self.folded = False
        self.raise_multiplier = 0     # 0 until Raised
        self.outcome = ""             # "fold" | "dealer_no_qualify" | "win" | "lose" | "push"

        self.ante_bet = 0.0
        self.ante_return = 0.0
        self.raise_bet = 0.0
        self.raise_return = 0.0
        self.flush_bet = 0.0
        self.flush_return = 0.0
        self.straight_flush_bet = 0.0
        self.straight_flush_return = 0.0
        self.jackpot_bet = 0.0
        self.jackpot_return = 0.0
        self.jackpot_won = False
        self.jackpot_pool_partial_fraction = 0.0

        self.total_wagered = 0.0
        self.total_returned = 0.0
        self.net_result = 0.0

        self.summary = ""


class HighCardFlushGame:
    """Engine for a single High Card Flush table. Create one instance per table."""

    def __init__(self):
        self.deck = Deck()
        self.result: Optional[RoundResult] = None

    def deal(self, ante_bet, flush_bet=0.0, straight_flush_bet=0.0, jackpot_bet=0.0) -> RoundResult:
        """Deals a new round: 7 cards to the player, 7 to the dealer, all
        face down. `ante_bet` must be > 0; `jackpot_bet` must be 0 or
        exactly JACKPOT_BET_AMOUNT."""
        if ante_bet <= 0:
            raise ValueError("An Ante bet is required to play a round.")
        if jackpot_bet not in (0, JACKPOT_BET_AMOUNT):
            raise ValueError(f"The jackpot side bet must be exactly £{JACKPOT_BET_AMOUNT:.0f} if played.")

        self.deck.reset()
        result = RoundResult()
        result.ante_bet = ante_bet
        result.flush_bet = flush_bet
        result.straight_flush_bet = straight_flush_bet
        result.jackpot_bet = jackpot_bet
        result.player_cards = self.deck.deal(7)
        result.dealer_cards = self.deck.deal(7)

        count, values, cards = _best_flush(result.player_cards)
        result.player_flush_count = count
        result.player_flush_values = values
        result.player_flush_cards = cards
        sf_count, sf_cards = _best_straight_flush(result.player_cards)
        result.player_straight_flush_count = sf_count
        result.player_straight_flush_cards = sf_cards

        self.result = result
        return result

    def fold(self) -> RoundResult:
        """Folds the round -- forfeits the Ante outright; the Raise was
        never placed. Flush/Straight Flush/Jackpot are unaffected -- they
        never key off `folded` at all (see settle())."""
        assert self.result is not None, "fold() called before deal()"
        self.result.folded = True
        return self.result

    def raise_bet(self, multiplier: int) -> RoundResult:
        """Places `multiplier` (1, 2, or 3) times the Ante into the Raise
        bet -- 2/3 are only legal once the player's own true flush is long
        enough (see max_raise_multiplier)."""
        assert self.result is not None, "raise_bet() called before deal()"
        result = self.result
        allowed = max_raise_multiplier(result.player_flush_count)
        if multiplier not in (1, 2, 3) or multiplier > allowed:
            raise ValueError(
                f"Raise multiplier {multiplier} isn't allowed with a {result.player_flush_count}-card "
                f"flush (max allowed is {allowed})."
            )
        result.raise_multiplier = multiplier
        result.raise_bet = result.ante_bet * multiplier
        return result

    def settle(self, jackpot_amount: float = 0.0) -> RoundResult:
        """Settles the round. `jackpot_amount` is the current jackpot
        value, needed only if the Jackpot side bet was placed -- pass
        JackpotManager.amount."""
        assert self.result is not None, "settle() called before deal()"
        result = self.result

        d_count, d_values, d_cards = _best_flush(result.dealer_cards)
        result.dealer_flush_count = d_count
        result.dealer_flush_values = d_values
        result.dealer_flush_cards = d_cards
        result.dealer_qualified = dealer_qualifies(d_count, d_values[0] if d_values else 0)

        if result.folded:
            result.outcome = "fold"
            # ante_return/raise_return stay 0 -- the Ante is forfeited and
            # the Raise was never placed.
        else:
            player_key = (result.player_flush_count, result.player_flush_values)
            dealer_key = (d_count, d_values)

            if not result.dealer_qualified:
                result.outcome = "dealer_no_qualify"
                result.ante_return = result.ante_bet * 2
                result.raise_return = result.raise_bet
            elif player_key > dealer_key:
                result.outcome = "win"
                result.ante_return = result.ante_bet * 2
                result.raise_return = result.raise_bet * 2
            elif player_key < dealer_key:
                result.outcome = "lose"
            else:
                result.outcome = "push"
                result.ante_return = result.ante_bet
                result.raise_return = result.raise_bet

        # --- Flush/Straight Flush/Jackpot: independent of Ante/Raise and
        # of folding entirely -- always resolved on the player's own true
        # hand, computed back in deal(). ---
        if result.flush_bet > 0:
            mult = FLUSH_BONUS_PAYTABLE.get(result.player_flush_count, 0)
            result.flush_return = result.flush_bet * (mult + 1) if mult else 0.0

        if result.straight_flush_bet > 0:
            mult = STRAIGHT_FLUSH_BONUS_PAYTABLE.get(result.player_straight_flush_count, 0)
            result.straight_flush_return = result.straight_flush_bet * (mult + 1) if mult else 0.0

        if result.jackpot_bet > 0:
            # Judged on the player's own STRAIGHT flush length -- not the
            # plain flush length every other bet here uses -- so the
            # jackpot only ever pays on a genuine straight flush.
            payout, hits_full_jackpot, partial_fraction = jackpot_payout(
                result.player_straight_flush_count, jackpot_amount
            )
            result.jackpot_return = payout
            result.jackpot_won = hits_full_jackpot
            result.jackpot_pool_partial_fraction = partial_fraction

        result.total_wagered = (
            result.ante_bet + result.raise_bet + result.flush_bet
            + result.straight_flush_bet + result.jackpot_bet
        )
        result.total_returned = (
            result.ante_return + result.raise_return + result.flush_return
            + result.straight_flush_return + result.jackpot_return
        )
        result.net_result = round(result.total_returned - result.total_wagered, 2)
        result.summary = _build_summary(result)
        return result


def _build_summary(result: RoundResult) -> str:
    if result.folded:
        return "You folded -- the Ante is forfeited."
    if not result.dealer_qualified:
        return "Dealer doesn't qualify (below a 3-card, 9-high flush) -- the Ante pays, Raise pushes."
    if result.outcome == "win":
        return f"You win! Ante and Raise pay 1:1 ({result.player_flush_count}-card flush)."
    if result.outcome == "push":
        return "Push -- Ante and Raise both push."
    return f"Dealer's hand wins ({result.dealer_flush_count}-card flush). Ante and Raise are lost."
