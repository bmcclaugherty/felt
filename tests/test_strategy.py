"""Basic-strategy chart for 6 decks, H17, DAS, late surrender, 3:2.

Expected cells below are the rules-fixed chart (sources in README):
  * Wizard of Odds — late surrender, four or more decks, total dependent (H17 column)
  * Blackjack Apprenticeship H17 basic strategy (LATE SURRENDER panel)
  * Wizard of Odds / blackjacktrainer.fyi 6D H17 DAS chart for hard/soft/pair cells
"""

import pytest

from felt.cards import Card
from felt.strategy import Advice, best_action, chart_action, hand_key

UP_RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "A"]


def c(rank: str) -> Card:
    return Card(rank, "♠")


def cards(*ranks: str) -> list[Card]:
    return [c(r) for r in ranks]


def act(*ranks: str, up: str, legal=None, initial: bool = True) -> Advice:
    legal = legal if legal is not None else {"hit", "stand", "double", "split", "surrender"}
    return best_action(cards(*ranks), c(up), legal=legal, initial=initial)


# --- Hard totals: exact chart row by row -------------------------------------
HARD = {
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
    15: "SSSSSHHHRR",
    16: "SSSSSHHRRR",
    17: "SSSSSSSSSR",
    18: "SSSSSSSSSS",
    19: "SSSSSSSSSS",
    20: "SSSSSSSSSS",
}


@pytest.mark.parametrize("total,row", sorted(HARD.items()))
def test_hard_chart_rows(total, row):
    # Build a two-card hard hand with the requested total.
    first, second = (10, total - 10) if total >= 12 else (total - 2, 2)
    for up, expected in zip(UP_RANKS, row):
        assert chart_action(cards(str(first), str(second)), up) == expected, (total, up)


SOFT = {
    ("A", "2"): "HHHDDHHHHH",
    ("A", "3"): "HHHDDHHHHH",
    ("A", "4"): "HHDDDHHHHH",
    ("A", "5"): "HHDDDHHHHH",
    ("A", "6"): "HDDDDHHHHH",
    ("A", "7"): "DDDDDSSHHH",
    ("A", "8"): "SSSSDSSSSS",
    ("A", "9"): "SSSSSSSSSS",
}


@pytest.mark.parametrize("hand,row", sorted(SOFT.items()))
def test_soft_chart_rows(hand, row):
    for up, expected in zip(UP_RANKS, row):
        assert chart_action(cards(*hand), up) == expected, (hand, up)


PAIRS = {
    ("2", "2"): "PPPPPPHHHH",
    ("3", "3"): "PPPPPPHHHH",
    ("4", "4"): "HHHPPHHHHH",
    ("5", "5"): "DDDDDDDDHH",
    ("6", "6"): "PPPPPHHHHH",
    ("7", "7"): "PPPPPPHHHH",
    ("8", "8"): "PPPPPPPPPR",
    ("9", "9"): "PPPPPSPPSS",
    ("10", "10"): "SSSSSSSSSS",
    ("A", "A"): "PPPPPPPPPP",
}


@pytest.mark.parametrize("pair,row", sorted(PAIRS.items()))
def test_pair_chart_rows(pair, row):
    for up, expected in zip(UP_RANKS, row):
        assert chart_action(cards(*pair), up) == expected, (pair, up)


def test_surrender_is_h17_specific():
    # H17: 15 vs A, 17 vs A, 8+8 vs A surrender. S17 would not.
    assert chart_action(cards("10", "5"), "A") == "R"
    assert chart_action(cards("10", "7"), "A") == "R"
    assert chart_action(cards("8", "8"), "A") == "R"
    assert chart_action(cards("10", "5"), "10") == "R"
    assert chart_action(cards("10", "6"), "9") == "R"
    assert chart_action(cards("10", "6"), "8") == "H"
    # 17 vs 10 stands; only the ace is a surrender.
    assert chart_action(cards("10", "7"), "10") == "S"


def test_11_vs_ace_doubles_in_h17():
    assert chart_action(cards("6", "5"), "A") == "D"


def test_soft_19_vs_6_doubles_else_stands():
    assert chart_action(cards("A", "8"), "6") == "D"
    assert chart_action(cards("A", "8"), "5") == "S"


def test_pair_of_tens_is_not_split():
    assert chart_action(cards("K", "Q"), "6") == "S"
    assert chart_action(cards("10", "J"), "5") == "S"


def test_hand_key_labels():
    assert hand_key(cards("10", "6")) == "16"
    assert hand_key(cards("A", "7")) == "A,7 (soft 18)"
    assert hand_key(cards("8", "8")) == "8,8"


# --- Legal-action fallbacks --------------------------------------------------
def test_double_unavailable_on_11_falls_back_to_hit_with_note():
    advice = act("6", "5", up="6", legal={"hit", "stand"})
    assert advice.action == "hit"
    assert advice.chart_action == "double"
    assert "double" in advice.note.lower()
    assert advice.why


def test_double_unavailable_soft_18_stands():
    advice = act("A", "7", up="3", legal={"hit", "stand"})
    assert advice.action == "stand"


def test_double_unavailable_soft_19_stands():
    advice = act("A", "8", up="6", legal={"hit", "stand"})
    assert advice.action == "stand"


def test_split_unavailable_8s_vs_10_hits():
    advice = act("8", "8", up="10", legal={"hit", "stand"})
    assert advice.action == "hit"
    assert advice.chart_action == "split"
    assert advice.note


def test_split_unavailable_8s_vs_6_stands():
    advice = act("8", "8", up="6", legal={"hit", "stand"})
    assert advice.action == "stand"


def test_surrender_unavailable_16_vs_10_hits():
    advice = act("10", "6", up="10", legal={"hit", "stand", "double", "split"})
    assert advice.action == "hit"
    assert advice.chart_action == "surrender"


def test_surrender_only_when_initial_hand():
    advice = act("10", "6", up="10", legal={"hit", "stand", "surrender"}, initial=False)
    assert advice.action == "hit"


def test_split_aces_advice_is_split():
    assert act("A", "A", up="9").action == "split"


def test_coach_reason_mentions_dealer_card():
    advice = act("10", "6", up="6")
    assert "6" in advice.why
    assert len(advice.why) > 20


def test_advice_reports_action_label():
    advice = act("10", "6", up="10")
    assert advice.action == "surrender"
    assert "surrender" in advice.why.lower()
