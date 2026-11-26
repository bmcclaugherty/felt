"""Felt — a blackjack table that coaches every decision after you make it."""

from __future__ import annotations

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Static

from .engine import Game, IllegalAction
from .session import SessionStats, StatsStore
from .ui import CARD_H, CARD_W, DIM, GOLD, GREEN, RED, cards_row, combine, to_text

ACTION_KEYS = {
    "h": "hit",
    "s": "stand",
    "d": "double",
    "p": "split",
    "r": "surrender",
}

KEY_HINTS = "h hit   s stand   d double   p split   r surrender   ± bet   ? help   t stats   q recap"


def money(value: float) -> str:
    return f"${value:,.2f}" if value % 1 else f"${value:,.0f}"


class TableScreen(Screen):
    """Default screen; owns resize so card sizes adapt live."""

    def on_resize(self, event) -> None:
        app = self.app
        if hasattr(app, "_size_cards"):
            app._size_cards()
            app._render()


class FeltApp(App):
    BINDINGS = [
        ("question_mark", "help", "Rules"),
        ("f1", "help", "Rules"),
        ("t", "stats", "Stats"),
        ("q", "recap", "Recap"),
        ("f2", "reset", "Reset"),
    ]

    CSS = """
    Screen {
        background: #062b1e;
        color: #f6efdd;
    }
    #topbar {
        height: 1;
        background: #04241a;
        color: #e6c15a;
        padding: 0 1;
    }
    #table {
        height: 1fr;
        padding: 1 2 0 2;
        align-horizontal: center;
        align-vertical: middle;
    }
    #dealer, #player {
        height: auto;
        width: auto;
    }
    #handwrap {
        height: auto;
        width: auto;
    }
    #player {
        margin-top: 1;
    }
    #coach {
        height: 6;
        border: round #b8912f;
        background: #06281c;
        padding: 0 1;
        margin: 0 2;
    }
    #prompt {
        height: 1;
        color: #e6c15a;
        padding: 0 3;
    }
    #keys {
        height: 1;
        background: #04241a;
        color: #7e9488;
        padding: 0 1;
    }
    ModalScreen {
        background: #041c14 85%;
    }
    .modal-box {
        width: 88%;
        max-width: 100;
        height: 82%;
        border: round #b8912f;
        background: #062b1e;
        padding: 1 2;
    }
    .modal-scroll {
        height: 1fr;
    }
    .modal-foot {
        height: 1;
        color: #e6c15a;
    }
    """

    def __init__(
        self,
        game: Game | None = None,
        stats: SessionStats | None = None,
        store: StatsStore | None = None,
    ) -> None:
        super().__init__()
        self.store = store or StatsStore()
        self.stats = stats if stats is not None else self.store.load()
        self.game = game or Game(bankroll=self.stats.bankroll)
        self.game.stats = self.stats
        self.stats.bankroll = self.game.bankroll
        self.notice = ""
        self._saved_round = False
        self.wide = False

    def get_default_screen(self) -> Screen:
        return TableScreen(id="_default")

    # -- composition -------------------------------------------------------
    def compose(self) -> ComposeResult:
        yield Static(id="topbar")
        with Vertical(id="table"):
            with Vertical(id="handwrap"):
                yield Static(id="dealer")
                yield Static(id="player")
        yield Static(id="coach")
        yield Static(id="prompt")
        yield Static(id="keys")

    def on_mount(self) -> None:
        self._size_cards()
        self._render()

    def _size_cards(self) -> None:
        self.wide = self.size.width >= 108

    @property
    def card_w(self) -> int:
        return 11 if self.wide else CARD_W

    @property
    def card_h(self) -> int:
        return 7 if self.wide else CARD_H

    # -- rendering ---------------------------------------------------------
    def _render(self) -> None:
        if not self.is_mounted:
            return
        self._update_topbar()
        self._update_table()
        self._update_coach()
        self._update_prompt()
        self._update_keys()
        if self.game.phase in ("settled", "broke") and not self._saved_round:
            self._saved_round = True
            self._persist()

    def _update_topbar(self) -> None:
        g = self.game
        t = Text()
        t.append("F E L T", style=f"bold {GOLD}")
        t.append("   ")
        t.append(money(g.bankroll), style=f"bold {GREEN if g.bankroll >= 1000 else '#f6efdd'}")
        t.append("  ·  ", style=DIM)
        t.append(f"bet {money(g.base_bet)}", style="#f6efdd")
        t.append("  ·  ", style=DIM)
        t.append("6D H17 DAS LS", style=DIM)
        t.append("  ·  ", style=DIM)
        t.append(f"shoe {int(100 * g.shoe.remaining / max(1, g.shoe.total))}%", style=DIM)
        self.query_one("#topbar", Static).update(t)

    def _update_table(self) -> None:
        g = self.game
        w, h = self.card_w, self.card_h

        dealer = Text()
        dealer.append("D E A L E R", style=f"bold {GOLD}")
        if g.dealer:
            if g.hole_revealed:
                soft = any(c.is_ace for c in g.dealer) and g.dealer_total <= 21
                label = f"   {g.dealer_total}" + (" soft" if soft else "")
                dealer.append(f"   {label}", style="#f6efdd")
            else:
                dealer.append(f"   shows {g.dealer[0].rank}", style=DIM)
        dealer.append("\n")
        if g.dealer:
            dealer.append_text(to_text(cards_row(g.dealer_cards(), width=w, height=h)))
        self.query_one("#dealer", Static).update(dealer)

        player = Text()
        if not g.hands:
            player.append("Y O U", style=f"bold {GOLD}")
            player.append("\n\n")
            player.append("Place a bet, then press Enter to deal.", style=DIM)
        else:
            blocks: list[list[Text]] = []
            compact = len(g.hands) > 2
            for i, hand in enumerate(g.hands):
                active = i == g.active and g.phase in ("player", "feedback") and not hand.done
                label = Text()
                name = f"H{i + 1}" if compact else f"HAND {i + 1}"
                if not compact:
                    label.append("▸ " if active else "  ", style=GOLD if active else DIM)
                label.append(name, style=f"bold {GOLD}" if active else DIM)
                label.append(f" {money(hand.bet)}", style=DIM)
                if hand.cards:
                    label.append(f" · {hand.total}", style=RED if hand.busted else "#f6efdd")
                if compact:
                    if hand.busted:
                        label.append(" BUST", style=f"bold {RED}")
                    elif hand.outcome:
                        tag = {"blackjack": " BJ", "win": " W", "lose": " L", "push": " P", "surrender": " SUR"}.get(hand.outcome, "")
                        label.append(tag, style=GREEN if hand.outcome in ("win", "blackjack") else DIM)
                    elif hand.done:
                        label.append(" DBL" if hand.doubled else " S", style=DIM)
                elif hand.busted:
                    label.append("  BUST", style=f"bold {RED}")
                elif hand.outcome:
                    label.append(f"  {hand.outcome.upper()}", style=GREEN if hand.outcome in ("win", "blackjack") else DIM)
                elif hand.done:
                    label.append("  doubled" if hand.doubled else "  stood", style=DIM)
                block = [label, *cards_row(hand.cards, width=w, height=h)]
                blocks.append(block)
            player.append("Y O U", style=f"bold {GOLD}")
            player.append("\n")
            player.append_text(to_text(combine(blocks, gap=3)))
        self.query_one("#player", Static).update(player)

    def _update_coach(self) -> None:
        g = self.game
        fb = g.feedback or g.last_feedback
        t = Text()
        if fb is None:
            t.append("C O A C H", style=f"bold {GOLD}")
            t.append("\n")
            if g.phase == "insurance":
                t.append("Insurance is offered before the dealer peeks. Buy or decline — then the coach grades it.", style=DIM)
            else:
                t.append("Decide first, learn after. Every action is graded against the chart.", style=DIM)
        else:
            if fb.insurance:
                head = "✓ Correct — decline insurance" if fb.was_correct else "✗ Chart: decline insurance"
            elif fb.was_correct:
                head = f"✓ Correct — {fb.chosen}"
            else:
                head = f"✗ Chart: {fb.advice.action}"
            t.append(head, style=f"bold {GREEN if fb.was_correct else RED}")
            if fb.hand and not fb.insurance:
                t.append(f"   hand {g.active + 1} · {fb.hand} vs {fb.up}", style=DIM)
            if fb.advice.fallback:
                t.append(f"   ({fb.advice.chart_action} unavailable)", style=GOLD)
            t.append("\n")
            t.append(fb.why_text, style="#f6efdd")
        self.query_one("#coach", Static).update(t)

    def _update_prompt(self) -> None:
        g = self.game
        if self.notice:
            text = self.notice
            style = GOLD
        elif g.phase == "betting":
            text = f"Bet {money(g.base_bet)}   [−/+]   ·   Enter ▸ deal"
            style = GOLD
        elif g.phase == "insurance":
            text = "Insurance?   i ▸ buy   n ▸ decline"
            style = GOLD
        elif g.phase == "player":
            legal = g.legal_actions()
            text = "Your move — " + " · ".join(a for a in legal)
            style = GOLD
        elif g.phase == "feedback":
            text = "Read the coach, then Enter ▸ continue"
            style = DIM
        elif g.phase == "settled":
            text = f"{g.result_message}   ·   Enter ▸ next hand"
            style = GREEN if any(h.outcome in ("win", "blackjack") for h in g.hands) else "#f6efdd"
        else:
            text = g.result_message
            style = DIM
        if g.is_broke and g.phase != "insurance":
            text = "Bankroll below the $5 minimum — F2 ▸ reset to $1,000"
            style = RED
        self.query_one("#prompt", Static).update(Text(text, style=style))

    def _update_keys(self) -> None:
        keys = KEY_HINTS
        if self.game.phase == "betting":
            keys = "± bet   Enter deal   ? rules   t stats   q recap"
        elif self.game.phase == "insurance":
            keys = "i buy insurance   n decline   ? rules"
        elif self.game.phase == "feedback":
            keys = "Enter continue   ? rules"
        elif self.game.phase == "player":
            keys = "h hit   s stand   d double   p split   r surrender   ? rules   q recap"
        self.query_one("#keys", Static).update(Text(keys, style=DIM))

    # -- input -------------------------------------------------------------
    def on_key(self, event) -> None:
        if len(self.screen_stack) > 1:
            return
        key = event.key
        if key in ("enter", "return"):
            self._on_enter()
            event.stop()
            return
        if key in ("plus", "=", "+", "shift+=", "up", "kp_plus"):
            self._adjust_bet(self._bet_step())
            event.stop()
            return
        if key in ("minus", "-", "down", "kp_minus"):
            self._adjust_bet(-self._bet_step())
            event.stop()
            return
        if key == "i" and self.game.phase == "insurance":
            self._insure(True)
            event.stop()
            return
        if key == "n" and self.game.phase == "insurance":
            self._insure(False)
            event.stop()
            return
        if key in ACTION_KEYS:
            self._act(ACTION_KEYS[key])
            event.stop()
            return

    # -- screen actions (bindings; pushing screens from a binding is safe) --
    def action_help(self) -> None:
        if len(self.screen_stack) > 1:
            return
        self.push_screen(HelpScreen())

    def action_stats(self) -> None:
        if len(self.screen_stack) > 1:
            return
        self.push_screen(RecapScreen(self.stats, self.game, quit_on_q=False))

    def action_recap(self) -> None:
        if len(self.screen_stack) > 1:
            return
        if self.stats.total_decisions or self.game.phase == "settled":
            self.push_screen(RecapScreen(self.stats, self.game, quit_on_q=True))
        else:
            self.exit()

    def action_reset(self) -> None:
        self._reset_bankroll()

    def _bet_step(self) -> float:
        return 5.0

    def _adjust_bet(self, delta: float) -> None:
        if self.game.phase not in ("betting", "settled"):
            self.notice = "Finish the hand before changing the bet."
            self._render()
            return
        g = self.game
        new = g.set_bet(g.base_bet + delta)
        if g.bankroll > 0:
            new = min(new, g.bankroll)
        g.base_bet = round(new, 2)
        self.notice = ""
        self._saved_round = False
        self._render()

    def _on_enter(self) -> None:
        g = self.game
        self.notice = ""
        if g.phase == "feedback":
            g.acknowledge()
            self._render()
            return
        if g.phase in ("betting", "settled"):
            self._saved_round = False
            try:
                g.start_round()
            except IllegalAction as exc:
                self.notice = str(exc)
            self._render()
            return
        if g.phase == "insurance":
            self.notice = "Choose i ▸ buy or n ▸ decline."
        elif g.phase == "player":
            self.notice = "Choose an action: " + " · ".join(g.legal_actions())
        self._render()

    def _act(self, action: str) -> None:
        g = self.game
        self.notice = ""
        if g.phase != "player":
            self.notice = "Not now — press Enter to continue." if g.phase == "feedback" else "No action available now."
            self._render()
            return
        if action not in g.legal_actions():
            self.notice = f"{action.title()} isn't available in this spot."
            self._render()
            return
        try:
            g.act(action)
        except IllegalAction as exc:
            self.notice = str(exc)
        self._render()

    def _insure(self, buy: bool) -> None:
        self.notice = ""
        try:
            self.game.take_insurance(buy)
        except IllegalAction as exc:
            self.notice = str(exc)
        self._render()

    def _reset_bankroll(self) -> None:
        self.stats.reset_run(1000.0)
        self.game.reset(1000.0)
        self.game.stats = self.stats
        self.stats.bankroll = 1000.0
        self.notice = "Fresh bankroll: $1,000.00"
        self._saved_round = False
        self._persist()
        self._render()

    # -- persistence -------------------------------------------------------
    def _persist(self) -> None:
        self.stats.bankroll = round(self.game.bankroll, 2)
        self.store.save(self.stats)

    def on_unmount(self) -> None:
        self._persist()


class HelpScreen(ModalScreen):
    BINDINGS = [
        ("escape", "dismiss", "Back"),
        ("q", "dismiss", "Back"),
    ]

    HELP = (
        "[bold #e6c15a]RULES AT THIS TABLE[/]\n"
        "  6 decks · dealer hits soft 17 (H17) · American hole card, peek on 10/A\n"
        "  Blackjack pays 3:2 · doubles any first two cards · double after split\n"
        "  Late surrender: initial unsplit hand only, after the peek · up to 4 hands\n"
        "  Split aces get one card each, no resplit · any 21 after a split pays 1:1\n"
        "  Insurance pays 2:1 and is offered before the peek · play money only\n\n"
        "[bold #e6c15a]CONTROLS[/]\n"
        "  h hit     s stand     d double     p split     r surrender\n"
        "  i buy insurance     n decline insurance\n"
        "  ± (or ↑/↓) change bet     Enter deal / continue / next hand\n"
        "  ? rules     t session stats     q recap & quit     F2 reset bankroll\n\n"
        "[bold #e6c15a]HOW COACHING WORKS[/]\n"
        "  You decide first; the coach grades that decision against total-dependent\n"
        "  basic strategy for these exact rules — never against the cards that\n"
        "  happen to fall. Feedback stays on screen until you press Enter.\n"
        "  If double or split is unavailable (funds or rules), the coach names the\n"
        "  correct fallback instead of marking the chart play against you.\n\n"
        "[bold #e6c15a]THE CHART (6D · H17 · DAS · LS)[/]\n"
        "  Hard 8 or less: hit.   9: double vs 3–6.   10: double vs 2–9.\n"
        "  11: double vs 2–A.   12: stand vs 4–6.   13–16: stand vs 2–6.\n"
        "  17+: stand.   Soft 13–16: double vs 4–6 (soft 13–14 vs 4+).\n"
        "  Soft 17: double vs 3–6.   Soft 18: double vs 2–6, stand vs 7–8, hit 9–A.\n"
        "  Soft 19: double vs 6 only.   8,8: split (surrender vs A).   9,9: split 2–6, 8–9.\n"
        "  A,A: always split.   10,10: stand.\n\n"
        "[bold #e6c15a]SURRENDER (late, H17)[/]\n"
        "  15 vs 10 or A · 16 vs 9, 10 or A · 17 vs A · 8,8 vs A\n\n"
        "[#7e9488]Chart sources: Wizard of Odds late-surrender tables (4+ decks, H17) and\n"
        "Wizard of Odds / Blackjack Apprenticeship H17 basic strategy. Full links and\n"
        "known marginal-cell notes are in the README.[/]"
    )

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="modal-box"):
            yield Static(self.HELP, classes="modal-scroll")
            yield Static("Esc ▸ back to the table", classes="modal-foot")

    def action_dismiss(self) -> None:
        self.dismiss()


class RecapScreen(ModalScreen):
    BINDINGS = [
        ("escape", "dismiss", "Back"),
        ("enter", "dismiss", "Back"),
        ("q", "quit_app", "Quit"),
    ]

    def __init__(self, stats: SessionStats, game: Game, quit_on_q: bool = False) -> None:
        super().__init__()
        self.stats = stats
        self.game = game
        self.quit_on_q = quit_on_q

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="modal-box"):
            yield Static(self._body(), classes="modal-scroll")
            foot = "q ▸ quit     Esc ▸ back to the table" if self.quit_on_q else "Esc or Enter ▸ back to the table"
            yield Static(foot, classes="modal-foot")

    def _body(self) -> str:
        s = self.stats
        acc = f"{s.accuracy:.0%}" if s.total_decisions else "—"
        lines = [
            "[bold #e6c15a]SESSION RECAP[/]",
            "",
            f"  Decisions graded   [bold]{s.total_decisions}[/]",
            f"  Correct            [bold]{s.correct_decisions}[/]  ([bold #7bdcae]{acc}[/])",
            f"  Hands settled      {s.rounds}   ·   W {s.wins} / L {s.losses} / P {s.pushes}   ·   blackjacks {s.blackjacks}",
            f"  Bankroll           {money(self.game.bankroll)}   (start {money(s.start_bankroll)}, net {money(s.net)})",
            f"  Peak               {money(s.peak_bankroll)}   ·   low {money(s.low_bankroll)}",
        ]
        mistakes = s.mistakes[-10:]
        lines.append("")
        if mistakes:
            lines.append("[bold #e6c15a]MISTAKES TO REVIEW[/]")
            for m in mistakes:
                label = "insurance" if m.insurance else f"{m.hand} vs {m.up}"
                lines.append(
                    f"  [bold]{label}[/] — you chose [bold #e2685f]{m.chosen}[/]; "
                    f"chart: [bold #7bdcae]{m.correct_action}[/]"
                )
        elif s.total_decisions:
            lines.append("[bold #7bdcae]No mistakes this session. Clean sheet.[/]")
        else:
            lines.append("[#7e9488]No decisions yet — deal a hand.[/]")
        lines.append("")
        lines.append(
            "[#7e9488]Coaching is total-dependent basic strategy for 6D H17 DAS LS, "
            "graded on the decision, not the result.[/]"
        )
        return "\n".join(lines)

    def action_dismiss(self) -> None:
        self.dismiss()

    def action_quit_app(self) -> None:
        if self.quit_on_q:
            self.app.exit()
        else:
            self.dismiss()


def main() -> None:
    FeltApp().run()


if __name__ == "__main__":
    main()
