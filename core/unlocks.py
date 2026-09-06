"""
Tracks which games are locked/unlocked, persisted the same way every other
piece of app state is (core/persistence.py). This module deliberately knows
nothing about *how* a game gets unlocked -- that's core/achievements.py's
own job now (AchievementsManager.award() calls set_unlocked() directly when
an achievement's own unlocks_game_keys fire), plus the admin checkbox panel
in Settings (ui/settings_screen.py's "$ game --unlock" section, gated the
same way its other admin sections are -- see ui/dialogs.py's
ensure_admin_unlocked) as a manual override.

ui/main_menu.py is what actually reads this to decide each tile's colours:
every tile always shows its real icon/name/subtitle regardless of lock
state -- an unlocked game (and, once it's actually been built, is playable)
renders normally; a locked one is recoloured into the dark-red "locked"
palette, with a padlock badge, but nothing about what it actually is stays
hidden. A game with more than one TABLE (see ui/table_menu.py) works the
same way one level down: its own sub-menu screen renders each table's tile
locked/unlocked exactly like a main-menu tile does, keyed by that table's
own entry here -- reaching the sub-menu at all still requires the main
tile's own key (almost always the base table's) to be unlocked first.

Every key here is a real *unlock* key -- not necessarily a distinct GAME_KEY
for GameStatsManager/achievements. A table variant that shares its base
game's stats bucket (see games/blackjack_count/logic.py, games/blackjack_6_5
/logic.py) still gets its own independent key here, so it can be locked or
unlocked without touching the base table's own state.

This is also the one place any OTHER Crowns-gated unlockable lives -- not
just games/tables. Premium themes (core/themes.py's PREMIUM_THEMES) work
exactly like a game does: earned via an achievement's own
unlocks_game_keys (core/achievements.py's award()/_reconcile_unlocks
already apply those through set_unlocked() with no idea whether the key
they're flipping is a game or a theme), or bought outright in the Crowns
Store (AchievementsManager.purchase_theme(), mirroring purchase_unlock()).
A future unlockable of a new kind (a card back style, a bonus feature...)
should follow the exact same shape: its own catalog dict (plus whatever
cosmetic/config data it carries), a flat Crowns price alongside the rest
of the Store's pricing (core/achievements_data.py), and ownership tracked
the same way, through this module's own is_unlocked/set_unlocked -- never
a bespoke owned-list of its own. core/themes.py's own THEMES catalog is
deliberately NOT here: those are always free, need no unlock state at all,
and READING that distinction (is this name always-free, or does it need an
entry in this module) is what tells the rest of the app whether a given
theme name needs an is_unlocked() check before it can be selected.
"""
from core.persistence import load_json, save_json

# Every game/table that can appear on a menu screen (the main menu, or a
# game's own table-picker sub-menu -- see ui/table_menu.py), in roughly the
# same order those screens list them. Three Card Poker is the only one that
# starts unlocked -- every other key here is one link in the single ordered
# progression chain core/achievements_data.py's PER_GAME_HANDS_MILESTONES/
# UNLOCK_SOURCE define (or bought early in the Crowns Store, main-menu-tile
# games only). Changing a value here only ever affects a brand-new player:
# UnlocksManager's own backfill (below) only ever fills in a key MISSING
# from an existing save, never overwrites one already present, so an
# existing player's own unlock state is untouched by a future change to
# these defaults.
DEFAULT_UNLOCKS = {
    "three_card_poker": True,
    "blackjack": False,
    "blackjack_count": False,
    "blackjack_6_5": False,
    "pai_gow_poker": False,
    "pai_gow_poker_face_up": False,
    "mississippi_stud": False,
    "baccarat": False,
    "let_it_ride": False,
    "ultimate_texas_holdem": False,
    "high_card_flush": False,
}

# Premium, Crowns-gated card styles -- same story as core/themes.py's
# PREMIUM_THEMES (bought via AchievementsManager.purchase_card_style, priced by
# core/achievements_data.py's CARD_STYLE_UNLOCK_PRICE_CROWNS, or unlocked by
# a future achievement), sitting alongside core/settings.py's own always-
# free STANDARD_CARD_STYLES the same way THEMES/PREMIUM_THEMES split (just
# across core/settings.py and here rather than both in core/themes.py --
# a card style is still purely a card's own look, never the whole app's).
# Dict shape is ui/card_widgets.py's own -- see that module's
# docstring for what each of front_bg/front_border/text_black/text_red/
# outline/back actually does. The two Gold styles deliberately SHARE one
# back dict object (front is the only thing "Gold (Light)" vs "Gold
# (Dark)" changes) -- Crimson and Void each get their own, echoing (not
# tied to owning) the Crimson Velvet/Neon Void felt themes' own palettes.
# Adding a new one is exactly this: one more entry here.
_GOLD_BACK = {"kind": "fancy", "bg": "#0d0a02", "trim": "#d4af37", "emblem": "star"}
PREMIUM_CARD_STYLES = {
    "Gold (Light)": {
        "front_bg": "#fdfdf5", "front_border": "#d4af37",
        "text_black": "#1a1a1a", "text_red": "#c0392b",
        "text_blue": "#1f5fa8", "text_green": "#1f7a3d",
        "outline": "#d4af37", "back": _GOLD_BACK,
    },
    "Gold (Dark)": {
        "front_bg": "#161616", "front_border": "#d4af37",
        "text_black": "#e8e8e8", "text_red": "#e83e3e",
        "text_blue": "#4fa8f5", "text_green": "#4caf50",
        "outline": "#d4af37", "back": _GOLD_BACK,
    },
    "Crimson": {
        "front_bg": "#fdfdf5", "front_border": "#ff4d6d",
        "text_black": "#1a1a1a", "text_red": "#c0392b",
        "text_blue": "#1f5fa8", "text_green": "#1f7a3d",
        "outline": "#ff4d6d", "back": {"kind": "fancy", "bg": "#3a0d14", "trim": "#ff4d6d", "emblem": "diamond"},
    },
    "Void": {
        "front_bg": "#161616", "front_border": "#b026ff",
        "text_black": "#e8e8e8", "text_red": "#e83e3e",
        "text_blue": "#4fa8f5", "text_green": "#4caf50",
        "outline": "#b026ff", "back": {"kind": "fancy", "bg": "#0a0018", "trim": "#b026ff", "emblem": "hex"},
    },
}

# Premium, Crowns-gated FEATURES -- distinct from a felt theme/card style
# not because it can't be cosmetic (four_colour_deck below is), but because
# it's TOGGLED on/off in Settings once owned rather than picked from a row
# of swatches (see ui/settings_screen.py's own "Features" category, only
# ever built for keys the player actually owns). Bought via
# AchievementsManager.purchase_feature, priced individually by each entry's
# own `price` (unlike the flat-priced catalogs above -- a feature can be
# anything from a purely cosmetic toggle to a genuine gameplay aid, so
# there's no one "fair" flat price the way there is for interchangeable
# felt colours), or unlocked by a future achievement the same way any
# game/theme/card style already can be. Keyed by a stable internal id (not
# a display name, unlike the catalogs above) -- `name`/`description` are
# what ui/store_screen.py actually renders. Adding a new one is exactly
# this: one more entry here, plus whatever game-side code actually reads
# app.achievements.owns_feature(key).
PREMIUM_FEATURES = {
    "strategy_guide": {
        "name": "Blackjack Strategy Guide",
        "description": "Live basic-strategy recommendations on the Blackjack table.",
        "price": 200,  # priced well above the purely-cosmetic entries below
        # since this is a functional gameplay aid, not just a look.
    },
    "four_colour_deck": {
        "name": "Four Colour Deck",
        "description": "Diamonds render blue and clubs render green, for easier suit reading.",
        "price": 20,  # a small, purely cosmetic toggle -- priced well under
        # even the flat 80 Crowns a premium theme/card style costs.
    },
}

# new entry-point key -> the OLD single flag a save predating that table
# might already have True -- see UnlocksManager's own migration using this.
_ENTRY_POINT_MIGRATIONS = {
    "blackjack_6_5": "blackjack",
    "pai_gow_poker_face_up": "pai_gow_poker",
}


class UnlocksManager:
    def __init__(self, save_path, always_unlocked=False):
        self.save_path = save_path
        # Sandbox Mode's own bypass -- every is_unlocked() call below
        # short-circuits to True regardless of what's actually on disk, so
        # a Sandbox player automatically owns anything unlockable added
        # later too, with no seed data to keep in sync (see main.py's
        # start_session, which derives this from the player's own
        # account_type). set_unlocked() still writes normally underneath;
        # it just never matters for a Sandbox player's own reads.
        self.always_unlocked = always_unlocked
        self.data = load_json(save_path, DEFAULT_UNLOCKS)
        changed = False
        # One-off migration: a multi-table game's own entry-point key
        # (blackjack_6_5, pai_gow_poker_face_up) didn't exist as a concept
        # before that game grew multiple tables -- an existing save that
        # already had the OLD single flag (blackjack, pai_gow_poker) True
        # shouldn't suddenly find itself locked out of the whole game just
        # because the main-menu tile's own gating key moved to the actual
        # entry point. Only ever applies the FIRST time the new key is
        # backfilled in (a player who's since earned/lost it for real keeps
        # whatever they actually have).
        for new_key, old_key in _ENTRY_POINT_MIGRATIONS.items():
            if new_key not in self.data and self.data.get(old_key):
                self.data[new_key] = True
                changed = True
        # A save file predating a since-added game key just won't have it --
        # fill it in from the default rather than treat a missing key as
        # locked/unlocked inconsistently depending on which lookup asked.
        for key, default in DEFAULT_UNLOCKS.items():
            if key not in self.data:
                self.data[key] = default
                changed = True
        if changed:
            self._save()

    def is_unlocked(self, game_key):
        if self.always_unlocked:
            return True
        return bool(self.data.get(game_key, DEFAULT_UNLOCKS.get(game_key, False)))

    def set_unlocked(self, game_key, unlocked):
        self.data[game_key] = bool(unlocked)
        self._save()

    def _save(self):
        save_json(self.save_path, self.data)
