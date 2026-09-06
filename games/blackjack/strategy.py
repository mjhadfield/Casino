"""
Basic Strategy lookup for Blackjack -- the standard 8-deck, dealer-stands-
on-soft-17, double-after-split, no-surrender chart (Blackjack
Apprenticeship's own published chart:
https://www.blackjackapprenticeship.com/wp-content/uploads/2018/08/BJA_Basic_Strategy.jpg
-- transcribed directly since it's exactly this game's own house rules,
see games/blackjack/logic.py's own module docstring: S17, DAS, no
surrender, no restriction on which first-two-card totals can double).
Every "Late Surrender" cell on that chart (16 vs 9/10/A, 15 vs 10) is
simply omitted here -- this game has no surrender action at all, and each
of those cells' own Hit/Stand answer (the chart's own fallback, shown
before Surrender overrides it) is exactly what HARD_TOTALS already gives.

Pure data + one lookup function, no tkinter -- lives alongside
games/blackjack/logic.py rather than in core/ since this is blackjack-
specific, not a cross-game utility (contrast core/hand_evaluator.py, which
several games' side bets actually share).
"""
from games.blackjack.logic import hand_value

DEALER_COLUMNS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "A"]

# Action codes -- every row is exactly len(DEALER_COLUMNS) long, in that
# same order: "H" Hit, "S" Stand, "P" Split (PAIRS only), "Dh"/"Ds"
# Double if allowed else Hit/Stand (the chart's own "D"/"Ds" cells).
ACTION_LABELS = {"H": "Hit", "S": "Stand", "P": "Split", "Dh": "Double", "Ds": "Double"}
DISPLAY_CHAR = {"H": "H", "S": "S", "P": "P", "Dh": "D", "Ds": "D"}

# Hard totals 9-16 -- 8 or less is always Hit, 17+ is always Stand, so
# neither needs its own row (see recommend()'s own fallback).
HARD_TOTALS = {
    9:  ["H", "Dh", "Dh", "Dh", "Dh", "H", "H", "H", "H", "H"],
    10: ["Dh", "Dh", "Dh", "Dh", "Dh", "Dh", "Dh", "Dh", "H", "H"],
    11: ["Dh", "Dh", "Dh", "Dh", "Dh", "Dh", "Dh", "Dh", "Dh", "Dh"],
    12: ["H", "H", "S", "S", "S", "H", "H", "H", "H", "H"],
    13: ["S", "S", "S", "S", "S", "H", "H", "H", "H", "H"],
    14: ["S", "S", "S", "S", "S", "H", "H", "H", "H", "H"],
    15: ["S", "S", "S", "S", "S", "H", "H", "H", "H", "H"],
    16: ["S", "S", "S", "S", "S", "H", "H", "H", "H", "H"],
}

# Soft totals 13 (A,2) through 20 (A,9) -- soft 21 is an untouched
# Blackjack, never a live decision point (Hand.__init__ marks it `done`
# immediately), and nothing softer than 13 has its own chart row (always
# Hit -- see recommend()'s own fallback for the near-impossible case of an
# unsplit soft 12 from a stuck A,A).
SOFT_TOTALS = {
    13: ["H", "H", "H", "Dh", "Dh", "H", "H", "H", "H", "H"],
    14: ["H", "H", "H", "Dh", "Dh", "H", "H", "H", "H", "H"],
    15: ["H", "H", "Dh", "Dh", "Dh", "H", "H", "H", "H", "H"],
    16: ["H", "H", "Dh", "Dh", "Dh", "H", "H", "H", "H", "H"],
    17: ["H", "Dh", "Dh", "Dh", "Dh", "H", "H", "H", "H", "H"],
    18: ["Ds", "Ds", "Ds", "Ds", "Ds", "S", "S", "H", "H", "H"],
    19: ["S", "S", "S", "S", "Ds", "S", "S", "S", "S", "S"],
    20: ["S", "S", "S", "S", "S", "S", "S", "S", "S", "S"],
}

# Keyed by the pair's own per-card Blackjack value (2-10, "A" for Aces).
# Every cell here is the FULL correct answer, split or not -- the chart's
# own non-split cells (e.g. 9,9 vs 7 = Stand, not Hit) are transcribed
# as-is, not re-derived from the hard/soft tables above. DAS is always
# offered in this engine (games/blackjack/logic.py's own house rules), so
# the chart's "Y/N" (split only if DAS offered) cells are plain "P" here
# -- there's no non-DAS variant to ever fall back to. 5,5 is `None`: the
# chart never splits it and treats it purely as a hard 10 instead (see
# recommend()), so it has no row of its own here at all.
PAIRS = {
    "A": ["P"] * 10,
    10: ["S"] * 10,   # never split -- stands as a hard 20 instead
    9:  ["P", "P", "P", "P", "P", "S", "P", "P", "S", "S"],
    8:  ["P"] * 10,
    7:  ["P", "P", "P", "P", "P", "P", "H", "H", "H", "H"],
    6:  ["P", "P", "P", "P", "P", "H", "H", "H", "H", "H"],
    5:  None,
    4:  ["H", "H", "H", "P", "P", "H", "H", "H", "H", "H"],
    3:  ["P", "P", "P", "P", "P", "P", "H", "H", "H", "H"],
    2:  ["P", "P", "P", "P", "P", "P", "H", "H", "H", "H"],
}


def _card_value(card):
    """Mirrors games/blackjack/logic.py's own _card_bj_value exactly (Ace
    =11, face cards=10) -- duplicated rather than imported, since that
    name is module-private there; a stable, 3-line mapping with no real
    risk of drifting out of sync."""
    if card.rank == "A":
        return 11
    if card.rank in ("J", "Q", "K"):
        return 10
    return int(card.rank)


def _resolve(code, can_double):
    """Downgrades a "Dh"/"Ds" code to its own plain fallback if `can_double`
    is False for this specific hand (e.g. it's already been hit past its
    first two cards) -- every other code is already unconditionally legal
    whenever recommend() would return it (see its own can_split gating)."""
    if code == "Dh" and not can_double:
        return "H"
    if code == "Ds" and not can_double:
        return "S"
    return code


def recommend(cards, dealer_up_card, can_double, can_split):
    """The one entry point: returns (label, row, dealer_col, effective) for
    `cards` (the active Hand's own .cards) against `dealer_up_card`
    (BlackjackGame.dealer_cards[0]).

    `can_double`/`can_split` are this exact hand's own CURRENT legality
    (Hand.can_double / Box.can_split(split_count())) -- used only to
    resolve the ONE highlighted cell's effective action; the other 9
    columns always show the chart's own raw code unchanged, since they're
    hypothetical context ("what if the dealer showed a different card"),
    not a live legality check for a card that isn't actually showing.

    `label` is a display string ("Hard 16"/"Soft 18"/"9,9"); `row` is the
    full 10-code list (index-aligned with DEALER_COLUMNS) for the context
    row; `dealer_col` is which index to highlight; `effective` is that
    cell's own code after `_resolve` -- what the player should actually do
    right now, for the buttons that actually exist on screen.
    """
    dealer_col = _card_value(dealer_up_card) - 2
    total, is_soft = hand_value(cards)

    if len(cards) == 2 and _card_value(cards[0]) == _card_value(cards[1]) and can_split:
        pair_value = cards[0].rank if cards[0].rank == "A" else _card_value(cards[0])
        row = PAIRS.get(pair_value)
        if row is not None:
            label = f"{cards[0].rank},{cards[0].rank}"
            return label, row, dealer_col, _resolve(row[dealer_col], can_double)

    if is_soft:
        row = SOFT_TOTALS.get(total, ["H"] * 10 if total < 13 else ["S"] * 10)
        label = f"Soft {total}"
    else:
        row = HARD_TOTALS.get(total, ["H"] * 10 if total <= 8 else ["S"] * 10)
        label = f"Hard {total}"
    return label, row, dealer_col, _resolve(row[dealer_col], can_double)
