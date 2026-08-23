# House Edge Casino

A small, extensible casino games library, built with Python's standard
library only (`tkinter` — no extra installs needed).

## Running it

```
python3 main.py
```

Requires Python 3.9+. On some minimal Linux installs `tkinter` isn't bundled
with Python by default — if you get `ModuleNotFoundError: No module named
'tkinter'`, install it with your package manager, e.g.:

```
# Debian/Ubuntu/CachyOS (Arch-based, use pacman instead):
sudo apt install python3-tk        # Debian/Ubuntu
sudo pacman -S tk                  # Arch/CachyOS
```

## What's here

- **Main menu** — bank balance button, settings gear, and a grid of game
  tiles. Three Card Poker is playable now; the rest are placeholder tiles
  ready to be wired up as the library grows.
- **Bank balance / Finances screen** — deposit funds (capped at £300 per
  transaction, no limit on the number of deposits), see your current
  balance, and track lifetime stats (total deposited, total wagered, total
  returned, net profit/loss, hands played, biggest single-round win).
- **Settings screen** — sound/animation toggles, a "confirm bets before
  dealing" option, three table felt themes, and a way to reset lifetime
  stats without touching your balance.
- **Three Card Poker** — full UK casino payout rules (see below).

Balance, lifetime stats, and settings are saved to `data/*.json` and persist
between sessions.

## Three Card Poker rules implemented

Main game (Ante & Play):
- Dealer qualifies with Queen-high or better.
- Player beats a qualifying dealer: Ante and Play both pay **1:1**.
- Dealer doesn't qualify: Ante pays **1:1**, Play **pushes** (returned).
- Dealer beats player: Ante and Play are both lost.
- Tie: both push.

Ante Bonus (paid regardless of the dealer's hand, forfeited if you fold):
- Straight Flush **5:1**, Three of a Kind **4:1**, Straight **1:1**.

Pair Plus side bet (resolved on your hand alone, unaffected by fold):
- Pair **1:1**, Flush **4:1**, Straight **6:1**, Three of a Kind **33:1**,
  Straight Flush **35:1**.

Prime side bet (UK variation, based on suit colour):
- All 3 of your cards the same colour: **3:1**
- All 6 cards (yours + dealer's) the same colour: **4:1** (this supersedes
  the 3:1 result rather than stacking with it)

Hand ranking order in 3-card poker (note Flush ranks *above* Straight,
unlike 5-card poker, since 3-card flushes are rarer than 3-card straights):
`Straight Flush > Three of a Kind > Straight > Flush > Pair > High Card`.

## Project layout (built for reuse across future games)

```
main.py                          # app window, frame stack, wiring
core/
  cards.py                       # Card, Deck — shared by every game
  hand_evaluator.py              # 3-card hand ranking/comparison logic
  finances.py                    # bank balance + lifetime stats, persisted
  settings.py                    # app-wide settings + table themes, persisted
  persistence.py                 # generic JSON load/save helper
ui/
  main_menu.py                   # main menu + game tile grid
  finances_screen.py             # deposit flow + lifetime stats
  settings_screen.py             # toggles, theme picker, stats reset
  card_widgets.py                # canvas card-drawing helpers, reusable
games/
  three_card_poker/
    logic.py                     # game engine: dealing, payouts, no UI/finance coupling
    ui.py                        # table screen: betting, dealing, results
data/                            # created at runtime — finances.json, settings.json
```

`core/` and `ui/card_widgets.py` are written to be game-agnostic: a new game
(Blackjack, Baccarat, Roulette, ...) reuses `Deck`/`Card`, the
`FinanceManager`/`SettingsManager`, and the JSON persistence helper, and only
needs its own `logic.py` (rules) + `ui.py` (table screen) under `games/`,
plus a tile added to `main_menu.py` and a frame registered in `main.py`.

## Roadmap ideas (not yet built)

- More tables: Blackjack, Roulette, Baccarat, Craps
- AI/CPU players at the table for a more social feel
- Progressive jackpots on side bets
- Milestone-based unlocks (new tables, higher bet limits, cosmetic themes)
- Bonus/free-bet promotions
- A stats/achievements screen alongside the existing lifetime stats
