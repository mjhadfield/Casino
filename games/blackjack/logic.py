"""
Blackjack game engine (8-deck shoe, UK casino payout rules).

Like Three Card Poker's logic.py, this module is decoupled from the bank
balance and the UI: it deals, tracks each hand's own state through
Hit/Stand/Double/Split/Insurance, and works out how much everything returns
once the round is settled. The calling UI debits/credits FinanceManager
based on what this returns.

House rules implemented (see the two reference rules documents this was
built from):
  - American-style dealer hole card with a peek: an Ace/10-value up-card
    checks the hole card immediately -- an early Dealer Blackjack ends the
    round for every box before anyone can Hit/Double/Split into extra
    exposure. Insurance is offered only on an Ace up-card, up to half a
    box's main bet, paid 2:1.
  - No restriction on what a first-two-cards total can be to Double.
    Splitting is allowed on any equal-*value* pair (so e.g. J+Q qualifies),
    up to 4 splits (5 hands); Double is allowed after a split too. The one
    exception is split Aces: each gets exactly one more card and then
    automatically stands, full stop -- no further Hit/Double/Split even on
    another Ace.
  - A 21 made on a split hand is just "21", not a bonus-paying natural --
    a natural Blackjack, by definition, only exists on an untouched
    original 2-card hand (see Hand.is_blackjack).
  - Dealer stands on all 17s (soft or hard) and always completes their hand
    (reveals the hole card and draws to 17) once every box is done, for a
    consistent reveal every round -- the same way Three Card Poker always
    reveals its dealer even on a fold.
  - Player Blackjack (Dealer not also Blackjack): 3:2. Bust: lose.
    Otherwise: higher total wins 1:1, equal totals push.

Side bets -- all four reuse core.hand_evaluator.evaluate_three_card_hand
directly, run against the box's own first two cards plus the Dealer's
up-card (exactly a Three Card Poker hand), with a couple of extra suited/
rank checks layered on top the same way three_card_poker/logic.py's
_is_royal layers onto the same base evaluator:
  Super Pairs (the box's own 2 cards only):
    Any Pair 5:1, Prime Pair (same colour, different suits) 10:1,
    Suited Pair 25:1, Suited Trips 50:1 (pair *and* the Dealer's up-card
    all share rank and suit -- only actually possible with a multi-deck
    shoe).
  21+3: Flush or better (Flush/Straight/Three of a Kind/Straight Flush)
    pays a flat 9:1.
  Top 3 (only playable alongside a 21+3 bet): Three of a Kind Suited 270:1,
    Straight Flush 180:1, Three of a Kind (any suits) 90:1.
  Jackpot (flat £1 on/off toggle, shares Three Card Poker's progressive
    pool via app.jackpot): Three of a Kind Aces/Kings/Queens -> 100% of the
    pool (split between boxes if more than one hits it the same round);
    Three of a Kind suited (other ranks) -> £625; Straight Flush -> £125;
    Three of a Kind off-suit (other ranks) -> £100; Straight -> £30;
    Flush -> £10.

All four side bets -- and the Jackpot's pool/fixed tiers -- settle
immediately off the Dealer's up-card once the initial deal completes,
before any Hit/Stand/Double/Split or even the Dealer's peek, and are
completely unaffected by an early Dealer Blackjack.
"""
from typing import List, Optional

from core.cards import Deck
from core.hand_evaluator import evaluate_three_card_hand, FLUSH, STRAIGHT, STRAIGHT_FLUSH, THREE_OF_A_KIND

# Identifies this game to GameStatsManager (core/game_stats.py) and the
# Stats screen (ui/stats_screen.py) -- see three_card_poker/logic.py's own
# GAME_KEY/BET_TYPES for the pattern this mirrors.
GAME_KEY = "blackjack"
GAME_LABEL = "Blackjack"
BET_TYPES = [
    ("blackjack", "Blackjack"),
    ("insurance", "Insurance"),
    ("super_pairs", "Super Pairs"),
    ("twenty_one_plus_three", "21+3"),
    ("top_three", "Top 3"),
    ("jackpot", "Jackpot"),
]
# Stats screen's "Hands Made" breakdown -- unlike Three Card Poker there's no
# "Fold" bucket (every hand is always played through to a result), so the
# Stats screen's own "Played vs Folded" framing just always reads 100% played
# for this game, which is accurate.
HAND_OUTCOME_LABELS = ["Bust", "Lose", "Push", "Win", "Blackjack"]

DECK_COUNT = 8

BLACKJACK_PAYOUT_MULTIPLIER = 1.5  # 3:2
INSURANCE_PAYOUT_MULTIPLIER = 2    # 2:1
MAX_SPLITS = 4                     # up to 4 splits -- 5 hands from one box

# --- Super Pairs ----------------------------------------------------------
SUPER_PAIRS_ANY_PAIR_MULTIPLIER = 5
SUPER_PAIRS_PRIME_PAIR_MULTIPLIER = 10
SUPER_PAIRS_SUITED_PAIR_MULTIPLIER = 25
SUPER_PAIRS_SUITED_TRIPS_MULTIPLIER = 50

# --- 21+3 / Top 3 -----------------------------------------------------------
TWENTY_ONE_PLUS_THREE_MULTIPLIER = 9  # flat, for a Flush or better

TOP_THREE_THREE_OF_A_KIND_MULTIPLIER = 90
TOP_THREE_STRAIGHT_FLUSH_MULTIPLIER = 180
TOP_THREE_THREE_OF_A_KIND_SUITED_MULTIPLIER = 270

# --- Jackpot side bet (flat £1, shares Three Card Poker's progressive pool) -
# Always exactly this amount if played -- see ui.py, which enforces it as an
# on/off toggle rather than a stackable chip amount, the same as Three Card
# Poker's own jackpot spot.
JACKPOT_BET_AMOUNT = 1.0

# Fixed £ amounts, taken from the reference paytable's £5-stake column
# applied to this flat £1 bet (see module docstring).
JACKPOT_FLUSH_PAYOUT = 10
JACKPOT_STRAIGHT_PAYOUT = 30
JACKPOT_THREE_OF_A_KIND_OFFSUIT_PAYOUT = 100
JACKPOT_STRAIGHT_FLUSH_PAYOUT = 125
JACKPOT_THREE_OF_A_KIND_SUITED_PAYOUT = 625
# Three of a Kind Aces/Kings/Queens (any suit arrangement) pays 100% of the
# jackpot pool instead of a fixed amount -- see _jackpot_tier.
_JACKPOT_POOL_RANKS = {"A", "K", "Q"}


def _card_bj_value(card):
    """Blackjack value of one card: Ace=11 (soft, downgraded in hand_value
    as needed), J/Q/K=10, else its face rank."""
    if card.rank == "A":
        return 11
    if card.rank in ("J", "Q", "K"):
        return 10
    return int(card.rank)


def hand_value(cards):
    """Returns (best_total, is_soft) for a Blackjack hand -- best_total is
    the highest total <=21 achievable by counting each Ace as 1 or 11,
    falling back to the (busted) all-aces-low total only if every
    combination busts. is_soft is True iff at least one Ace is still being
    counted as 11 in that best total."""
    total = sum(_card_bj_value(c) for c in cards)
    soft_aces = sum(1 for c in cards if c.rank == "A")
    while total > 21 and soft_aces > 0:
        total -= 10
        soft_aces -= 1
    return total, soft_aces > 0


def is_blackjack(cards):
    """True iff `cards` is an untouched 2-card 21 (Ace + any 10-value
    card) -- the only way 2 cards can total 21 at all."""
    return len(cards) == 2 and hand_value(cards)[0] == 21


class Hand:
    """One hand within a Box -- a Box starts with exactly one and can grow
    to up to 5 via Split. Mutated in place by BlackjackGame's Hit/Stand/
    Double/Split/settle; safe to read from once `done`."""

    def __init__(self, cards, bet, from_split=False, split_aces=False):
        self.cards = list(cards)
        self.bet = bet
        self.doubled = False
        # `from_split`: this hand came from a Split, so it can never count
        # as a bonus-paying natural Blackjack even if it totals 21 (see
        # is_blackjack). `split_aces`: this hand is specifically one half of
        # a split pair of Aces -- gets exactly one more card, then must
        # stand, no further action, ever (see BlackjackGame.split).
        self.from_split = from_split
        self.split_aces = split_aces
        self.done = False
        self.outcome = None   # set by settle(): "Bust"|"Lose"|"Push"|"Win"|"Blackjack"
        self.payout = 0.0     # total returned for this hand once settled
        if self.total == 21:
            # A fresh natural Blackjack, or a split hand that lands on a
            # bare 21 -- either way, "not allowed to draw or double on any
            # hand that is 21".
            self.done = True

    @property
    def total(self):
        return hand_value(self.cards)[0]

    @property
    def is_soft(self):
        return hand_value(self.cards)[1]

    @property
    def is_bust(self):
        return self.total > 21

    @property
    def is_blackjack(self):
        return not self.from_split and is_blackjack(self.cards)

    @property
    def can_hit(self):
        return not self.done

    @property
    def can_double(self):
        return len(self.cards) == 2 and not self.done and not self.split_aces

    def can_split(self, split_count):
        if self.done or len(self.cards) != 2 or self.split_aces:
            return False
        if split_count >= MAX_SPLITS:
            return False
        a, b = self.cards
        return _card_bj_value(a) == _card_bj_value(b)


class Box:
    """One betting box -- a player choosing to play 2 boxes gets two of
    these, dealt and played independently against the same Dealer hand,
    with identical bets on each (see ui.py's box-count toggle)."""

    def __init__(self, main_bet, super_pairs_bet=0.0, twenty_one_plus_three_bet=0.0,
                 top_three_bet=0.0, jackpot_bet=0.0):
        self.main_bet = main_bet
        self.super_pairs_bet = super_pairs_bet
        self.twenty_one_plus_three_bet = twenty_one_plus_three_bet
        self.top_three_bet = top_three_bet
        self.jackpot_bet = jackpot_bet
        self.insurance_bet = 0.0
        self.hands: List[Hand] = []  # populated by BlackjackGame.deal()
        self.side_bet_results = {}   # bet_key -> £ returned, filled by _resolve_side_bets

    def split_count(self):
        return len(self.hands) - 1

    def active_hand(self) -> Optional[Hand]:
        for hand in self.hands:
            if not hand.done:
                return hand
        return None

    def all_done(self):
        return self.active_hand() is None


def _super_pairs_multiplier(c1, c2, dealer_up):
    if c1.rank != c2.rank:
        return 0
    suited_pair = c1.suit == c2.suit
    if suited_pair and dealer_up.rank == c1.rank and dealer_up.suit == c1.suit:
        return SUPER_PAIRS_SUITED_TRIPS_MULTIPLIER
    if suited_pair:
        return SUPER_PAIRS_SUITED_PAIR_MULTIPLIER
    if c1.color == c2.color:
        return SUPER_PAIRS_PRIME_PAIR_MULTIPLIER
    return SUPER_PAIRS_ANY_PAIR_MULTIPLIER


def _top_three_multiplier(three_eval, three_cards):
    rank = three_eval[0]
    if rank == THREE_OF_A_KIND:
        if len({c.suit for c in three_cards}) == 1:
            return TOP_THREE_THREE_OF_A_KIND_SUITED_MULTIPLIER
        return TOP_THREE_THREE_OF_A_KIND_MULTIPLIER
    if rank == STRAIGHT_FLUSH:
        return TOP_THREE_STRAIGHT_FLUSH_MULTIPLIER
    return 0


def _jackpot_tier(three_eval, three_cards):
    """Returns (amount, is_pool_share) for the flat £1 Jackpot side bet.
    is_pool_share is True only for Three of a Kind Aces/Kings/Queens, which
    pays out of the shared progressive pool rather than a fixed amount --
    the caller divides the pool's current value by however many boxes hit
    this tier in the same round (see BlackjackGame._resolve_side_bets)."""
    rank = three_eval[0]
    if rank == THREE_OF_A_KIND:
        hand_rank = three_cards[0].rank  # a 3oak, so any one card's rank says it all
        if hand_rank in _JACKPOT_POOL_RANKS:
            return 0.0, True
        if len({c.suit for c in three_cards}) == 1:
            return JACKPOT_THREE_OF_A_KIND_SUITED_PAYOUT, False
        return JACKPOT_THREE_OF_A_KIND_OFFSUIT_PAYOUT, False
    if rank == STRAIGHT_FLUSH:
        return JACKPOT_STRAIGHT_FLUSH_PAYOUT, False
    if rank == STRAIGHT:
        return JACKPOT_STRAIGHT_PAYOUT, False
    if rank == FLUSH:
        return JACKPOT_FLUSH_PAYOUT, False
    return 0.0, False


def _settle_hand(hand, dealer_total, dealer_bust, dealer_blackjack):
    if hand.is_bust:
        return "Bust", 0.0
    if hand.is_blackjack:
        if dealer_blackjack:
            return "Push", hand.bet
        return "Blackjack", hand.bet * (1 + BLACKJACK_PAYOUT_MULTIPLIER)
    if dealer_blackjack:
        return "Lose", 0.0
    if dealer_bust or hand.total > dealer_total:
        return "Win", hand.bet * 2
    if hand.total == dealer_total:
        return "Push", hand.bet
    return "Lose", 0.0


class HandResult:
    """Read-only snapshot of one settled hand -- unlike Hand (this game's
    live/mutable hand-in-progress object), safe for the UI to keep around
    for display/animation/stats once the round's done."""

    def __init__(self, hand: Hand):
        self.cards = list(hand.cards)
        self.bet = hand.bet
        self.doubled = hand.doubled
        self.from_split = hand.from_split
        self.split_aces = hand.split_aces
        self.total = hand.total
        self.outcome = hand.outcome  # "Bust"|"Lose"|"Push"|"Win"|"Blackjack"
        self.payout = hand.payout    # total returned, 0 for Bust/Lose


class BoxResult:
    def __init__(self, box: Box):
        self.main_bet = box.main_bet
        self.hands = [HandResult(h) for h in box.hands]
        self.insurance_bet = box.insurance_bet
        self.insurance_return = 0.0  # filled by BlackjackGame.settle()
        self.super_pairs_bet = box.super_pairs_bet
        self.twenty_one_plus_three_bet = box.twenty_one_plus_three_bet
        self.top_three_bet = box.top_three_bet
        self.jackpot_bet = box.jackpot_bet
        self.side_bet_results = dict(box.side_bet_results)  # bet_key -> £ returned

    @property
    def main_wagered(self):
        return sum(h.bet for h in self.hands)

    @property
    def main_returned(self):
        return sum(h.payout for h in self.hands)


class RoundSummary:
    """Everything the UI/stats need once a round's fully settled -- the
    Blackjack equivalent of Three Card Poker's RoundResult, shaped around a
    list of boxes (each with a list of hands) instead of one flat hand."""

    def __init__(self):
        self.dealer_cards = []
        self.dealer_blackjack = False
        self.dealer_total = 0
        self.boxes: List[BoxResult] = []
        self.jackpot_pool_won = False  # True if any box hit the AKQ 100%-pool tier
        self.total_wagered = 0.0
        self.total_returned = 0.0
        self.net_result = 0.0


class BlackjackGame:
    """Engine for a single Blackjack table (8-deck shoe). Create one
    instance per table."""

    def __init__(self):
        self.shoe = Deck(num_decks=DECK_COUNT)
        self.dealer_cards = []
        self.boxes: List[Box] = []
        self.insurance_offered = False
        self.dealer_blackjack = False
        self.jackpot_pool_won = False

    def deal(self, main_bets, side_bets_per_box, jackpot_amount=0.0):
        """Starts a new round. `main_bets`: list of main-bet amounts, one
        per box in play (length 1 or 2). `side_bets_per_box`: a matching
        list of dicts, each with any of "super_pairs_bet"/
        "twenty_one_plus_three_bet"/"top_three_bet"/"jackpot_bet" (omitted
        keys default to 0). `jackpot_amount`: the current pool value
        (JackpotManager.amount), needed only if a box might hit the AKQ
        100% tier.

        Deals 2 cards to every box and the Dealer, resolves every side bet
        immediately off the Dealer's up-card, and runs the Dealer's peek if
        their up-card is an Ace or a 10-value card. After this, the caller
        drives play via hit/stand/double/split/take_insurance (checking
        self.dealer_blackjack first -- an early Dealer Blackjack means no
        box gets to act at all), then settle()."""
        if not main_bets or len(main_bets) > 2:
            raise ValueError("Blackjack is played with 1 or 2 boxes.")
        if any(bet <= 0 for bet in main_bets):
            raise ValueError("Every box needs a Blackjack bet to play.")

        self.shoe.reset()  # a fresh, reshuffled 8-deck shoe every round
        self.boxes = [
            Box(main_bet=bet, **side_bets_per_box[i])
            for i, bet in enumerate(main_bets)
        ]
        for box in self.boxes:
            box.hands = [Hand(self.shoe.deal(2), bet=box.main_bet)]
        self.dealer_cards = self.shoe.deal(2)

        self._resolve_side_bets(jackpot_amount)

        up_card = self.dealer_cards[0]
        self.insurance_offered = up_card.rank == "A"
        peek = up_card.rank == "A" or _card_bj_value(up_card) == 10
        self.dealer_blackjack = peek and is_blackjack(self.dealer_cards)
        return self

    def _resolve_side_bets(self, jackpot_amount):
        up_card = self.dealer_cards[0]
        pool_hit_boxes = []
        for box in self.boxes:
            p1, p2 = box.hands[0].cards
            three = [p1, p2, up_card]
            box.side_bet_results = {}

            if box.super_pairs_bet > 0:
                mult = _super_pairs_multiplier(p1, p2, up_card)
                box.side_bet_results["super_pairs"] = box.super_pairs_bet * (mult + 1) if mult else 0.0

            need_three_eval = box.twenty_one_plus_three_bet > 0 or box.top_three_bet > 0 or box.jackpot_bet > 0
            three_eval = evaluate_three_card_hand(three) if need_three_eval else None

            if box.twenty_one_plus_three_bet > 0:
                qualifies = three_eval[0] >= FLUSH
                box.side_bet_results["twenty_one_plus_three"] = (
                    box.twenty_one_plus_three_bet * (TWENTY_ONE_PLUS_THREE_MULTIPLIER + 1) if qualifies else 0.0
                )

            if box.top_three_bet > 0:
                mult = _top_three_multiplier(three_eval, three)
                box.side_bet_results["top_three"] = box.top_three_bet * (mult + 1) if mult else 0.0

            if box.jackpot_bet > 0:
                amount, is_pool = _jackpot_tier(three_eval, three)
                if is_pool:
                    pool_hit_boxes.append(box)
                else:
                    box.side_bet_results["jackpot"] = amount

        if pool_hit_boxes:
            share = jackpot_amount / len(pool_hit_boxes)
            for box in pool_hit_boxes:
                box.side_bet_results["jackpot"] = share
        self.jackpot_pool_won = bool(pool_hit_boxes)

    # ------------------------------------------------------------------ play
    def hit(self, box_idx):
        hand = self.boxes[box_idx].active_hand()
        if hand is None or not hand.can_hit:
            raise ValueError("This hand can't take another card.")
        hand.cards.extend(self.shoe.deal(1))
        if hand.is_bust or hand.total == 21:
            hand.done = True
        return hand

    def stand(self, box_idx):
        hand = self.boxes[box_idx].active_hand()
        if hand is None:
            raise ValueError("No hand to stand on.")
        hand.done = True
        return hand

    def double(self, box_idx):
        hand = self.boxes[box_idx].active_hand()
        if hand is None or not hand.can_double:
            raise ValueError("This hand can't be doubled.")
        hand.doubled = True
        hand.bet *= 2
        hand.cards.extend(self.shoe.deal(1))
        hand.done = True  # exactly one more card, then a forced stand
        return hand

    def split(self, box_idx):
        box = self.boxes[box_idx]
        hand = box.active_hand()
        if hand is None or not hand.can_split(box.split_count()):
            raise ValueError("This hand can't be split.")
        c1, c2 = hand.cards
        is_aces = c1.rank == "A" and c2.rank == "A"
        idx = box.hands.index(hand)
        new_a = Hand([c1] + self.shoe.deal(1), bet=hand.bet, from_split=True, split_aces=is_aces)
        new_b = Hand([c2] + self.shoe.deal(1), bet=hand.bet, from_split=True, split_aces=is_aces)
        if is_aces:
            # "After splitting Aces however, he receives one more card only
            # on each" -- no further action even if that card doesn't make 21.
            new_a.done = True
            new_b.done = True
        box.hands[idx:idx + 1] = [new_a, new_b]
        return new_a, new_b

    def take_insurance(self, box_idx, amount):
        box = self.boxes[box_idx]
        if not self.insurance_offered:
            raise ValueError("Insurance isn't offered this round.")
        max_allowed = box.main_bet / 2
        if amount <= 0 or amount > max_allowed + 1e-9:
            raise ValueError(f"Insurance can be at most £{max_allowed:.2f} on this box.")
        box.insurance_bet = amount

    def all_boxes_done(self):
        return all(box.all_done() for box in self.boxes)

    # ------------------------------------------------------------------ settle
    def _play_dealer_hand(self):
        while hand_value(self.dealer_cards)[0] < 17:
            self.dealer_cards.extend(self.shoe.deal(1))

    def settle(self) -> RoundSummary:
        """Plays the Dealer out (unless they already peeked a Blackjack) and
        resolves every hand in every box, plus Insurance. Call once every
        box's every hand is done (or immediately, if self.dealer_blackjack
        was already True right after deal())."""
        if not self.dealer_blackjack:
            self._play_dealer_hand()
        dealer_total, _ = hand_value(self.dealer_cards)
        dealer_bust = dealer_total > 21

        summary = RoundSummary()
        summary.dealer_cards = list(self.dealer_cards)
        summary.dealer_blackjack = self.dealer_blackjack
        summary.dealer_total = dealer_total
        summary.jackpot_pool_won = self.jackpot_pool_won

        total_wagered = 0.0
        total_returned = 0.0
        for box in self.boxes:
            for hand in box.hands:
                outcome, payout = _settle_hand(hand, dealer_total, dealer_bust, self.dealer_blackjack)
                hand.outcome = outcome
                hand.payout = payout
                total_wagered += hand.bet
                total_returned += payout

            box_result = BoxResult(box)
            if box.insurance_bet > 0:
                box_result.insurance_return = (
                    box.insurance_bet * (INSURANCE_PAYOUT_MULTIPLIER + 1) if self.dealer_blackjack else 0.0
                )
                total_wagered += box.insurance_bet
                total_returned += box_result.insurance_return

            for key, ret in box.side_bet_results.items():
                total_wagered += getattr(box, f"{key}_bet")
                total_returned += ret

            summary.boxes.append(box_result)

        summary.total_wagered = total_wagered
        summary.total_returned = total_returned
        summary.net_result = round(total_returned - total_wagered, 2)
        return summary
