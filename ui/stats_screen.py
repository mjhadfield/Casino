import tkinter as tk

from games.three_card_poker import logic as tcp_logic
from ui.scrollable import ScrollableFrame

BG = "#0b0b0b"
PANEL_BG = "#131313"
GOLD = "#d4af37"

# One entry per game the Stats screen knows about -- "bet_types" and
# "hand_labels" are the ordered lists each game's own logic module exposes
# (see e.g. games/three_card_poker/logic.py's BET_TYPES/HAND_OUTCOME_LABELS),
# used to look up that game's recorded stats from GameStatsManager. A game
# that isn't implemented yet just gets empty lists and renders as a "coming
# soon" section instead of a breakdown -- add its real entry here once it
# ships, the same data-driven way ui/main_menu.py's GAMES list works.
GAME_SECTIONS = [
    {"key": tcp_logic.GAME_KEY, "label": tcp_logic.GAME_LABEL, "enabled": True,
     "bet_types": tcp_logic.BET_TYPES, "hand_labels": tcp_logic.HAND_OUTCOME_LABELS},
    {"key": "blackjack", "label": "Blackjack", "enabled": False, "bet_types": [], "hand_labels": []},
]

LIFETIME_STAT_ROWS = [
    ("lifetime_deposited", "Total Deposited", "money"),
    ("deposits_made", "Deposits Made", "count"),
    ("lifetime_withdrawn", "Total Withdrawn", "money"),
    ("withdrawals_made", "Withdrawals Made", "count"),
    ("lifetime_wagered", "Total Wagered", "money"),
    ("lifetime_returned", "Total Returned", "money"),
    ("net", "Lifetime Net Profit / Loss", "signed_money"),
    ("hands_played", "Hands Played", "count"),
    ("biggest_win", "Biggest Single-Round Net Win", "money"),
]


class StatsFrame(tk.Frame):
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
        tk.Label(top_bar, text="Stats", bg="#111111", fg=GOLD,
                 font=("Georgia", 18, "bold")).pack(side="left", padx=10)

        # Scrollable -- lifetime stats plus a growing list of per-game
        # sections easily outgrows the window, especially once more games
        # are added; see ui/scrollable.py.
        scroll = ScrollableFrame(self, bg=BG)
        scroll.pack(fill="both", expand=True)
        self.body = tk.Frame(scroll.inner, bg=BG)
        self.body.pack(fill="both", expand=True, padx=40, pady=20)

        self._build_lifetime_panel()
        self._build_game_sections()

    # ------------------------------------------------------------------ lifetime stats
    def _build_lifetime_panel(self):
        panel = tk.LabelFrame(
            self.body, text=" Lifetime Statistics ", bg=PANEL_BG, fg=GOLD,
            font=("Helvetica", 11, "bold"), bd=2, relief="groove",
        )
        panel.pack(fill="x", pady=(10, 24))
        grid = tk.Frame(panel, bg=PANEL_BG)
        grid.pack(padx=20, pady=15, fill="x")

        self.lifetime_labels = {}
        for i, (key, label, _kind) in enumerate(LIFETIME_STAT_ROWS):
            r, c = divmod(i, 2)
            tk.Label(grid, text=label + ":", bg=PANEL_BG, fg="#aaaaaa",
                     font=("Helvetica", 10), anchor="w").grid(row=r, column=c * 2, sticky="w", padx=(0, 6), pady=4)
            val_lbl = tk.Label(grid, text="-", bg=PANEL_BG, fg="#f0f0f0",
                                font=("Helvetica", 10, "bold"), anchor="w")
            val_lbl.grid(row=r, column=c * 2 + 1, sticky="w", padx=(0, 30), pady=4)
            self.lifetime_labels[key] = val_lbl

    def _refresh_lifetime_panel(self):
        f = self.app.finance
        for key, _label, kind in LIFETIME_STAT_ROWS:
            lbl = self.lifetime_labels[key]
            if key == "net":
                net = f.lifetime_net()
                lbl.configure(text=f"£{net:,.2f}", fg="#4be36b" if net >= 0 else "#e05555")
            elif kind == "count":
                lbl.configure(text=str(f.data[key]))
            else:
                lbl.configure(text=f"£{f.data[key]:,.2f}")

    # ------------------------------------------------------------------ per-game breakdown
    def _build_game_sections(self):
        self.game_panels = []  # (section, panel_body) -- refreshed on every on_show
        for section in GAME_SECTIONS:
            panel = tk.LabelFrame(
                self.body, text=f" {section['label']} ", bg=PANEL_BG, fg=GOLD,
                font=("Helvetica", 11, "bold"), bd=2, relief="groove",
            )
            panel.pack(fill="x", pady=(0, 20))
            panel_body = tk.Frame(panel, bg=PANEL_BG)
            panel_body.pack(fill="x", padx=20, pady=15)
            self.game_panels.append((section, panel_body))

    def _refresh_game_sections(self):
        for section, panel_body in self.game_panels:
            for w in panel_body.winfo_children():
                w.destroy()
            if not section["enabled"]:
                tk.Label(
                    panel_body, text="Coming soon.", bg=PANEL_BG, fg="#666666",
                    font=("Helvetica", 10, "italic"),
                ).pack(anchor="w")
                continue

            bets = self.app.game_stats.game_bets(section["key"])
            hands = self.app.game_stats.game_hand_counts(section["key"])
            if not bets and not hands:
                tk.Label(
                    panel_body, text="No hands played yet.", bg=PANEL_BG, fg="#888888",
                    font=("Helvetica", 10, "italic"),
                ).pack(anchor="w")
                continue

            self._build_hands_summary(panel_body, hands)

            # Everything wagered/returned so far, grouped under one house-edge
            # figure per bet type plus the combined figure across all of them
            # -- previously just an unlabelled table; the heading is what was
            # missing to make clear that's what this whole block is.
            self._section_header(panel_body, "Overall House Edge", pady_top=4)
            edge = self.app.game_stats.game_house_edge(section["key"])
            edge_text = f"{edge:.2f}%" if edge is not None else "-"
            tk.Label(
                panel_body, text=f"Combined across every bet: {edge_text}", bg=PANEL_BG, fg="#f0f0f0",
                font=("Helvetica", 10, "bold"),
            ).pack(anchor="w", pady=(2, 8))
            self._build_bet_table(panel_body, section["bet_types"], bets)

            self._section_header(panel_body, "Hands Made", pady_top=18)
            self._build_hand_table(panel_body, section["hand_labels"], hands)

    def _build_hands_summary(self, parent, hand_counts):
        """Total rounds played -- broken down into Played vs Folded, each as
        a percentage of that total -- right at the top of the game's
        section, above the more detailed breakdowns below it. "Folded" is
        just the "Fold" bucket from hand_counts; every other bucket in it
        (High Card, Pair, ... Royal Flush) is a hand that was actually
        played, so "Played" is simply everything else."""
        total = sum(hand_counts.values())
        folded = hand_counts.get("Fold", 0)
        played = total - folded
        played_pct = (played / total * 100) if total else 0.0
        folded_pct = (folded / total * 100) if total else 0.0
        tk.Label(
            parent, text=f"Total Hands: {total}", bg=PANEL_BG, fg="#f0f0f0",
            font=("Helvetica", 11, "bold"),
        ).pack(anchor="w", pady=(0, 4))
        tk.Label(
            parent, text=f"Played: {played} ({played_pct:.1f}%)    Folded: {folded} ({folded_pct:.1f}%)",
            bg=PANEL_BG, fg="#aaaaaa", font=("Helvetica", 10),
        ).pack(anchor="w", pady=(0, 12))

    def _section_header(self, parent, text, pady_top=0):
        tk.Label(
            parent, text=text.upper(), bg=PANEL_BG, fg="#8fd6a8", font=("Helvetica", 10, "bold"),
        ).pack(anchor="w", pady=(pady_top, 6))

    def _build_table(self, parent, headers, rows):
        """A compact, left-hugging grid: `rows` is a list of (values, colors)
        -- both same length as `headers`. Deliberately not stretched to the
        panel's full width (no column ever gets grid weight, and the table
        itself is packed at its natural size rather than fill="x") -- with
        weight, the value columns are dragged out to the panel's far right
        edge, opening up a wide, eye-tiring gap between a label and its own
        value; unstretched, every column just hugs its own content."""
        table = tk.Frame(parent, bg=PANEL_BG)
        table.pack(anchor="w")
        for c, text in enumerate(headers):
            tk.Label(
                table, text=text, bg=PANEL_BG, fg="#8fd6a8", font=("Helvetica", 9, "bold"),
                anchor="w" if c == 0 else "e",
            ).grid(row=0, column=c, sticky="ew", padx=(0 if c == 0 else 18, 0), pady=(0, 6))
        for r, (values, colors) in enumerate(rows, start=1):
            for c, (text, color) in enumerate(zip(values, colors)):
                tk.Label(
                    table, text=text, bg=PANEL_BG, fg=color, font=("Helvetica", 9),
                    anchor="w" if c == 0 else "e",
                ).grid(row=r, column=c, sticky="ew", padx=(0 if c == 0 else 18, 0), pady=3)

    def _build_bet_table(self, parent, bet_types, bets):
        headers = ["Bet", "Wagered", "Returned", "Net", "Win / Loss / Push", "House Edge"]
        rows = []
        for key, label in bet_types:
            stats = bets.get(key)
            if stats is None:
                # Never actually placed this bet -- still shown, at zero,
                # so the table's rows always match the game's full set of
                # bet types rather than only the ones tried so far.
                wagered = returned = 0.0
                wins = losses = pushes = 0
            else:
                wagered, returned = stats["wagered"], stats["returned"]
                wins, losses, pushes = stats["wins"], stats["losses"], stats["pushes"]
            net = returned - wagered
            bet_edge = self.app.game_stats.house_edge(wagered, returned)
            edge_text = f"{bet_edge:.2f}%" if bet_edge is not None else "-"

            values = [
                label,
                f"£{wagered:,.2f}",
                f"£{returned:,.2f}",
                f"{'+' if net > 0 else ''}£{net:,.2f}" if net else "£0.00",
                f"{wins} / {losses} / {pushes}",
                edge_text,
            ]
            net_color = "#4be36b" if net > 0 else ("#e05555" if net < 0 else "#f0f0f0")
            rows.append((values, ["#f0f0f0", "#f0f0f0", "#f0f0f0", net_color, "#f0f0f0", "#f0f0f0"]))
        self._build_table(parent, headers, rows)

    def _build_hand_table(self, parent, hand_labels, hand_counts):
        total = sum(hand_counts.values())
        headers = ["Hand", "Count", "Percentage"]
        rows = []
        for label in hand_labels:
            count = hand_counts.get(label, 0)
            pct = (count / total * 100) if total else 0.0
            rows.append(([label, str(count), f"{pct:.1f}%"], ["#f0f0f0", "#f0f0f0", "#f0f0f0"]))
        self._build_table(parent, headers, rows)

    # ------------------------------------------------------------------ lifecycle
    def on_show(self):
        self._refresh_lifetime_panel()
        self._refresh_game_sections()
