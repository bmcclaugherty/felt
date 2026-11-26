"""Rendering primitives: big cards and horizontal composition, in Rich Text."""

from __future__ import annotations

from rich.text import Text

from .cards import Card

GOLD = "#e6c15a"
GOLD_DIM = "#a8873a"
CREAM = "#f6efdd"
RED = "#e2685f"
GREEN = "#7bdcae"
DIM = "#7e9488"
FELT = "#0a3b2a"

CARD_W = 7
CARD_H = 5


def card_lines(card: Card, hidden: bool = False, width: int = CARD_W, height: int = CARD_H) -> list[Text]:
    """A big, bordered card as ``height`` lines of exactly ``width`` cells."""
    inner = width - 2
    lines: list[Text] = []

    top = Text("┌" + "─" * inner + "┐", style=f"bold {GOLD_DIM}")
    bottom = Text("└" + "─" * inner + "┘", style=f"bold {GOLD_DIM}")

    if hidden:
        body = []
        for _ in range(height - 2):
            body.append(Text("│" + "░" * inner + "│", style=f"{GOLD_DIM} on #06281c"))
        return [top, *body, bottom]

    suit_style = RED if card.is_red else CREAM
    rank_style = f"bold {suit_style}"

    mid = height - 2
    for row in range(mid):
        if mid == 3:
            if row == 0:
                line = Text("│ ", style=GOLD_DIM)
                line.append(card.rank.ljust(inner - 2), style=rank_style)
                line.append(" │", style=GOLD_DIM)
            elif row == 1:
                line = Text("│", style=GOLD_DIM)
                line.append(card.suit.center(inner), style=f"bold {suit_style}")
                line.append("│", style=GOLD_DIM)
            else:
                line = Text("│ ", style=GOLD_DIM)
                line.append(card.rank.rjust(inner - 2), style=rank_style)
                line.append(" │", style=GOLD_DIM)
        else:
            # Wider/taller cards get a blank breathing line above and below the pip.
            if row == 0:
                line = Text("│", style=GOLD_DIM)
                line.append(" " + card.rank + " " * max(0, inner - 1 - len(card.rank)), style=rank_style)
                line.append("│", style=GOLD_DIM)
            elif row == mid - 1:
                line = Text("│", style=GOLD_DIM)
                line.append(" " * max(0, inner - 1 - len(card.rank)) + card.rank + " ", style=rank_style)
                line.append("│", style=GOLD_DIM)
            elif row == mid // 2:
                line = Text("│", style=GOLD_DIM)
                line.append(card.suit.center(inner), style=f"bold {suit_style}")
                line.append("│", style=GOLD_DIM)
            else:
                line = Text("│" + " " * inner + "│", style=GOLD_DIM)
        lines.append(line)

    if len(lines) != height - 2:
        raise AssertionError("card height mismatch")
    return [top, *lines, bottom]


def combine(blocks: list[list[Text]], gap: int = 2) -> list[Text]:
    """Lay blocks out side by side, top-aligned, padding shorter blocks."""
    if not blocks:
        return []
    widths = [b[0].cell_len if b else 0 for b in blocks]
    height = max((len(b) for b in blocks), default=0)
    out: list[Text] = []
    for row in range(height):
        line = Text()
        for i, block in enumerate(blocks):
            if i:
                line.append(" " * gap)
            if row < len(block):
                line.append_text(block[row])
            else:
                line.append(" " * widths[i])
        out.append(line)
    return out


def to_text(lines: list[Text]) -> Text:
    result = Text()
    for i, line in enumerate(lines):
        if i:
            result.append("\n")
        result.append_text(line)
    return result


def cards_row(cards: list[Card | None], width: int = CARD_W, height: int = CARD_H) -> list[Text]:
    blocks = [
        card_lines(c, hidden=c is None, width=width, height=height) if c is not None else card_lines(Card("A", "♠"), hidden=True, width=width, height=height)
        for c in cards
    ]
    return combine(blocks, gap=1)
