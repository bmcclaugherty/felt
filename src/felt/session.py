"""Session statistics and JSON persistence (opt-in, portable)."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DecisionRecord:
    hand: str
    up: str
    chosen: str
    correct_action: str
    was_correct: bool
    why: str
    insurance: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DecisionRecord":
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


@dataclass
class SessionStats:
    bankroll: float = 1000.0
    start_bankroll: float = 1000.0
    rounds: int = 0
    decisions: list[DecisionRecord] = field(default_factory=list)
    peak_bankroll: float = 1000.0
    low_bankroll: float = 1000.0
    wins: int = 0
    losses: int = 0
    pushes: int = 0
    blackjacks: int = 0

    # -- recording ---------------------------------------------------------
    def record_decision(
        self, hand: str, up: str, chosen: str, correct_action: str, why: str,
        *, insurance: bool = False,
    ) -> DecisionRecord:
        rec = DecisionRecord(
            hand=hand, up=up, chosen=chosen, correct_action=correct_action,
            was_correct=chosen == correct_action, why=why, insurance=insurance,
        )
        self.decisions.append(rec)
        return rec

    def record_round(self, outcome: str, bankroll: float) -> None:
        self.rounds += 1
        if outcome == "win":
            self.wins += 1
        elif outcome == "lose":
            self.losses += 1
        elif outcome == "push":
            self.pushes += 1
        elif outcome == "blackjack":
            self.wins += 1
            self.blackjacks += 1
        self.bankroll = round(bankroll, 2)
        self.peak_bankroll = max(self.peak_bankroll, self.bankroll)
        self.low_bankroll = min(self.low_bankroll, self.bankroll)

    # -- reporting ---------------------------------------------------------
    @property
    def total_decisions(self) -> int:
        return len(self.decisions)

    @property
    def correct_decisions(self) -> int:
        return sum(1 for d in self.decisions if d.was_correct)

    @property
    def accuracy(self) -> float:
        if not self.decisions:
            return 0.0
        return self.correct_decisions / len(self.decisions)

    @property
    def mistakes(self) -> list[DecisionRecord]:
        return [d for d in self.decisions if not d.was_correct]

    @property
    def net(self) -> float:
        return round(self.bankroll - self.start_bankroll, 2)

    def reset_run(self, bankroll: float) -> None:
        """Start a fresh run: keep lifetime stats? Here: clear the session only."""
        self.bankroll = self.start_bankroll = bankroll
        self.peak_bankroll = self.low_bankroll = bankroll
        self.rounds = 0
        self.decisions.clear()
        self.wins = self.losses = self.pushes = self.blackjacks = 0

    # -- persistence -------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["decisions"] = [d.to_dict() for d in self.decisions[-400:]]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionStats":
        stats = cls()
        for key in cls.__dataclass_fields__:
            if key == "decisions":
                continue
            if key in data:
                setattr(stats, key, data[key])
        stats.decisions = [DecisionRecord.from_dict(d) for d in data.get("decisions", [])]
        return stats


def data_dir() -> Path:
    override = os.environ.get("FELT_HOME")
    if override:
        return Path(override).expanduser()
    base = os.environ.get("XDG_DATA_HOME")
    root = Path(base).expanduser() if base else Path.home() / ".local" / "share"
    return root / "felt"


class StatsStore:
    """Atomic JSON store; failures never break play."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else data_dir() / "stats.json"

    def load(self) -> SessionStats:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return SessionStats.from_dict(data)
        except (OSError, ValueError, TypeError):
            return SessionStats()

    def save(self, stats: SessionStats) -> bool:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(stats.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)
            return True
        except OSError:
            return False
