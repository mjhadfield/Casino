"""
Progressive jackpot, shared infrastructure for any game that wants one.

Three Card Poker's spades Royal Flush is the only thing that currently pays
it out (see games/three_card_poker/logic.py), but the manager itself knows
nothing about that -- it just owns a persisted amount that grows on its own
clock, the same way FinanceManager owns the balance and SettingsManager owns
preferences.

Growth is driven by `start()`, which reschedules itself on the Tk root for
as long as the app is running -- the jackpot does *not* catch up for time
spent with the app closed, only for elapsed time actually spent ticking.
The amount is still persisted to disk, so the *level* it reached carries
over between runs -- only the "clock" resets.
"""
import time

from core.persistence import load_json, save_json

JACKPOT_FLOOR = 5000.00
JACKPOT_CEILING = 50000.00
DEFAULT_RATE_PER_SECOND = 0.01

# How often the persisted file is rewritten while ticking -- independent of
# the tick interval, so a fast/animated tick rate doesn't thrash the disk.
SAVE_INTERVAL_SECONDS = 1.0

DEFAULT_JACKPOT_DATA = {"amount": JACKPOT_FLOOR}


class JackpotManager:
    """Owns the jackpot's persisted amount and its continuous, real-time
    growth. `settings` supplies the growth rate (£/second) via the
    "jackpot_rate_per_second" preference, so Settings can tune -- or, for
    debugging, directly override -- the amount without this class knowing
    anything about how that UI works."""

    def __init__(self, save_path, settings):
        self.save_path = save_path
        self.settings = settings
        self.data = load_json(save_path, DEFAULT_JACKPOT_DATA)
        self.data["amount"] = self._clamp(float(self.data.get("amount", JACKPOT_FLOOR)))
        self._listeners = []
        self._last_tick = time.monotonic()  # re-set by start(); never actually read before then
        self._save_accum = 0.0

    @staticmethod
    def _clamp(amount):
        return min(max(amount, JACKPOT_FLOOR), JACKPOT_CEILING)

    @property
    def amount(self) -> float:
        """Current jackpot, rounded to the penny -- what's actually paid out
        and recorded to disk."""
        return round(self.data["amount"], 2)

    @property
    def raw_amount(self) -> float:
        """Full sub-penny precision, for a display that rolls continuously
        rather than jumping once a second as the rounded penny ticks over."""
        return self.data["amount"]

    def add_listener(self, callback):
        """`callback(raw_amount)` fires after every tick and after any manual
        change (set_amount / win) -- lets a display stay live without polling."""
        self._listeners.append(callback)

    # ------------------------------------------------------------------ growth
    def start(self, tk_root, interval_ms=100):
        """Begins the continuous-growth loop, self-rescheduling on `tk_root`
        for as long as the app runs. Call once, e.g. from CasinoApp.__init__."""
        self._last_tick = time.monotonic()
        self._tick_loop(tk_root, interval_ms)

    def _tick_loop(self, tk_root, interval_ms):
        now = time.monotonic()
        elapsed = now - self._last_tick
        self._last_tick = now
        self._grow(elapsed)
        tk_root.after(interval_ms, self._tick_loop, tk_root, interval_ms)

    def _grow(self, elapsed_seconds):
        if elapsed_seconds <= 0:
            return
        rate = self.settings.get("jackpot_rate_per_second")
        if rate is None:
            rate = DEFAULT_RATE_PER_SECOND
        if rate > 0 and self.data["amount"] < JACKPOT_CEILING:
            self.data["amount"] = self._clamp(self.data["amount"] + rate * elapsed_seconds)
            self._notify()

        # Persist roughly once a second rather than on every tick -- the
        # in-memory amount (and every listener) still updates every tick.
        self._save_accum += elapsed_seconds
        if self._save_accum >= SAVE_INTERVAL_SECONDS:
            self._save_accum = 0.0
            self._save()

    # ------------------------------------------------------------------ manual control
    def set_amount(self, amount):
        """Manual override, clamped to [floor, ceiling] -- used by the
        Settings debug control."""
        self.data["amount"] = self._clamp(float(amount))
        self._save()
        self._notify()

    def win(self):
        """Resets the jackpot to its floor after it's been paid out."""
        self.data["amount"] = JACKPOT_FLOOR
        self._save()
        self._notify()

    # ------------------------------------------------------------------ internals
    def _notify(self):
        for callback in self._listeners:
            callback(self.data["amount"])

    def _save(self):
        save_json(self.save_path, {"amount": self.data["amount"]})
