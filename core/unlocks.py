"""
Foundations for a future achievements/unlock-progression system -- tracks
which games are locked/unlocked, persisted the same way every other piece of
app state is (core/persistence.py). This module deliberately knows nothing
about *how* a game gets unlocked -- that's a future achievements engine;
today the only unlocking mechanism is the admin checkbox panel in Settings
(ui/settings_screen.py's "$ game --unlock" section, gated the same way its
other admin sections are -- see ui/dialogs.py's ensure_admin_unlocked).

ui/main_menu.py is what actually reads this to decide each tile's colours:
every tile always shows its real icon/name/subtitle regardless of lock
state -- an unlocked game (and, once it's actually been built, is playable)
renders normally; a locked one is recoloured into the dark-red "locked"
palette, with a padlock badge, but nothing about what it actually is stays
hidden.
"""
from core.persistence import load_json, save_json

# Every game that can appear on the main menu, in the same order the tile
# grid lists them (ui/main_menu.py's GAMES) -- the four already-shipped
# games start (and, until achievements actually exist, always stay)
# unlocked; every not-yet-built one starts locked, so its tile shows in the
# dark-red "locked" palette until an admin (soon, an achievement) unlocks it.
DEFAULT_UNLOCKS = {
    "three_card_poker": True,
    "blackjack": True,
    "blackjack_count": True,
    "pai_gow_poker": True,
    "pai_gow_poker_face_up": True,
    "mississippi_stud": True,
    "baccarat": True,
    "let_it_ride": True,
    "ultimate_texas_holdem": True,
    "high_card_flush": True,
}


class UnlocksManager:
    def __init__(self, save_path):
        self.save_path = save_path
        self.data = load_json(save_path, DEFAULT_UNLOCKS)
        # A save file predating a since-added game key just won't have it --
        # fill it in from the default rather than treat a missing key as
        # locked/unlocked inconsistently depending on which lookup asked.
        changed = False
        for key, default in DEFAULT_UNLOCKS.items():
            if key not in self.data:
                self.data[key] = default
                changed = True
        if changed:
            self._save()

    def is_unlocked(self, game_key):
        return bool(self.data.get(game_key, DEFAULT_UNLOCKS.get(game_key, False)))

    def set_unlocked(self, game_key, unlocked):
        self.data[game_key] = bool(unlocked)
        self._save()

    def _save(self):
        save_json(self.save_path, self.data)
