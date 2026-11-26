"""Rules-fixed basic strategy for 6 decks, H17, DAS, late surrender.

Chart sources (see README):
  * Wizard of Odds — late surrender, 4+ decks, total dependent, H17 column
  * Blackjack Apprenticeship — H17 basic strategy, late surrender panel
  * Wizard of Odds / blackjacktrainer.fyi — 6D H17 DAS hard/soft/pair chart
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from .cards import Card, hand_value, is_pair
from .odds import dealer_bust_prob

ACTIONS = ("hit", "stand", "double", "split", "surrender")
_CODE = {"H": "hit", "S": "stand", "D": "double", "P": "split", "R": "surrender"}

# Dealer upcard order used by all chart tables.
UPS = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "A")

HARD_CHART: dict[int, str] = {
    5: "HHHHHHHHHH",
    6: "HHHHHHHHHH",
    7: "HHHHHHHHHH",
    8: "HHHHHHHHHH",
    9: "HDDDDHHHHH",
    10: "DDDDDDDDHH",
    11: "DDDDDDDDDD",
    12: "HHSSSHHHHH",
    13: "SSSSSHHHHH",
    14: "SSSSSHHHHH",
    15: "SSSSSHHHHH",
    16: "SSSSSHHHHH",
    17: "SSSSSSSSSS",
    18: "SSSSSSSSSS",
    19: "SSSSSSSSSS",
    20: "SSSSSSSSSS",
    21: "SSSSSSSSSS",
}

SOFT_CHART: dict[int, str] = {
    13: "HHHDDHHHHH",
    14: "HHHDDHHHHH",
    15: "HHDDDHHHHH",
    16: "HHDDDHHHHH",
    17: "HDDDDHHHHH",
    18: "DDDDDSSHHH",
    19: "SSSSDSSSSS",
    20: "SSSSSSSSSS",
    21: "SSSSSSSSSS",
}

PAIR_CHART: dict[str, str] = {
    "2": "PPPPPPHHHH",
    "3": "PPPPPPHHHH",
    "4": "HHHPPHHHHH",
    "5": "DDDDDDDDHH",
    "6": "PPPPPHHHHH",
    "7": "PPPPPPHHHH",
    "8": "PPPPPPPPPR",
    "9": "PPPPPSPPSS",
    "10": "SSSSSSSSSS",
    "A": "PPPPPPPPPP",
}


def normalize_up(up: Card | str) -> str:
    rank = up.rank if isinstance(up, Card) else up
    return "10" if rank in ("10", "J", "Q", "K") else rank


def _up_index(up: Card | str) -> int:
    return UPS.index(normalize_up(up))


def _pair_key(cards: Sequence[Card]) -> str | None:
    if not is_pair(cards):
        return None
    return "A" if cards[0].is_ace else str(cards[0].hard_value) if cards[0].hard_value < 10 else "10"


def chart_action(
    cards: Sequence[Card],
    up: Card | str,
    *,
    initial: bool = True,
    surrender_allowed: bool = True,
    ignore_pair: bool = False,
) -> str:
    """Return the raw chart letter H/S/D/P/R for this hand."""
    if not cards:
        return "H"
    total, soft = hand_value(cards)
    up_rank = normalize_up(up)
    idx = _up_index(up_rank)
    pair = _pair_key(cards)

    if initial and surrender_allowed and len(cards) == 2 and not soft:
        if pair == "8" and up_rank == "A":
            return "R"
    if initial and surrender_allowed and len(cards) == 2:
        if pair == "8" and up_rank == "A":
            return "R"
        if pair is None and not soft:
            if total == 15 and up_rank in ("10", "A"):
                return "R"
            if total == 16 and up_rank in ("9", "10", "A"):
                return "R"
            if total == 17 and up_rank == "A":
                return "R"

    if pair is not None and not ignore_pair:
        return PAIR_CHART[pair][idx]
    if soft:
        return SOFT_CHART.get(min(max(total, 13), 21), "S")[idx]
    return HARD_CHART[min(max(total, 5), 21)][idx]


def hand_key(cards: Sequence[Card]) -> str:
    """Human label for stats: '16', 'A,7 (soft 18)', '8,8'."""
    if not cards:
        return "—"
    pair = _pair_key(cards)
    total, soft = hand_value(cards)
    if pair is not None:
        return f"{pair},{pair}"
    if soft and total <= 21:
        ranks = ",".join(c.rank for c in cards)
        return f"{ranks} (soft {total})"
    return str(total)


@dataclass(frozen=True)
class Advice:
    action: str          # what the player should do *given what is legal*
    chart_action: str    # what the chart says with every option available
    why: str
    note: str = ""

    @property
    def fallback(self) -> bool:
        return self.action != self.chart_action


def _label(action: str) -> str:
    return action


def _fallback(
    cards: Sequence[Card],
    up: Card | str,
    legal: set[str],
    chart: str,
    *,
    initial: bool,
    surrender_allowed: bool,
) -> tuple[str, str]:
    """Best legal action when the chart's first choice is unavailable."""
    up_rank = normalize_up(up)
    total, soft = hand_value(cards)
    pair = _pair_key(cards)
    note_parts: list[str] = []

    # Split unavailable: evaluate the hand as a total instead.
    if chart == "split":
        note_parts.append("Splitting isn't available here, so play the total.")
        if pair == "8" and up_rank == "A" and "surrender" in legal:
            return "surrender", " ".join(note_parts)
        if pair == "A":
            return ("hit" if "hit" in legal else "stand"), " ".join(note_parts)
        # Re-evaluate as a normal total (8,8 -> hard 16, 9,9 -> hard 18...).
        sub = chart_action(
            cards, up_rank, initial=initial,
            surrender_allowed="surrender" in legal, ignore_pair=True,
        )
        if sub in ("H", "S", "D") and _CODE[sub] in legal:
            return _CODE[sub], " ".join(note_parts)
        return ("stand" if total >= 17 else "hit"), " ".join(note_parts)

    # Surrender unavailable: fall through to the hit/stand/double chart.
    if chart == "surrender":
        note_parts.append("Surrender isn't offered on this hand; play it out.")
        legal2 = set(legal) - {"surrender"}
        sub = chart_action(cards, up_rank, initial=initial, surrender_allowed=False)
        if _CODE[sub] in legal2:
            return _CODE[sub], " ".join(note_parts)
        return ("stand" if total >= 17 else "hit"), " ".join(note_parts)

    # Double unavailable: hit, except the hands that must stand.
    if chart == "double":
        note_parts.append("Chart says double; doubling isn't available — take the next best play.")
        if soft and total >= 18:
            return ("stand" if "stand" in legal else "hit"), " ".join(note_parts)
        return ("hit" if "hit" in legal else "stand"), " ".join(note_parts)

    return ("hit" if "hit" in legal else "stand"), " ".join(note_parts)


def _why(cards: Sequence[Card], up: Card | str, action: str, chart: str, note: str) -> str:
    up_rank = normalize_up(up)
    total, soft = hand_value(cards)
    bust = dealer_bust_prob(up_rank)
    key = hand_key(cards)
    dealer_phrase = f"dealer {up_rank}"
    prefix = f"{note} " if note else ""

    if action == "surrender":
        return (
            f"{prefix}Hard {total} vs {dealer_phrase} loses more than half its stake "
            f"even played perfectly — surrender salvages half the bet."
        )
    if action == "split":
        if _pair_key(cards) == "A":
            return f"{prefix}Split aces: two chances at 21, one card each, no resplit."
        if _pair_key(cards) == "8":
            return (
                f"{prefix}16 is the worst total; two hands starting at 8 beat one 16, "
                f"and the {up_rank} is beatable."
            )
        if _pair_key(cards) == "9":
            return (
                f"{prefix}Split 9s vs {up_rank}: your 18 is strong, but two 9s "
                f"build more winning hands against this upcard."
            )
        return f"{prefix}Split the pair: two starting hands are worth more than this total vs {up_rank}."
    if action == "double":
        if soft:
            return (
                f"{prefix}Soft {total} vs {dealer_phrase} is a favorite — double to "
                f"get another unit down while you can't bust."
            )
        return (
            f"{prefix}Hard {total} vs {dealer_phrase} is strong enough to double: "
            f"you can't bust and the dealer is under pressure."
        )
    if action == "stand":
        if total >= 17:
            return (
                f"{prefix}Stand on {key}: the {dealer_phrase} must come to you, "
                f"and it busts about {bust:.0%} of the time."
            )
        if 12 <= total <= 16:
            return (
                f"{prefix}Stand on {key} vs {dealer_phrase}: the dealer busts about "
                f"{bust:.0%} of the time, so don't risk busting first."
            )
        return f"{prefix}Stand on {key}; drawing adds risk without enough reward."
    # hit
    if soft:
        return (
            f"{prefix}Soft {total} vs {dealer_phrase} isn't strong enough to stand — "
            f"hit, and you can't bust on the next card."
        )
    return (
        f"{prefix}Hit {key} vs {dealer_phrase}: standing loses too often here; "
        f"draw to improve, even with bust risk."
    )


def best_action(
    cards: Sequence[Card],
    up: Card | str,
    *,
    legal: Iterable[str],
    initial: bool = True,
) -> Advice:
    legal_set = {a for a in legal if a in ACTIONS}
    # chart_action always shows the full chart (surrender included) in feedback.
    chart = chart_action(cards, up, initial=initial, surrender_allowed=True)
    wanted = _CODE[chart]
    note = ""
    if wanted in legal_set:
        action = wanted
    else:
        action, note = _fallback(
            cards, up, legal_set, wanted, initial=initial,
            surrender_allowed="surrender" in legal_set,
        )
    if action not in legal_set:
        action = "stand" if "stand" in legal_set else "hit"
    return Advice(
        action=action,
        chart_action=wanted,
        why=_why(cards, up, action, chart, note),
        note=note,
    )
