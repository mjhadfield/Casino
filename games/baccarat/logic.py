"""
Baccarat game engine.

The first game in this library with genuinely zero player decisions after
the bet -- there's no Fold/Raise/Hit/Stand step at all, so `deal()` deals
both hands, resolves the standard drawing rules, and settles every bet in
one call, returning a fully-resolved RoundResult. The UI never blocks on
player input mid-round; it purely replays that already-known result across
a scripted animation timeline.

Dealt from an 8-deck shoe (`Deck(num_decks=8)`), reshuffled fresh every
round -- this app's usual per-round instant-settle convention, same as
every other game here; there's no persistent cut-card/shoe-depletion
mechanic.

Card points are NOT `Card.value` (which is Ace-high, 2-14, shared by every
other game here) -- Baccarat has its own scale entirely: Ace=1, 2-9=face
value, 10/J/Q/K=0. A hand's total is the sum of its cards' points, mod 10.

Round shape: Player, Banker and/or Tie bets (at least one required), plus
five fully independent side bets that never key off the main outcome at
all -- Player Dragon / Banker Dragon (Dragon Bonus, judged on whichever
side you back) and Fortune 7 / Golden 8 / Heavenly 9 / Blazing 7's / Cover
All (5 Treasures, judged purely on qualifying events in the round, whether
or not that specific spot was staked -- Cover All in particular pays if
*any* of the other four events fired, regardless of what was actually bet).

Payout rules implemented:
  Player: 1:1 if Player's final total beats Banker's; push on a tie; else
  loses.
  Banker: 1:1 minus a 5% commission (net win = bet*0.95, i.e. total
  return = bet*1.95) if Banker's final total beats Player's, deducted
  immediately per winning bet -- no running commission-owed tray across
  rounds; push on a tie; else loses.
  Tie: pays 8:1 on an actual tie; otherwise loses outright (does NOT push
  -- only Player/Banker push on a tie).
  Dragon Bonus (Player Dragon / Banker Dragon, independent spots): your
  side losing the main comparison always loses; a tie pushes only if it
  was a natural tie (both hands' own two-card totals were 8 or 9 and
  equal), else loses; your side winning via its own natural (two-card 8
  or 9) pays flat even money regardless of margin; otherwise pays by
  margin of victory -- margins 1-3 lose, 4 through 9 pay 1:1 up to 30:1.
  5 Treasures (five independent spots, judged on qualifying events alone):
  Fortune 7 (Banker 3-card total 7, 40:1), Golden 8 (Player 3-card total
  8, 25:1), Heavenly 9 (both sides 3-card total 9 -> 75:1, else either
  side alone -> 10:1), Blazing 7's (both sides 3-card total 7 -> 200:1,
  else both sides 2-card total 7 -> 50:1 -- these two conditions are
  mutually exclusive), Cover All (6:1 if any of the above four events
  fired this round, independent of whether that spot was itself staked).
"""
from typing import Dict, List, Optional

from core.cards import Card, Deck

GAME_KEY = "baccarat"
GAME_LABEL = "Baccarat"
BET_TYPES = [
    ("player", "Player"),
    ("banker", "Banker"),
    ("tie", "Tie"),
    ("player_dragon", "Player Dragon"),
    ("banker_dragon", "Banker Dragon"),
    ("fortune_7", "Fortune 7"),
    ("golden_8", "Golden 8"),
    ("heavenly_9", "Heavenly 9"),
    ("blazing_7s", "Blazing 7's"),
    ("cover_all", "Cover All"),
]

# Stats screen's "Hands Made" breakdown -- six buckets instead of a plain
# three-way Player/Banker/Tie split, since how often naturals turn up is
# this game's single most flavourful stat and costs nothing extra to track.
HAND_OUTCOME_LABELS = [
    "Player Win", "Player Natural Win", "Banker Win", "Banker Natural Win",
    "Tie", "Natural Tie",
]

# --- Card points -- NOT Card.value (Ace-high, 2-14, used by every other
# game here). Baccarat's own scale: Ace=1, 2-9=face, 10/J/Q/K=0.
BACCARAT_VALUES = {**{r: int(r) for r in "23456789"}, "10": 0, "J": 0, "Q": 0, "K": 0, "A": 1}

# --- Banker's third-card rule, only reached once neither hand is a
# natural and the Player DID draw a third card -- a literal transcription
# of the rack card's own table, keyed by Banker's own two-card total, each
# value the set of Player third-card points that trigger a Banker draw.
_ALL_POINTS = set(range(10))
BANKER_DRAW_TABLE = {
    0: _ALL_POINTS,
    1: _ALL_POINTS,
    2: _ALL_POINTS,
    3: _ALL_POINTS - {8},
    4: {2, 3, 4, 5, 6, 7},
    5: {4, 5, 6, 7},
    6: {6, 7},
    7: set(),
}

# --- Dragon Bonus -- paid by margin of (non-natural) victory. Margins 1-3
# aren't listed here at all -- they simply lose.
DRAGON_BONUS_MARGIN_PAYTABLE = {9: 30, 8: 10, 7: 6, 6: 4, 5: 2, 4: 1}

# --- 5 Treasures.
FORTUNE_7_PAYOUT = 40
GOLDEN_8_PAYOUT = 25
HEAVENLY_9_PAYOUTS = {"both": 75, "one": 10}
BLAZING_7S_PAYOUTS = {"both_3card": 200, "both_2card": 50}
COVER_ALL_PAYOUT = 6


def baccarat_value(card: Card) -> int:
    return BACCARAT_VALUES[card.rank]


def hand_total(cards: List[Card]) -> int:
    return sum(baccarat_value(c) for c in cards) % 10


def resolve_hands(player_cards: List[Card], banker_cards: List[Card], deck) -> dict:
    """Given the initial two-card Player/Banker hands (already dealt),
    mutates each list in place with any third card the standard drawing
    rules call for, and returns every derived field. `deck` only ever
    needs `.deal(1)` here -- tests can pass a tiny list-backed stub instead
    of a real shuffled Deck, to hand-construct exact scenarios (forced
    naturals, forced draws, every Banker-table row) deterministically."""
    player_initial_total = hand_total(player_cards)
    banker_initial_total = hand_total(banker_cards)
    player_natural = player_initial_total in (8, 9)
    banker_natural = banker_initial_total in (8, 9)

    if not player_natural and not banker_natural:
        player_third: Optional[Card] = None
        if player_initial_total <= 5:
            player_third = deck.deal(1)[0]
            player_cards.append(player_third)

        if player_third is None:
            # Player stood -- Banker mirrors the Player's own two-card rule.
            banker_draws = banker_initial_total <= 5
        else:
            banker_draws = baccarat_value(player_third) in BANKER_DRAW_TABLE[banker_initial_total]
        if banker_draws:
            banker_cards.append(deck.deal(1)[0])

    return {
        "player_initial_total": player_initial_total,
        "banker_initial_total": banker_initial_total,
        "player_natural": player_natural,
        "banker_natural": banker_natural,
        "player_total": hand_total(player_cards),
        "banker_total": hand_total(banker_cards),
    }


def fortune_7_hit(banker_total: int, banker_card_count: int) -> bool:
    return banker_card_count == 3 and banker_total == 7


def golden_8_hit(player_total: int, player_card_count: int) -> bool:
    return player_card_count == 3 and player_total == 8


def heavenly_9_tier(player_total: int, banker_total: int, player_card_count: int, banker_card_count: int) -> int:
    """0 / HEAVENLY_9_PAYOUTS['one'] / HEAVENLY_9_PAYOUTS['both']."""
    player_9 = player_card_count == 3 and player_total == 9
    banker_9 = banker_card_count == 3 and banker_total == 9
    if player_9 and banker_9:
        return HEAVENLY_9_PAYOUTS["both"]
    if player_9 or banker_9:
        return HEAVENLY_9_PAYOUTS["one"]
    return 0


def blazing_7s_tier(player_total: int, banker_total: int, player_card_count: int, banker_card_count: int) -> int:
    """0 / BLAZING_7S_PAYOUTS['both_2card'] / BLAZING_7S_PAYOUTS['both_3card']
    -- the two winning conditions are mutually exclusive (one requires both
    sides drew a third card, the other requires neither did)."""
    if player_card_count == 3 and banker_card_count == 3 and player_total == 7 and banker_total == 7:
        return BLAZING_7S_PAYOUTS["both_3card"]
    if player_card_count == 2 and banker_card_count == 2 and player_total == 7 and banker_total == 7:
        return BLAZING_7S_PAYOUTS["both_2card"]
    return 0


def cover_all_hit(fortune_7: bool, golden_8: bool, h9_tier: int, b7_tier: int) -> bool:
    """Fires purely off any of the other four events' qualifying condition
    -- independent of whether that specific spot was itself staked."""
    return fortune_7 or golden_8 or h9_tier > 0 or b7_tier > 0


def _dragon_bonus_return(bet: float, side_won: bool, side_natural: bool,
                          tie: bool, natural_tie: bool, margin: int) -> float:
    if bet <= 0:
        return 0.0
    if tie:
        return bet if natural_tie else 0.0
    if not side_won:
        return 0.0
    if side_natural:
        return bet * 2  # flat even money, regardless of margin
    mult = DRAGON_BONUS_MARGIN_PAYTABLE.get(margin, 0)
    return bet * (mult + 1) if mult else 0.0


def hand_outcome_label(result: "RoundResult") -> str:
    if result.outcome == "tie":
        return "Natural Tie" if result.natural_tie else "Tie"
    if result.outcome == "player":
        return "Player Natural Win" if result.player_natural else "Player Win"
    return "Banker Natural Win" if result.banker_natural else "Banker Win"


class RoundResult:
    """Plain data holder describing the outcome of one round."""

    def __init__(self):
        self.player_cards: List[Card] = []
        self.banker_cards: List[Card] = []

        self.player_initial_total = 0
        self.banker_initial_total = 0
        self.player_natural = False
        self.banker_natural = False
        self.player_total = 0
        self.banker_total = 0

        self.outcome = ""            # "player" | "banker" | "tie"
        self.natural_tie = False

        # 5 Treasures' qualifying events -- always computed regardless of
        # whether that spot (or Cover All) was actually staked.
        self.fortune_7_hit = False
        self.golden_8_hit = False
        self.heavenly_9_tier = 0     # 0 / 10 / 75
        self.blazing_7s_tier = 0     # 0 / 50 / 200
        self.cover_all_hit = False

        # One <key>_bet / <key>_return pair per BET_TYPES entry.
        for key, _ in BET_TYPES:
            setattr(self, f"{key}_bet", 0.0)
            setattr(self, f"{key}_return", 0.0)

        self.total_wagered = 0.0
        self.total_returned = 0.0
        self.net_result = 0.0

        self.summary = ""

    def bet_lines(self):
        """(key, label, bet, return) for every BET_TYPES entry -- the one
        place that knows the "<key>_bet"/"<key>_return" naming convention,
        so the UI's stats-recording loop and payout panel don't each
        re-derive it by hand across all 10 spots."""
        return [(key, label, getattr(self, f"{key}_bet"), getattr(self, f"{key}_return"))
                for key, label in BET_TYPES]


class BaccaratGame:
    """Engine for a single Baccarat table. Create one instance per table."""

    def __init__(self):
        self.deck = Deck(num_decks=8)
        self.result: Optional[RoundResult] = None

    def deal(self, bets: Dict[str, float]) -> RoundResult:
        """Deals and fully settles one round in a single call -- there's no
        player decision to wait on. `bets` maps any subset of BET_TYPES
        keys to amounts; at least one of "player"/"banker"/"tie" must be
        positive (the side bets alone aren't a playable round, mirroring
        every other game's own "a base bet is required" validation)."""
        if bets.get("player", 0) + bets.get("banker", 0) + bets.get("tie", 0) <= 0:
            raise ValueError("At least one of Player, Banker or Tie must be bet to play a round.")

        self.deck.reset()
        result = RoundResult()
        for key, _ in BET_TYPES:
            setattr(result, f"{key}_bet", bets.get(key, 0.0))

        # Player, Banker, Player, Banker -- the real deal order, one card
        # at a time, so the UI can animate it faithfully.
        result.player_cards = self.deck.deal(1)
        result.banker_cards = self.deck.deal(1)
        result.player_cards += self.deck.deal(1)
        result.banker_cards += self.deck.deal(1)

        derived = resolve_hands(result.player_cards, result.banker_cards, self.deck)
        result.player_initial_total = derived["player_initial_total"]
        result.banker_initial_total = derived["banker_initial_total"]
        result.player_natural = derived["player_natural"]
        result.banker_natural = derived["banker_natural"]
        result.player_total = derived["player_total"]
        result.banker_total = derived["banker_total"]

        if result.player_total > result.banker_total:
            result.outcome = "player"
        elif result.banker_total > result.player_total:
            result.outcome = "banker"
        else:
            result.outcome = "tie"
        result.natural_tie = (
            result.outcome == "tie" and result.player_natural and result.banker_natural
        )

        self._settle(result)
        self.result = result
        return result

    def _settle(self, result: RoundResult):
        # --- Main bets. ---
        if result.player_bet > 0:
            if result.outcome == "player":
                result.player_return = result.player_bet * 2
            elif result.outcome == "tie":
                result.player_return = result.player_bet
        if result.banker_bet > 0:
            if result.outcome == "banker":
                result.banker_return = result.banker_bet * 1.95
            elif result.outcome == "tie":
                result.banker_return = result.banker_bet
        if result.tie_bet > 0 and result.outcome == "tie":
            result.tie_return = result.tie_bet * 9

        # --- Dragon Bonus -- independent of the main bets entirely. ---
        margin = abs(result.player_total - result.banker_total)
        tie = result.outcome == "tie"
        result.player_dragon_return = _dragon_bonus_return(
            result.player_dragon_bet, result.outcome == "player", result.player_natural,
            tie, result.natural_tie, margin,
        )
        result.banker_dragon_return = _dragon_bonus_return(
            result.banker_dragon_bet, result.outcome == "banker", result.banker_natural,
            tie, result.natural_tie, margin,
        )

        # --- 5 Treasures -- judged purely on qualifying events, independent
        # of the main outcome and of whether each individual spot was bet.
        player_n, banker_n = len(result.player_cards), len(result.banker_cards)
        result.fortune_7_hit = fortune_7_hit(result.banker_total, banker_n)
        result.golden_8_hit = golden_8_hit(result.player_total, player_n)
        result.heavenly_9_tier = heavenly_9_tier(result.player_total, result.banker_total, player_n, banker_n)
        result.blazing_7s_tier = blazing_7s_tier(result.player_total, result.banker_total, player_n, banker_n)
        result.cover_all_hit = cover_all_hit(
            result.fortune_7_hit, result.golden_8_hit, result.heavenly_9_tier, result.blazing_7s_tier
        )

        if result.fortune_7_bet > 0 and result.fortune_7_hit:
            result.fortune_7_return = result.fortune_7_bet * (FORTUNE_7_PAYOUT + 1)
        if result.golden_8_bet > 0 and result.golden_8_hit:
            result.golden_8_return = result.golden_8_bet * (GOLDEN_8_PAYOUT + 1)
        if result.heavenly_9_bet > 0 and result.heavenly_9_tier > 0:
            result.heavenly_9_return = result.heavenly_9_bet * (result.heavenly_9_tier + 1)
        if result.blazing_7s_bet > 0 and result.blazing_7s_tier > 0:
            result.blazing_7s_return = result.blazing_7s_bet * (result.blazing_7s_tier + 1)
        if result.cover_all_bet > 0 and result.cover_all_hit:
            result.cover_all_return = result.cover_all_bet * (COVER_ALL_PAYOUT + 1)

        result.total_wagered = sum(getattr(result, f"{key}_bet") for key, _ in BET_TYPES)
        result.total_returned = sum(getattr(result, f"{key}_return") for key, _ in BET_TYPES)
        result.net_result = round(result.total_returned - result.total_wagered, 2)
        result.summary = _build_summary(result)


def _build_summary(result: RoundResult) -> str:
    if result.outcome == "tie":
        kind = "Natural Tie" if result.natural_tie else "Tie"
        return f"{kind} ({result.player_total}-{result.banker_total}) -- Player/Banker push, Tie pays 8:1."
    winner = "Player" if result.outcome == "player" else "Banker"
    natural = result.player_natural if result.outcome == "player" else result.banker_natural
    kind = " with a Natural" if natural else ""
    return f"{winner} wins{kind} ({result.player_total}-{result.banker_total})."
