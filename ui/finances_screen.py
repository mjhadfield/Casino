import tkinter as tk

from core.finances import MAX_DEPOSIT

BG = "#0b0b0b"
PANEL_BG = "#131313"


class FinancesFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app

        top_bar = tk.Frame(self, bg="#111111")
        top_bar.pack(fill="x")
        tk.Button(
            top_bar, text="\u2190 Back", bg="#1c1c1c", fg="#cccccc", relief="flat",
            font=("Helvetica", 11), padx=12, pady=6, cursor="hand2",
            command=lambda: app.show_frame("menu"),
        ).pack(side="left", padx=20, pady=12)
        tk.Label(top_bar, text="Finances", bg="#111111", fg="#d4af37",
                 font=("Georgia", 18, "bold")).pack(side="left", padx=10)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=40, pady=20)

        self.balance_lbl = tk.Label(body, text="£0.00", bg=BG, fg="#4be36b", font=("Helvetica", 42, "bold"))
        self.balance_lbl.pack(pady=(10, 0))
        tk.Label(body, text="Current Balance", bg=BG, fg="#888888", font=("Helvetica", 11)).pack()

        # --- deposit ---
        deposit_frame = tk.LabelFrame(
            body, text=" Deposit Funds ", bg=PANEL_BG, fg="#d4af37",
            font=("Helvetica", 11, "bold"), bd=2, relief="groove",
        )
        deposit_frame.pack(fill="x", pady=25)

        tk.Label(
            deposit_frame, text=f"Maximum £{MAX_DEPOSIT:.0f} per deposit \u2022 unlimited number of deposits",
            bg=PANEL_BG, fg="#999999", font=("Helvetica", 9),
        ).pack(pady=(10, 4))

        quick_row = tk.Frame(deposit_frame, bg=PANEL_BG)
        quick_row.pack(pady=6)
        for amt in (10, 25, 50, 100, 200, 300):
            tk.Button(
                quick_row, text=f"£{amt}", bg="#1c1c1c", fg="#f0f0f0", relief="flat",
                font=("Helvetica", 10, "bold"), padx=10, pady=6, cursor="hand2",
                command=lambda a=amt: self._quick_fill(a),
            ).pack(side="left", padx=4)

        entry_row = tk.Frame(deposit_frame, bg=PANEL_BG)
        entry_row.pack(pady=10)
        tk.Label(entry_row, text="£", bg=PANEL_BG, fg="#f0f0f0", font=("Helvetica", 13)).pack(side="left")
        self.deposit_var = tk.StringVar()
        tk.Entry(
            entry_row, textvariable=self.deposit_var, width=10, font=("Helvetica", 13), justify="center",
        ).pack(side="left", padx=6)
        tk.Button(
            entry_row, text="Deposit", bg="#215a2b", fg="#ffffff", relief="flat",
            font=("Helvetica", 11, "bold"), padx=16, pady=6, cursor="hand2",
            command=self._do_deposit,
        ).pack(side="left", padx=10)

        self.deposit_msg = tk.Label(deposit_frame, text="", bg=PANEL_BG, fg="#e05555", font=("Helvetica", 9))
        self.deposit_msg.pack(pady=(0, 10))

        # --- lifetime stats ---
        stats_frame = tk.LabelFrame(
            body, text=" Lifetime Statistics ", bg=PANEL_BG, fg="#d4af37",
            font=("Helvetica", 11, "bold"), bd=2, relief="groove",
        )
        stats_frame.pack(fill="both", expand=True, pady=10)
        stats_grid = tk.Frame(stats_frame, bg=PANEL_BG)
        stats_grid.pack(padx=20, pady=15, fill="x")

        self.stat_labels = {}
        rows = [
            ("lifetime_deposited", "Total Deposited"),
            ("deposits_made", "Deposits Made"),
            ("lifetime_wagered", "Total Wagered"),
            ("lifetime_returned", "Total Returned"),
            ("net", "Lifetime Net Profit / Loss"),
            ("hands_played", "Hands Played"),
            ("biggest_win", "Biggest Single-Round Net Win"),
        ]
        for i, (key, label) in enumerate(rows):
            r, c = divmod(i, 2)
            tk.Label(stats_grid, text=label + ":", bg=PANEL_BG, fg="#aaaaaa",
                     font=("Helvetica", 10), anchor="w").grid(row=r, column=c * 2, sticky="w", padx=(0, 6), pady=4)
            val_lbl = tk.Label(stats_grid, text="-", bg=PANEL_BG, fg="#f0f0f0",
                                font=("Helvetica", 10, "bold"), anchor="w")
            val_lbl.grid(row=r, column=c * 2 + 1, sticky="w", padx=(0, 30), pady=4)
            self.stat_labels[key] = val_lbl

    def _quick_fill(self, amount):
        self.deposit_var.set(str(amount))
        self.deposit_msg.configure(text="")

    def _do_deposit(self):
        raw = self.deposit_var.get().strip().replace("£", "")
        try:
            amount = float(raw)
        except ValueError:
            self.deposit_msg.configure(text="Enter a valid amount.", fg="#e05555")
            return
        try:
            self.app.finance.deposit(amount)
        except ValueError as e:
            self.deposit_msg.configure(text=str(e), fg="#e05555")
            return

        self.deposit_msg.configure(text=f"Deposited £{amount:.2f} successfully.", fg="#4be36b")
        self.deposit_var.set("")
        self.refresh()
        self.app.on_balance_changed()

    def on_show(self):
        self.refresh()

    def refresh(self):
        f = self.app.finance
        self.balance_lbl.configure(text=f"£{f.balance:,.2f}")
        self.stat_labels["lifetime_deposited"].configure(text=f"£{f.data['lifetime_deposited']:,.2f}")
        self.stat_labels["deposits_made"].configure(text=str(f.data["deposits_made"]))
        self.stat_labels["lifetime_wagered"].configure(text=f"£{f.data['lifetime_wagered']:,.2f}")
        self.stat_labels["lifetime_returned"].configure(text=f"£{f.data['lifetime_returned']:,.2f}")
        net = f.lifetime_net()
        self.stat_labels["net"].configure(text=f"£{net:,.2f}", fg="#4be36b" if net >= 0 else "#e05555")
        self.stat_labels["hands_played"].configure(text=str(f.data["hands_played"]))
        self.stat_labels["biggest_win"].configure(text=f"£{f.data['biggest_win']:,.2f}")
