import json

from felt.session import DecisionRecord, SessionStats, StatsStore, data_dir


def test_accuracy_and_mistakes():
    s = SessionStats()
    s.record_decision("16", "10", "hit", "surrender", "why")
    s.record_decision("11", "6", "double", "double", "why")
    s.record_decision("insurance", "A", "buy", "decline", "why", insurance=True)
    assert s.total_decisions == 3
    assert s.correct_decisions == 1
    assert abs(s.accuracy - 1 / 3) < 1e-9
    assert len(s.mistakes) == 2
    assert s.mistakes[0].correct_action == "surrender"


def test_record_round_tracks_wins_and_peak():
    s = SessionStats(bankroll=1000)
    s.record_round("win", 1050)
    s.record_round("lose", 1025)
    s.record_round("blackjack", 1062.5)
    assert (s.wins, s.losses, s.rounds) == (2, 1, 3)
    assert s.peak_bankroll == 1062.5
    assert s.low_bankroll == 1000
    assert s.net == 62.5


def test_roundtrip_through_store(tmp_path):
    store = StatsStore(tmp_path / "stats.json")
    s = SessionStats(bankroll=975, start_bankroll=1000)
    s.record_decision("16", "10", "stand", "surrender", "half a bet is better")
    s.record_round("lose", 975)
    assert store.save(s)
    loaded = store.load()
    assert loaded.bankroll == 975
    assert loaded.decisions[0].chosen == "stand"
    assert loaded.decisions[0].was_correct is False
    assert loaded.rounds == 1


def test_corrupt_store_falls_back_to_defaults(tmp_path):
    path = tmp_path / "stats.json"
    path.write_text("{not json", encoding="utf-8")
    assert StatsStore(path).load().bankroll == 1000


def test_missing_store_is_defaults(tmp_path):
    assert StatsStore(tmp_path / "nope.json").load().bankroll == 1000


def test_env_override_home(monkeypatch, tmp_path):
    monkeypatch.setenv("FELT_HOME", str(tmp_path / "felt-home"))
    assert data_dir() == tmp_path / "felt-home"
    store = StatsStore()
    assert store.path == tmp_path / "felt-home" / "stats.json"


def test_saved_json_is_valid_and_bounded(tmp_path):
    store = StatsStore(tmp_path / "stats.json")
    s = SessionStats()
    for i in range(450):
        s.record_decision("16", "10", "hit", "stand", f"why {i}")
    store.save(s)
    data = json.loads((tmp_path / "stats.json").read_text())
    assert len(data["decisions"]) == 400
    for rec in data["decisions"]:
        DecisionRecord.from_dict(rec)
