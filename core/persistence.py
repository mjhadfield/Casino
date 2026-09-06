"""Tiny generic JSON load/save helper, shared by finances.py and settings.py
(and by any future game that needs its own persisted state)."""
import json
import os


def load_raw(path) -> dict:
    """The file's own content, with nothing from any `defaults` dict merged
    in -- {} if it doesn't exist or fails to parse. load_json() below (what
    almost every caller actually wants) pre-seeds every default key, which
    makes "is this key actually IN THE SAVE FILE" and "is this key just
    sitting at its own default value" indistinguishable from its result;
    a one-off key-rename migration (see core/settings.py's own "theme" for
    an example) needs the former, so it reads this instead."""
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                return loaded
        except (json.JSONDecodeError, OSError):
            pass  # fall back to {} rather than crash on a corrupt save file
    return {}


def load_json(path, defaults: dict) -> dict:
    data = dict(defaults)
    data.update(load_raw(path))
    return data


def save_json(path, data: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, path)  # atomic-ish write, avoids truncated saves
