"""
Reusable playing card primitives.

This module is deliberately generic (standard 52-card deck) so every game in
the library -- Three Card Poker today, Blackjack/Baccarat/etc. later -- can
share the same Card/Deck classes instead of re-implementing them.
"""
import random
from enum import Enum


class Suit(Enum):
    HEARTS = "Hearts"
    DIAMONDS = "Diamonds"
    CLUBS = "Clubs"
    SPADES = "Spades"


SUIT_SYMBOLS = {
    Suit.HEARTS: "\u2665",   # ♥
    Suit.DIAMONDS: "\u2666",  # ♦
    Suit.CLUBS: "\u2663",     # ♣
    Suit.SPADES: "\u2660",    # ♠
}

SUIT_COLORS = {
    Suit.HEARTS: "red",
    Suit.DIAMONDS: "red",
    Suit.CLUBS: "black",
    Suit.SPADES: "black",
}

# Ace-high ordering used by most casino card games.
RANK_ORDER = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
RANK_VALUES = {rank: index + 2 for index, rank in enumerate(RANK_ORDER)}


class Card:
    __slots__ = ("rank", "suit")

    def __init__(self, rank: str, suit: Suit):
        if rank not in RANK_VALUES:
            raise ValueError(f"Invalid rank: {rank}")
        self.rank = rank
        self.suit = suit

    @property
    def value(self) -> int:
        """Numeric rank value, 2-14 (Ace high)."""
        return RANK_VALUES[self.rank]

    @property
    def color(self) -> str:
        return SUIT_COLORS[self.suit]

    @property
    def symbol(self) -> str:
        return SUIT_SYMBOLS[self.suit]

    def short_name(self) -> str:
        return f"{self.rank}{self.symbol}"

    def __repr__(self):
        return f"Card({self.rank}{self.symbol})"

    def __eq__(self, other):
        return isinstance(other, Card) and self.rank == other.rank and self.suit == other.suit

    def __hash__(self):
        return hash((self.rank, self.suit))


class Deck:
    """A standard, shuffled 52-card deck -- or a shoe of several standard
    decks shuffled together, via `num_decks` (e.g. Blackjack's 8-deck shoe).
    Reusable across any game. `num_decks` copies of the same rank+suit
    combination are equal (Card.__eq__ compares rank/suit only) and can
    genuinely all appear in the same hand -- that's real, expected shoe
    behaviour, not a bug (see e.g. Blackjack's "Suited Trips" side bet,
    which specifically relies on that being possible)."""

    def __init__(self, num_decks: int = 1):
        self.num_decks = num_decks
        self._all_cards = [
            Card(rank, suit)
            for _ in range(num_decks)
            for suit in Suit
            for rank in RANK_ORDER
        ]
        self.cards = []
        self.reset()

    def reset(self):
        """Return every card to the deck and shuffle -- call at the start of each round."""
        self.cards = list(self._all_cards)
        self.shuffle()

    def shuffle(self):
        random.shuffle(self.cards)

    def deal(self, count: int = 1):
        if count > len(self.cards):
            raise ValueError("Not enough cards left in the deck.")
        dealt, self.cards = self.cards[:count], self.cards[count:]
        return dealt

    def cards_remaining(self) -> int:
        return len(self.cards)
