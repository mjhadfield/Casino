"""
Per-game statistics -- a separate concern from FinanceManager
(core/finances.py), which only tracks the account's overall lifetime totals.
This is what powers the "Stats" screen's game-by-game breakdown: three kinds
of data per game, kept in separate namespaces under that game's own key --

  "bets":     per-bet-type (Ante, Pair Plus, Prime, ...) wagered/returned/
              win-loss-push, and the house edge that's actually been
              realised on it -- see record_bet/game_bets/game_house_edge.
  "hands":    how often each possible hand outcome (High Card, Pair, ...,
              Royal Flush, or a fold) has actually come up -- see
              record_hand/game_hand_counts.
  "strategy": how often the player's Play/Fold decision itself was the
              statistically wrong one -- see record_strategy_decision/
              game_strategy_incorrect_counts. Only incorrect decisions are
              ever recorded (a save file predating this tracking has none,
              which reads as "every earlier decision was correct" -- the
              deliberate, explicitly-requested assumption, not an oversight).

A game's UI reports one resolved bet/hand/decision at a time; this module
knows nothing about any particular game's rules, so a future game (e.g.
Blackjack) just calls in with its own keys and a new section appears on the
Stats screen with no changes needed here.
"""
from core.persistence import load_json, save_json

DEFAULT_BET_STATS = {"wagered": 0.0, "returned": 0.0, "wins": 0, "losses": 0, "pushes": 0}


class GameStatsManager:
    def __init__(self, save_path):
        self.save_path = save_path
        self.data = load_json(save_path, {})
        self._migrate()

    def _migrate(self):
        """Save files from before "hands" existed stored each bet type
        directly under the game key (game_key -> bet_key -> stats, with no
        "bets"/"hands" nesting). Wraps those under "bets" so hand-frequency
        counts can live alongside them without colliding with a bet-type
        key. A no-op once a file's already in the current shape."""
        changed = False
        for game_key, game_data in list(self.data.items()):
            if "bets" not in game_data:
                self.data[game_key] = {"bets": game_data, "hands": {}}
                changed = True
        if changed:
            self._save()

    def _game(self, game_key):
        return self.data.setdefault(game_key, {"bets": {}, "hands": {}})

    def record_bet(self, game_key, bet_key, wagered, returned):
        """Records one resolved bet -- `wagered` is what was staked on it,
        `returned` is what came back: 0 for a loss, exactly `wagered` for a
        push, more than `wagered` for a win. A no-op if nothing was actually
        staked (a bet type that wasn't in play that round)."""
        if wagered <= 0:
            return
        bets = self._game(game_key)["bets"]
        bet = bets.setdefault(bet_key, dict(DEFAULT_BET_STATS))
        bet["wagered"] += wagered
        bet["returned"] += returned
        if returned > wagered + 1e-9:
            bet["wins"] += 1
        elif returned < wagered - 1e-9:
            bet["losses"] += 1
        else:
            bet["pushes"] += 1
        self._save()

    def game_bets(self, game_key):
        """bet_key -> stats dict for one game -- empty if nothing's been
        wagered on it yet (e.g. a game that isn't implemented yet)."""
        return self.data.get(game_key, {}).get("bets", {})

    def house_edge(self, wagered, returned):
        """The house edge realised over a wagered/returned pair, as a
        percentage -- None if nothing's been wagered (rather than a
        misleading 0%, which would read as "an edge of zero" instead of
        "no data yet")."""
        if wagered <= 0:
            return None
        return round((wagered - returned) / wagered * 100, 2)

    def game_house_edge(self, game_key):
        """Overall house edge across every bet type in one game."""
        bets = self.game_bets(game_key)
        wagered = sum(b["wagered"] for b in bets.values())
        returned = sum(b["returned"] for b in bets.values())
        return self.house_edge(wagered, returned)

    def record_hand(self, game_key, hand_label):
        """Records one round's outcome for the "Hands Made" breakdown --
        `hand_label` is any label the game defines (e.g. Three Card Poker's
        HAND_OUTCOME_LABELS: its 6 hand ranks, "Royal Flush" broken out
        from an ordinary Straight Flush, and "Fold")."""
        hands = self._game(game_key)["hands"]
        hands[hand_label] = hands.get(hand_label, 0) + 1
        self._save()

    def game_hand_counts(self, game_key):
        """hand_label -> count for one game -- empty if none recorded yet."""
        return self.data.get(game_key, {}).get("hands", {})

    def record_strategy_decision(self, game_key, folded, correct):
        """Records one round's Play/Fold decision -- a no-op if it was the
        statistically correct one, since only the incorrect count is
        actually stored (see the module docstring for why that's enough)."""
        if correct:
            return
        strategy = self._game(game_key).setdefault("strategy", {})
        key = "folded_incorrectly" if folded else "played_incorrectly"
        strategy[key] = strategy.get(key, 0) + 1
        self._save()

    def game_strategy_incorrect_counts(self, game_key):
        """{"played_incorrectly": N, "folded_incorrectly": M} for one game
        -- either key absent/0 if every decision so far (including all of a
        save file predating this tracking) was correct."""
        return self.data.get(game_key, {}).get("strategy", {})

    def record_round_net(self, game_key, net_result):
        """Tracks the single biggest net win this game has ever paid out in
        one round -- the per-game equivalent of FinanceManager's own
        lifetime `biggest_win` (see its record_round_played), same
        only-ever-moves-up-on-a-bigger-win convention: a losing or
        break-even round is a no-op, not a decrease."""
        game = self._game(game_key)
        if net_result > game.get("biggest_win", 0.0):
            game["biggest_win"] = round(net_result, 2)
            self._save()

    def game_biggest_win(self, game_key):
        """The biggest single-round net win recorded for one game -- 0.0 if
        none recorded yet (including a game that isn't implemented, or one
        played only before this tracking existed)."""
        return self.data.get(game_key, {}).get("biggest_win", 0.0)

    def reset(self):
        self.data = {}
        self._save()

    def reset_game(self, game_key):
        """Wipes just one game's entry (bets/hands/strategy all together) --
        e.g. Settings' per-game "Reset" buttons, which are meant to clear a
        single game's breakdown without touching any other game's data or
        the lifetime finance totals (see FinanceManager.reset_stats_only,
        a separate reset for that). A no-op if the game has no data yet --
        harmless to call for a game that isn't implemented yet, like
        Blackjack, whose key simply isn't present."""
        if self.data.pop(game_key, None) is not None:
            self._save()

    def _save(self):
        save_json(self.save_path, self.data)
