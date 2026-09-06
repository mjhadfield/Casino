"""
Achievement definitions -- plain data, no tkinter/app dependency, following
this codebase's "hardcoded Python constants" convention (see
core/themes.py's THEMES, core/unlocks.py's DEFAULT_UNLOCKS).
Checking *whether* an achievement's condition is met is bespoke code in
core/achievements.py, keyed by each Achievement's own `key` -- these vary
too much (a deposit total, a cross-game round tally, a same-round multi-bet
combo, a fold that still wins a side bet...) to force into one generic
predicate shape. The one deliberate exception is HANDS_LADDER/
PER_GAME_HANDS_MILESTONES below, which really are just numeric thresholds.

A game_key here is always the STATS-bucket key (GameStatsManager/
AchievementsManager's own game_rounds_played), which several tables can
share (see games/blackjack_6_5/logic.py, games/blackjack_count/logic.py) --
never a specific table's own unlock key. An achievement's own
unlocks_game_keys, by contrast, are core/unlocks.py's real unlock keys,
since those are what actually get flipped on -- a tuple, not a single
key, since one achievement CAN unlock more than one thing at once (no
current achievement actually needs to, but the mechanism supports it, and
did briefly get used for exactly that before the 20-hand tier below took
over "unlock the next main game" duty from the 100-hand one).
"""
from dataclasses import dataclass
from typing import Optional, Tuple

CATEGORY_MONEY = "money"
CATEGORY_GLOBAL = "global"
CATEGORY_GAME = "game"
CATEGORY_ALL = "all"


@dataclass(frozen=True)
class Achievement:
    key: str
    name: str
    description: str                         # placeholder copy for every entry today
    crowns: int                              # per-achievement, not a global constant
    categories: Tuple[str, ...]              # supports multi-category membership
    game_key: Optional[str] = None           # which single game a "game" achievement belongs to
    unlocks_game_keys: Tuple[str, ...] = ()  # every unlock this achievement applies at once (often none, sometimes 1, occasionally more)


PLACEHOLDER = "Placeholder achievement text."

_DEFS = [
    # -- Money: cumulative lifetime deposit ladder --------------------------
    # See DEPOSIT_LADDER below -- lifetime total, same "lifetime cumulative"
    # semantics across the whole ladder, not per-transaction.
    Achievement("deposit_200", "Deposit £200", "Back to the ATM", 10, (CATEGORY_MONEY,)),
    Achievement("deposit_1000", "Deposit £1,000", "Surely my luck will change", 10, (CATEGORY_MONEY,)),
    Achievement("deposit_5000", "Deposit £5,000", "Help is available if you need it", 10, (CATEGORY_MONEY,)),
    Achievement("deposit_10000", "Deposit £10,000", "Maybe you should step away for a while", 10,
                (CATEGORY_MONEY,)),

    # -- Money: single-transaction withdrawal ladder ------------------------
    # See WITHDRAW_LADDER below -- deliberately NOT cumulative (unlike the
    # deposit ladder above): each of these only fires when ONE withdrawal is
    # itself at least this big, not a running lifetime total, so it reads as
    # "had a session/run good enough to cash this much out at once" rather
    # than "eventually withdrew this much in dribs and drabs".
    Achievement("withdraw_200", "Withdraw £200", "Money back!", 10, (CATEGORY_MONEY,)),
    Achievement("withdraw_1000", "Withdraw £1,000", "Decent session", 10, (CATEGORY_MONEY,)),
    Achievement("withdraw_5000", "Withdraw £5,000", "Take the money and run", 10, (CATEGORY_MONEY,)),
    Achievement("withdraw_10000", "Withdraw £10,000", "Running like an absolute god", 10, (CATEGORY_MONEY,)),

    # -- Global: cross-game rounds-played ladder ---------------------------
    Achievement("hands_10", "Play 10 Hands", "This is kinda fun!", 10, (CATEGORY_GLOBAL,)),
    Achievement("hands_100", "Play 100 Hands", "Still not bored yet", 10, (CATEGORY_GLOBAL,)),
    Achievement("hands_500", "Play 500 Hands", "That's a lot of cards", 10, (CATEGORY_GLOBAL,)),
    Achievement("hands_1000", "Play 1,000 Hands", "I can stop any time I want", 10, (CATEGORY_GLOBAL,)),
    Achievement("hands_2500", "Play 2,500 Hands", "At least I'm getting good at this", 10, (CATEGORY_GLOBAL,)),
    Achievement("hands_5000", "Play 5,000 Hands", "Professional degeneracy unlocked", 10, (CATEGORY_GLOBAL,)),
    Achievement("hands_10000", "Play 10,000 Hands", "Send help", 10, (CATEGORY_GLOBAL,)),

    # -- Global: per-game streaks (any ONE game reaching the streak) -------
    Achievement("streak_win_5", "Win 5 In A Row", "I've got a system", 10, (CATEGORY_GLOBAL,)),
    Achievement("streak_lose_5", "Lose 5 In A Row", "This game is rigged", 10, (CATEGORY_GLOBAL,)),

    # -- The full progression chain -----------------------------------------
    # Three Card Poker is the only game that's ever unlocked by default (see
    # core/unlocks.py's DEFAULT_UNLOCKS) -- every other game is a link in
    # one single ordered chain, unlocked by that game's own 20-hand
    # achievement (moved here from the 100-hand one, so reaching the next
    # MAIN game only takes 20 hands, not 100). Blackjack and Pai Gow Poker
    # each additionally have their own TABLE variations (6:5/Standard/
    # Counting; Face Up/Standard) -- those stay gated on whichever
    # threshold they always were (100 hands for a Standard table, 500 for
    # Blackjack Counting), deliberately untouched by the 20-hand change,
    # since unlocking a further table of a game you already have access to
    # is a different kind of milestone than reaching the next game
    # entirely. Every game also carries the same 20/100/500/1,000/5,000
    # completionist ladder as every other one (mirroring the cross-game
    # HANDS_LADDER's own shape), whether or not that particular threshold
    # happens to also unlock something.

    # -- Three Card Poker (game) -- covers every table sharing this GAME_KEY --
    Achievement("tcp_hands_20", "Play 20 Hands (Three Card Poker)", "You've unlocked Blackjack (6:5).", 10,
                (CATEGORY_GAME,), game_key="three_card_poker", unlocks_game_keys=("blackjack_6_5",)),
    Achievement("tcp_hands_100", "Play 100 Hands (Three Card Poker)", "Ante enthusiast", 10,
                (CATEGORY_GAME,), game_key="three_card_poker"),
    Achievement("tcp_hands_500", "Play 500 Hands (Three Card Poker)", "Prime real estate", 10,
                (CATEGORY_GAME,), game_key="three_card_poker"),
    Achievement("tcp_hands_1000", "Play 1,000 Hands (Three Card Poker)", "Fold this into your daily routine", 10,
                (CATEGORY_GAME,), game_key="three_card_poker"),
    Achievement("tcp_hands_5000", "Play 5,000 Hands (Three Card Poker)", "You could deal this one in your sleep",
                10, (CATEGORY_GAME,), game_key="three_card_poker"),
    Achievement("tcp_triple_bonus", "Ante, Pair Plus & Prime", "The holy trinity", 10,
                (CATEGORY_GAME,), game_key="three_card_poker"),
    Achievement("tcp_fold_prime", "Fold & Still Win Prime", "Folding was the right call", 10,
                (CATEGORY_GAME,), game_key="three_card_poker"),

    # -- Blackjack (game) -- covers Standard + Counting + 6:5, one shared
    # GAME_KEY -- 100/500 are its own table-unlock milestones, deliberately
    # untouched by the "next main game" move to 20 hands (see above).
    Achievement("bj_hands_20", "Play 20 Hands (Blackjack)", "You've unlocked Pai Gow Poker (Face Up!).", 10,
                (CATEGORY_GAME,), game_key="blackjack", unlocks_game_keys=("pai_gow_poker_face_up",)),
    Achievement("bj_hands_100", "Play 100 Hands (Blackjack)", "You've unlocked Blackjack (Standard).", 10,
                (CATEGORY_GAME,), game_key="blackjack", unlocks_game_keys=("blackjack",)),
    Achievement("bj_hands_500", "Play 500 Hands (Blackjack)", "You've unlocked Blackjack (Counting).", 10,
                (CATEGORY_GAME,), game_key="blackjack", unlocks_game_keys=("blackjack_count",)),
    Achievement("bj_hands_1000", "Play 1,000 Hands (Blackjack)", "The house respects you now", 10,
                (CATEGORY_GAME,), game_key="blackjack"),
    Achievement("bj_hands_5000", "Play 5,000 Hands (Blackjack)", "Basic strategy is basically your native tongue",
                10, (CATEGORY_GAME,), game_key="blackjack"),
    Achievement("bj_both_boxes_main", "Double Winner (Main Bet)", "Blackjack!", 10,
                (CATEGORY_GAME,), game_key="blackjack"),
    Achievement("bj_both_boxes_side", "Double Winner (Side Bet)", "Winner, Winner, Chicken Dinner!", 10,
                (CATEGORY_GAME,), game_key="blackjack"),

    # -- Pai Gow Poker (game) -- Standard and Face Up are NOT a shared
    # GAME_KEY the way Blackjack's three tables are (see
    # games/pai_gow_poker/logic.py vs games/pai_gow_poker_face_up/logic.py --
    # "pai_gow_poker" vs "pai_gow_poker_face_up", genuinely separate stats
    # buckets, and that stays true -- the Stats screen still breaks them out
    # separately). For ACHIEVEMENT purposes, though, a hand of either table
    # should count as a hand of "Pai Gow Poker" -- see
    # ACHIEVEMENT_GAME_KEY_ALIASES below, which folds
    # "pai_gow_poker_face_up" into this shared "pai_gow_poker" bucket
    # before check_round ever looks at PER_GAME_HANDS_MILESTONES, so these
    # are keyed to the merged bucket directly (not either table's own raw
    # GAME_KEY).
    Achievement("pgp_hands_20", "Play 20 Hands (Pai Gow Poker)", "You've unlocked Mississippi Stud.", 10,
                (CATEGORY_GAME,), game_key="pai_gow_poker", unlocks_game_keys=("mississippi_stud",)),
    Achievement("pgp_hands_100", "Play 100 Hands (Pai Gow Poker)",
                "You've unlocked Pai Gow Poker (Standard).", 10,
                (CATEGORY_GAME,), game_key="pai_gow_poker", unlocks_game_keys=("pai_gow_poker",)),
    Achievement("pgp_hands_500", "Play 500 Hands (Pai Gow Poker)",
                "Front hand, back hand, whole hand devoted", 10,
                (CATEGORY_GAME,), game_key="pai_gow_poker"),
    Achievement("pgp_hands_1000", "Play 1,000 Hands (Pai Gow Poker)",
                "Setting hands is basically a reflex now", 10,
                (CATEGORY_GAME,), game_key="pai_gow_poker"),
    Achievement("pgp_hands_5000", "Play 5,000 Hands (Pai Gow Poker)", "Dragon-level dedication", 10,
                (CATEGORY_GAME,), game_key="pai_gow_poker"),

    # -- One 20/100/500/1,000/5,000 ladder per remaining game, each 20-hand
    # entry the chain's own link to the next game -- bac_hands_20 is the
    # exception, since Baccarat is the end of the chain with nothing left
    # to unlock.
    Achievement("ms_hands_20", "Play 20 Hands (Mississippi Stud)", "You've unlocked Ultimate Texas Hold'em.", 10,
                (CATEGORY_GAME,), game_key="mississippi_stud", unlocks_game_keys=("ultimate_texas_holdem",)),
    Achievement("ms_hands_100", "Play 100 Hands (Mississippi Stud)", "Riverboat regular", 10,
                (CATEGORY_GAME,), game_key="mississippi_stud"),
    Achievement("ms_hands_500", "Play 500 Hands (Mississippi Stud)", "3rd street, 4th street, home street", 10,
                (CATEGORY_GAME,), game_key="mississippi_stud"),
    Achievement("ms_hands_1000", "Play 1,000 Hands (Mississippi Stud)", "The riverboat knows your name", 10,
                (CATEGORY_GAME,), game_key="mississippi_stud"),
    Achievement("ms_hands_5000", "Play 5,000 Hands (Mississippi Stud)", "You ARE the riverboat now", 10,
                (CATEGORY_GAME,), game_key="mississippi_stud"),

    Achievement("uth_hands_20", "Play 20 Hands (Ultimate Texas Hold'em)", "You've unlocked Let It Ride.", 10,
                (CATEGORY_GAME,), game_key="ultimate_texas_holdem", unlocks_game_keys=("let_it_ride",)),
    Achievement("uth_hands_100", "Play 100 Hands (Ultimate Texas Hold'em)", "Check-raise reflexes installed", 10,
                (CATEGORY_GAME,), game_key="ultimate_texas_holdem"),
    Achievement("uth_hands_500", "Play 500 Hands (Ultimate Texas Hold'em)", "Trip bets, trip dedication", 10,
                (CATEGORY_GAME,), game_key="ultimate_texas_holdem"),
    Achievement("uth_hands_1000", "Play 1,000 Hands (Ultimate Texas Hold'em)",
                "The dealer deals to you personally now", 10, (CATEGORY_GAME,), game_key="ultimate_texas_holdem"),
    Achievement("uth_hands_5000", "Play 5,000 Hands (Ultimate Texas Hold'em)",
                "You've gone all-in on this one, haven't you", 10,
                (CATEGORY_GAME,), game_key="ultimate_texas_holdem"),

    Achievement("lir_hands_20", "Play 20 Hands (Let It Ride)", "You've unlocked High Card Flush.", 10,
                (CATEGORY_GAME,), game_key="let_it_ride", unlocks_game_keys=("high_card_flush",)),
    Achievement("lir_hands_100", "Play 100 Hands (Let It Ride)", "Letting it ride, repeatedly", 10,
                (CATEGORY_GAME,), game_key="let_it_ride"),
    Achievement("lir_hands_500", "Play 500 Hands (Let It Ride)", "Pulling back is for other people", 10,
                (CATEGORY_GAME,), game_key="let_it_ride"),
    Achievement("lir_hands_1000", "Play 1,000 Hands (Let It Ride)",
                "You let it ride so often it's basically parked", 10, (CATEGORY_GAME,), game_key="let_it_ride"),
    Achievement("lir_hands_5000", "Play 5,000 Hands (Let It Ride)",
                "At this point just leave the bet there permanently", 10,
                (CATEGORY_GAME,), game_key="let_it_ride"),

    Achievement("hcf_hands_20", "Play 20 Hands (High Card Flush)", "You've unlocked Baccarat.", 10,
                (CATEGORY_GAME,), game_key="high_card_flush", unlocks_game_keys=("baccarat",)),
    Achievement("hcf_hands_100", "Play 100 Hands (High Card Flush)", "Flush with experience", 10,
                (CATEGORY_GAME,), game_key="high_card_flush"),
    Achievement("hcf_hands_500", "Play 500 Hands (High Card Flush)", "Straight to the point by now", 10,
                (CATEGORY_GAME,), game_key="high_card_flush"),
    Achievement("hcf_hands_1000", "Play 1,000 Hands (High Card Flush)", "You could flush out a living at this",
                10, (CATEGORY_GAME,), game_key="high_card_flush"),
    Achievement("hcf_hands_5000", "Play 5,000 Hands (High Card Flush)", "A high card connoisseur", 10,
                (CATEGORY_GAME,), game_key="high_card_flush"),

    # Baccarat is the end of the chain -- none of its own milestones unlock
    # anything further.
    Achievement("bac_hands_20", "Play 20 Hands (Baccarat)", "Warming up the shoe", 10,
                (CATEGORY_GAME,), game_key="baccarat"),
    Achievement("bac_hands_100", "Play 100 Hands (Baccarat)", "Bond would be proud", 10,
                (CATEGORY_GAME,), game_key="baccarat"),
    Achievement("bac_hands_500", "Play 500 Hands (Baccarat)", "Bank on it", 10,
                (CATEGORY_GAME,), game_key="baccarat"),
    Achievement("bac_hands_1000", "Play 1,000 Hands (Baccarat)", "Tie bets are basically your love language now",
                10, (CATEGORY_GAME,), game_key="baccarat"),
    Achievement("bac_hands_5000", "Play 5,000 Hands (Baccarat)", "You've dealt more shoes than the casino has",
                10, (CATEGORY_GAME,), game_key="baccarat"),
]

ACHIEVEMENTS = {a.key: a for a in _DEFS}  # dict preserves the display order above

# (threshold, achievement_key) -- checked against FinanceManager's own
# lifetime_deposited, so (like HANDS_LADDER) every threshold at or below the
# current lifetime total is (re-)checked on every deposit, not just the one
# just crossed -- award()'s own idempotency back-fills the rest for free.
DEPOSIT_LADDER = [
    (200, "deposit_200"), (1000, "deposit_1000"), (5000, "deposit_5000"), (10000, "deposit_10000"),
]

# (threshold, achievement_key) -- checked against a single withdrawal's own
# amount, NOT a lifetime running total (unlike DEPOSIT_LADDER just above) --
# see AchievementsManager.check_withdraw. A big enough single withdrawal
# still fires every threshold it clears at once (e.g. one £10,000 cash-out
# fires all four), same "back-fill everything already met" idempotency.
WITHDRAW_LADDER = [
    (200, "withdraw_200"), (1000, "withdraw_1000"), (5000, "withdraw_5000"), (10000, "withdraw_10000"),
]

# (threshold, achievement_key) -- every threshold at or below the current
# cross-game total is (re-)checked every round, not just the one just
# crossed, so award()'s own idempotency also back-fills an existing save's
# backlog for free the first time this ships (see
# AchievementsManager.check_round).
HANDS_LADDER = [
    (10, "hands_10"), (100, "hands_100"), (500, "hands_500"), (1000, "hands_1000"),
    (2500, "hands_2500"), (5000, "hands_5000"), (10000, "hands_10000"),
]

# game_key -> [(threshold, achievement_key), ...] -- a LIST per game (not
# just one tuple), same "every threshold at or below the current total is
# (re-)checked every round" shape as HANDS_LADDER above. Every game carries
# the same five thresholds (20/100/500/1,000/5,000) as every other one --
# only WHICH of those, if any, also carries an unlocks_game_keys effect
# differs: the 20-hand entry unlocks the next MAIN game in the chain (see
# the achievement definitions' own top-of-section comment for why it's 20
# and not 100), while Blackjack's own 100/500 and Pai Gow Face Up's own
# 100 additionally unlock a further TABLE of that same game, untouched by
# the 20-hand change. Adding a game's own next milestone later is just one
# more tuple in its own list.
PER_GAME_HANDS_MILESTONES = {
    "three_card_poker": [
        (20, "tcp_hands_20"), (100, "tcp_hands_100"), (500, "tcp_hands_500"),
        (1000, "tcp_hands_1000"), (5000, "tcp_hands_5000"),
    ],
    "blackjack": [
        (20, "bj_hands_20"), (100, "bj_hands_100"), (500, "bj_hands_500"),
        (1000, "bj_hands_1000"), (5000, "bj_hands_5000"),
    ],
    "pai_gow_poker": [
        (20, "pgp_hands_20"), (100, "pgp_hands_100"), (500, "pgp_hands_500"),
        (1000, "pgp_hands_1000"), (5000, "pgp_hands_5000"),
    ],
    "mississippi_stud": [
        (20, "ms_hands_20"), (100, "ms_hands_100"), (500, "ms_hands_500"),
        (1000, "ms_hands_1000"), (5000, "ms_hands_5000"),
    ],
    "ultimate_texas_holdem": [
        (20, "uth_hands_20"), (100, "uth_hands_100"), (500, "uth_hands_500"),
        (1000, "uth_hands_1000"), (5000, "uth_hands_5000"),
    ],
    "let_it_ride": [
        (20, "lir_hands_20"), (100, "lir_hands_100"), (500, "lir_hands_500"),
        (1000, "lir_hands_1000"), (5000, "lir_hands_5000"),
    ],
    "high_card_flush": [
        (20, "hcf_hands_20"), (100, "hcf_hands_100"), (500, "hcf_hands_500"),
        (1000, "hcf_hands_1000"), (5000, "hcf_hands_5000"),
    ],
    "baccarat": [
        (20, "bac_hands_20"), (100, "bac_hands_100"), (500, "bac_hands_500"),
        (1000, "bac_hands_1000"), (5000, "bac_hands_5000"),
    ],
}

# unlocks_game_key -> Achievement -- the reverse lookup for "which
# achievement unlocks this game/table", used by a locked tile's hover
# tooltip and its early-unlock-for-Crowns click prompt (see
# ui/main_menu.py/ui/table_menu.py). Built from EVERY key in each
# achievement's own unlocks_game_keys (not just the first) -- the
# mechanism supports one achievement unlocking more than one thing even
# though none currently do -- still one-to-one per unlock key (nothing is
# ever unlocked two different ways), so the last achievement to declare a
# given key would silently win if that ever stopped being true.
UNLOCK_SOURCE = {key: a for a in _DEFS for key in a.unlocks_game_keys}

# raw game_key (as passed to check_round by a specific table's own UI) ->
# the key achievement PROGRESS actually accumulates under, for a family of
# tables that should count as "the same game" for achievement purposes
# without necessarily sharing a GameStatsManager/Stats-screen bucket too.
# Blackjack's own 3 tables need no entry here at all -- blackjack_count and
# blackjack_6_5 simply never override their parent's GAME_KEY, so all 3
# already pass the literal same string ("blackjack") into check_round with
# zero aliasing required. Pai Gow Poker's 2 tables, by contrast, keep
# genuinely separate GAME_KEYs (separate Stats-screen sections -- see
# games/pai_gow_poker/logic.py vs games/pai_gow_poker_face_up/logic.py), so
# achievement-side merging has to happen explicitly, here, instead.
ACHIEVEMENT_GAME_KEY_ALIASES = {
    "pai_gow_poker_face_up": "pai_gow_poker",
}

# -- Crowns Store pricing (kept here, alongside the rest of the Crowns
# economy, rather than in ui/store_screen.py) -------------------------------
STORE_UNLOCK_PRICE_CROWNS = 150  # a deliberately steep price relative to the
# uniform 10 Crowns/achievement economy today (roughly 15 achievements'
# worth) -- the store is a pay-to-skip convenience, not meant to trivialize
# playing toward an unlock achievement. Easily retuned later; it's one
# constant.
THEME_UNLOCK_PRICE_CROWNS = 80  # one flat price for every premium theme in
# core/themes.py's own PREMIUM_THEMES catalog (used to be priced
# per-theme, all three happening to already be 80 -- flattened since there
# was never a reason for two premium themes to cost different amounts, and
# a flat price means adding a new one never means also deciding what to
# charge for it).
CARD_STYLE_UNLOCK_PRICE_CROWNS = 80  # same flat-pricing reasoning as
# THEME_UNLOCK_PRICE_CROWNS just above, for core/unlocks.py's own
# PREMIUM_CARD_STYLES catalog -- kept at the same 80 since a card style is
# the same kind of purely-cosmetic purchase a felt theme already is, not
# because the two catalogs need to share one price forever.
#
# core/unlocks.py's own PREMIUM_FEATURES catalog is priced PER-ENTRY (its
# own `price` key) rather than with a flat constant here -- unlike the
# three interchangeable catalogs above, one feature can be a functional
# gameplay aid (Blackjack Strategy Guide, 200) and the next a small
# cosmetic toggle (Four Colour Deck, 20), with no one "fair" flat price
# that fits both.
