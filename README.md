# Hadfield Casino

**Version 1.2.0**

A small, extensible casino games library, built with Python's standard
library only (`tkinter` — no extra installs needed).

## Running it

**Windows:** double-click `Launch Casino.bat`. If that reports Python is
missing, run `Install prerequisites.bat` once first (no admin rights
needed — it installs Python + tkinter for your user account only), then
try `Launch Casino.bat` again.

**Everyone else:**

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

## Games Implemented

- **Three Card Poker** — full UK casino payout rules (see below).
- **Blackjack** — 8-deck shoe with four side bets (see below).
- **Pai Gow Poker** — 53-card deck (with a Joker), Fortune and
  Jackpot side bets (see below).
- **Pai Gow Poker (Face Up!)** — the same core game, with the Dealer's hand
  set and revealed *before* you set your own, an automatic Ante push on an
  Ace-high Pai Gow, and no commission (see below).
- **Mississippi Stud** — a 5-card Ante/3rd-4th-5th-Street game, plus a
  3 Card Bonus and a shared Jackpot side bet (see below).

Balance, lifetime stats, per-game stats, jackpot progress, and settings are
all saved to `data/*.json` and persist between sessions.


## Project layout (built for reuse across future games)

```
main.py                          # app window, frame stack, wiring
Launch Casino.bat                # Windows: double-click to run
Install prerequisites.bat        # Windows: one-time Python + tkinter setup
core/
  cards.py                       # Card, Deck (multi-deck shoes, optional Joker) -- shared by every game
  hand_evaluator.py              # 3-card and standard 5-card hand ranking/comparison logic
  finances.py                    # bank balance + lifetime stats, persisted
  game_stats.py                  # per-game bets/hands/strategy stats, persisted
  jackpot.py                     # shared progressive jackpot, ticks in real time
  settings.py                    # app-wide settings + table themes, persisted
  unlocks.py                     # per-game locked/unlocked status, persisted -- foundation for future achievements
  persistence.py                 # generic JSON load/save helper
ui/
  main_menu.py                   # main menu + game tile grid
  finances_screen.py             # deposit/withdraw flow + lifetime stats
  settings_screen.py             # toggles, theme picker, jackpot rate, stats reset
  stats_screen.py                # per-game bets/hands/strategy breakdown
  card_widgets.py                # canvas card-drawing helpers, reusable
  chips.py                       # canvas chip-stack drawing helpers, reusable
  jackpot_display.py             # odometer-style progressive jackpot meter
  game_icons.py                  # vector icons for the menu's game tiles
  dialogs.py                     # styled modal dialogs (confirm/info/document)
  collapsible.py                 # collapsible bordered section, used in Settings
  scrollable.py                  # scrollable container, used in Stats
games/
  three_card_poker/
    logic.py                     # game engine: dealing, payouts, no UI/finance coupling
    ui.py                        # table screen: betting, dealing, results
  blackjack/
    logic.py                     # game engine: shoe, boxes/hands, Hit/Stand/Double/Split
    ui.py                        # table screen: betting, dealing, play, results
  pai_gow_poker/
    logic.py                     # game engine: Joker rules, House Way, Fortune/Jackpot
    ui.py                        # table screen: betting, dealing, setting your hand, results
  pai_gow_poker_face_up/
    logic.py                     # PaiGowFaceUpGame -- subclasses pai_gow_poker's own engine
    ui.py                        # PaiGowPokerFaceUpFrame -- subclasses pai_gow_poker's own table screen
  mississippi_stud/
    logic.py                     # game engine: Ante/3rd-4th-5th Street, 3 Card Bonus, Jackpot
    ui.py                        # table screen: betting, per-street bet-or-fold, results
data/                            # created at runtime -- finances.json, settings.json, ...
```

`core/` and the reusable bits of `ui/` are written to be game-agnostic: a
new game reuses `Deck`/`Card`, `FinanceManager`/`SettingsManager`/
`GameStatsManager`, the chip/card drawing helpers, and the JSON persistence
helper, and only needs its own `logic.py` (rules) + `ui.py` (table screen)
under `games/`, plus a tile added to `main_menu.py`, a section added to
`stats_screen.py`, and a frame registered in `main.py`.

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

Jackpot side bet (flat £1, shared progressive pool): a spade-suited Royal
Flush pays **100% of the pool**; any other Royal Flush **£500**; a
non-royal Straight Flush **£100**; Three of a Kind **£60**; a Straight
**£6**.

Hand ranking order in 3-card poker (note Flush ranks *above* Straight,
unlike 5-card poker, since 3-card flushes are rarer than 3-card straights):
`Straight Flush > Three of a Kind > Straight > Flush > Pair > High Card`.

## Blackjack rules implemented

8-deck shoe, freshly reshuffled every round. Up to 2 boxes can be played
at once, side by side, with identical bets on each.

Main game:
- American-style dealer hole card with a peek: an Ace/10-value up-card
  checks the hole card immediately — an early Dealer Blackjack ends the
  round for every box before anyone can Hit/Double/Split into extra
  exposure.
- Insurance is offered only on an Ace up-card, up to half a box's main
  bet, and pays **2:1**.
- No restriction on what a first-two-cards total can be to Double.
  Splitting is allowed on any equal-*value* pair (so e.g. J+Q qualifies),
  up to 4 splits (5 hands); Double is allowed after a split too. The one
  exception is split Aces: each gets exactly one more card and then
  automatically stands, no further Hit/Double/Split even on another Ace.
- A 21 made on a split hand is just "21", not a bonus-paying natural — a
  natural Blackjack only exists on an untouched original 2-card hand.
- Dealer stands on all 17s (soft or hard) and always completes their hand
  — reveals the hole card and draws to 17 — once every box is done, for a
  consistent reveal every round, even after an early resolution.
- Player Blackjack (Dealer not also Blackjack) pays **3:2**. Bust: lose.
  Otherwise the higher total wins **1:1**; equal totals push.

Side bets — all four are evaluated against the box's own first two cards
plus the Dealer's up-card (i.e. a 3-card poker hand, same ranking order as
Three Card Poker's above):

- **Super Pairs** (the box's own 2 cards only): Any Pair **5:1**, Prime
  Pair (same colour, different suits) **10:1**, Suited Pair **25:1**,
  Suited Trips **50:1** (the pair *and* the Dealer's up-card all share
  rank and suit — only possible thanks to the 8-deck shoe).
- **21+3**: Flush or better pays a flat **9:1**.
- **Top 3** (only playable alongside a 21+3 bet): Three of a Kind **90:1**,
  Straight Flush **180:1**, Three of a Kind Suited **270:1**.
- **Jackpot** (flat £1, shared progressive pool): a *suited* Three of a
  Kind Aces/Kings/Queens pays **100% of the pool** (split between boxes if
  more than one hits it the same round); Three of a Kind suited, other
  ranks, **£625**; Straight Flush **£125**; Three of a Kind off-suit (any
  rank, Aces/Kings/Queens included) **£100**; Straight **£30**; Flush
  **£10**.

## Pai Gow Poker rules implemented

53-card deck (52 + one Joker), freshly reshuffled every round. You and the
Dealer each get 7 cards; you arrange yours into a 2-card **Front** hand and
a 5-card **Back** hand, and the Back must rank strictly higher than the
Front (a "foul" — Confirm stays disabled until it does). The Dealer always
sets their own hand by the exact Casino Real House Way chart, which also
backs your own optional House Way button. The Joker is semi-wild, not a
pure wildcard: it can only complete a Straight, Flush, or Straight Flush,
or otherwise stand in as a bare Ace — it can never impersonate an arbitrary
card just to fake an unrelated pair, trips, quads, or full house.

Main game (Ante):
- Win both Front and Back: Ante pays **1:1**, less a **5% commission on
  the win** (the standard "vig" — nothing's deducted on a loss or push).
- Lose both: Ante is lost.
- Split (win one hand, lose the other): **push**, stake returned.
- A tied hand ("copy") is won by the Dealer.

Fortune side bet (own stake, no cap) — the best hand from your own 7 cards:
7-Card Straight Flush **5000:1**, Royal Flush + Royal Match (a Royal Flush
plus the other 2 cards King-Queen suited) **2000:1**, 7-Card Straight
Flush with the Joker **1000:1**, Five Aces **400:1**, Royal Flush
**150:1**, Straight Flush **50:1**, Four of a Kind **25:1**, Full House
**5:1**, Flush **4:1**, Three of a Kind **3:1**, Straight **2:1**.

Jackpot side bet (flat £1, shares the same progressive pool as the other
tables): 7-Card Straight Flush **100% of the pool**; Royal Flush + Royal
Match **50% of the pool**; 7-Card Straight Flush with the Joker **25% of
the pool**; Five Aces **£2,500**; Royal Flush **£200**; Straight Flush
**£100**; Four of a Kind **£75**; Full House **£6**.

Hand ranking here is standard 5-card poker (unlike the 3-card ranking used
above): `Straight Flush > Four of a Kind > Full House > Flush > Straight >
Three of a Kind > Two Pair > One Pair > High Card`.

## Pai Gow Poker (Face Up!) rules implemented

The same core game as Pai Gow Poker above (deck, Joker rules, hand
evaluation, House Way chart, Fortune and Jackpot side bets — all identical
and unchanged), with three differences:

- **The Dealer plays first, face up.** The Dealer's hand is always set by
  House Way immediately after dealing — Face Up reveals it right away,
  before you arrange your own 7 cards, rather than keeping it hidden until
  Confirm.
- **Ace-high Pai Gow pushes automatically.** If the Dealer's revealed hand
  has no pair, straight, or flush anywhere across all 7 cards — the lowest
  possible hand, with an Ace as the single highest card — the round ends
  immediately: the Ante pushes (stake returned), Fortune/Jackpot still pay
  exactly as normal, and you don't set a hand at all that round.
- **No commission.** A win pays a flat **1:1** on the Ante — none of the
  standard game's 5% vig.

## Mississippi Stud rules implemented

Deck: a plain 52-card deck (no Joker), reshuffled each round.

Deal & streets: you're dealt 2 cards face up; 3 community cards are dealt
face down at the same time, revealed one at a time. At 3rd, 4th, and 5th
Street in turn you either fold (forfeiting the Ante and any street bets
already placed) or bet **1x-3x** your Ante — each played bet reveals that
street's community card. Your balance must be at least **3x your Ante** to
deal at all, and a 2x/3x bet at 3rd or 4th Street is only offered if you'd
still be able to afford at least a 1x bet on the next street afterwards.

Main game: your final hand is your 2 cards plus all 3 community cards.
Every bet still in play (Ante + whichever streets you played) pays the
**same** odds, looked up once from that hand:

| Hand | Pays | Hand | Pays |
|---|---|---|---|
| Royal Flush | 500:1 | Three of a Kind | 3:1 |
| Straight Flush | 100:1 | Two Pair | 2:1 |
| Four of a Kind | 40:1 | Pair, Jacks or better | 1:1 |
| Full House | 10:1 | Pair, 6s-10s | Push |
| Flush | 6:1 | Pair, 2s-5s / High Card | Lose |
| Straight | 4:1 | | |

3 Card Bonus side bet (own spot, resolved on the 3 community cards alone,
independent of your own hand or fold — it stays "in action" until all 3 are
exposed, even forcing a reveal on a fold): Mini-Royal (A-K-Q suited)
**50:1**, Straight Flush **40:1**, Three of a Kind **30:1**, Straight
**6:1**, Flush **3:1**, Pair **1:1**.

Jackpot side bet (flat £1, shared progressive pool — same as the other
tables; never pays on a folded round): Royal Flush **100% of the pool**;
Straight Flush **10% of the pool** (a partial drawdown, doesn't reset it);
Four of a Kind **£300**; Full House **£50**; Flush **£40**; Straight
**£30**; Three of a Kind **£9**.

## Roadmap ideas (not yet built)

- More tables: Baccarat, Let It Ride, Ultimate Texas Hold'em, High Card
  Flush — already placeholder tiles on the main menu, each starting locked
  (see core/unlocks.py) until built
- AI/CPU players at the table for a more social feel
- Milestone-based unlocks (new tables, higher bet limits, cosmetic themes)
- Bonus/free-bet promotions
- An achievements screen alongside the existing lifetime/per-game stats
