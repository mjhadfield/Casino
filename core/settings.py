"""App-wide settings, shared across all games."""
from core.persistence import load_json, save_json
from core.unlocks import PREMIUM_CARD_STYLES, PREMIUM_TABLE_THEMES

DEFAULT_SETTINGS = {
    "sound_enabled": True,
    "animations_enabled": True,
    "table_theme": "Terminal",
    "card_style": "Light",
    "strategy_guide_enabled": False,
    "jackpot_rate_per_second": 0.01,
}

# Table felt options -- purely a per-table cosmetic choice (the poker table's
# own felt background + trim), independent of the app's one fixed global
# accent (see ui/theme.py) used everywhere else. Reskinned to fit that same
# terminal aesthetic without becoming a global accent picker themselves.
#
# "Terminal" is the default: its felt (#141917) is the exact same background
# as the Main Menu's own page (ui/theme.py's MENU_BG) and its accent
# (#35e0a0) is the app's one global accent (ui/theme.py's ACCENT) -- not
# imported directly (core/ stays UI-framework-agnostic), just kept in sync by
# hand since it's meant to look like the rest of the app rather than a
# distinct felt colourway the other four are.
TABLE_THEMES = {
    "Terminal": {"felt": "#141917", "felt_dark": "#0b0e0d", "accent": "#35e0a0"},
    "Classic Green": {"felt": "#0a2e14", "felt_dark": "#051a0b", "accent": "#39ff88"},
    "Amber CRT": {"felt": "#3a2308", "felt_dark": "#1f1204", "accent": "#ffb347"},
    "Muted Grey": {"felt": "#2a2a2a", "felt_dark": "#151515", "accent": "#cfd6d1"},
}

# Premium, Crowns-gated felt themes now live in core/unlocks.py's own
# PREMIUM_TABLE_THEMES (imported above), alongside every other kind of
# Crowns-gated unlockable, tracked the same way a game's own lock state is
# (see that module's own docstring) -- theme() below needs it for its own
# fallback lookup.

# Card style options -- a card's own front colours/outline effect and back
# design (see ui/card_widgets.py's own docstring for the shared dict shape
# every entry here follows). "Light" is the default -- today's one and
# only look, before card styles existed at all. "Dark" keeps the exact
# same (felt-themed) back Light has -- only the FRONT changes, to a black
# background with light rank/suit text and a light inner accent border.
# Premium styles (core/unlocks.py's PREMIUM_CARD_STYLES) work exactly like
# PREMIUM_TABLE_THEMES above: bought in the Crowns Store or unlocked by a
# future achievement, through that module's own is_unlocked/set_unlocked.
STANDARD_CARD_STYLES = {
    "Light": {
        "front_bg": "#fdfdf5", "front_border": "#222222",
        "text_black": "#1a1a1a", "text_red": "#c0392b",
        "outline": None, "back": {"kind": "felt"},
    },
    "Dark": {
        "front_bg": "#161616", "front_border": "#555555",
        "text_black": "#e8e8e8", "text_red": "#e83e3e",
        "outline": None, "back": {"kind": "felt"},
    },
}

# Available chip denominations for bet controls -- shared across games.
CHIP_VALUES = [1, 5, 10, 25, 50, 100]


class SettingsManager:
    def __init__(self, save_path):
        self.save_path = save_path
        self.data = load_json(save_path, DEFAULT_SETTINGS)

    def get(self, key):
        return self.data.get(key, DEFAULT_SETTINGS.get(key))

    def set(self, key, value):
        self.data[key] = value
        self._save()

    def theme(self):
        # Falls back through TABLE_THEMES then PREMIUM_TABLE_THEMES since a
        # player's saved table_theme can now legitimately name a purchased
        # premium theme -- SettingsManager itself stays ownership-agnostic
        # (it doesn't know about AchievementsManager); ui/settings_screen.py
        # is solely responsible for only ever letting a player select a
        # theme they actually own.
        name = self.data.get("table_theme", "Terminal")
        return TABLE_THEMES.get(name) or PREMIUM_TABLE_THEMES.get(name) or TABLE_THEMES["Terminal"]

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
