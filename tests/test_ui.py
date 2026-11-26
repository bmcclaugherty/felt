from felt.cards import Card
from felt.ui import CARD_H, CARD_W, card_lines, cards_row, combine, to_text


def test_card_dimensions_and_glyphs():
    lines = card_lines(Card("A", "♠"))
    assert len(lines) == CARD_H
    assert all(line.cell_len == CARD_W for line in lines)
    raw = to_text(lines).plain
    assert "A" in raw and "♠" in raw
    assert raw.splitlines()[0].startswith("┌")


def test_hidden_card_shows_no_rank():
    raw = to_text(card_lines(Card("K", "♦"), hidden=True)).plain
    assert "K" not in raw and "♦" not in raw
    assert "░" in raw


def test_wide_card_is_width_nine():
    lines = card_lines(Card("10", "♥"), width=9, height=6)
    assert len(lines) == 6
    assert all(line.cell_len == 9 for line in lines)
    assert "10" in to_text(lines).plain


def test_compose_two_cards_side_by_side():
    row = cards_row([Card("A", "♠"), None])
    assert len(row) == CARD_H
    assert row[0].cell_len == CARD_W * 2 + 1
    assert "A" in "\n".join(line.plain for line in row)


def test_combine_pads_shorter_block():
    a = [to_text_line("aaa")]
    b = [to_text_line("b"), to_text_line("b")]
    rows = combine([a, b], gap=1)
    assert rows[0].plain == "aaa b"
    assert rows[1].plain == "    b"


def test_combine_aligns_variable_width_blocks():
    rows = combine([
        [to_text_line("a"), to_text_line("aaaa")],
        [to_text_line("bb"), to_text_line("b")],
    ], gap=1)
    assert rows[0].plain == "a    bb"
    assert rows[1].plain == "aaaa b "


def to_text_line(s):
    from rich.text import Text

    return Text(s)
