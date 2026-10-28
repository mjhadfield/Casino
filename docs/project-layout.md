# Project layout

Every game is split into a `logic.py` (the rules engine, no UI or money handling) and a `ui.py` (the table screen). Everything shared lives in `core/` (no tkinter) and `ui/`.

```
main.py                          # app window, player sessions, frame stack
Launch Casino (windows).bat      # Windows launcher (installs Python per-user if needed)
Launch Casino (linux).sh         # Linux launcher (prints an install command if needed)
core/
  cards.py                       # Card and Deck (multi-deck shoes, optional Joker)
  hand_evaluator.py              # 3-card and 5-card hand ranking and comparison
  finances.py                    # balance, deposits/withdrawals, lifetime stats
  game_stats.py                  # per-game bets/hands/outcome stats
  jackpot.py                     # the shared progressive jackpot, ticks in real time
  players.py                     # player profiles (one save folder each)
  achievements_data.py           # achievement definitions
  achievements.py                # tracking achievements and Crowns, purchases
  unlocks.py                     # locked/unlocked tables, premium card styles and features
  themes.py                      # app-wide themes (free and premium)
  settings.py                    # per-player settings
  persistence.py                 # JSON load/save helper
ui/
  logon_screen.py                # character select
  main_menu.py, game_tile.py     # main menu and its game tiles
  table_menu.py                  # table picker for games with more than one table
  blackjack_menu.py              # Blackjack's picker (6:5 / Standard / Counting)
  pai_gow_poker_menu.py          # Pai Gow's picker (Face Up! / Standard)
  finances_screen.py             # the Cashier
  stats_screen.py                # per-game stats
  settings_screen.py             # preferences, themes, card styles, features, jackpot, admin
  achievements_screen.py         # achievements list
  store_screen.py                # Crowns Store
  achievement_banner.py          # "Achievement Unlocked" pop-up
  card_widgets.py                # canvas card drawing (no image assets)
  chips.py                       # casino chip colours and chip-stack drawing
  jackpot_display.py             # odometer-style jackpot meter
  game_icons.py                  # vector icons for the menu tiles
  theme.py                       # colours, fonts and shared widget styles
  dialogs.py                     # terminal-styled modal dialogs
  collapsible.py, scrollable.py, tooltip.py
games/
  three_card_poker/              # logic.py + ui.py
  blackjack/                     # logic.py + ui.py + strategy.py (basic-strategy chart)
  blackjack_6_5/                 # subclasses Blackjack, pays 6:5
  blackjack_count/               # subclasses Blackjack, persistent shoe + Hi-Lo count
  pai_gow_poker/                 # logic.py + ui.py (Joker rules, House Way)
  pai_gow_poker_face_up/         # subclasses Pai Gow, dealer face up
  mississippi_stud/
  ultimate_texas_holdem/
  let_it_ride/
  high_card_flush/
  baccarat/
data/                            # created at runtime, one folder per player (git-ignored)
```

Adding a game means a new folder under `games/` with its own `logic.py` and `ui.py`, a tile on the main menu, a section on the Stats screen and a frame registered in `main.py`. Everything else (cards, chips, finances, stats, jackpot, themes) is reused.

Variant tables (6:5, Counting, Face Up!) subclass the base game and override only what's different, and share its stats.
