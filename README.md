# Hadfield Casino

**Version 1.8.0**

A small, extensible casino games library, built with Python's standard
library only (`tkinter` — no extra installs needed).

## Running it

**Windows:** double-click `Launch Casino (windows).bat`. If Python is not installed it will prompt a local (user) installation, no admin credentials are required.

**Linux:** run `./Launch Casino (linux).sh`. If Python 3 or Tkinter is missing it prints the install command for your distro (apt/pacman/dnf/zypper/apk) rather than installing anything itself -- a system Python package needs root on Linux, unlike Windows' per-user installer.

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

## Upgrading from an earlier version

All player information and statistics are held in the "data" folder which is generated on game launch and no longer included in the repo. If you are moving from a version earlier than 1.6, copy your data folder into the new folder. 

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
- **Ultimate Texas Hold'em** — head-to-head Hold'em against the dealer,
  linked Ante/Blind bets, a 3-stage Bet-or-Check/Fold decision, a Trips
  bonus, and a shared Jackpot side bet (see below).
- **Let It Ride** — three equal starter bets you can partially pull back as
  more of your hand is revealed, plus a Bonus, a 3 Card Bonus, and a shared
  Jackpot side bet (see below).
- **High Card Flush** — not poker at all: your rank is purely how many of
  your 7 cards share one suit. An Ante/Raise main game plus independent
  Flush, Straight Flush, and Jackpot side bets (see below).
- **Baccarat** — an 8-deck shoe, zero player decisions after the bet:
  Player/Banker/Tie plus the Dragon Bonus and 5 Treasures side bets (see
  below). No progressive jackpot.

Balance, lifetime stats, per-game stats, jackpot progress, and settings are
all saved to `data/*.json` and persist between sessions.


## Project layout (built for reuse across future games)

```
main.py                          # app window, frame stack, wiring
Launch Casino (windows).bat      # Windows: double-click to run (installs Python if needed)
Launch Casino (linux).sh         # Linux: run to launch (prints an install command if needed)
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
  ultimate_texas_holdem/
    logic.py                     # game engine: shared community cards, best-5-of-7, Trips/Jackpot
    ui.py                        # table screen: betting, 3-stage bet-or-check/fold, results
  let_it_ride/
    logic.py                     # game engine: 3 linked starter bets, Pull Back/Let It Ride, Bonus/3 Card/Jackpot
    ui.py                        # table screen: betting, 2-stage pull-back-or-let-it-ride, results
  high_card_flush/
    logic.py                     # game engine: same-suit-count ranking, Ante/Raise, Flush/Straight Flush/Jackpot
    ui.py                        # table screen: betting, 7-card arrange/fold/raise, results
  baccarat/
    logic.py                     # game engine: natural/draw rules, Player/Banker/Tie, Dragon Bonus/5 Treasures
    ui.py                        # one fixed table screen (no betting/play split): betting, deal, results
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

## Ultimate Texas Hold'em rules implemented

Deck: a plain 52-card deck (no Joker), reshuffled each round. Ante and
Blind are always equal, linked bets — there's no way to place them unequal.
Trips and the Jackpot side bet are both optional. Your balance must be at
least **3x your Ante** to deal.

Deal & betting: you and the dealer are each dealt 2 private cards; 5
community cards are dealt face down and shared by both hands (true
Hold'em rules, unlike this app's other multi-street games). You face up to
3 decisions in turn:
- **Pre-flop** (hole cards only): bet **4x** or **3x** your Ante into Play,
  or Check — the flop (first 3 community cards) is then revealed.
- **Post-flop** (if you haven't bet yet): bet **2x** or Check — the turn is
  then revealed.
- **Post-turn** (if you still haven't bet): bet **1x** or **Fold**
  (forfeiting Ante, Blind and Trips) — the river is then revealed.

Whichever point you actually bet, every remaining community card is
revealed immediately, then the dealer's own 2 cards, and the hand settles.

Main game: your hand and the dealer's are each the best 5 of your own 2
cards plus all 5 community cards. The dealer needs a **Pair or better** to
qualify — if they don't, the **Ante pushes** regardless of the comparison,
but Play and Blind still settle by it either way (qualification only ever
gates the Ante). A win pays Ante and Play **1:1**. The Blind only pays out
(see table) if you win with a **Straight or better** — winning with
anything weaker just pushes the Blind instead of losing it.

| Hand | Trips | Blind* |
|---|---|---|
| Royal Flush | 50:1 | 500:1 |
| Straight Flush | 40:1 | 50:1 |
| Four of a Kind | 20:1 | 10:1 |
| Full House | 7:1 | 3:1 |
| Flush | 6:1 | 3:2 |
| Straight | 5:1 | 1:1 |
| Three of a Kind | 3:1 | — |

*Blind only ever pays on a hand this good, and only if it beats the dealer.

Trips side bet (own spot, resolved on your own best 7-card hand alone,
independent of beating the dealer — forfeited outright on a Fold, since a
fold can only happen before the river).

Jackpot side bet (flat £1, shared progressive pool — same as the other
tables): a genuinely different 5-card hand from every other bet here — your
2 hole cards **plus the 3-card flop only**, fixed the moment the flop is
revealed and never affected by the turn/river. Royal Flush **100% of the
pool**; Straight Flush **10% of the pool** (a partial drawdown, doesn't
reset it); Four of a Kind **£300**; Full House **£50**; Flush **£40**;
Straight **£30**; Three of a Kind **£9**. Never pays on a folded round,
even though the flop-only hand was already fully known by then.

## Let It Ride rules implemented

Deck: a plain 52-card deck (no Joker), reshuffled each round. Three equal
bets — **£** (always plays), **2** (second decision), **1** (first
decision) — are placed together and tracked as a single linked value, the
same way Ultimate Texas Hold'em's own Ante/Blind pair is. Bonus and Jackpot
are both locked at a flat **£1**; the 3 Card Bonus is a variable bet.

Deal & betting: you're dealt 3 cards; the dealer's own 2 cards are dealt
face down and act as shared community cards. You face two decisions in
turn:
- **First decision** (your own 3 cards only): Pull Back bet "1" (get it
  back in full) or Let It Ride — the first community card is then revealed.
- **Second decision** (with 4 of your final 5 cards now known): Pull Back
  bet "2" or Let It Ride — the second community card is then revealed and
  your final 5-card hand is complete.

Main game: a **Pair of Tens or better** is needed to win — any hand ranked
above a single pair always qualifies (Two Pair included), while a pair
below Tens, or worse, simply loses with no push. Every base bet still in
play (£, plus 1/2 if not pulled back) pays independently at the table
below.

| Hand | Base Game | Bonus* | 3 Card** |
|---|---|---|---|
| Royal Flush | 500:1 | 10000:1 | 40:1 |
| Straight Flush | 100:1 | 2000:1 | 40:1 |
| Four of a Kind | 25:1 | 400:1 | — |
| Full House | 15:1 | 200:1 | — |
| Flush | 10:1 | 50:1 | 4:1 |
| Straight | 5:1 | 25:1 | 6:1 |
| Three of a Kind | 3:1 | 5:1 | 30:1 |
| Two Pair | 2:1 | — | — |
| Pair of Tens+ | 1:1 | — | — |
| Pair (any) | — | — | 1:1 |

*Bonus (flat £1) is judged on the same final 5-card hand, needs Three of a
Kind or better — Two Pair, which wins the Base Game, still loses the Bonus.
**3 Card is judged on your own 3 cards only (no community cards), needs a
Pair or better; A-K-Q suited pays the same as any other Straight Flush.

Bonus and 3 Card are both fully independent of the Base Game's own outcome
and of your Pull Back/Let It Ride decisions — they always resolve on the
full hand regardless.

Jackpot side bet (flat £1, shared progressive pool — same as the other
tables): the same final 5-card hand as the Base Game and Bonus, judged at
final settlement (nothing here is frozen early). Royal Flush **100% of the
pool**; Straight Flush **10% of the pool** (a partial drawdown, doesn't
reset it); Four of a Kind **£300**; Full House **£50**; Flush **£40**;
Straight **£30**; Three of a Kind **£9**.

## High Card Flush rules implemented

Deck: a plain 52-card deck, reshuffled each round. Player and dealer are
each dealt **7 cards**, face down. A hand's rank is purely how many cards
of one suit it holds — longer always beats shorter regardless of rank;
equal length is broken by comparing ranks descending. A "straight flush"
(consecutive ranks) has no bearing on this comparison — only the separate
Straight Flush bonus cares about that.

Betting: an Ante, plus optional Flush / Straight Flush / Jackpot side bets
(all independent of the Ante/Raise outcome and of folding). After seeing
your own 7 cards, **Fold** (forfeit the Ante) or **Raise** — normally fixed
at 1x the Ante, but up to **2x** with a 5-flush, up to **3x** with a 6- or
7-flush. The on-screen "YOUR FLUSH" placement is purely visual — your real
payout always uses your true best flush, whatever you actually place there.

Dealer qualifies with a **3-card, 9-high flush or better** (any 4+ card
flush always qualifies too). Doesn't qualify: Ante pays **1:1**, Raise
**pushes**. Qualifies: win pays both **1:1**; lose loses both; tie pushes
both.

| Flush length | Flush Bonus | Straight Flush Bonus |
|---|---|---|
| 7-card | 250:1 | 500:1 |
| 6-card | 100:1 | 200:1 |
| 5-card | 10:1 | 100:1 |
| 4-card | 1:1 | 60:1 |
| 3-card | — | 8:1 |

Both bonuses are judged on the player's own true hand alone, independent of
the Ante/Raise outcome and of a fold.

Jackpot side bet (flat £1, shared progressive pool — same as the other
tables, independent of a fold): judged on the player's own Straight Flush
length, not the plain Flush every other bet here uses — 7-card straight
flush **100% of the pool**; 6-card **50% of the pool** (a partial
drawdown, doesn't reset it); 5-card **£250**; 4-card **£50**; 3-card
**£5**.

## Baccarat rules implemented

Dealt from an **8-deck shoe**, reshuffled fresh each round (no persistent
cut-card across rounds, same per-round convention every other game here
uses). Card points: Ace=1, 2-9=face value, 10/J/Q/K=0 — a hand's total is
the sum of its cards, only the last digit counted.

**Natural**: a two-card total of 8 or 9 for either hand ends the round
immediately — no more cards to anyone. Otherwise **Player** draws a third
card on a two-card total of 0-5, stands on 6-7. **Banker** draws on 0-5 if
the Player stood; if the Player drew, Banker's own total decides,
cross-referenced against the Player's third card:

| Banker total | Draws when Player's 3rd card is |
|---|---|
| 0, 1, 2 | always draws |
| 3 | anything except 8 |
| 4 | 2-7 |
| 5 | 4-7 |
| 6 | 6-7 |
| 7 | never (always stands) |

**Main bets**: Player pays **1:1**; Banker pays **1:1 minus a 5%
commission** (deducted immediately per winning bet — £10 staked returns
£19.50); both push on a tie. Tie pays **8:1** on an actual tie, otherwise
**loses outright** (does not push).

**Dragon Bonus** (Player Dragon / Banker Dragon, independent spots, judged
on whichever side you bet): your side losing always loses; a natural tie
pushes, any other tie loses; a natural win pays flat even money regardless
of margin; otherwise paid by margin of victory — margins 1-3 lose, 4
through 9 pay 1:1 up to 30:1.

**5 Treasures** (five independent spots, judged purely on qualifying
events in the round, regardless of the main outcome and of whether that
spot itself was staked):

| Bet | Qualifying event | Payout |
|---|---|---|
| Fortune 7 | Banker 3-card total 7 | 40:1 |
| Golden 8 | Player 3-card total 8 | 25:1 |
| Heavenly 9 | both sides 3-card total 9 | 75:1 |
| Heavenly 9 | either side alone, 3-card total 9 | 10:1 |
| Blazing 7's | both sides 3-card total 7 | 200:1 |
| Blazing 7's | both sides 2-card total 7 (neither drew) | 50:1 |
| Cover All | any of the above four events fired | 6:1 |

Cover All is the one bet here with a cross-dependency — it pays purely off
another event having occurred, independent of whether *that* event's own
spot was staked.

## Roadmap ideas (not yet built)

- AI/CPU players at the table for a more social feel
- Milestone-based unlocks (new tables, higher bet limits, cosmetic themes)
- Bonus/free-bet promotions
- An achievements screen alongside the existing lifetime/per-game stats