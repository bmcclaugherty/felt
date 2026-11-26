"""Blackjack round engine: rules, actions, dealer play, and settlement.

Rules are fixed: six decks, dealer hits soft 17 (H17), double after split (DAS),
late surrender on the initial unsplit hand after the peek, American hole card
with a peek on ten/ace, 3:2 naturals, up to four hands, split aces get one card
each with no resplit, and any 21 made after a split pays even money.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .cards import Card, Shoe, hand_value, is_blackjack, is_pair
from .session import SessionStats
from .strategy import Advice, best_action, hand_key


class IllegalAction(RuntimeError):
    """Raised when an action is not legal in the current state."""


@dataclass(frozen=True)
class Rules:
    decks: int = 6
    h17: bool = True
    das: bool = True
    late_surrender: bool = True
    blackjack_pays: float = 1.5
    max_hands: int = 4
    peek: bool = True
    insurance: bool = True
    min_bet: float = 5.0
    max_bet: float = 500.0


@dataclass
class Hand:
    cards: list[Card]
    bet: float
    from_split: bool = False
    split_aces: bool = False
    doubled: bool = False
    surrendered: bool = False
    done: bool = False
    history: list[str] = field(default_factory=list)
    outcome: str | None = None
    payout: float = 0.0

    @property
    def total(self) -> int:
        return hand_value(self.cards)[0]

    @property
    def soft(self) -> bool:
        return hand_value(self.cards)[1]

    @property
    def busted(self) -> bool:
        return self.total > 21

    @property
    def is_natural(self) -> bool:
        return is_blackjack(self.cards) and not self.from_split

    @property
    def can_split(self) -> bool:
        return is_pair(self.cards) and not self.split_aces

    def label(self) -> str:
        return "surrender" if self.surrendered else hand_key(self.cards)


@dataclass
class Feedback:
    chosen: str
    advice: Advice
    why_text: str
    insurance: bool = False
    was_correct: bool = True
    hand: str = ""
    up: str = ""

    @property
    def correct_action(self) -> str:
        return self.advice.action


class Game:
    def __init__(
        self,
        shoe: Shoe | None = None,
        bankroll: float = 1000.0,
        base_bet: float = 25.0,
        rules: Rules | None = None,
        stats: SessionStats | None = None,
    ) -> None:
        self.rules = rules or Rules()
        self.shoe = shoe or Shoe(decks=self.rules.decks)
        self.bankroll = float(bankroll)
        self.base_bet = float(base_bet)
        self.stats = stats
        self.phase = "betting"
        self.dealer: list[Card] = []
        self.hands: list[Hand] = []
        self.active = 0
        self.insurance_bet = 0.0
        self.insurance_offered = False
        self.insurance_result: str | None = None
        self.hole_revealed = False
        self.peeked = False
        self.dealer_blackjack = False
        self.feedback: Feedback | None = None
        self.last_feedback: Feedback | None = None
        self._pending: str | None = None
        self.result_message = ""
        self.shuffled = False

    # -- convenience -------------------------------------------------------
    @property
    def player_hand(self) -> Hand:
        return self.hands[self.active]

    @property
    def active_hand(self) -> Hand | None:
        return self.hands[self.active] if self.hands else None

    @property
    def dealer_upcard(self) -> Card | None:
        return self.dealer[0] if self.dealer else None

    @property
    def dealer_total(self) -> int:
        return hand_value(self.dealer)[0]

    def dealer_cards(self, reveal: bool | None = None) -> list[Card | None]:
        """Visible dealer cards; the hole card is None until revealed."""
        if not self.dealer:
            return []
        show = self.hole_revealed if reveal is None else reveal
        if show or len(self.dealer) < 2:
            return list(self.dealer)
        return [self.dealer[0], None]

    def can_bet(self, amount: float) -> bool:
        return self.rules.min_bet <= amount <= self.bankroll

    def set_bet(self, amount: float) -> float:
        amount = max(self.rules.min_bet, min(float(amount), self.rules.max_bet))
        if self.bankroll > 0:
            amount = min(amount, self.bankroll)
        self.base_bet = round(amount, 2)
        return self.base_bet

    def adjust_bet(self, delta: float) -> float:
        return self.set_bet(self.base_bet + delta)

    # -- round start -------------------------------------------------------
    def start_round(self, bet: float | None = None) -> None:
        if self.phase not in ("betting", "settled", "broke"):
            raise IllegalAction(f"Cannot deal now (phase={self.phase}).")
        if bet is not None:
            self.base_bet = round(float(bet), 2)
        if self.base_bet < self.rules.min_bet:
            raise IllegalAction(f"Minimum bet is ${self.rules.min_bet:.0f}.")
        if self.base_bet > self.bankroll:
            raise IllegalAction(
                f"Bet ${self.base_bet:.0f} exceeds bankroll ${self.bankroll:.2f}."
            )

        self.shuffled = False
        if self.shoe.needs_shuffle:
            self.shoe.shuffle()
            self.shuffled = True

        self.hands = []
        self.active = 0
        self.dealer = []
        self.insurance_bet = 0.0
        self.insurance_offered = False
        self.insurance_result = None
        self.hole_revealed = False
        self.peeked = False
        self.dealer_blackjack = False
        self.feedback = None
        self._pending = None
        self.result_message = ""

        self.bankroll = round(self.bankroll - self.base_bet, 2)
        p1 = self.shoe.draw()
        up = self.shoe.draw()
        p2 = self.shoe.draw()
        hole = self.shoe.draw()
        self.hands = [Hand([p1, p2], self.base_bet)]
        self.dealer = [up, hole]

        if up.is_ace and self.rules.insurance:
            self.insurance_offered = True
            self.phase = "insurance"
            return
        self._after_peek()

    def _after_peek(self) -> None:
        self.peeked = True
        self.dealer_blackjack = is_blackjack(self.dealer)
        if self.dealer_blackjack:
            self.hole_revealed = True
            self._settle()
            return
        if self.hands[0].is_natural:
            self.hole_revealed = True
            self._settle()
            return
        self.phase = "player"

    # -- insurance ---------------------------------------------------------
    def take_insurance(self, buy: bool) -> Feedback:
        if self.phase != "insurance":
            raise IllegalAction("Insurance is not being offered.")
        if buy:
            cost = round(self.hands[0].bet / 2, 2)
            if cost > self.bankroll:
                raise IllegalAction("Not enough bankroll to insure.")
            self.bankroll = round(self.bankroll - cost, 2)
            self.insurance_bet = cost

        advice = Advice(
            action="decline",
            chart_action="decline",
            why=(
                "Insurance is a side bet that the hole card is a ten — it wins less "
                "than a third of the time. Basic strategy always declines; the "
                "3:2 natural already pays you enough."
            ),
        )
        chosen = "buy" if buy else "decline"
        fb = Feedback(
            chosen=chosen,
            advice=advice,
            why_text=advice.why,
            insurance=True,
            was_correct=not buy,
            hand="insurance",
            up="A",
        )
        if self.stats is not None:
            self.stats.record_decision(
                "insurance", "A", chosen, "decline", advice.why, insurance=True
            )
        self.feedback = self.last_feedback = fb
        self._pending = "post_insurance"
        self.phase = "feedback"
        return fb

    # -- legal actions -----------------------------------------------------
    def legal_actions(self) -> list[str]:
        if self.phase != "player" or not self.hands:
            return []
        hand = self.player_hand
        if hand.done or hand.total >= 21:
            return []
        acts = ["hit", "stand"]
        if len(hand.cards) == 2 and not hand.split_aces:
            if self.bankroll >= hand.bet and (not hand.from_split or self.rules.das):
                acts.append("double")
        if (
            len(hand.cards) == 2
            and hand.can_split
            and len(self.hands) < self.rules.max_hands
            and self.bankroll >= hand.bet
        ):
            acts.append("split")
        if (
            self.rules.late_surrender
            and len(self.hands) == 1
            and not hand.from_split
            and len(hand.cards) == 2
            and not hand.history
            and self.peeked
            and not self.dealer_blackjack
        ):
            acts.append("surrender")
        return acts

    # -- actions -----------------------------------------------------------
    def act(self, action: str) -> Feedback:
        action = action.lower().strip()
        if self.phase == "feedback":
            raise IllegalAction("Acknowledge the coach's feedback first (Enter).")
        if self.phase != "player":
            raise IllegalAction(f"No player action now (phase={self.phase}).")
        legal = self.legal_actions()
        if action not in legal:
            raise IllegalAction(
                f"Illegal action '{action}' here. Legal: {', '.join(legal) or 'none'}."
            )

        hand = self.player_hand
        before_cards = list(hand.cards)
        initial = (
            len(self.hands) == 1 and not hand.from_split and not hand.history
        )
        advice = best_action(
            before_cards,
            self.dealer[0],
            legal=legal,
            initial=initial,
        )

        if action == "hit":
            hand.history.append("hit")
            hand.cards.append(self.shoe.draw())
            if hand.busted or hand.total == 21:
                hand.done = True
        elif action == "stand":
            hand.history.append("stand")
            hand.done = True
        elif action == "double":
            hand.history.append("double")
            self.bankroll = round(self.bankroll - hand.bet, 2)
            hand.bet = round(hand.bet * 2, 2)
            hand.doubled = True
            hand.cards.append(self.shoe.draw())
            hand.done = True
        elif action == "surrender":
            hand.history.append("surrender")
            hand.surrendered = True
            hand.done = True
        elif action == "split":
            hand.history.append("split")
            self._split(hand)

        fb = Feedback(
            chosen=action,
            advice=advice,
            why_text=advice.why,
            was_correct=action == advice.action,
            hand=hand_key(before_cards),
            up=str(self.dealer[0].rank),
        )
        if self.stats is not None:
            self.stats.record_decision(
                fb.hand, fb.up, action, advice.action, advice.why
            )
        self.feedback = self.last_feedback = fb
        self._pending = "advance"
        self.phase = "feedback"
        return fb

    def _split(self, hand: Hand) -> None:
        self.bankroll = round(self.bankroll - hand.bet, 2)
        second = hand.cards.pop()
        new_hand = Hand([second], hand.bet, from_split=True)
        hand.from_split = True
        hand.cards.append(self.shoe.draw())
        new_hand.cards.append(self.shoe.draw())
        if second.is_ace:
            hand.split_aces = new_hand.split_aces = True
            hand.done = new_hand.done = True
        else:
            if hand.total == 21:
                hand.done = True
            if new_hand.total == 21:
                new_hand.done = True
        self.hands.insert(self.active + 1, new_hand)

    # -- progression -------------------------------------------------------
    def acknowledge(self) -> None:
        if self.phase != "feedback":
            raise IllegalAction("Nothing to acknowledge.")
        pending = self._pending
        self._pending = None
        self.feedback = None

        if pending == "post_insurance":
            self._after_peek()
            return
        self._advance()

    def _advance(self) -> None:
        for idx, hand in enumerate(self.hands):
            if not hand.done:
                self.active = idx
                self.phase = "player"
                return
        self._dealer_turn()

    def _dealer_turn(self) -> None:
        self.hole_revealed = True
        live = [h for h in self.hands if not h.busted and not h.surrendered]
        if live:
            while True:
                total, soft = hand_value(self.dealer)
                if total < 17 or (total == 17 and soft and self.rules.h17):
                    self.dealer.append(self.shoe.draw())
                else:
                    break
        self._settle()

    # -- settlement --------------------------------------------------------
    def _settle(self) -> None:
        self.hole_revealed = True
        dealer_total = self.dealer_total
        dealer_bj = is_blackjack(self.dealer)
        self.dealer_blackjack = dealer_bj

        for hand in self.hands:
            returned = 0.0
            if hand.surrendered:
                outcome = "surrender"
                returned = round(hand.bet / 2, 2)
            elif hand.busted:
                outcome = "bust"
            elif hand.is_natural:
                if dealer_bj:
                    outcome = "push"
                    returned = hand.bet
                else:
                    outcome = "blackjack"
                    returned = round(hand.bet * (1 + self.rules.blackjack_pays), 2)
            elif dealer_bj:
                outcome = "lose"
            elif dealer_total > 21 or hand.total > dealer_total:
                outcome = "win"
                returned = round(hand.bet * 2, 2)
            elif hand.total == dealer_total:
                outcome = "push"
                returned = hand.bet
            else:
                outcome = "lose"
            hand.outcome = outcome
            hand.payout = returned
            self.bankroll = round(self.bankroll + returned, 2)
            if self.stats is not None:
                self.stats.record_round(outcome, self.bankroll)

        if self.insurance_bet:
            if dealer_bj:
                self.bankroll = round(self.bankroll + self.insurance_bet * 3, 2)
                self.insurance_result = "won"
            else:
                self.insurance_result = "lost"

        self.phase = "settled"
        self.result_message = self._summary()

    @property
    def is_broke(self) -> bool:
        return self.bankroll < self.rules.min_bet

    def _summary(self) -> str:
        if not self.hands:
            return ""
        if len(self.hands) == 1:
            hand = self.hands[0]
            net = hand.payout - hand.bet
            sign = "+" if net >= 0 else "−"
            return f"{hand.outcome.upper()}  ({sign}${abs(net):,.2f})"
        net = sum(h.payout - h.bet for h in self.hands)
        parts = ", ".join(h.outcome or "?" for h in self.hands)
        sign = "+" if net >= 0 else "−"
        return f"{parts}  ({sign}${abs(net):,.2f})"

    # -- misc --------------------------------------------------------------
    def reset(self, bankroll: float = 1000.0) -> None:
        self.bankroll = float(bankroll)
        self.phase = "betting"
        self.hands = []
        self.dealer = []
        self.feedback = None
        self.last_feedback = None
        self.result_message = ""
        self.insurance_bet = 0.0

    def snapshot(self) -> dict:
        return {
            "phase": self.phase,
            "bankroll": self.bankroll,
            "bet": self.base_bet,
            "dealer": [c.label() if c else "??" for c in self.dealer_cards()],
            "hands": [
                {"cards": [c.label() for c in h.cards], "total": h.total, "bet": h.bet}
                for h in self.hands
            ],
        }
