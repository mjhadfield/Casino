import tkinter as tk

from core.finances import MAX_TRANSACTION, TRANSACTION_BALANCE_THRESHOLD
from ui.scrollable import ScrollableFrame

BG = "#0b0b0b"
PANEL_BG = "#131313"

QUICK_AMOUNTS = (10, 25, 50, 100, 200)


class FinancesFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app

        top_bar = tk.Frame(self, bg="#111111")
        top_bar.pack(fill="x")
        tk.Button(
            top_bar, text="← Back", bg="#1c1c1c", fg="#cccccc", relief="flat",
            font=("Helvetica", 11), padx=12, pady=6, cursor="hand2",
            command=lambda: app.show_frame("menu"),
        ).pack(side="left", padx=20, pady=12)
        tk.Label(top_bar, text="Cashier", bg="#111111", fg="#d4af37",
                 font=("Georgia", 18, "bold")).pack(side="left", padx=10)

        # Scrollable -- two transaction panels plus their quick-amount rows
        # add up to more vertical space than the window's minimum height
        # comfortably fits; see ui/scrollable.py.
        scroll = ScrollableFrame(self, bg=BG)
        scroll.pack(fill="both", expand=True)
        body = tk.Frame(scroll.inner, bg=BG)
        body.pack(fill="both", expand=True, padx=40, pady=20)

        self.balance_lbl = tk.Label(body, text="£0.00", bg=BG, fg="#4be36b", font=("Helvetica", 42, "bold"))
        self.balance_lbl.pack(pady=(10, 0))
        tk.Label(body, text="Current Balance", bg=BG, fg="#888888", font=("Helvetica", 11)).pack()

        # --- deposit ---
        deposit_frame = tk.LabelFrame(
            body, text=" Deposit Funds ", bg=PANEL_BG, fg="#d4af37",
            font=("Helvetica", 11, "bold"), bd=2, relief="groove",
        )
        deposit_frame.pack(fill="x", pady=(25, 12))

        tk.Label(
            deposit_frame,
            text=f"Maximum £{MAX_TRANSACTION:.0f} per deposit • only while your balance is "
                 f"£{TRANSACTION_BALANCE_THRESHOLD:.0f} or below",
            bg=PANEL_BG, fg="#999999", font=("Helvetica", 9),
        ).pack(pady=(10, 4))

        quick_row = tk.Frame(deposit_frame, bg=PANEL_BG)
        quick_row.pack(pady=6)
        for amt in QUICK_AMOUNTS:
            tk.Button(
                quick_row, text=f"£{amt}", bg="#1c1c1c", fg="#f0f0f0", relief="flat",
                font=("Helvetica", 10, "bold"), padx=10, pady=6, cursor="hand2",
                command=lambda a=amt: self._quick_fill(self.deposit_var, self.deposit_msg, a),
            ).pack(side="left", padx=4)

        entry_row = tk.Frame(deposit_frame, bg=PANEL_BG)
        entry_row.pack(pady=10)
        tk.Label(entry_row, text="£", bg=PANEL_BG, fg="#f0f0f0", font=("Helvetica", 13)).pack(side="left")
        self.deposit_var = tk.StringVar()
        tk.Entry(
            entry_row, textvariable=self.deposit_var, width=10, font=("Helvetica", 13), justify="center",
        ).pack(side="left", padx=6)
        self.deposit_btn = tk.Button(
            entry_row, text="Deposit", bg="#215a2b", fg="#ffffff", relief="flat",
            font=("Helvetica", 11, "bold"), padx=16, pady=6, cursor="hand2",
            command=self._do_deposit,
        )
        self.deposit_btn.pack(side="left", padx=10)

        self.deposit_msg = tk.Label(deposit_frame, text="", bg=PANEL_BG, fg="#e05555", font=("Helvetica", 9))
        self.deposit_msg.pack(pady=(0, 10))

        # --- withdraw ---
        withdraw_frame = tk.LabelFrame(
            body, text=" Withdraw Funds ", bg=PANEL_BG, fg="#d4af37",
            font=("Helvetica", 11, "bold"), bd=2, relief="groove",
        )
        withdraw_frame.pack(fill="x", pady=12)

        tk.Label(
            withdraw_frame,
            text=f"Maximum £{MAX_TRANSACTION:.0f} per withdrawal • only while your balance is over "
                 f"£{TRANSACTION_BALANCE_THRESHOLD:.0f}",
            bg=PANEL_BG, fg="#999999", font=("Helvetica", 9),
        ).pack(pady=(10, 4))

        withdraw_quick_row = tk.Frame(withdraw_frame, bg=PANEL_BG)
        withdraw_quick_row.pack(pady=6)
        for amt in QUICK_AMOUNTS:
            tk.Button(
                withdraw_quick_row, text=f"£{amt}", bg="#1c1c1c", fg="#f0f0f0", relief="flat",
                font=("Helvetica", 10, "bold"), padx=10, pady=6, cursor="hand2",
                command=lambda a=amt: self._quick_fill(self.withdraw_var, self.withdraw_msg, a),
            ).pack(side="left", padx=4)

        withdraw_entry_row = tk.Frame(withdraw_frame, bg=PANEL_BG)
        withdraw_entry_row.pack(pady=10)
        tk.Label(withdraw_entry_row, text="£", bg=PANEL_BG, fg="#f0f0f0", font=("Helvetica", 13)).pack(side="left")
        self.withdraw_var = tk.StringVar()
        tk.Entry(
            withdraw_entry_row, textvariable=self.withdraw_var, width=10, font=("Helvetica", 13), justify="center",
        ).pack(side="left", padx=6)
        self.withdraw_btn = tk.Button(
            withdraw_entry_row, text="Withdraw", bg="#5a1c1c", fg="#ffffff", relief="flat",
            font=("Helvetica", 11, "bold"), padx=16, pady=6, cursor="hand2",
            command=self._do_withdraw,
        )
        self.withdraw_btn.pack(side="left", padx=10)

        self.withdraw_msg = tk.Label(withdraw_frame, text="", bg=PANEL_BG, fg="#e05555", font=("Helvetica", 9))
        self.withdraw_msg.pack(pady=(0, 10))

        # Lifetime statistics (deposits/withdrawals included) now live on
        # their own Stats screen -- see ui/stats_screen.py -- this is just a
        # shortcut there rather than duplicating them here.
        tk.Button(
            body, text="View Lifetime Stats →", bg=BG, fg="#8fd6a8", relief="flat",
            font=("Helvetica", 10, "underline"), cursor="hand2", bd=0, activebackground=BG,
            activeforeground="#d4af37", command=lambda: app.show_frame("stats"),
        ).pack(pady=(4, 20))

    def _quick_fill(self, var, msg_lbl, amount):
        var.set(str(amount))
        msg_lbl.configure(text="")

    def _do_deposit(self):
        raw = self.deposit_var.get().strip().replace("£", "")
        try:
            amount = float(raw)
        except ValueError:
            self.deposit_msg.configure(text="Enter a valid amount.", fg="#e05555")
            return
        balance_before = self.app.finance.balance
        try:
            self.app.finance.deposit(amount)
        except ValueError as e:
            self.deposit_msg.configure(text=str(e), fg="#e05555")
            return

        # deposit() itself only returns the new balance, not how much of the
        # request actually got credited (see its own docstring) -- worked
        # out here instead, so a deposit reduced by the £200 balance cap
        # says so rather than claiming the full requested amount landed.
        credited = round(self.app.finance.balance - balance_before, 2)
        if credited < amount - 1e-9:
            text = f"Deposited £{credited:.2f} -- capped at the £{TRANSACTION_BALANCE_THRESHOLD:.0f} balance ceiling."
        else:
            text = f"Deposited £{credited:.2f} successfully."
        self.deposit_msg.configure(text=text, fg="#4be36b")
        self.deposit_var.set("")
        self.refresh()
        self.app.on_balance_changed()

    def _do_withdraw(self):
        raw = self.withdraw_var.get().strip().replace("£", "")
        try:
            amount = float(raw)
        except ValueError:
            self.withdraw_msg.configure(text="Enter a valid amount.", fg="#e05555")
            return
        try:
            self.app.finance.withdraw(amount)
        except ValueError as e:
            self.withdraw_msg.configure(text=str(e), fg="#e05555")
            return

        self.withdraw_msg.configure(text=f"Withdrew £{amount:.2f} successfully.", fg="#4be36b")
        self.withdraw_var.set("")
        self.refresh()
        self.app.on_balance_changed()

    def on_show(self):
        self.refresh()

    def refresh(self):
        balance = self.app.finance.balance
        self.balance_lbl.configure(text=f"£{balance:,.2f}")
        # Greyed out (rather than left clickable and only failing after the
        # fact) whenever the current balance is on the wrong side of
        # TRANSACTION_BALANCE_THRESHOLD for that action -- see deposit()/
        # withdraw()'s own matching checks in core/finances.py, which still
        # apply too, since this is just a UI-level convenience on top.
        self.deposit_btn.configure(state="normal" if balance < TRANSACTION_BALANCE_THRESHOLD else "disabled")
        self.withdraw_btn.configure(state="normal" if balance > TRANSACTION_BALANCE_THRESHOLD else "disabled")
