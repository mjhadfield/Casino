import tkinter as tk

from core.finances import MAX_TRANSACTION, TRANSACTION_BALANCE_THRESHOLD
from ui import theme
from ui.scrollable import ScrollableFrame

QUICK_AMOUNTS = (10, 25, 50, 100, 200)


class FinancesFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.BG)
        self.app = app

        top_bar = tk.Frame(self, bg=theme.BG_ELEVATED)
        top_bar.pack(fill="x")
        tk.Button(
            top_bar, text="← Back", bg=theme.BG_ELEVATED, fg=theme.FG_DIM, relief="flat",
            font=theme.font(11), padx=12, pady=6, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.BORDER, highlightcolor=theme.ACCENT,
            command=lambda: app.show_frame("menu"),
        ).pack(side="left", padx=(20, 10), pady=12)
        tk.Label(top_bar, text="Cashier", bg=theme.BG_ELEVATED, fg=theme.ACCENT,
                 font=theme.font(18, weight="bold")).pack(side="left", padx=10)
        theme.breadcrumb(top_bar, "cashier", bg=theme.BG_ELEVATED).pack(side="right", padx=20, pady=12)

        # Scrollable -- two transaction panels plus their quick-amount rows
        # add up to more vertical space than the window's minimum height
        # comfortably fits; see ui/scrollable.py.
        scroll = ScrollableFrame(self, bg=theme.BG)
        scroll.pack(fill="both", expand=True)
        body = tk.Frame(scroll.inner, bg=theme.BG)
        body.pack(fill="both", expand=True, padx=40, pady=20)

        self.balance_lbl = tk.Label(body, text="£0.00", bg=theme.BG, fg=theme.WIN_COLOR, font=theme.font(42, weight="bold"))
        self.balance_lbl.pack(pady=(10, 0))
        tk.Label(body, text="Current Balance", bg=theme.BG, fg=theme.FG_DIM, font=theme.font(11)).pack()

        # --- deposit ---
        deposit_frame = self._make_panel(body, "$ deposit --new")
        deposit_frame.pack(fill="x", pady=(25, 12))

        tk.Label(
            deposit_frame,
            text=f"Maximum £{MAX_TRANSACTION:.0f} per deposit • only while your balance is "
                 f"£{TRANSACTION_BALANCE_THRESHOLD:.0f} or below",
            bg=theme.BG_ELEVATED, fg=theme.FG_DIM, font=theme.font(9),
        ).pack(pady=(4, 4))

        quick_row = tk.Frame(deposit_frame, bg=theme.BG_ELEVATED)
        quick_row.pack(pady=6)
        for amt in QUICK_AMOUNTS:
            tk.Button(
                quick_row, text=f"£{amt}", bg=theme.GREY_BTN_BG, fg=theme.FG, relief="flat",
                font=theme.font(10, weight="bold"), padx=10, pady=6, cursor="hand2",
                highlightthickness=1, highlightbackground=theme.GREY_BTN_BORDER,
                command=lambda a=amt: self._quick_fill(self.deposit_var, self.deposit_msg, a),
            ).pack(side="left", padx=4)

        entry_row = tk.Frame(deposit_frame, bg=theme.BG_ELEVATED)
        entry_row.pack(pady=10)
        tk.Label(entry_row, text="£", bg=theme.BG_ELEVATED, fg=theme.FG, font=theme.font(13)).pack(side="left")
        self.deposit_var = tk.StringVar()
        tk.Entry(
            entry_row, textvariable=self.deposit_var, width=10, font=theme.font(13), justify="center",
            bg=theme.BG, fg=theme.FG, insertbackground=theme.FG, relief="flat",
            highlightthickness=1, highlightbackground=theme.BORDER, highlightcolor=theme.ACCENT,
        ).pack(side="left", padx=6)
        self.deposit_btn = tk.Button(
            entry_row, text="Deposit", bg=theme.ACCENT_DIM_BG_ELEVATED, fg=theme.ACCENT, relief="flat",
            font=theme.font(11, weight="bold"), padx=16, pady=6, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.ACCENT,
            command=self._do_deposit,
        )
        self.deposit_btn.pack(side="left", padx=10)

        self.deposit_msg = tk.Label(deposit_frame, text="", bg=theme.BG_ELEVATED, fg=theme.LOSE_COLOR, font=theme.font(9))
        self.deposit_msg.pack(pady=(0, 10))

        # --- withdraw ---
        withdraw_frame = self._make_panel(body, "$ withdraw --new")
        withdraw_frame.pack(fill="x", pady=12)

        tk.Label(
            withdraw_frame,
            text=f"Maximum £{MAX_TRANSACTION:.0f} per withdrawal • only while your balance is over "
                 f"£{TRANSACTION_BALANCE_THRESHOLD:.0f}",
            bg=theme.BG_ELEVATED, fg=theme.FG_DIM, font=theme.font(9),
        ).pack(pady=(4, 4))

        withdraw_quick_row = tk.Frame(withdraw_frame, bg=theme.BG_ELEVATED)
        withdraw_quick_row.pack(pady=6)
        for amt in QUICK_AMOUNTS:
            tk.Button(
                withdraw_quick_row, text=f"£{amt}", bg=theme.GREY_BTN_BG, fg=theme.FG, relief="flat",
                font=theme.font(10, weight="bold"), padx=10, pady=6, cursor="hand2",
                highlightthickness=1, highlightbackground=theme.GREY_BTN_BORDER,
                command=lambda a=amt: self._quick_fill(self.withdraw_var, self.withdraw_msg, a),
            ).pack(side="left", padx=4)

        withdraw_entry_row = tk.Frame(withdraw_frame, bg=theme.BG_ELEVATED)
        withdraw_entry_row.pack(pady=10)
        tk.Label(withdraw_entry_row, text="£", bg=theme.BG_ELEVATED, fg=theme.FG, font=theme.font(13)).pack(side="left")
        self.withdraw_var = tk.StringVar()
        tk.Entry(
            withdraw_entry_row, textvariable=self.withdraw_var, width=10, font=theme.font(13), justify="center",
            bg=theme.BG, fg=theme.FG, insertbackground=theme.FG, relief="flat",
            highlightthickness=1, highlightbackground=theme.BORDER, highlightcolor=theme.ACCENT,
        ).pack(side="left", padx=6)
        self.withdraw_btn = tk.Button(
            withdraw_entry_row, text="Withdraw", bg=theme.LOSE_DIM_BG_ELEVATED, fg=theme.LOSE_COLOR, relief="flat",
            font=theme.font(11, weight="bold"), padx=16, pady=6, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.LOSE_COLOR,
            command=self._do_withdraw,
        )
        self.withdraw_btn.pack(side="left", padx=10)

        self.withdraw_msg = tk.Label(withdraw_frame, text="", bg=theme.BG_ELEVATED, fg=theme.LOSE_COLOR, font=theme.font(9))
        self.withdraw_msg.pack(pady=(0, 10))

        # Lifetime statistics (deposits/withdrawals included) now live on
        # their own Stats screen -- see ui/stats_screen.py -- this is just a
        # shortcut there rather than duplicating them here.
        tk.Button(
            body, text="View Lifetime Stats →", bg=theme.BG, fg=theme.FG_DIM, relief="flat",
            font=(theme.mono_family(), 10, "underline"), cursor="hand2", bd=0, highlightthickness=0,
            activebackground=theme.BG, activeforeground=theme.ACCENT, command=lambda: app.show_frame("stats"),
        ).pack(pady=(4, 20))

    def _make_panel(self, parent, title):
        """The standard bordered "terminal panel" look: an outer Frame with
        a thin accent-dim border and a shell-prompt-style title along the
        top -- used in place of a tk.LabelFrame, whose relief="groove" can't
        take a clean single-color border."""
        panel = tk.Frame(parent, bg=theme.BG_ELEVATED, highlightbackground=theme.BORDER, highlightthickness=1)
        tk.Label(panel, text=title, bg=theme.BG_ELEVATED, fg=theme.ACCENT,
                 font=theme.font(11, weight="bold")).pack(anchor="w", padx=14, pady=(10, 0))
        return panel

    def _quick_fill(self, var, msg_lbl, amount):
        var.set(str(amount))
        msg_lbl.configure(text="")

    def _do_deposit(self):
        raw = self.deposit_var.get().strip().replace("£", "")
        try:
            amount = float(raw)
        except ValueError:
            self.deposit_msg.configure(text="Enter a valid amount.", fg=theme.LOSE_COLOR)
            return
        balance_before = self.app.finance.balance
        try:
            self.app.finance.deposit(amount)
        except ValueError as e:
            self.deposit_msg.configure(text=str(e), fg=theme.LOSE_COLOR)
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
        self.deposit_msg.configure(text=text, fg=theme.WIN_COLOR)
        self.deposit_var.set("")
        self.refresh()
        self.app.on_balance_changed()

    def _do_withdraw(self):
        raw = self.withdraw_var.get().strip().replace("£", "")
        try:
            amount = float(raw)
        except ValueError:
            self.withdraw_msg.configure(text="Enter a valid amount.", fg=theme.LOSE_COLOR)
            return
        try:
            self.app.finance.withdraw(amount)
        except ValueError as e:
            self.withdraw_msg.configure(text=str(e), fg=theme.LOSE_COLOR)
            return

        self.withdraw_msg.configure(text=f"Withdrew £{amount:.2f} successfully.", fg=theme.WIN_COLOR)
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
