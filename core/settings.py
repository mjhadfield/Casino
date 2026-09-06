"""App-wide settings, shared across all games."""
from core.persistence import load_json, load_raw, save_json
from core.unlocks import PREMIUM_CARD_STYLES
from core.themes import resolve as resolve_theme

DEFAULT_SETTINGS = {
    "sound_enabled": True,
    "animations_enabled": True,
    "theme": "Terminal",
    "card_style": "Light",
    "strategy_guide_enabled": False,
    "four_colour_deck_enabled": False,
    "jackpot_rate_per_second": 0.01,
}

# The theme catalog itself (free THEMES + Crowns-gated PREMIUM_THEMES) now
# lives in core/themes.py -- see that module's own docstring for the full
# 8-key shape (felt/felt_dark/accent, still read directly by every game
# table, plus the app-wide bg/bg_elevated/menu_bg/border/border_soft chrome
# tokens ui/theme.py applies everywhere else). theme() below just resolves
# a saved name through it.

# Card style options -- a card's own front colours/outline effect and back
# design (see ui/card_widgets.py's own docstring for the shared dict shape
# every entry here follows). "Light" is the default -- today's one and
# only look, before card styles existed at all. "Dark" keeps the exact
# same (felt-themed) back Light has -- only the FRONT changes, to a black
# background with light rank/suit text and a light inner accent border.
# Premium styles (core/unlocks.py's PREMIUM_CARD_STYLES) work exactly like
# core/themes.py's PREMIUM_THEMES: bought in the Crowns Store or unlocked by
# a future achievement, through that module's own is_unlocked/set_unlocked.
STANDARD_CARD_STYLES = {
    "Light": {
        "front_bg": "#fdfdf5", "front_border": "#222222",
        "text_black": "#1a1a1a", "text_red": "#c0392b",
        "text_blue": "#1f5fa8", "text_green": "#1f7a3d",
        "outline": None, "back": {"kind": "felt"},
    },
    "Dark": {
        "front_bg": "#161616", "front_border": "#555555",
        "text_black": "#e8e8e8", "text_red": "#e83e3e",
        "text_blue": "#4fa8f5", "text_green": "#4caf50",
        "outline": None, "back": {"kind": "felt"},
    },
}

# Available chip denominations for bet controls -- shared across games.
CHIP_VALUES = [1, 5, 10, 25, 50, 100]


class SettingsManager:
    def __init__(self, save_path):
        self.save_path = save_path
        self.data = load_json(save_path, DEFAULT_SETTINGS)
        # One-off migration: "table_theme" (the old felt-only setting key)
        # became "theme" once it started driving the whole app, not just a
        # table's felt -- see core/themes.py. Checked against load_raw()
        # (the save FILE's own content) rather than self.data above, since
        # load_json has already back-filled self.data["theme"] from
        # DEFAULT_SETTINGS regardless of whether the file itself ever had
        # it -- an existing save that already picked a theme under the old
        # key keeps that exact choice; only a save with neither key gets
        # DEFAULT_SETTINGS' own "theme" fallback via get() below.
        raw = load_raw(save_path)
        if "theme" not in raw and "table_theme" in raw:
            self.data["theme"] = raw["table_theme"]
            self._save()

    def get(self, key):
        return self.data.get(key, DEFAULT_SETTINGS.get(key))

    def set(self, key, value):
        self.data[key] = value
        self._save()

    def theme(self):
        # SettingsManager stays ownership-agnostic (it doesn't know about
        # AchievementsManager) -- ui/settings_screen.py is solely
        # responsible for only ever letting a player select a theme they
        # actually own. resolve_theme() (core/themes.py) falls back to
        # Terminal for an unknown/no-longer-owned name.
        return resolve_theme(self.data.get("theme", "Terminal"))

    def card_style(self):
        # Same fallback shape as theme() just above, and the same ownership
        # caveat: this stays ownership-agnostic (it doesn't know about
        # AchievementsManager), so ui/settings_screen.py is solely
        # responsible for only ever letting a player select a style they
        # actually own.
        name = self.data.get("card_style", "Light")
        return STANDARD_CARD_STYLES.get(name) or PREMIUM_CARD_STYLES.get(name) or STANDARD_CARD_STYLES["Light"]

    def _save(self):
        save_json(self.save_path, self.data)
