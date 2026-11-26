"""Cards, shoe, and hand valuation for Felt."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Iterable, Sequence

RANKS = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K")
SUITS = ("♠", "♥", "♦", "♣")
RED_SUITS = frozenset({"♥", "♦"})

RANK_VALUE = {
    "A": 1,
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "10": 10,
    "J": 10,
    "Q": 10,
    "K": 10,
}

DECKS = 6
PENETRATION = 0.75


@dataclass(frozen=True, slots=True)
class Card:
    rank: str
    suit: str

    def __post_init__(self) -> None:
        if self.rank not in RANK_VALUE:
            raise ValueError(f"bad rank: {self.rank!r}")
        if self.suit not in SUITS:
            raise ValueError(f"bad suit: {self.suit!r}")

    @property
    def hard_value(self) -> int:
        return RANK_VALUE[self.rank]

    @property
    def is_ace(self) -> bool:
        return self.rank == "A"

    @property
    def is_red(self) -> bool:
        return self.suit in RED_SUITS

    def as_tuple(self) -> tuple[str, str]:
        return (self.rank, self.suit)

    def label(self) -> str:
        return f"{self.rank}{self.suit}"

    def face(self) -> str:
        """Two-line card face used by compact widgets."""
        return f"{self.rank:>2}{self.suit}"

    def hidden_face(self) -> str:
        return "▒▒▒"


def hand_value(cards: Sequence[Card]) -> tuple[int, bool]:
    """Return (best total, is_soft). Aces count 11 only when it cannot bust."""
    total = sum(c.hard_value for c in cards)
    aces = sum(1 for c in cards if c.is_ace)
    soft = False
    while aces and total + 10 <= 21:
        total += 10
        aces -= 1
        soft = True
    return total, soft


def is_blackjack(cards: Sequence[Card]) -> bool:
    return len(cards) == 2 and hand_value(cards) == (21, True)


def is_pair(cards: Sequence[Card]) -> bool:
    """Split eligibility: equal *rank* (10/J/Q/K are one rank for splitting)."""
    if len(cards) != 2:
        return False
    a, b = cards
    if a.rank == b.rank:
        return True
    return a.hard_value == 10 and b.hard_value == 10 and not a.is_ace and not b.is_ace


def describe(cards: Sequence[Card]) -> str:
    if not cards:
        return "—"
    total, soft = hand_value(cards)
    if is_blackjack(cards):
        return "blackjack"
    if soft and total <= 21:
        return f"soft {total}"
    return f"hard {total}"


@dataclass
class Shoe:
    """A six-deck shoe. Pass ``cards`` for a deterministic injected shoe."""

    decks: int = DECKS
    seed: int | None = None
    cards: list[Card] = field(default_factory=list)
    _rng: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)
        if not self.cards:
            self.cards = [Card(r, s) for _ in range(self.decks) for s in SUITS for r in RANKS]
            self._rng.shuffle(self.cards)
        self._total = len(self.cards)
        self.discard_pile: list[Card] = []

    @property
    def remaining(self) -> int:
        return len(self.cards)

    @property
    def total(self) -> int:
        return self._total

    @property
    def needs_shuffle(self) -> bool:
        return self.remaining <= self._total * (1 - PENETRATION)

    def draw(self) -> Card:
        if not self.cards:
            self.shuffle()
        # Draw from the front so an injected shoe plays in the order given.
        return self.cards.pop(0)

    def draw_many(self, n: int) -> list[Card]:
        return [self.draw() for _ in range(n)]

    def shuffle(self) -> None:
        """Reshuffle all cards (discards plus undealt). Used between shoes."""
        fresh = [Card(r, s) for _ in range(self.decks) for s in SUITS for r in RANKS]
        self.cards = fresh
        getattr(self, "discard_pile", []).clear()
        self._rng.shuffle(self.cards)
        self._total = len(self.cards)

    def burn(self, n: int = 1) -> None:
        for _ in range(n):
            self.draw()
