import tkinter as tk

from core.finances import TRANSACTION_BALANCE_THRESHOLD, deposit_limit
from ui import dialogs, theme
from ui.collapsible import make_collapsible
from ui.scrollable import ScrollableFrame

QUICK_AMOUNTS = (10, 25, 50, 100, 200)


class FinancesFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.BG)
        self.app = app
        self._section_resets = []  # gated sections' "back to collapsed" fns -- see on_show

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
        theme.breadcrumb(top_bar, "cashier", bg=theme.BG_ELEVATED,
                          player=app.current_player["name"]).pack(side="right", padx=20, pady=12)

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

        # Text set by refresh() -- the actual per-transaction limit is
        # tiered by the current balance (see core/finances.py's
        # deposit_limit), so this can't be a fixed string the way it used
        # to be when there was just one flat cap.
        self.deposit_limit_lbl = tk.Label(
            deposit_frame, text="", bg=theme.BG_ELEVATED, fg=theme.FG_DIM, font=theme.font(9),
        )
        self.deposit_limit_lbl.pack(pady=(4, 4))

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
            withdraw_frame, text="No maximum per withdrawal",
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

        # --- admin override -- collapsed by default, admin-gated to expand,
        # same pattern as Settings' Jackpot Config / Danger Zone sections --
        # and red-tinted like Danger Zone too, not the usual neutral panel.
        override_inner = make_collapsible(
            body, "$ override --modify", pady=(12, 20),
            bg=theme.LOSE_DIM_BG, border=theme.LOSE_COLOR, fg=theme.LOSE_COLOR,
            before_expand=lambda: dialogs.ensure_admin_unlocked(self.app, self, "override"),
            reset_list=self._section_resets,
        )
        balance_row = tk.Frame(override_inner, bg=theme.LOSE_DIM_BG)
        balance_row.pack(pady=4)
        tk.Label(balance_row, text="£", bg=theme.LOSE_DIM_BG, fg=theme.FG, font=theme.font(13)).pack(side="left")
        self.override_balance_var = tk.StringVar()
        tk.Entry(
            balance_row, textvariable=self.override_balance_var, width=10, font=theme.font(13), justify="center",
            bg=theme.BG, fg=theme.FG, insertbackground=theme.FG, relief="flat",
            highlightthickness=1, highlightbackground=theme.BORDER, highlightcolor=theme.ACCENT,
        ).pack(side="left", padx=6)
        tk.Button(
            balance_row, text="Set", bg=theme.LOSE_DIM_BG_ELEVATED, fg=theme.LOSE_COLOR, relief="flat",
            font=theme.font(11, weight="bold"), padx=16, pady=6, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.LOSE_COLOR,
            command=self._apply_balance_override,
        ).pack(side="left", padx=10)

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
        try:
            self.app.finance.deposit(amount)
        except ValueError as e:
            self.deposit_msg.configure(text=str(e), fg=theme.LOSE_COLOR)
            return

        # deposit() is all-or-nothing now (see its own docstring) -- it
        # either credits exactly `amount` or raises beforehand, so there's
        # no partial-credit figure to work out here any more.
        self.deposit_msg.configure(text=f"Deposited £{amount:.2f} successfully.", fg=theme.WIN_COLOR)
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

    def _apply_balance_override(self):
        try:
            amount = float(self.override_balance_var.get().strip().replace("£", "").replace(",", ""))
            if amount < 0:
                raise ValueError
        except ValueError:
            dialogs.info(
                self, "$ override --modify", "Enter a valid, non-negative £ amount.", accent=theme.WARN,
            )
            return
        self.app.finance.set_balance(amount)
        self.refresh()
        self.app.on_balance_changed()
        dialogs.info(self, "$ override --modify", f"Balance manually set to £{self.app.finance.balance:,.2f}.")

    def on_show(self):
        self.refresh()
        # Same "start fresh every visit" rule as Settings/Stats' gated
        # sections -- collapsed again regardless of how it was left, though
        # app.admin_unlocked (once entered) still carries over.
        for reset in self._section_resets:
            reset()

    def refresh(self):
        balance = self.app.finance.balance
        self.balance_lbl.configure(text=f"£{balance:,.2f}")
        self.override_balance_var.set(f"{balance:.2f}")
        limit = deposit_limit(balance)
        if limit > 0:
            limit_text = f"You may deposit up to £{limit:.0f} per transaction"
        else:
            limit_text = f"Deposits are blocked once your balance reaches £{TRANSACTION_BALANCE_THRESHOLD:.0f}"
        self.deposit_limit_lbl.configure(text=limit_text)
        self.deposit_btn.configure(state="normal" if limit > 0 else "disabled")

        self.withdraw_btn.configure(state="normal" if balance > 0 else "disabled")
