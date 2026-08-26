"""
Fortune Pai Gow Poker game engine.

Built from the CA DOJ "Casino Real Fortune Pai Gow Poker" rules (a standard
52-card deck plus one Joker, 53 total). Two deliberate divergences from that
source, per this project's own house rules:
  - Collection fee: a flat 5% commission on the Ante, deducted from a WIN
    only (the standard "vig" convention every commercial Pai Gow
    implementation uses) -- not the source document's stepped flat-fee
    schedule, which is collected upfront regardless of outcome.
  - Banking: the player can never act as banker/player-dealer -- there's
    only one seat, so the house computer dealer always banks, always plays,
    and always sets its own hand by House Way. The Envy Bonus (a payout to
    *other* seated players) and the Action-button/dice-cup/seat-rotation
    table-management procedure are both cut entirely for the same reason --
    they only mean anything with other players at the table.

Rules implemented:
  Deal: player and dealer each get 7 cards from a fresh 53-card deck. The
  Joker is semi-wild, not a pure wildcard -- it may only complete a
  Straight, Flush, or Straight Flush, or otherwise stand in as a bare Ace
  (see best_five_card_eval_with_joker / _joker_candidates). It can never
  impersonate an arbitrary card just to fake an unrelated pair, trips,
  quads, or full house.

  Setting: the player arranges their 7 cards into a 2-card "front" hand and
  a 5-card "back" hand; the back must rank strictly higher than the front
  (a "foul" -- set_player_hand refuses an invalid split; the UI never offers
  Confirm for one in the first place). The dealer's hand is always set by
  the Casino Real House Way chart (see house_way_set), which also backs the
  player's own optional House Way button.

  Settling: front vs. front, back vs. back. Win both -> Ante pays 1:1 (less
  the 5% win commission). Lose both -> lose the Ante. Split (one hand each)
  -> push, stake returned. A tied hand ("copy") is won by the dealer.

  Fortune side bet (own stake, no cap) and Jackpot side bet (flat £1, shares
  the app-wide progressive pool) both resolve immediately off the player's
  own raw 7 cards, independent of the Ante's own outcome -- see
  classify_seven_card_bonus and the FORTUNE_MULTIPLIERS/JACKPOT_TIERS tables.
"""
from itertools import combinations
from typing import List, Optional, Tuple

from core.cards import Card, Deck, RANK_ORDER, Suit
from core.hand_evaluator import (
    HandEval,
    compare_hands,
    evaluate_five_card_hand,
    FIVE_CARD_STRAIGHT_FLUSH,
    FOUR_OF_A_KIND,
    FULL_HOUSE,
    FIVE_CARD_FLUSH,
    FIVE_CARD_STRAIGHT,
    FIVE_CARD_THREE_OF_A_KIND,
)

# Identifies this game to GameStatsManager (core/game_stats.py) and the
# Stats screen (ui/stats_screen.py), same convention as the other two games.
GAME_KEY = "pai_gow_poker"
GAME_LABEL = "Pai Gow Poker"
BET_TYPES = [
    ("ante", "Ante"),
    ("fortune", "Fortune"),
    ("jackpot", "Jackpot"),
]
# No fold concept (same as Blackjack) -- every round settles to one of these.
HAND_OUTCOME_LABELS = ["Lose", "Push", "Win"]

ANTE_COMMISSION_RATE = 0.05  # 5%, deducted from a WIN only -- see module docstring

JACKPOT_BET_AMOUNT = 1.0

# --- 2-card ("front") hand ranks --------------------------------------------
TWO_CARD_HIGH_CARD = 0
TWO_CARD_PAIR = 1


def evaluate_two_card_hand(two_cards) -> HandEval:
    """The front hand: a pair beats any non-pair, else the higher single
    card wins (the other card as the final tiebreak). A Joker among the two
    always plays as an Ace -- with only 2 cards there's no straight/flush
    for it to complete, so that's its only possible role here."""
    if len(two_cards) != 2:
        raise ValueError("A Pai Gow Poker front hand must contain exactly 2 cards.")
    values = sorted((14 if c.is_joker else c.value for c in two_cards), reverse=True)
    if values[0] == values[1]:
        return (TWO_CARD_PAIR, "Pair", tuple(values))
    return (TWO_CARD_HIGH_CARD, "High Card", tuple(values))


# --- Joker-aware 5-card evaluation ------------------------------------------
# The Joker is NOT a pure wildcard -- it can only (a) complete a Straight,
# Flush, or Straight Flush from the other 4 cards, or (b) otherwise stand in
# as a bare Ace. It can never impersonate an arbitrary card just to make an
# unrelated pair/trips/quads/full house (e.g. two Kings + Joker is NOT
# "three Kings" -- it's just a pair of Kings with an Ace kicker).
_RANK_FOR_VALUE = {i + 2: rank for i, rank in enumerate(RANK_ORDER)}


def _missing_straight_ranks(values) -> List[int]:
    """Every rank (2-14) that, added to these 4 distinct real values, would
    complete a 5-card straight (Ace playing high or low). Empty if the 4
    values already repeat a rank (no 5-distinct-rank straight is possible
    with one more real card) or don't sit within reach of any run."""
    unique = sorted(set(values))
    if len(unique) != 4:
        return []
    found = []
    for candidate in range(2, 15):
        if candidate in unique:
            continue
        combined = sorted(unique + [candidate])
        if combined[-1] - combined[0] == 4:
            found.append(candidate)
            continue
        alt = sorted(1 if v == 14 else v for v in combined)  # Ace-low wheel
        if len(set(alt)) == 5 and alt[-1] - alt[0] == 4:
            found.append(candidate)
    return found


def _joker_candidates(other_cards) -> List[Card]:
    """The Joker's only legal substitutes among these other 4 real cards:
    whichever rank(s) complete a Straight (tried in every suit -- suit
    doesn't matter for a plain straight, and the one suit that also matches
    a flush naturally yields a Straight Flush "for free"), the best
    Flush-completing card (the matching suit's highest missing rank -- a
    higher rank can never rank worse within a flush, so trying only the
    best is sufficient), and -- always available as the fallback -- a bare
    Ace."""
    candidates = []
    for rank_value in _missing_straight_ranks([c.value for c in other_cards]):
        rank_str = _RANK_FOR_VALUE[rank_value]
        for suit in Suit:
            candidates.append(Card(rank_str, suit))

    suits = {c.suit for c in other_cards}
    if len(suits) == 1:
        flush_suit = next(iter(suits))
        used_ranks = {c.rank for c in other_cards}
        for rank in reversed(RANK_ORDER):
            if rank not in used_ranks:
                candidates.append(Card(rank, flush_suit))
                break

    ace_suit = next((s for s in Suit if s not in suits), Suit.SPADES)
    candidates.append(Card("A", ace_suit))
    return candidates


def best_five_card_eval_with_joker(cards) -> HandEval:
    """The best evaluate_five_card_hand result achievable from exactly 5
    cards, substituting a Joker (if present) for whichever *legal* stand-in
    produces the strongest hand -- see _joker_candidates. A no-op (just
    evaluate_five_card_hand directly) when there's no Joker among the 5."""
    if len(cards) != 5:
        raise ValueError("Five card poker hands must contain exactly 5 cards.")
    joker_idx = next((i for i, c in enumerate(cards) if c.is_joker), None)
    if joker_idx is None:
        return evaluate_five_card_hand(cards)
    other_cards = [c for i, c in enumerate(cards) if i != joker_idx]
    best_eval = None
    for sub in _joker_candidates(other_cards):
        trial = list(cards)
        trial[joker_idx] = sub
        ev = evaluate_five_card_hand(trial)
        if best_eval is None or compare_hands(ev, best_eval) > 0:
            best_eval = ev
    assert best_eval is not None  # _joker_candidates always yields the bare-Ace fallback
    return best_eval


def best_five_of_seven(seven_cards) -> Tuple[HandEval, List[Card]]:
    """The best possible 5-card poker hand achievable from 7 cards (Joker
    handled per-combination via best_five_card_eval_with_joker). Returns
    (hand_eval, the actual 5 original cards -- Joker included if it's one
    of them -- that achieve it)."""
    best_eval = None
    best_cards = None
    for combo in combinations(seven_cards, 5):
        combo = list(combo)
        ev = best_five_card_eval_with_joker(combo)
        if best_eval is None or compare_hands(ev, best_eval) > 0:
            best_eval = ev
            best_cards = combo
    assert best_eval is not None and best_cards is not None  # 7 cards always yield C(7,5)=21 combos
    return best_eval, best_cards


# --- Seven-card bonus classification (Fortune + Jackpot side bets) ---------
SEVEN_CARD_STRAIGHT_FLUSH = "seven_card_straight_flush"
ROYAL_FLUSH_ROYAL_MATCH = "royal_flush_royal_match"
SEVEN_CARD_STRAIGHT_FLUSH_JOKER = "seven_card_straight_flush_joker"
FIVE_ACES = "five_aces"
ROYAL_FLUSH = "royal_flush"
STRAIGHT_FLUSH_TIER = "straight_flush"
FOUR_OF_A_KIND_TIER = "four_of_a_kind"
FULL_HOUSE_TIER = "full_house"
FLUSH_TIER = "flush"
THREE_OF_A_KIND_TIER = "three_of_a_kind"
STRAIGHT_TIER = "straight"

# PDF's own FPG-05 paytable -- "X to 1".
FORTUNE_MULTIPLIERS = {
    SEVEN_CARD_STRAIGHT_FLUSH: 5000,
    ROYAL_FLUSH_ROYAL_MATCH: 2000,
    SEVEN_CARD_STRAIGHT_FLUSH_JOKER: 1000,
    FIVE_ACES: 400,
    ROYAL_FLUSH: 150,
    STRAIGHT_FLUSH_TIER: 50,
    FOUR_OF_A_KIND_TIER: 25,
    FULL_HOUSE_TIER: 5,
    FLUSH_TIER: 4,
    THREE_OF_A_KIND_TIER: 3,
    STRAIGHT_TIER: 2,
}

# (fixed £ payout, pool_fraction) -- exactly one of the two is set.
# pool_fraction 1.0 pays the jackpot in full and resets it to floor
# (jackpot.win()); a smaller fraction pays that share of the *current*
# amount and leaves the rest still growing (jackpot.set_amount(amount *
# (1 - fraction))) -- see games/pai_gow_poker/ui.py's _on_round_settled,
# which is the only place that actually touches the JackpotManager (this
# module stays finance/jackpot-manager-decoupled, same as the other games).
JACKPOT_TIERS = {
    SEVEN_CARD_STRAIGHT_FLUSH: (None, 1.0),
    ROYAL_FLUSH_ROYAL_MATCH: (None, 0.5),
    SEVEN_CARD_STRAIGHT_FLUSH_JOKER: (None, 0.25),
    FIVE_ACES: (2500, None),
    ROYAL_FLUSH: (200, None),
    STRAIGHT_FLUSH_TIER: (100, None),
    FOUR_OF_A_KIND_TIER: (75, None),
    FULL_HOUSE_TIER: (6, None),
}


def _seven_card_straight_flush_no_joker(seven_cards) -> bool:
    if any(c.is_joker for c in seven_cards):
        return False
    if len({c.suit for c in seven_cards}) != 1:
        return False
    values = sorted(c.value for c in seven_cards)
    if len(set(values)) != 7:
        return False
    if values[-1] - values[0] == 6:
        return True
    # Low-end wrap: 7,6,5,4,3,2 and Ace (the Ace plays low) -- the doc's own
    # lowest-ranked example.
    alt = sorted(1 if v == 14 else v for v in values)
    return alt[-1] - alt[0] == 6


def _seven_card_straight_flush_with_joker(seven_cards) -> bool:
    """The other 6 (all one suit) plus the Joker span a 7-card run -- either
    they already span 6 with one internal gap the Joker fills, or they're
    already 6 bare-consecutive (span 5) and the Joker extends either end."""
    joker = next((c for c in seven_cards if c.is_joker), None)
    if joker is None:
        return False
    others = [c for c in seven_cards if not c.is_joker]
    if len({c.suit for c in others}) != 1:
        return False

    def fits(values):
        values = sorted(set(values))
        if len(values) != 6:
            return False
        span = values[-1] - values[0]
        return span in (5, 6)

    values = [c.value for c in others]
    if fits(values):
        return True
    alt = [1 if v == 14 else v for v in values]
    return fits(alt)


def _royal_flush_royal_match(seven_cards) -> bool:
    """A Royal Flush (5 cards) plus the other 2 being King-Queen suited (to
    each other -- necessarily a different suit than the Royal Flush's own,
    since a single 52-card deck can't hold two Kings of the same suit)."""
    if any(c.is_joker for c in seven_cards):
        return False
    for combo in combinations(seven_cards, 5):
        values = {c.value for c in combo}
        suits = {c.suit for c in combo}
        if values == {14, 13, 12, 11, 10} and len(suits) == 1:
            other = [c for c in seven_cards if c not in combo]
            if {c.value for c in other} == {13, 12} and other[0].suit == other[1].suit:
                return True
    return False


def _five_aces(seven_cards) -> bool:
    joker = next((c for c in seven_cards if c.is_joker), None)
    if joker is None:
        return False
    aces = [c for c in seven_cards if not c.is_joker and c.rank == "A"]
    return len(aces) == 4


def classify_seven_card_bonus(seven_cards) -> Optional[str]:
    """The best bonus tier the player's raw 7 dealt cards achieve --
    independent of how they're later set into front/back -- feeding both
    the Fortune and Jackpot paytables above. None if nothing qualifies
    (below a Straight)."""
    if len(seven_cards) != 7:
        raise ValueError("Pai Gow Poker deals exactly 7 cards to a hand.")
    if _seven_card_straight_flush_no_joker(seven_cards):
        return SEVEN_CARD_STRAIGHT_FLUSH
    if _royal_flush_royal_match(seven_cards):
        return ROYAL_FLUSH_ROYAL_MATCH
    if _seven_card_straight_flush_with_joker(seven_cards):
        return SEVEN_CARD_STRAIGHT_FLUSH_JOKER
    if _five_aces(seven_cards):
        return FIVE_ACES
    best_eval, _ = best_five_of_seven(seven_cards)
    rank = best_eval[0]
    if rank == FIVE_CARD_STRAIGHT_FLUSH:
        return ROYAL_FLUSH if best_eval[2][0] == 14 else STRAIGHT_FLUSH_TIER
    if rank == FOUR_OF_A_KIND:
        return FOUR_OF_A_KIND_TIER
    if rank == FULL_HOUSE:
        return FULL_HOUSE_TIER
    if rank == FIVE_CARD_FLUSH:
        return FLUSH_TIER
    if rank == FIVE_CARD_STRAIGHT:
        return STRAIGHT_TIER
    if rank == FIVE_CARD_THREE_OF_A_KIND:
        return THREE_OF_A_KIND_TIER
    return None


# --- House Way ---------------------------------------------------------------
# Implements the exact "Casino Real Fortune Pai Gow Poker House Way" chart --
# used unconditionally for the dealer's own hand, and by the player's
# optional House Way button. Real (non-Joker) rank-count structure drives
# which branch of the chart applies; the Joker's own role is resolved
# explicitly per branch -- exactly where the chart itself calls it out
# (Two Pairs' "an Ace or Joker", Five Aces) or via the Joker-aware
# straight/flush search (best_five_card_eval_with_joker) for the
# "Straight, Flush or Straight Flush" variants of the No Pair/One Pair/
# Three of a Kind rows.

def _rank_value(card) -> int:
    return 14 if card.is_joker else card.value


def _sorted_desc(cards) -> List[Card]:
    return sorted(cards, key=_rank_value, reverse=True)


def _remove(cards, to_remove) -> List[Card]:
    remaining = list(cards)
    for c in to_remove:
        remaining.remove(c)
    return remaining


def _real_groups(seven_cards):
    """Real (non-Joker) same-rank groups of size >= 2 (pairs/trips/quads),
    sorted (size, rank) descending -- the Joker is never silently folded
    into a group here; each House Way branch below decides its own role for
    it explicitly, matching how the chart itself only names it in specific
    spots rather than treating it as a wild for general pair-detection."""
    by_rank = {}
    for c in seven_cards:
        if not c.is_joker:
            by_rank.setdefault(c.value, []).append(c)
    groups = [g for g in by_rank.values() if len(g) >= 2]
    groups.sort(key=lambda g: (len(g), g[0].value), reverse=True)
    return groups


def _best_pair_from(cards) -> Optional[List[Card]]:
    """The highest pair achievable from `cards` -- 2 real same-rank cards,
    or a Joker paired with a real Ace (the Joker's only pairing role, since
    it's not a pure wildcard and can't stand in for any other rank) -- or
    None if no pair is possible at all."""
    by_rank = {}
    joker = None
    for c in cards:
        if c.is_joker:
            joker = c
        else:
            by_rank.setdefault(c.value, []).append(c)
    candidates = [(rank, g[:2]) for rank, g in by_rank.items() if len(g) >= 2]
    if joker is not None and by_rank.get(14):
        candidates.append((14, [joker, by_rank[14][0]]))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _search_two_front_leaving_made_hand(seven_cards, min_back_rank) -> Optional[Tuple[List[Card], List[Card]]]:
    """Tries every way to split 7 cards into a 2-card front / 5-card back;
    among the splits where the back is `min_back_rank` or stronger, returns
    the one with the highest-ranking front (per evaluate_two_card_hand).
    None if no split leaves a qualifying back. Powers the "Straight, Flush
    or Straight Flush" variants of the No Pair / One Pair / Three of a Kind
    rows below -- all phrased as "two highest possible cards in front that
    leaves [a/any complete hand] in back".

    `best` is a single front+back pair (not two separate nullable
    variables) specifically so its type stays provably either "a real
    front/back pair" or "nothing" -- never "a front with no matching back",
    which two separately-tracked variables can't rule out to a type
    checker even though they're always assigned together here."""
    best: Optional[Tuple[List[Card], List[Card]]] = None
    best_front_eval: Optional[HandEval] = None
    for idx_combo in combinations(range(7), 2):
        front = [seven_cards[i] for i in idx_combo]
        back = [seven_cards[i] for i in range(7) if i not in idx_combo]
        if best_five_card_eval_with_joker(back)[0] < min_back_rank:
            continue
        front_eval = evaluate_two_card_hand(front)
        if best_front_eval is None or compare_hands(front_eval, best_front_eval) > 0:
            best, best_front_eval = (front, back), front_eval
    return best


def _set_four_of_a_kind(seven_cards, quad):
    quad_rank = quad[0].value
    rest = _sorted_desc(_remove(seven_cards, quad))

    def split():
        return quad[:2], quad[2:] + rest

    if quad_rank >= 12:  # A, K, Q: back if at least a pair up front, else split
        pair = _best_pair_from(rest)
        if pair:
            return pair, quad + _remove(rest, pair)
        return split()
    if quad_rank >= 9:  # J, 10, 9: back if at least a King up front, else split
        threshold = 13
    elif quad_rank >= 6:  # 8, 7, 6: back if at least a Queen up front, else split
        threshold = 12
    else:  # 5, 4, 3, 2: never split
        return rest[:2], quad + rest[2:]
    if rest and _rank_value(rest[0]) >= threshold:
        return rest[:2], quad + rest[2:]
    return split()


def _set_two_trips(seven_cards, trips):
    high_trip, low_trip = sorted(trips, key=lambda g: g[0].value, reverse=True)
    kicker = _remove(seven_cards, high_trip + low_trip)
    return high_trip[:2], [high_trip[2]] + low_trip + kicker


def _set_three_pairs(seven_cards, pairs):
    pairs_sorted = sorted(pairs, key=lambda g: g[0].value, reverse=True)
    highest = pairs_sorted[0]
    others = pairs_sorted[1] + pairs_sorted[2]
    kicker = _remove(seven_cards, highest + others)
    return highest, others + kicker


def _set_full_house(seven_cards, trip, pair):
    # Chart: "Highest possible pair in front." The only two candidate front
    # pairs are the real (separate) pair, or 2 cards broken out of the
    # trip -- but breaking the trip always leaves just a lone trip-card +
    # the real pair in back (a bare "One Pair" of the *separate* pair's
    # rank), which is never higher-ranked than the broken-trip pair itself
    # whenever trip.value > pair.value -- i.e. breaking the trip is either
    # a guaranteed foul (front's pair would outrank back's) or, when
    # pair.value > trip.value, strictly worse than just using the real
    # pair anyway (which also leaves the trip whole in back as a much
    # stronger Three of a Kind). So "the highest possible pair" that's
    # actually achievable without fouling is always the real, separate
    # pair -- never the trip.
    return pair, trip + _remove(seven_cards, trip + pair)


def _set_three_of_a_kind(seven_cards, trip):
    # "Straight, Flush or Straight Flush with Trips" takes priority over
    # the plain Three of a Kind row whenever breaking one trip card out
    # still leaves a complete straight/flush/straight-flush behind --
    # checked first, for any trip rank (this is a separate chart row, not
    # a rank-tier exception within Three of a Kind itself).
    rest = _remove(seven_cards, trip)
    for tc in trip:
        candidate_back = [tc] + rest
        if best_five_card_eval_with_joker(candidate_back)[0] >= FIVE_CARD_STRAIGHT:
            return [c for c in trip if c != tc], candidate_back
    rest_sorted = _sorted_desc(rest)
    if trip[0].value == 14:  # Aces: "A+ next highest card in front"
        ace = trip[0]
        return [ace, rest_sorted[0]], [c for c in trip if c is not ace] + rest_sorted[1:]
    # K's and below: "Put three of a kind in back and the two other
    # highest cards in front."
    return rest_sorted[:2], trip + rest_sorted[2:]


def _set_two_pairs(seven_cards, pairs):
    big_pair, small_pair = sorted(pairs, key=lambda g: g[0].value, reverse=True)
    big_rank = big_pair[0].value
    rest = _sorted_desc(_remove(seven_cards, big_pair + small_pair))

    def split():
        return small_pair, big_pair + rest

    def both_back_if(qualifies):
        if rest and qualifies(rest[0]):
            return rest[:2], big_pair + small_pair + rest[2:]
        return split()

    if big_rank >= 12:  # A, K, Q: always split
        return split()
    if big_rank >= 9:  # J, 10, 9: both back if an Ace or Joker is available
        return both_back_if(lambda c: c.is_joker or c.value == 14)
    if big_rank >= 6:  # 8, 7, 6: both back if a King+ is available
        return both_back_if(lambda c: _rank_value(c) >= 13)
    return both_back_if(lambda c: _rank_value(c) >= 12)  # 5, 4, 3: both back if a Queen+ is available


def _set_one_pair(seven_cards, pair):
    found = _search_two_front_leaving_made_hand(seven_cards, FIVE_CARD_STRAIGHT)
    if found:
        return found
    rest_sorted = _sorted_desc(_remove(seven_cards, pair))
    return rest_sorted[:2], pair + rest_sorted[2:]


def _set_no_pair(seven_cards):
    found = _search_two_front_leaving_made_hand(seven_cards, FIVE_CARD_STRAIGHT)
    if found:
        return found
    sorted_desc = _sorted_desc(seven_cards)
    return sorted_desc[1:3], [sorted_desc[0]] + sorted_desc[3:]


def _house_way_set_by_chart(seven_cards) -> Tuple[List[Card], List[Card]]:
    """The Casino Real House Way chart's own branch dispatch, exactly as
    documented above. See house_way_set for the validity safety net wrapped
    around this."""
    joker = next((c for c in seven_cards if c.is_joker), None)
    if joker is not None:
        aces = [c for c in seven_cards if not c.is_joker and c.rank == "A"]
        if len(aces) == 4:  # Five Aces: "put pair if Aces in front"
            front = aces[:2]
            back = aces[2:] + [joker] + _remove(seven_cards, aces + [joker])
            return front, back

    groups = _real_groups(seven_cards)
    if groups and len(groups[0]) == 4:
        return _set_four_of_a_kind(seven_cards, groups[0])
    trips = [g for g in groups if len(g) == 3]
    if len(trips) == 2:
        return _set_two_trips(seven_cards, trips)
    pairs = [g for g in groups if len(g) == 2]
    if len(pairs) == 3 and not trips:
        return _set_three_pairs(seven_cards, pairs)
    if len(trips) == 1 and len(pairs) == 1:
        return _set_full_house(seven_cards, trips[0], pairs[0])
    if len(trips) == 1:
        return _set_three_of_a_kind(seven_cards, trips[0])
    if len(pairs) == 2:
        return _set_two_pairs(seven_cards, pairs)
    if len(pairs) == 1:
        return _set_one_pair(seven_cards, pairs[0])
    return _set_no_pair(seven_cards)


def _strongest_valid_split(seven_cards) -> Optional[Tuple[List[Card], List[Card]]]:
    """Exhaustive fallback: among every 2/5 split where the back legitimately
    outranks the front, the one with the strongest front. Used only as a
    safety net (see house_way_set) -- e.g. when a chart branch's "the N
    highest remaining cards go to a harmless High Card front" assumption is
    invalidated by the Joker landing next to a real Ace, silently forming a
    Pair the chart's own author never anticipated there."""
    best = None
    best_front_eval: Optional[HandEval] = None
    for idx_combo in combinations(range(7), 2):
        front = [seven_cards[i] for i in idx_combo]
        back = [seven_cards[i] for i in range(7) if i not in idx_combo]
        front_eval = evaluate_two_card_hand(front)
        back_eval = best_five_card_eval_with_joker(back)
        if compare_hands(back_eval, front_eval) <= 0:
            continue
        if best_front_eval is None or compare_hands(front_eval, best_front_eval) > 0:
            best, best_front_eval = (front, back), front_eval
    return best


def house_way_set(seven_cards) -> Tuple[List[Card], List[Card]]:
    """Sets a 7-card hand into (front_2, back_5) per the Casino Real House
    Way chart. Used unconditionally for the dealer's own hand and, on
    request, for the player's own House Way button.

    Wrapped with a defensive validity check: the chart's own branches
    assume things like "the 2 highest remaining cards make a harmless High
    Card front" that don't always hold once the Joker is involved (it can
    silently pair with a stray real Ace among those "highest cards" and
    outrank a weak back). If the chart's own pick would foul, this falls
    back to the strongest split that doesn't -- the dealer must never be
    dealt an invalid hand."""
    if len(seven_cards) != 7:
        raise ValueError("Pai Gow Poker deals exactly 7 cards to a hand.")
    front, back = _house_way_set_by_chart(seven_cards)
    front_eval = evaluate_two_card_hand(front)
    back_eval = best_five_card_eval_with_joker(back)
    if compare_hands(back_eval, front_eval) > 0:
        return front, back
    safe = _strongest_valid_split(seven_cards)
    assert safe is not None, "no valid front/back split exists for this 7-card hand"
    return safe


# --- Round orchestration -----------------------------------------------------
def hand_outcome_label(result: "RoundResult") -> str:
    return {"win": "Win", "push": "Push", "lose": "Lose"}[result.outcome]


class RoundResult:
    """Plain data holder describing the outcome of one round."""

    def __init__(self):
        self.player_cards: List[Card] = []
        self.dealer_cards: List[Card] = []

        self.player_front: List[Card] = []
        self.player_back: List[Card] = []
        self.dealer_front: List[Card] = []
        self.dealer_back: List[Card] = []

        self.player_front_eval: Optional[HandEval] = None
        self.player_back_eval: Optional[HandEval] = None
        self.dealer_front_eval: Optional[HandEval] = None
        self.dealer_back_eval: Optional[HandEval] = None

        self.outcome = ""  # "win" | "lose" | "push"

        self.ante_bet = 0.0
        self.ante_return = 0.0
        self.ante_commission = 0.0

        self.fortune_bet = 0.0
        self.fortune_return = 0.0
        self.fortune_tier: Optional[str] = None

        self.jackpot_bet = 0.0
        self.jackpot_return = 0.0
        # True only for the 100%-of-pool tier -- caller resets via
        # JackpotManager.win(). A partial (50%/25%) tier instead sets this
        # fraction so the caller can draw the meter down by that much
        # without resetting it -- see the JACKPOT_TIERS comment above.
        self.jackpot_pool_won = False
        self.jackpot_pool_partial_fraction: Optional[float] = None

        self.total_wagered = 0.0
        self.total_returned = 0.0
        self.net_result = 0.0

        self.summary = ""


class PaiGowPokerGame:
    """Engine for a single Fortune Pai Gow Poker table. Create one instance
    per table."""

    def __init__(self):
        self.deck = Deck(include_joker=True)
        self.result: Optional[RoundResult] = None

    def deal(self, ante_bet, fortune_bet=0.0, jackpot_bet=0.0, jackpot_amount=0.0) -> RoundResult:
        """Deals a new round: 7 cards each to player and dealer from a fresh
        53-card deck. Resolves Fortune/Jackpot immediately (they depend only
        on the player's raw 7 cards) and sets the dealer's hand via House
        Way. The player's own hand isn't set yet -- call set_player_hand,
        then settle()."""
        if ante_bet <= 0:
            raise ValueError("An Ante bet is required to play a round.")
        if jackpot_bet not in (0, JACKPOT_BET_AMOUNT):
            raise ValueError(f"The jackpot side bet must be exactly £{JACKPOT_BET_AMOUNT:.0f} if played.")

        self.deck.reset()  # a fresh, reshuffled 53-card deck every round
        result = RoundResult()
        result.ante_bet = ante_bet
        result.fortune_bet = fortune_bet
        result.jackpot_bet = jackpot_bet

        result.player_cards = self.deck.deal(7)
        result.dealer_cards = self.deck.deal(7)

        tier = classify_seven_card_bonus(result.player_cards)
        result.fortune_tier = tier
        if tier is not None:
            if fortune_bet > 0:
                multiplier = FORTUNE_MULTIPLIERS.get(tier, 0)
                result.fortune_return = fortune_bet * (multiplier + 1)
            if jackpot_bet > 0 and tier in JACKPOT_TIERS:
                fixed, pool_fraction = JACKPOT_TIERS[tier]
                if pool_fraction is None:
                    result.jackpot_return = fixed
                elif pool_fraction >= 1.0:
                    result.jackpot_return = jackpot_amount
                    result.jackpot_pool_won = True
                else:
                    result.jackpot_return = jackpot_amount * pool_fraction
                    result.jackpot_pool_partial_fraction = pool_fraction

        result.dealer_front, result.dealer_back = house_way_set(result.dealer_cards)

        self.result = result
        return result

    def set_player_hand(self, front, back) -> RoundResult:
        """Records the player's chosen front/back split -- raises if it
        fouls (back doesn't outrank front); the UI's own Confirm button
        never offers an invalid split in the first place, but this keeps
        the engine correct independent of that."""
        assert self.result is not None, "set_player_hand() called before deal()"
        if len(front) != 2 or len(back) != 5:
            raise ValueError("A hand is exactly a 2-card front and a 5-card back.")
        front_eval = evaluate_two_card_hand(front)
        back_eval = best_five_card_eval_with_joker(back)
        if compare_hands(back_eval, front_eval) <= 0:
            raise ValueError("The back hand must rank higher than the front hand.")
        self.result.player_front = list(front)
        self.result.player_back = list(back)
        return self.result

    def settle(self) -> RoundResult:
        """Settles the round once the player's hand has been set -- front
        vs. front, back vs. back; a tied hand ("copy") is won by the
        dealer."""
        result = self.result
        assert result is not None and result.player_front and result.player_back, \
            "settle() called before set_player_hand()"

        result.player_front_eval = evaluate_two_card_hand(result.player_front)
        result.player_back_eval = best_five_card_eval_with_joker(result.player_back)
        result.dealer_front_eval = evaluate_two_card_hand(result.dealer_front)
        result.dealer_back_eval = best_five_card_eval_with_joker(result.dealer_back)

        front_win = compare_hands(result.player_front_eval, result.dealer_front_eval) > 0
        back_win = compare_hands(result.player_back_eval, result.dealer_back_eval) > 0

        total_wagered = result.ante_bet + result.fortune_bet + result.jackpot_bet
        total_returned = result.fortune_return + result.jackpot_return

        if front_win and back_win:
            result.outcome = "win"
            commission = round(result.ante_bet * ANTE_COMMISSION_RATE, 2)
            result.ante_commission = commission
            result.ante_return = result.ante_bet * 2 - commission
            result.summary = f"You win! Ante pays 1:1 (5% commission: -£{commission:.2f})."
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
