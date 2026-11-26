"""Headless UI tests: real key presses, feedback gating, help, resize."""

import pytest
from textual.widgets import Static

from felt.app import FeltApp, HelpScreen, RecapScreen
from felt.cards import Card, Shoe
from felt.engine import Game
from felt.session import StatsStore


def make_game(*tokens: str, bankroll: float = 1000.0) -> Game:
    cards = [Card(t[:-1], t[-1]) for t in tokens]
    return Game(shoe=Shoe(cards=cards, seed=1), bankroll=bankroll)


def text_of(app: FeltApp, selector: str) -> str:
    widget = app.query_one(selector, Static)
    content = widget.content
    return content.plain if hasattr(content, "plain") else str(content)


def screen_text(app: FeltApp) -> str:
    return "\n".join(text_of(app, sel) for sel in ("#topbar", "#dealer", "#player", "#coach", "#prompt", "#keys"))


@pytest.mark.asyncio
async def test_boot_shows_table_and_deal(tmp_path):
    game = make_game("10♠", "9♥", "7♦", "8♣")
    app = FeltApp(game=game, store=StatsStore(tmp_path / "s.json"))
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        text = screen_text(app)
        assert "F E L T" in text
        assert "$1,000" in text
        assert "Enter ▸ deal" in text
        assert game.phase == "betting"
        await pilot.press("enter")
        await pilot.pause()
        assert game.phase == "player"
        table = text_of(app, "#player")
        assert "10" in table and "7" in table
        assert "HAND 1" in table


@pytest.mark.asyncio
async def test_feedback_stays_until_acknowledged(tmp_path):
    # 16 vs 10 -> chart says surrender.
    game = make_game("10♠", "10♥", "6♦", "9♣", "5♠")
    app = FeltApp(game=game, store=StatsStore(tmp_path / "s.json"))
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("h")
        await pilot.pause()
        assert game.phase == "feedback"
        coach = text_of(app, "#coach")
        assert "Chart: surrender" in coach
        assert "surrender salvages" in coach
        # Pressing another action must not erase or advance the feedback.
        await pilot.press("s")
        await pilot.pause()
        assert game.phase == "feedback"
        assert text_of(app, "#coach") == coach
        await pilot.press("enter")
        await pilot.pause()
        assert game.phase in ("settled", "broke")


@pytest.mark.asyncio
async def test_correct_decision_feedback(tmp_path):
    game = make_game("10♠", "6♥", "6♦", "10♣")
    app = FeltApp(game=game, store=StatsStore(tmp_path / "s.json"))
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("enter")
        await pilot.press("s")
        await pilot.pause()
        coach = text_of(app, "#coach")
        assert "Correct — stand" in coach
        assert "busts about" in coach
        await pilot.press("enter")
        await pilot.pause()
        assert game.phase in ("settled", "broke")


@pytest.mark.asyncio
async def test_insurance_flow_keys_and_feedback(tmp_path):
    game = make_game("10♠", "A♥", "9♦", "5♣", "2♠", "3♥")
    app = FeltApp(game=game, store=StatsStore(tmp_path / "s.json"))
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("enter")
        await pilot.pause()
        assert game.phase == "insurance"
        assert "Insurance?" in text_of(app, "#prompt")
        await pilot.press("n")
        await pilot.pause()
        assert game.phase == "feedback"
        assert "Correct — decline insurance" in text_of(app, "#coach")
        await pilot.press("enter")
        await pilot.pause()
        assert game.phase == "player"


@pytest.mark.asyncio
async def test_buying_insurance_is_graded_as_mistake(tmp_path):
    game = make_game("10♠", "A♥", "9♦", "5♣", "2♠", "3♥")
    app = FeltApp(game=game, store=StatsStore(tmp_path / "s.json"))
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("enter")
        await pilot.press("i")
        await pilot.pause()
        assert "Chart: decline insurance" in text_of(app, "#coach")
        assert game.bankroll == 962.5


@pytest.mark.asyncio
async def test_bet_adjustment_keys(tmp_path):
    game = make_game("10♠", "9♥", "7♦", "8♣")
    app = FeltApp(game=game, store=StatsStore(tmp_path / "s.json"))
    async with app.run_test(size=(80, 24)) as pilot:
        assert game.base_bet == 25
        await pilot.press("plus")
        await pilot.pause()
        assert game.base_bet == 30
        await pilot.press("minus")
        await pilot.press("minus")
        await pilot.pause()
        assert game.base_bet == 20


@pytest.mark.asyncio
async def test_illegal_action_shows_notice_not_advice(tmp_path):
    game = make_game("10♠", "6♥", "6♦", "10♣")
    app = FeltApp(game=game, store=StatsStore(tmp_path / "s.json"))
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("enter")
        await pilot.press("p")
        await pilot.pause()
        assert game.phase == "player"
        assert "isn't available" in text_of(app, "#prompt")
        assert game.stats.total_decisions == 0


@pytest.mark.asyncio
async def test_help_screen_and_back(tmp_path):
    game = make_game("10♠", "9♥", "7♦", "8♣")
    app = FeltApp(game=game, store=StatsStore(tmp_path / "s.json"))
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("question_mark")
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)
        help_text = " ".join(str(w.content) for w in app.screen.query(Static))
        assert "RULES AT THIS TABLE" in help_text
        assert "Split aces" in help_text
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, HelpScreen)
        assert game.phase == "betting"


@pytest.mark.asyncio
async def test_recap_screen_shows_accuracy_and_mistakes(tmp_path):
    game = make_game("10♠", "10♥", "6♦", "9♣", "5♠")
    app = FeltApp(game=game, store=StatsStore(tmp_path / "s.json"))
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("enter")
        await pilot.press("h")
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("q")
        await pilot.pause()
        await pilot.pause()
        assert isinstance(app.screen, RecapScreen)
        body = " ".join(str(w.content) for w in app.screen.query(Static))
        assert "SESSION RECAP" in body
        assert "MISTAKES TO REVIEW" in body
        assert "surrender" in body
        await pilot.press("escape")
        await pilot.pause()
        assert game.phase in ("settled", "broke")


@pytest.mark.asyncio
@pytest.mark.parametrize("size,wide", [((80, 24), False), ((120, 40), True)])
async def test_layout_at_sizes_and_screenshot(tmp_path, size, wide):
    game = make_game("10♠", "9♥", "7♦", "8♣")
    app = FeltApp(game=game, store=StatsStore(tmp_path / "s.json"))
    async with app.run_test(size=size) as pilot:
        await pilot.press("enter")
        await pilot.press("s")
        await pilot.pause()
        assert app.wide is wide
        art = tmp_path / f"felt-{size[0]}x{size[1]}.svg"
        svg = app.export_screenshot()
        art.write_text(svg, encoding="utf-8")
        assert "<svg" in svg and len(svg) > 1000
        # No line of the table should exceed the terminal width.
        for line in screen_text(app).splitlines():
            assert len(line) <= size[0]


@pytest.mark.asyncio
async def test_resize_keeps_rendering(tmp_path):
    game = make_game("10♠", "9♥", "7♦", "8♣")
    app = FeltApp(game=game, store=StatsStore(tmp_path / "s.json"))
    async with app.run_test(size=(80, 24)) as pilot:
        assert app.wide is False
        await pilot.resize_terminal(120, 40)
        await pilot.pause()
        assert app.wide is True
        await pilot.resize_terminal(80, 24)
        await pilot.pause()
        assert app.wide is False
        assert "F E L T" in screen_text(app)


@pytest.mark.asyncio
async def test_session_persisted_after_round(tmp_path):
    store = StatsStore(tmp_path / "stats.json")
    game = make_game("10♠", "10♥", "6♦", "9♣")
    app = FeltApp(game=game, store=store)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("enter")
        await pilot.press("s")
        await pilot.press("enter")
        await pilot.pause()
    assert store.path.exists()
    loaded = store.load()
    assert loaded.total_decisions == 1
    assert loaded.rounds == 1


@pytest.mark.asyncio
async def test_four_hands_fit_within_80_columns(tmp_path):
    cards = [
        "8♠", "6♥", "8♦", "10♣", "8♣", "8♥", "8♦", "2♠",
        "2♥", "3♣", "4♦", "5♠", "6♠", "7♥", "9♦", "10♠",
    ]
    game = Game(shoe=Shoe(cards=[Card(t[:-1], t[-1]) for t in cards], seed=1), bankroll=1000)
    app = FeltApp(game=game, store=StatsStore(tmp_path / "s.json"))
    async with app.run_test(size=(80, 24)) as pilot:
        for key in ("enter", "p", "enter", "p", "enter", "p"):
            await pilot.press(key)
            await pilot.pause()
        assert len(game.hands) == 4
        player = text_of(app, "#player")
        assert max(len(line) for line in player.splitlines()) <= 76
        assert all(f"H{i + 1}" in player for i in range(4))
