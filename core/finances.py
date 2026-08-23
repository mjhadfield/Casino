"""
Bank balance / finances tracking, shared by every game in the library.

Games never touch the balance directly -- they report wagers and returns
through this manager, which keeps a persisted running total so the
"Bank Balance" screen and lifetime stats stay accurate across sessions.
"""
from datetime import datetime, timezone

from core.persistence import load_json, save_json

MAX_DEPOSIT = 300.0  # per-transaction cap; number of deposits is unlimited

DEFAULT_FINANCE_DATA = {
    "balance": 0.0,
    "lifetime_deposited": 0.0,
    "lifetime_wagered": 0.0,
    "lifetime_returned": 0.0,
    "deposits_made": 0,
    "hands_played": 0,
    "biggest_win": 0.0,
    "account_created": None,
}


class FinanceManager:
    def __init__(self, save_path):
        self.save_path = save_path
        self.data = load_json(save_path, DEFAULT_FINANCE_DATA)
        if not self.data.get("account_created"):
            self.data["account_created"] = datetime.now(timezone.utc).isoformat()
            self._save()

    @property
    def balance(self) -> float:
        return round(self.data["balance"], 2)

    def deposit(self, amount) -> float:
        try:
            amount = round(float(amount), 2)
        except (TypeError, ValueError):
            raise ValueError("Enter a valid amount.")
        if amount <= 0:
            raise ValueError("Deposit amount must be greater than £0.")
        if amount > MAX_DEPOSIT:
            raise ValueError(f"Deposits are capped at £{MAX_DEPOSIT:.0f} per transaction.")
        self.data["balance"] += amount
        self.data["lifetime_deposited"] += amount
        self.data["deposits_made"] += 1
        self._save()
        return self.balance

    def can_afford(self, amount) -> bool:
        return self.data["balance"] >= amount - 1e-9

    def place_wager(self, amount):
        """Deducts a wager from the balance. Raises if funds are insufficient."""
        if amount <= 0:
            return
        if not self.can_afford(amount):
            raise ValueError("Insufficient balance for this wager.")
        self.data["balance"] -= amount
        self.data["lifetime_wagered"] += amount
        self._save()

    def add_return(self, amount):
        """Any money paid back to the player: wins, bonuses, pushes, stakes returned."""
        if amount <= 0:
            return
        self.data["balance"] += amount
        self.data["lifetime_returned"] += amount
        self._save()

    def record_round_played(self, net_result):
        self.data["hands_played"] += 1
        if net_result > self.data["biggest_win"]:
            self.data["biggest_win"] = round(net_result, 2)
        self._save()

    def lifetime_net(self) -> float:
        return round(self.data["lifetime_returned"] - self.data["lifetime_wagered"], 2)

    def reset_stats_only(self):
        """Resets lifetime statistics but keeps the current balance intact."""
        balance = self.data["balance"]
        created = self.data["account_created"]
        self.data = dict(DEFAULT_FINANCE_DATA)
        self.data["balance"] = balance
        self.data["account_created"] = created
        self._save()

    def _save(self):
        save_json(self.save_path, self.data)
