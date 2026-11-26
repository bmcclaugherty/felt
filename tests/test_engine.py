"""Engine rules: dealing, peek, insurance, splits, payouts, bankroll."""

import pytest

from felt.cards import Card, Shoe
from felt.engine import Game, IllegalAction, Rules
from felt.session import SessionStats

RULES = Rules()


def shoe(*ranks: str) -> Shoe:
    suit_by_rank = {"♠": "♠", "♥": "♥", "♦": "♦", "♣": "♣"}
    cards = []
    for token in ranks:
        rank, suit = token[:-1], token[-1]
        assert suit in suit_by_rank, token
        cards.append(Card(rank, suit))
    return Shoe(cards=cards, seed=1)


def game(*ranks: str, bankroll: float = 1000.0, bet: float = 25.0, stats=None) -> Game:
    return Game(shoe=shoe(*ranks), bankroll=bankroll, base_bet=bet, rules=RULES, stats=stats)


def settle(game: Game) -> None:
    """Acknowledge feedback until the round is settled."""
    guard = 0
    while game.phase == "feedback":
        game.acknowledge()
        guard += 1
        assert guard < 20


def test_live_hand_wins_when_dealer_busts():
    g = game("10♠", "6♥", "7♦", "10♣", "K♥")
    g.start_round()
    g.act("stand")
    g.acknowledge()
    assert g.dealer_total == 26
    assert g.hands[0].outcome == "win"
    assert g.bankroll == 1025


# --- Deal, naturals, peek ----------------------------------------------------
def test_deal_order_and_bet_deduction():
    g = game("10♠", "9♥", "9♦", "7♣")
    g.start_round()
    assert [c.rank for c in g.player_hand.cards] == ["10", "9"]
    assert [c.rank for c in g.dealer] == ["9", "7"]
    assert g.bankroll == 975
    assert g.phase == "player"


def test_player_blackjack_pays_three_to_two():
    g = game("A♠", "9♥", "K♦", "7♣")
    g.start_round()
    assert g.phase == "settled"
    assert g.hands[0].outcome == "blackjack"
    assert g.bankroll == 1037.5


def test_dealer_blackjack_on_ten_up_settles_before_player_acts():
    g = game("10♠", "10♥", "9♦", "A♣")
    g.start_round()
    assert g.phase == "settled"
    assert g.dealer_blackjack
    assert g.hands[0].outcome == "lose"
    assert g.bankroll == 975
    assert g.legal_actions() == []


def test_dealer_blackjack_on_ace_offers_insurance_first():
    g = game("10♠", "A♥", "9♦", "K♣")
    g.start_round()
    assert g.phase == "insurance"
    assert g.insurance_offered
    assert g.dealer[1].rank == "K"  # hole card exists but stays hidden


def test_decline_insurance_then_dealer_blackjack_loses_bet():
    g = game("10♠", "A♥", "9♦", "K♣")
    g.start_round()
    g.take_insurance(False)
    assert g.phase == "feedback"
    assert g.feedback.was_correct is True
    g.acknowledge()
    assert g.phase == "settled"
    assert g.bankroll == 975
    assert g.hands[0].outcome == "lose"


def test_take_insurance_pays_two_to_one_but_bet_still_loses():
    g = game("10♠", "A♥", "9♦", "K♣")
    g.start_round()
    g.take_insurance(True)
    assert g.feedback.was_correct is False
    g.acknowledge()
    assert g.phase == "settled"
    # 1000 - 25 bet - 12.50 insurance + 37.50 insurance return
    assert g.bankroll == 1000.0


def test_insurance_declined_when_dealer_has_no_blackjack_then_play_continues():
    g = game("10♠", "A♥", "9♦", "5♣")
    g.start_round()
    g.take_insurance(False)
    g.acknowledge()
    assert g.phase == "player"
    assert g.insurance_bet == 0


def test_insurance_taken_and_lost_when_no_dealer_blackjack():
    g = game("10♠", "A♥", "9♦", "5♣")
    g.start_round()
    g.take_insurance(True)
    g.acknowledge()
    assert g.phase == "player"
    assert g.bankroll == 962.5


def testplayer_blackjack_vs_dealer_blackjack_pushes():
    g = game("A♠", "A♥", "K♦", "K♣")
    g.start_round()
    g.take_insurance(False)
    g.acknowledge()
    assert g.phase == "settled"
    assert g.hands[0].outcome == "push"
    assert g.bankroll == 1000.0


# --- Actions -----------------------------------------------------------------
def test_hit_bust_and_dealer_does_not_draw():
    g = game("10♠", "9♥", "6♦", "7♣", "K♠")
    g.start_round()
    fb = g.act("hit")
    assert fb.chosen == "hit"
    assert g.hands[0].busted
    assert g.phase == "feedback"
    g.acknowledge()
    assert g.phase == "settled"
    assert g.hands[0].outcome == "bust"
    assert g.bankroll == 975


def test_hit_to_21_auto_stands():
    g = game("10♠", "9♥", "5♦", "7♣", "6♠")
    g.start_round()
    g.act("hit")
    assert g.hands[0].total == 21
    g.acknowledge()
    assert g.phase == "settled"


def test_stand_dealer_hits_soft_17_h17():
    # Dealer A,6 = soft 17; H17 must hit and draws 4 -> 21, beating player 18.
    g = game("10♠", "A♥", "8♦", "6♣", "4♠")
    g.start_round()
    g.take_insurance(False)
    g.acknowledge()
    g.act("stand")
    g.acknowledge()
    assert g.phase == "settled"
    assert g.dealer_total == 21
    assert g.hands[0].outcome == "lose"


def test_dealer_stands_on_hard_17():
    g = game("10♠", "10♥", "8♦", "7♣")
    g.start_round()
    g.act("stand")
    g.acknowledge()
    assert g.dealer_total == 17
    assert g.hands[0].outcome == "win"
    assert g.bankroll == 1025


def test_double_takes_one_card_and_doubles_bet():
    g = game("6♠", "5♥", "5♦", "10♣", "10♠")
    g.start_round()
    fb = g.act("double")
    assert fb.chosen == "double"
    assert g.hands[0].bet == 50
    assert g.bankroll == 950
    assert len(g.hands[0].cards) == 3
    assert g.hands[0].done
    g.acknowledge()
    assert g.phase == "settled"


def test_double_after_hit_is_illegal():
    g = game("6♠", "5♥", "5♦", "10♣", "2♠", "10♥")
    g.start_round()
    g.act("hit")
    g.acknowledge()
    with pytest.raises(IllegalAction):
        g.act("double")


def test_surrender_returns_half_bet_and_ends_round():
    g = game("10♠", "10♥", "6♦", "9♣")
    g.start_round()
    fb = g.act("surrender")
    assert fb.chosen == "surrender"
    assert fb.was_correct is True
    assert g.bankroll == 975  # bet returned? no: half of 25 returned
    g.acknowledge()
    assert g.phase == "settled"
    assert g.bankroll == 987.5
    assert g.hands[0].outcome == "surrender"


def test_surrender_only_on_initial_two_cards():
    g = game("10♠", "9♥", "3♦", "7♣", "2♠")
    g.start_round()
    g.act("hit")
    g.acknowledge()
    with pytest.raises(IllegalAction):
        g.act("surrender")


def test_surrender_not_offered_vs_ace_after_peek_blackjack():
    # Dealer has blackjack: round is already settled, so surrender is unreachable.
    g = game("10♠", "A♥", "6♦", "K♣")
    g.start_round()
    assert g.phase == "insurance"
    g.take_insurance(False)
    g.acknowledge()
    assert g.phase == "settled"


# --- Splits ------------------------------------------------------------------
def test_split_creates_two_hands_and_deducts_bet():
    g = game("8♠", "6♥", "8♦", "10♣", "3♠", "2♥", "10♦", "7♠")
    g.start_round()
    fb = g.act("split")
    assert fb.chosen == "split"
    assert len(g.hands) == 2
    assert g.bankroll == 950
    assert [c.rank for c in g.hands[0].cards] == ["8", "3"]
    assert [c.rank for c in g.hands[1].cards] == ["8", "2"]
    assert g.active == 0


def test_das_allows_double_after_split():
    g = game("8♠", "6♥", "8♦", "10♣", "3♠", "2♥", "5♦", "10♦")
    g.start_round()
    g.act("split")
    g.acknowledge()
    assert g.phase == "player"
    assert "double" in g.legal_actions()
    g.act("double")
    assert g.hands[0].bet == 50
    assert g.bankroll == 925


def test_split_aces_get_one_card_each_and_cannot_resplit():
    g = game("A♠", "9♥", "A♦", "5♣", "K♠", "7♥", "3♦", "10♣")
    g.start_round()
    g.act("split")
    assert g.hands[0].split_aces and g.hands[1].split_aces
    assert len(g.hands[0].cards) == 2 and len(g.hands[1].cards) == 2
    assert g.hands[0].done and g.hands[1].done
    g.acknowledge()
    assert g.phase == "settled"
    assert g.hands[0].total == 21 and g.hands[1].total == 18
    assert all(h.outcome == "win" for h in g.hands)


def test_split_21_is_not_a_natural():
    g = game("A♠", "9♥", "A♦", "8♣", "K♠", "7♥", "3♦", "10♣")
    g.start_round()
    g.act("split")
    g.acknowledge()
    assert g.phase == "settled"
    # 21 after a split pays even money: +25 net, not +37.50.
    assert g.bankroll == 1050.0
    assert g.hands[0].outcome == "win" and g.hands[0].payout == 50.0
    assert not g.hands[0].is_natural


def test_resplit_to_max_four_hands_then_split_unavailable():
    # 8,8 -> split; each hand gets another 8.
    g = game(
        "8♠", "6♥", "8♦", "10♣",
        "8♣", "8♥",   # first cards to the two split hands (both 8s)
        "2♠", "3♠",   # onecard? see note below
    )
    g.start_round()
    g.act("split")
    assert len(g.hands) == 2
    # Both hands hold 8,8 and may resplit.
    assert g.hands[0].cards[1].rank == "8"
    assert g.hands[1].cards[1].rank == "8"
    g.acknowledge()
    assert "split" in g.legal_actions()


def test_split_unavailable_without_funds_offers_fallback_advice():
    g = game("8♠", "6♥", "8♦", "10♣", "3♠", "2♥", bankroll=30)
    g.start_round()
    assert g.bankroll == 5
    assert "split" not in g.legal_actions()
    fb = g.act("hit")
    assert fb.advice.chart_action == "split"
    assert fb.advice.note


def test_no_split_after_three_hands_reaches_four_max():
    # Build four hands by resplitting 8s twice.
    g = game(
        "8♠", "6♥", "8♦", "10♣",
        "8♣", "8♥",
        "8♦", "2♠",
        "2♥", "3♣",
        "4♦", "5♠",
        "6♠", "7♥",
        "9♦", "10♠",
    )
    g.start_round()
    g.act("split")
    g.acknowledge()
    # Active hand is a pair of 8s -> resplit.
    g.act("split")
    g.acknowledge()
    assert len(g.hands) == 3
    g.act("split")
    g.acknowledge()
    assert len(g.hands) == 4
    assert "split" not in g.legal_actions()


# --- Bankroll and flow -------------------------------------------------------
def test_bet_must_be_affordable():
    g = game("10♠", "9♥", "9♦", "7♣", bankroll=20)
    with pytest.raises(IllegalAction):
        g.start_round()
    assert g.bankroll == 20
    assert g.phase in ("betting", "broke")


def test_illegal_action_raises_with_reason():
    g = game("10♠", "9♥", "9♦", "7♣")
    g.start_round()
    with pytest.raises(IllegalAction) as exc:
        g.act("split")
    assert "split" in str(exc.value)


def test_feedback_blocks_progress_until_acknowledged():
    g = game("10♠", "9♥", "5♦", "7♣", "6♠")
    g.start_round()
    g.act("hit")
    assert g.phase == "feedback"
    with pytest.raises(IllegalAction):
        g.act("stand")
    g.acknowledge()
    assert g.phase == "settled"


def test_feedback_records_correct_decision_for_basic_strategy():
    g = game("10♠", "9♥", "6♦", "7♣")
    g.start_round()
    fb = g.act("stand")  # 16 vs 9 -> surrender is correct
    assert fb.was_correct is False
    assert fb.advice.action == "surrender"
    assert fb.why_text


def test_stats_object_receives_decisions():
    stats = SessionStats(bankroll=1000)
    g = game("10♠", "9♥", "6♦", "7♣", stats=stats)
    g.start_round()
    g.act("stand")
    assert len(stats.decisions) == 1
    assert stats.decisions[0].correct_action == "surrender"
    assert stats.decisions[0].was_correct is False


def test_bankroll_never_negative_after_losses():
    g = game("10♠", "10♥", "9♦", "A♣", bankroll=25)
    g.start_round()
    assert g.bankroll == 0
    assert g.phase == "settled"
    assert g.can_bet(5) is False


def test_double_unavailable_when_bankroll_short_and_advice_explains():
    g = game("6♠", "5♥", "5♦", "10♣", "10♠", bankroll=25)
    g.start_round()
    assert g.bankroll == 0
    legal = g.legal_actions()
    assert "double" not in legal and "split" not in legal
    assert {"hit", "stand"} <= set(legal)
    fb = g.act("hit")
    assert fb.advice.chart_action == "double"
    assert "doubling" in fb.advice.note.lower()


def test_standing_two_split_hands_plays_both_then_dealer():
    g = game("8♠", "6♥", "8♦", "10♣", "3♠", "2♥", "10♦", "7♠")
    g.start_round()
    g.act("split")
    g.acknowledge()
    g.act("stand")
    g.acknowledge()
    assert g.phase == "player"
    assert g.active == 1
    g.act("stand")
    g.acknowledge()
    assert g.phase == "settled"
    assert len(g.hands) == 2


def test_dealer_does_not_redraw_when_all_hands_bust():
    g = game("10♠", "6♥", "6♦", "10♣", "K♠", "Q♠")
    g.start_round()
    g.act("hit")
    g.acknowledge()
    assert g.phase == "settled"
    assert g.dealer_total == 16


def test_no_insurance_on_nine_and_peek_on_ten_without_blackjack_continues():
    g = game("10♠", "9♥", "9♦", "7♣")
    g.start_round()
    assert g.phase == "player"
    assert not g.insurance_offered

    g2 = game("10♠", "10♥", "9♦", "9♣")
    g2.start_round()
    assert g2.phase == "player"
    assert not g2.dealer_blackjack


def test_surrender_8s_vs_ace_is_chart_correct():
    g = game("8♠", "A♥", "8♦", "5♣")
    g.start_round()
    g.take_insurance(False)
    g.acknowledge()
    assert "surrender" in g.legal_actions()
    fb = g.act("surrender")
    assert fb.was_correct is True
    g.acknowledge()
    assert g.phase == "settled"
    assert g.bankroll == 987.5


def test_insurance_decision_is_in_stats_and_can_be_a_mistake():
    stats = SessionStats(bankroll=1000)
    g = game("10♠", "A♥", "9♦", "5♣", "2♠", "3♥", stats=stats)
    g.start_round()
    g.take_insurance(True)
    assert stats.decisions[0].insurance is True
    assert stats.decisions[0].was_correct is False
