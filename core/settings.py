"""App-wide settings, shared across all games."""
from core.persistence import load_json, save_json

DEFAULT_SETTINGS = {
    "sound_enabled": True,
    "animations_enabled": True,
    "table_theme": "Emerald",
}

TABLE_THEMES = {
    "Emerald": {"felt": "#0b3d24", "felt_dark": "#062616", "accent": "#d4af37"},
    "Crimson": {"felt": "#4a0f1a", "felt_dark": "#2b0810", "accent": "#d4af37"},
    "Sapphire": {"felt": "#0b2545", "felt_dark": "#071730", "accent": "#c0c0c0"},
    "Graphite": {"felt": "#26282b", "felt_dark": "#0b0c0c", "accent": "#d0cdcd"},
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
        return TABLE_THEMES.get(self.data.get("table_theme", "Emerald"), TABLE_THEMES["Emerald"])

    def _save(self):
        save_json(self.save_path, self.data)
