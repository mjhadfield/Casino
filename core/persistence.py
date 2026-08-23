"""Tiny generic JSON load/save helper, shared by finances.py and settings.py
(and by any future game that needs its own persisted state)."""
import json
import os


def load_json(path, defaults: dict) -> dict:
    data = dict(defaults)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                data.update(loaded)
        except (json.JSONDecodeError, OSError):
            pass  # fall back to defaults rather than crash on a corrupt save file
    return data


def save_json(path, data: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, path)  # atomic-ish write, avoids truncated saves
