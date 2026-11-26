"""Render preview screenshots (SVG + optional PNG) without a terminal.

Usage: .venv/bin/python scripts/preview.py
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from felt.app import FeltApp
from felt.cards import Card, Shoe
from felt.engine import Game
from felt.session import SessionStats, StatsStore

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts"


def demo_game() -> Game:
    # 8,8 vs 6: split, then hit the first hand to 21, then stand the second.
    cards = ["8♠", "6♥", "8♦", "10♣", "3♠", "2♥", "10♦", "7♠"]
    shoe = Shoe(cards=[Card(t[:-1], t[-1]) for t in cards], seed=1)
    stats = SessionStats(bankroll=1000)
    game = Game(shoe=shoe, bankroll=1000, stats=stats)
    return game


async def shot(size: tuple[int, int], name: str) -> None:
    game = demo_game()
    store = StatsStore(ROOT / "artifacts" / "preview-stats.json")
    app = FeltApp(game=game, store=store)
    async with app.run_test(size=size) as pilot:
        await pilot.press("enter")
        await pilot.press("p")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        svg = app.export_screenshot()
        (ART / f"{name}.svg").write_text(svg, encoding="utf-8")
        print(f"wrote {ART / (name + '.svg')}")
        try:
            import cairosvg

            cairosvg.svg2png(bytestring=svg.encode(), write_to=str(ART / f"{name}.png"), scale=1)
            print(f"wrote {ART / (name + '.png')}")
        except Exception as exc:  # pragma: no cover - optional tooling
            print(f"(png skipped: {exc})")


async def main() -> None:
    ART.mkdir(exist_ok=True)
    await shot((80, 24), "felt-80x24")
    await shot((120, 40), "felt-120x40")


if __name__ == "__main__":
    asyncio.run(main())
