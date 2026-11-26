"""Dealer outcome probabilities (infinite-deck approximation).

Used only to phrase the coach's *why* explanations with real numbers; the
strategy chart itself is the rules-fixed table in :mod:`felt.strategy`.
"""

from __future__ import annotations

from functools import lru_cache

RANK_PROB = {
    "A": 1 / 13,
    "2": 1 / 13,
    "3": 1 / 13,
    "4": 1 / 13,
    "5": 1 / 13,
    "6": 1 / 13,
    "7": 1 / 13,
    "8": 1 / 13,
    "9": 1 / 13,
    "10": 4 / 13,
}
VALUE = {"A": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "10": 10}


def _add(total: int, soft: bool, rank: str) -> tuple[int, bool]:
    """Add one card to a (total, soft) state, keeping the best ace count."""
    if rank == "A":
        if soft:
            # Existing ace still counts 11; the new ace counts 1.
            return total + 1, True
        if total + 11 <= 21:
            return total + 11, True
        return total + 1, False
    ntotal = total + VALUE[rank]
    if ntotal > 21 and soft:
        return ntotal - 10, False
    return ntotal, soft


@lru_cache(maxsize=None)
def _finish(total: int, soft: bool) -> tuple[tuple[int, float], ...]:
    """Return ((final_total, probability), ...); 22 means bust."""
    if total > 21:
        return ((22, 1.0),)
    if total >= 18 or (total == 17 and not soft):
        return ((total, 1.0),)
    acc: dict[int, float] = {}
    for rank, p in RANK_PROB.items():
        ntotal, nsoft = _add(total, soft, rank)
        for final, q in _finish(ntotal, nsoft):
            acc[final] = acc.get(final, 0.0) + p * q
    return tuple(sorted(acc.items()))


def dealer_distribution(up_rank: str, peeked: bool = True) -> dict[int, float]:
    """Final dealer totals given the upcard, H17, hitting soft 17. 22 = bust.

    ``peeked`` conditions on the dealer *not* having a natural, which is the
    information a player has after an American hole-card peek.
    """
    if up_rank not in RANK_PROB:
        up_rank = "10"
    start_total, start_soft = (11, True) if up_rank == "A" else (VALUE[up_rank], False)
    # Hole-card distribution, conditioned on no dealer blackjack.
    excluded = {"10"} if up_rank == "A" else ({"A"} if up_rank == "10" else set())
    hole = {r: p for r, p in RANK_PROB.items() if not (peeked and r in excluded)}
    mass = sum(hole.values())
    acc: dict[int, float] = {}
    for rank, p in hole.items():
        total, soft = _add(start_total, start_soft, rank)
        for final, q in _finish(total, soft):
            acc[final] = acc.get(final, 0.0) + (p / mass) * q
    return acc


def dealer_bust_prob(up_rank: str) -> float:
    return dealer_distribution(up_rank).get(22, 0.0)


def dealer_blackjack_prob(up_rank: str) -> float:
    """Chance the hole card completes a natural, from the player's view."""
    if up_rank not in ("A", "10"):
        return 0.0
    return 4 / 13
