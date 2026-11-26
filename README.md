# Felt

**A blackjack table in your terminal that coaches you after every decision.**

Felt deals a real six-deck shoe, then grades each hit, stand, double, split,
surrender, and insurance choice against total-dependent basic strategy for the
exact rules on the table. You decide first; the coach answers after — never
before and never with a hint about the cards you cannot see.

```
F E L T   $1,000  ·  bet $25  ·  6D H17 DAS LS  ·  shoe 96%
DEALER  shows 6
┌─────┐ ┌─────┐
│ 6   │ │ ░░░ │
│  ♥  │ │ ░░░ │
│   6 │ │ ░░░ │
└─────┘ └─────┘
YOU
▸ HAND 1  $25  ·  16
┌─────┐ ┌─────┐
│10   │ │ 6   │
│  ♠  │ │  ♦  │
│  10 │ │   6 │
└─────┘ └─────┘
╭─ COACH ──────────────────────────────────────────────╮
│ ✓ Correct — stand   hand 1 · 16 vs 6                 │
│ Stand on 16 vs dealer 6: the dealer busts about 42%  │
│ of the time, so don't risk busting first.            │
│ Enter ▸ continue                                     │
╰──────────────────────────────────────────────────────╯
```

## Install and run

Requires Python 3.10+ and a true-color terminal.

```bash
# isolated install from a checkout (recommended)
uv build
pipx install dist/felt-0.1.0-py3-none-any.whl
# or: uv tool install dist/felt-0.1.0-py3-none-any.whl

# development install from a checkout
uv venv
uv pip install -e .
uv run felt
```

The project is packaged for PyPI (`pipx install felt` once published) but is
not published from this workspace.

`uv sync` also works if you prefer a project environment. There is no server,
no network access, and no account — everything runs locally.

From this checkout you can also:

```bash
./launch.sh          # creates .venv and launches
uv run pytest        # full test suite (headless)
uv run python scripts/preview.py   # write SVG screenshots (PNG if cairosvg is present)
```

The console command is `felt`; `python -m felt` is equivalent.

## Rules on this table (fixed)

| Rule | Value |
| --- | --- |
| Decks | 6 |
| Dealer soft 17 | **Hits** (H17) |
| Hole card | American; peek on 10 and ace |
| Blackjack pays | 3:2 |
| Double | Any first two cards; after split (DAS) allowed |
| Split | Any equal-rank pair, up to **4 hands**; 10/J/Q/K count as a pair |
| Split aces | One card each, no resplit, no double |
| 21 after a split | Pays 1:1 — **not** a natural |
| Surrender | Late, initial unsplit two-card hand only, after the peek |
| Insurance | Offered on dealer ace **before** the peek, pays 2:1 |
| Bankroll | Play money, starts at $1,000, bet $25, adjustable in $5 steps |

Illegal actions are rejected with a plain explanation; they never change the
bankroll. If the bankroll cannot cover a double or split, the coach grades the
correct fallback instead of the unavailable chart play.

## How the coaching works

- The engine snapshots your hand and the dealer's **upcard** before applying
  your action. The hole card is not consulted for advice or grading.
- Advice is total-dependent basic strategy (no composition-dependent
  exceptions, no card counting).
- Feedback is produced for **every** decision, including insurance. It stays on
  screen until you press `Enter`; no other key can advance the hand, so a hit,
  bust, or stand can never erase the explanation.
- Correctness is judged on the decision, not the result. Winning with a bad hit
  still counts as a mistake.
- If a chart play is unavailable, the panel says so (`chart: double
  unavailable`) and grades the legal fallback. Examples: soft 18 and soft 19
  stand when doubling is not possible; 8,8 vs 6 stands when splitting is not
  possible; 16 vs 10 hits when surrender is not offered.
- Insurance is graded as a mistake when bought: basic strategy declines it.

## Controls

| Key | Action |
| --- | --- |
| `h` `s` `d` `p` `r` | hit, stand, double, split, surrender |
| `i` / `n` | buy / decline insurance |
| `+` `-` (or `↑` `↓`) | adjust bet by $5 |
| `Enter` | deal, acknowledge feedback, next hand |
| `?` or `F1` | rules, chart summary, sources |
| `t` | session stats and mistakes |
| `q` | session recap, then quit |
| `F2` | reset to a fresh $1,000 bankroll |

The layout adapts to the terminal: 80×24 is the supported minimum, cards grow
at 108+ columns, and the table re-centers on resize.

## Strategy sources (verified, not guessed)

The chart is fixed for 6D · H17 · DAS · late surrender · 3:2 and was checked
against these sources:

- **Wizard of Odds — Blackjack Surrender** (late surrender, four or more decks,
  total dependent; H17 column):
  <https://wizardofodds.com/games/blackjack/surrender/>
  Confirms: 15 vs 10/A, 16 vs 9/10/A, **17 vs A**, and 8,8 vs A.
- **Blackjack Apprenticeship — H17 Basic Strategy (late surrender)**:
  <https://www.blackjackapprenticeship.com/wp-content/uploads/2024/09/H17-Basic-Strategy.pdf>
  Confirms 11 vs A doubles, 10 vs 10/A hits, soft/pair rows, and the surrender panel.
- **Wizard of Odds — Basic Strategy Calculator**:
  <https://wizardofodds.com/games/blackjack/strategy/calculator/>
- **Wizard of Odds — 4- to 8-deck strategy, text form with the H17
  modifications** (primary cell-by-cell confirmation for the hard, soft, and
  pair rows):
  <https://wizardofodds.com/games/blackjack/strategy/4-decks/>
  Confirms: 11 vs A, soft 18 vs 2, soft 19 vs 6, 15/17/8,8 vs A surrender,
  soft 13–14 vs 5–6, soft 17 vs 3–6, and the DAS pair rows.
- **blackjacktrainer.fyi — 6D H17 DAS chart** (cross-check only):
  <https://www.blackjacktrainer.fyi/charts/basic-strategy>

**Source caveat.** The blackjacktrainer.fyi page lists hard 17 vs A as *stand*
and its fallback note says to hit soft 18 vs 2. Both conflict with standard H17
late-surrender strategy. We did **not** copy those cells: surrender comes from
the Wizard table above (17 vs A surrenders), and soft 18 vs 2 doubles, standing
only when doubling is unavailable. Where sources disagreed, the two independent
surrender sources won.

### Independent EV check

`scripts/verify_strategy.py` recomputes the EV of stand/hit/double/surrender for
every hard and soft cell with an infinite-deck dealer model and compares it to
the chart. Result: **220 cells checked, 1 disagreement** — soft 13 (A,2) vs 5,
where the published 6-deck chart doubles and the infinite-deck model prefers
hitting by 0.006 units. That is a known razor-thin, card-removal-sensitive cell;
the 6-deck published chart is kept. Split cells are excluded from this check
(they need a split-EV model); the split chart is taken from the published
6-deck H17 DAS chart. The dealer bust percentages in coach explanations come
from the same approximation and are rounded; they are flavor, not part of the
grading.

## Session stats

Stats and bankroll persist as JSON at `$FELT_HOME/stats.json`, or
`$XDG_DATA_HOME/felt/stats.json`, or `~/.local/share/felt/stats.json`.
The file is written atomically after each settled round and on exit; a corrupt
or missing file silently falls back to defaults. `t` shows accuracy, results,
and the last ten mistakes; `q` shows the recap before quitting. `F2` starts a
fresh run.

## Development

```bash
uv venv --python 3.13
uv pip install -e . --group dev
uv run pytest
```

Tests were developed test-first for the cards, chart, engine, and UI slices
(red, then green). They cover hand values, payouts, H17 dealer behavior,
peek/insurance timing, splits and split aces, surrender legality, bankroll
limits, deterministic injected shoes, every chart cell and fallback,
persistence, and headless Textual `Pilot` runs at 80×24 and 120×40 including
help, insurance, feedback gating, and recap.

Layout:

```
src/felt/cards.py     cards, shoe, hand value
src/felt/engine.py    round state machine, legal actions, settlement
src/felt/strategy.py  rules-fixed chart, fallbacks, coach explanations
src/felt/odds.py      dealer distribution used for explanations
src/felt/session.py   session stats + atomic JSON persistence
src/felt/ui.py        big-card rendering
src/felt/app.py       Textual app, help/recap screens, key handling
scripts/verify_strategy.py  independent EV check
scripts/preview.py          headless SVG/PNG screenshots
```

## Caveats

- Play money only. No gambling, no real-money integration, no server.
- Total-dependent strategy; composition-dependent surrender exceptions other
  than 8,8 vs A are not modeled.
- The chart assumes the rules above. Changing the rules means changing the chart.
- Coach percentages use an infinite-deck dealer model, so they can differ by a
  few tenths of a percent from a six-deck shoe.
- Terminal fonts need box-drawing and suit glyphs; a Nerd Font is not required.

MIT licensed.
