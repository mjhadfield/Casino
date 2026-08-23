"""
Hand evaluation utilities.

Currently implements 3-card poker hand ranking. Kept in its own module,
separate from game flow/UI, so a future game that needs a different
evaluator (e.g. standard 5-card poker) can be added alongside this one
without touching Three Card Poker's logic.

3-card poker hand ranking (highest to lowest) -- note Flush outranks
Straight here, the opposite of 5-card poker, because there are fewer
possible 3-card flushes than 3-card straights:
    Straight Flush > Three of a Kind > Straight > Flush > Pair > High Card
"""
from collections import Counter
from typing import Tuple

# (rank_value, rank_name, tiebreaker_tuple) -- see evaluate_three_card_hand.
HandEval = Tuple[int, str, Tuple[int, ...]]

STRAIGHT_FLUSH = 6
THREE_OF_A_KIND = 5
STRAIGHT = 4
FLUSH = 3
PAIR = 2
HIGH_CARD = 1

HAND_NAMES = {
    STRAIGHT_FLUSH: "Straight Flush",
    THREE_OF_A_KIND: "Three of a Kind",
    STRAIGHT: "Straight",
    FLUSH: "Flush",
    PAIR: "Pair",
    HIGH_CARD: "High Card",
}

DEALER_QUALIFY_MIN_VALUE = 12  # Queen high or better qualifies the dealer


def _check_straight(values):
    """values: list of the 3 card numeric values. Returns (is_straight, high_card)."""
    unique_values = sorted(set(values))
    if len(unique_values) != 3:
        return False, None
    if unique_values[2] - unique_values[1] == 1 and unique_values[1] - unique_values[0] == 1:
        return True, unique_values[2]
    # Ace-low straight: A-2-3 (Ace plays low here; the "high" card is the 3)
    if set(unique_values) == {14, 3, 2}:
        return True, 3
    return False, None


def evaluate_three_card_hand(cards) -> HandEval:
    """Returns (rank_value, rank_name, tiebreaker_tuple) for a 3-card hand.
    A hand with a higher rank_value wins; ties are broken by comparing
    tiebreaker_tuple element-by-element (higher wins)."""
    if len(cards) != 3:
        raise ValueError("Three card poker hands must contain exactly 3 cards.")

    values = sorted((c.value for c in cards), reverse=True)
    is_flush = len({c.suit for c in cards}) == 1
    is_straight, straight_high = _check_straight(values)
    counts = Counter(values)
    count_sizes = sorted(counts.values(), reverse=True)

    if is_straight and is_flush:
        return (STRAIGHT_FLUSH, HAND_NAMES[STRAIGHT_FLUSH], (straight_high,))
    if count_sizes[0] == 3:
        return (THREE_OF_A_KIND, HAND_NAMES[THREE_OF_A_KIND], (values[0],))
    if is_straight:
        return (STRAIGHT, HAND_NAMES[STRAIGHT], (straight_high,))
    if is_flush:
        return (FLUSH, HAND_NAMES[FLUSH], tuple(values))
    if count_sizes[0] == 2:
        pair_value = next(v for v, c in counts.items() if c == 2)
        kicker = next(v for v, c in counts.items() if c == 1)
        return (PAIR, HAND_NAMES[PAIR], (pair_value, kicker))
    return (HIGH_CARD, HAND_NAMES[HIGH_CARD], tuple(values))


def compare_hands(hand_eval_a: HandEval, hand_eval_b: HandEval) -> int:
    """Returns 1 if a beats b, -1 if b beats a, 0 for a tie."""
    rank_a, _, tie_a = hand_eval_a
    rank_b, _, tie_b = hand_eval_b
    if rank_a != rank_b:
        return 1 if rank_a > rank_b else -1
    if tie_a != tie_b:
        return 1 if tie_a > tie_b else -1
    return 0


def dealer_qualifies(dealer_eval: HandEval) -> bool:
    """Dealer qualifies with Queen-high or better."""
    rank_value, _, tiebreak = dealer_eval
    if rank_value > HIGH_CARD:
        return True  # a pair or anything stronger always qualifies
    return tiebreak[0] >= DEALER_QUALIFY_MIN_VALUE
