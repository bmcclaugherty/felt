"""Independent EV check of the hard/soft chart (infinite deck).

Run: .venv/bin/python scripts/verify_strategy.py
Prints every cell where the chart's first choice differs from the EV-best
action. Split cells are excluded (they need a split-EV model; the split
chart is taken from the published 6D H17 DAS chart).
"""

from __future__ import annotations

from functools import lru_cache

from felt.cards import Card, hand_value
from felt.odds import RANK_PROB, VALUE, dealer_distribution
from felt.strategy import SOFT_CHART, UPS, chart_action


def _up(rank: str) -> str:
    return "10" if rank in ("J", "Q", "K") else rank


@lru_cache(maxsize=None)
def stand_ev(total: int, soft: bool, up: str) -> float:
    dist = dealer_distribution(_up(up))
    ev = 0.0
    for final, p in dist.items():
        if final == 22 or final < total:
            ev += p
        elif final > total:
            ev -= p
    return ev


@lru_cache(maxsize=None)
def hit_ev(total: int, soft: bool, up: str) -> float:
    ev = 0.0
    for rank, p in RANK_PROB.items():
        nt, ns = total, soft
        if rank == "A":
            if soft:
                nt, ns = total + 1, True
            elif total + 11 <= 21:
                nt, ns = total + 11, True
            else:
                nt, ns = total + 1, False
        else:
            nt = total + VALUE[rank]
            if nt > 21 and soft:
                nt, ns = nt - 10, False
        if nt > 21:
            ev -= p
        else:
            ev += p * best_play_ev(nt, ns, up)
    return ev


@lru_cache(maxsize=None)
def double_ev(total: int, soft: bool, up: str) -> float:
    """Double: one card, then stand."""
    ev = 0.0
    for rank, p in RANK_PROB.items():
        nt, ns = total, soft
        if rank == "A":
            if soft:
                nt, ns = total + 1, True
            elif total + 11 <= 21:
                nt, ns = total + 11, True
            else:
                nt, ns = total + 1, False
        else:
            nt = total + VALUE[rank]
            if nt > 21 and soft:
                nt, ns = nt - 10, False
        if nt > 21:
            ev -= 2 * p
        else:
            ev += 2 * p * stand_ev(nt, ns, up)
    return ev


@lru_cache(maxsize=None)
def best_play_ev(total: int, soft: bool, up: str) -> float:
    if total > 21:
        return -1.0
    return max(stand_ev(total, soft, up), hit_ev(total, soft, up))


def _cards_for(total: int) -> list[Card]:
    if total <= 11:
        return [Card(str(total - 2), "♠"), Card("2", "♠")]
    return [Card("10", "♠"), Card(str(total - 10), "♠")]


def main() -> int:
    problems = 0
    checked = 0
    for total in range(5, 18):
        for up in UPS:
            if total < 12:
                soft = False
            else:
                soft = False
            chart = chart_action(_cards_for(total), up, initial=True)
            opts = {
                "stand": stand_ev(total, False, up),
                "hit": hit_ev(total, False, up),
            }
            if total in (9, 10, 11):
                opts["double"] = double_ev(total, False, up)
            if total in (15, 16, 17):
                opts["surrender"] = -0.5
            best = max(opts, key=opts.get)
            letter = {"stand": "S", "hit": "H", "double": "D", "surrender": "R"}[best]
            checked += 1
            if chart != letter:
                problems += 1
                print(f"HARD {total} vs {up}: chart {chart}, EV best {letter}  {opts}")

    for soft_total, row in SOFT_CHART.items():
        for up in UPS:
            chart = row[UPS.index(up)]
            opts = {
                "stand": stand_ev(soft_total, True, up),
                "hit": hit_ev(soft_total, True, up),
            }
            if soft_total >= 13:
                opts["double"] = double_ev(soft_total, True, up)
            best = max(opts, key=opts.get)
            letter = {"stand": "S", "hit": "H", "double": "D"}[best]
            checked += 1
            if chart != letter:
                problems += 1
                print(f"SOFT {soft_total} vs {up}: chart {chart}, EV best {letter}  {opts}")

    print(f"checked {checked} hard/soft cells, {problems} disagreements")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
