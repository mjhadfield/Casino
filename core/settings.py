"""App-wide settings, shared across all games."""
from core.persistence import load_json, save_json

DEFAULT_SETTINGS = {
    "sound_enabled": True,
    "animations_enabled": True,
    "table_theme": "Matrix",
    "jackpot_rate_per_second": 0.01,
}

# Table felt options -- purely a per-table cosmetic choice (the poker table's
# own felt background + trim), independent of the app's one fixed global
# accent (see ui/theme.py) used everywhere else. Reskinned to fit that same
# terminal aesthetic without becoming a global accent picker themselves.
TABLE_THEMES = {
    "Matrix": {"felt": "#0a2e14", "felt_dark": "#051a0b", "accent": "#39ff88"},
    "Amber CRT": {"felt": "#3a2308", "felt_dark": "#1f1204", "accent": "#ffb347"},
    "Ice": {"felt": "#0d2a45", "felt_dark": "#071a2c", "accent": "#5fd4ff"},
    "Mono": {"felt": "#2a2a2a", "felt_dark": "#151515", "accent": "#cfd6d1"},
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
        return TABLE_THEMES.get(self.data.get("table_theme", "Matrix"), TABLE_THEMES["Matrix"])

    def _save(self):
        save_json(self.save_path, self.data)
