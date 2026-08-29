"""
Player roster -- the character-select layer sitting in front of every other
piece of app state. Persisted the same way everything else is
(core/persistence.py): one small JSON file, data/players.json, listing every
profile that's ever been created.

A player's *slug* (its directory name under data/players/<slug>/) is chosen
once, at creation, and never changes -- only the display `name` is editable
later (a future rename in Settings, say), so renaming a player never means
moving a live save directory around.

This module deliberately knows nothing about *which* manager files live
inside a player's directory -- that's core/players.py's caller (main.py's
CasinoApp.start_session), the same separation of concerns core/unlocks.py's
docstring describes for itself.
"""
import os
import re
import shutil
from datetime import datetime, timezone

from core.persistence import load_json, save_json

DEFAULT_ROSTER = {"players": []}

# The 13 flat save files a pre-player-select install has directly under
# data/ -- everything except jackpot.json, which stays global (see
# core/jackpot.py's docstring: one shared pot, not one per player).
LEGACY_FILENAMES = [
    "finances.json",
    "game_stats.json",
    "settings.json",
    "unlocks.json",
    "blackjack_state.json",
    "three_card_poker_state.json",
    "pai_gow_poker_state.json",
    "pai_gow_poker_face_up_state.json",
    "mississippi_stud_state.json",
    "ultimate_texas_holdem_state.json",
    "let_it_ride_state.json",
    "high_card_flush_state.json",
    "baccarat_state.json",
]

_SLUG_RUN = re.compile(r"[^a-z0-9]+")


def _now():
    return datetime.now(timezone.utc).isoformat()


class PlayerManager:
    def __init__(self, save_path):
        self.save_path = save_path
        self.data = load_json(save_path, DEFAULT_ROSTER)
        if not isinstance(self.data.get("players"), list):
            self.data["players"] = []

    def list_players(self):
        """Every profile, most-recently-played first; profiles that have
        never actually been logged into (just created, or the readme-only
        edge case of a roster entry with no last_played_at) sort last."""
        return sorted(
            self.data["players"],
            key=lambda p: p.get("last_played_at") or "",
            reverse=True,
        )

    def get(self, slug):
        for player in self.data["players"]:
            if player["slug"] == slug:
                return player
        return None

    def slugify(self, name):
        slug = _SLUG_RUN.sub("-", name.strip().lower()).strip("-")
        return slug or "player"

    def _unique_slug(self, base_slug):
        existing = {p["slug"] for p in self.data["players"]}
        if base_slug not in existing:
            return base_slug
        n = 2
        while f"{base_slug}-{n}" in existing:
            n += 1
        return f"{base_slug}-{n}"

    def create_player(self, name):
        name = name.strip()
        if not name:
            raise ValueError("Player name can't be empty.")
        slug = self._unique_slug(self.slugify(name))
        self.data["players"].append({
            "slug": slug,
            "name": name,
            "created_at": _now(),
            "last_played_at": None,
        })
        self._save()
        return slug

    def touch_last_played(self, slug):
        player = self.get(slug)
        if player is not None:
            player["last_played_at"] = _now()
            self._save()

    def player_dir(self, slug, data_root):
        return os.path.join(data_root, "players", slug)

    def delete_player(self, slug, data_root):
        """Permanently removes a player: drops their roster entry and
        deletes their entire save directory (balance, stats, unlocks,
        settings, every game's bet-tray state). Irreversible -- the logon
        screen's delete-accounts flow (ui/logon_screen.py) is the only
        caller."""
        self.data["players"] = [p for p in self.data["players"] if p["slug"] != slug]
        self._save()
        player_dir = self.player_dir(slug, data_root)
        if os.path.isdir(player_dir):
            shutil.rmtree(player_dir)

    def _save(self):
        save_json(self.save_path, self.data)


def legacy_migration_needed(data_dir, players_save_path):
    if os.path.exists(players_save_path):
        return False
    return os.path.exists(os.path.join(data_dir, "finances.json"))


def migrate_legacy_data(data_dir, players_save_path, name):
    """One-time upgrade path: folds a pre-player-select install's flat save
    files into a new profile called `name`, registered in the roster at
    players_save_path."""
    manager = PlayerManager(players_save_path)
    name = name.strip()
    slug = manager._unique_slug(manager.slugify(name))

    player_dir = os.path.join(data_dir, "players", slug)
    os.makedirs(player_dir, exist_ok=True)
    for filename in LEGACY_FILENAMES:
        src = os.path.join(data_dir, filename)
        if os.path.exists(src):
            shutil.move(src, os.path.join(player_dir, filename))

    manager.data["players"].append({
        "slug": slug,
        "name": name,
        "created_at": _now(),
        "last_played_at": None,
    })
    manager._save()
    return slug
