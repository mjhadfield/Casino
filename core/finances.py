"""
Bank balance / finances tracking, shared by every game in the library.

Games never touch the balance directly -- they report wagers and returns
through this manager, which keeps a persisted running total so the
"Cashier" screen and the lifetime stats on the "Stats" screen stay accurate
across sessions. Per-game, per-bet-type breakdowns (for Stats' game-by-game
section) are a separate concern -- see core/game_stats.py.
"""
from datetime import datetime, timezone

from core.persistence import load_json, save_json

MAX_TRANSACTION = 200.0  # per-transaction cap, both directions; unlimited number of transactions

# Anti-cheat rail, both directions gated off the same line: a withdrawal is
# only allowed strictly above it, and a deposit is not just blocked above it
# but actively capped AT it -- deposit() silently reduces the amount
# actually credited so a deposit can never land the balance past this line,
# no matter how large a deposit is requested. Without that cap, only the
# *starting* balance of a deposit was ever checked, not where it would
# land -- so a small withdrawal down to just below the line, followed by a
# full-size deposit back past it, could park the balance at roughly double
# this line indefinitely (withdraw £2, deposit £200, withdraw £200, deposit
# £200, ...) purely by shuffling money, no play required. Capping the
# deposit itself closes that off: the balance can only ever get above this
# line by actually winning at the tables.
TRANSACTION_BALANCE_THRESHOLD = 200.0

DEFAULT_FINANCE_DATA = {
    "balance": 0.0,
    "lifetime_deposited": 0.0,
    "lifetime_withdrawn": 0.0,
    "lifetime_wagered": 0.0,
    "lifetime_returned": 0.0,
    "deposits_made": 0,
    "withdrawals_made": 0,
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
        """Credits up to `amount` -- silently less, if `amount` would carry
        the balance past TRANSACTION_BALANCE_THRESHOLD, see its own comment
        above for why. Check actual_deposit_amount() first (e.g. to tell the
        player up front how much of their requested amount will actually
        land) if that matters to the caller; this doesn't repeat it as a
        return value, to keep deposit()'s own return consistent with every
        other balance-changing method here (the new balance, not the delta)."""
        try:
            amount = round(float(amount), 2)
        except (TypeError, ValueError):
            raise ValueError("Enter a valid amount.")
        if amount <= 0:
            raise ValueError("Deposit amount must be greater than £0.")
        if amount > MAX_TRANSACTION:
            raise ValueError(f"Deposits are capped at £{MAX_TRANSACTION:.0f} per transaction.")
        actual = self.actual_deposit_amount(amount)
        if actual <= 0:
            raise ValueError(
                f"Your balance is already at the £{TRANSACTION_BALANCE_THRESHOLD:.0f} deposit cap."
            )
        self.data["balance"] += actual
        self.data["lifetime_deposited"] += actual
        self.data["deposits_made"] += 1
        self._save()
        return self.balance

    def actual_deposit_amount(self, amount) -> float:
        """How much of a deposit of `amount` would actually be credited --
        less than `amount` if it would otherwise carry the balance past
        TRANSACTION_BALANCE_THRESHOLD, 0 if the balance's already there or
        beyond. Doesn't validate `amount` itself (see deposit()) -- exposed
        separately so the UI can show the player the real figure (e.g.
        "capped at £150") before/without actually making the deposit."""
        room = round(TRANSACTION_BALANCE_THRESHOLD - self.balance, 2)
        return max(0.0, min(amount, room))

    def withdraw(self, amount) -> float:
        try:
            amount = round(float(amount), 2)
        except (TypeError, ValueError):
            raise ValueError("Enter a valid amount.")
        if amount <= 0:
            raise ValueError("Withdrawal amount must be greater than £0.")
        if amount > MAX_TRANSACTION:
            raise ValueError(f"Withdrawals are capped at £{MAX_TRANSACTION:.0f} per transaction.")
        if self.balance <= TRANSACTION_BALANCE_THRESHOLD:
            raise ValueError(f"You can only withdraw while your balance is over £{TRANSACTION_BALANCE_THRESHOLD:.0f}.")
        if not self.can_afford(amount):
            raise ValueError("Your balance is too low to withdraw that much.")
        self.data["balance"] -= amount
        self.data["lifetime_withdrawn"] += amount
        self.data["withdrawals_made"] += 1
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
