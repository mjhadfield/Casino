# Progression, Crowns and the Cashier

## Players

Launching the casino opens a character select screen. Each player has their own balance, stats, achievements, unlocks and settings, saved under `data/players/<name>/`. You can get back to it at any time from Settings → **Player Screen**.

## Money and the Cashier

Every new player starts with **£200**. The Cashier handles deposits and withdrawals, with a rail to stop you topping up forever:

| Balance before depositing | Most you can deposit |
|---|---|
| Under £100 | £200 |
| £100 to £200 | £100 |
| £200 or more | Deposits blocked |

Withdrawals are never restricted. All of it is fake money.

## The progressive jackpot

There's one jackpot pool, shared by every table that has a Jackpot side bet (everything except Baccarat). It grows on its own while the app is open (it doesn't catch up for time spent closed), and the rate can be changed in Settings under `$ jackpot --config`.

## Story mode

A new player starts with only **Three Card Poker** unlocked. Every other table unlocks through an achievement:

| Achievement | Unlocks |
|---|---|
| Play 20 hands of Three Card Poker | Blackjack (6:5) |
| Play 20 hands of Blackjack | Pai Gow Poker (Face Up!) |
| Play 100 hands of Blackjack | Blackjack (Standard, 3:2) |
| Play 500 hands of Blackjack | Blackjack (Counting) |
| Play 20 hands of Pai Gow Poker | Mississippi Stud |
| Play 100 hands of Pai Gow Poker | Pai Gow Poker (Standard) |
| Play 20 hands of Mississippi Stud | Ultimate Texas Hold'em |
| Play 20 hands of Ultimate Texas Hold'em | Let It Ride |
| Play 20 hands of Let It Ride | High Card Flush |
| Play 20 hands of High Card Flush | Baccarat |

Yes, you have to put up with the 6:5 Blackjack table before you earn the proper one.

## Achievements and Crowns

There are 61 achievements across money milestones, hands played (overall and per game) and one-off moments. Each one pays **10 Crowns**, a separate currency that can't be bought with casino money. A banner pops up over whatever you're playing when you earn one, and several at once are queued rather than stacked.

## Crowns Store

| Item | Price |
|---|---|
| Early unlock of a locked table | 150 Crowns |
| Premium theme (Crimson Velvet, Royal Gold, Neon Void, Blue Ice). Reskins the whole app, not just the felt | 80 Crowns |
| Premium card style (Gold Light, Gold Dark, Crimson, Void) | 80 Crowns |
| Blackjack Strategy Guide (see [Blackjack](blackjack.md#strategy-guide)) | 200 Crowns |
| Four Colour Deck (blue diamonds, green clubs) | 20 Crowns |

Anything bought shows up in Settings, where themes, card styles and features can be switched on and off.

## Stats

The Stats screen breaks down every game: bets placed, hands played, how each hand type turned out, and lifetime money in and out. Stats can be reset from Settings.
