from felt.cards import Card, Shoe, hand_value, is_blackjack


def test_card_values():
    assert Card("A", "♠").hard_value == 1
    assert Card("K", "♥").hard_value == 10
    assert Card("10", "♦").hard_value == 10
    assert Card("7", "♣").hard_value == 7


def test_hand_value_soft_ace():
    total, soft = hand_value([Card("A", "♠"), Card("6", "♥")])
    assert (total, soft) == (17, True)
    total, soft = hand_value([Card("A", "♠"), Card("6", "♥"), Card("10", "♦")])
    assert (total, soft) == (17, False)


def test_two_aces_are_soft_twelve():
    total, soft = hand_value([Card("A", "♠"), Card("A", "♥")])
    assert (total, soft) == (12, True)


def test_blackjack_only_natural_two_card_21():
    assert is_blackjack([Card("A", "♠"), Card("K", "♥")])
    assert not is_blackjack([Card("A", "♠"), Card("5", "♥"), Card("5", "♦")])
    assert not is_blackjack([Card("K", "♠"), Card("Q", "♥"), Card("A", "♦")])


def test_shoe_six_decks_and_deterministic_seed():
    a = Shoe(seed=7)
    b = Shoe(seed=7)
    assert len(a.cards) == 312
    assert [a.draw().as_tuple() for _ in range(20)] == [b.draw().as_tuple() for _ in range(20)]


def test_injected_shoe_pops_in_order():
    cards = [Card("A", "♠"), Card("9", "♥"), Card("5", "♦"), Card("K", "♣")]
    shoe = Shoe(cards=cards, seed=1)
    assert shoe.draw().as_tuple() == ("A", "♠")
    assert shoe.draw().as_tuple() == ("9", "♥")
    assert shoe.remaining == 2


def test_shoe_reshuffle_flag_at_penetration():
    shoe = Shoe(seed=3)
    for _ in range(int(312 * 0.75)):
        shoe.draw()
    assert shoe.needs_shuffle


def test_display_hidden_card():
    c = Card("Q", "♦")
    assert "Q" in c.face()
    assert c.hidden_face().strip() != c.face().strip()
