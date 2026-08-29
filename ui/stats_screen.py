import tkinter as tk

from games.three_card_poker import logic as tcp_logic
from games.blackjack import logic as bj_logic
from games.pai_gow_poker import logic as pgp_logic
from games.pai_gow_poker_face_up import logic as pgpfu_logic
from games.mississippi_stud import logic as ms_logic
from games.ultimate_texas_holdem import logic as uth_logic
from games.let_it_ride import logic as lir_logic
from games.high_card_flush import logic as hcf_logic
from games.baccarat import logic as bacc_logic
from ui import theme
from ui.collapsible import make_collapsible
from ui.scrollable import ScrollableFrame

# One entry per game the Stats screen knows about -- "bet_types" and
# "hand_labels" are the ordered lists each game's own logic module exposes
# (see e.g. games/three_card_poker/logic.py's BET_TYPES/HAND_OUTCOME_LABELS),
# used to look up that game's recorded stats from GameStatsManager. A game
# that isn't implemented yet just gets empty lists and renders as a "coming
# soon" section instead of a breakdown -- add its real entry here once it
# ships, the same data-driven way ui/main_menu.py's GAMES list works.
#
# "tracks_folding": whether this game has a Fold-style decision at all --
# Three card poker is currently the only game where it's being tracked and compared to optimal
# Will do the others when I'm ready to do some sort of "training mode", probably after achievements. 
GAME_SECTIONS = [
    {"key": tcp_logic.GAME_KEY, "label": tcp_logic.GAME_LABEL, "enabled": True, "tracks_folding": True,
     "bet_types": tcp_logic.BET_TYPES, "hand_labels": tcp_logic.HAND_OUTCOME_LABELS},
     # Currently the only game that specifically tracks folding and compares to otpimal play. Easy logic, Q-6-4 or better. 
    {"key": bj_logic.GAME_KEY, "label": bj_logic.GAME_LABEL, "enabled": True, "tracks_folding": False,
     "bet_types": bj_logic.BET_TYPES, "hand_labels": bj_logic.HAND_OUTCOME_LABELS},
    {"key": pgp_logic.GAME_KEY, "label": pgp_logic.GAME_LABEL, "enabled": True, "tracks_folding": False,
     "bet_types": pgp_logic.BET_TYPES, "hand_labels": pgp_logic.HAND_OUTCOME_LABELS},
    {"key": pgpfu_logic.GAME_KEY, "label": pgpfu_logic.GAME_LABEL, "enabled": True, "tracks_folding": False,
     "bet_types": pgpfu_logic.BET_TYPES, "hand_labels": pgpfu_logic.HAND_OUTCOME_LABELS},
    {"key": ms_logic.GAME_KEY, "label": ms_logic.GAME_LABEL, "enabled": True, "tracks_folding": False,
     "bet_types": ms_logic.BET_TYPES, "hand_labels": ms_logic.HAND_OUTCOME_LABELS},
    # tracks_folding=False until I can be bothered to implement Kisenwether's strategy.
    {"key": uth_logic.GAME_KEY, "label": uth_logic.GAME_LABEL, "enabled": True, "tracks_folding": False,
     "bet_types": uth_logic.BET_TYPES, "hand_labels": uth_logic.HAND_OUTCOME_LABELS},
    # tracks_folding=False probably forever, optimal strategy is convoluted.  
    {"key": lir_logic.GAME_KEY, "label": lir_logic.GAME_LABEL, "enabled": True, "tracks_folding": False,
     "bet_types": lir_logic.BET_TYPES, "hand_labels": lir_logic.HAND_OUTCOME_LABELS},
    # tracks_folding=False until optimal strategy can be implemented, pretty high complexity though.
    {"key": hcf_logic.GAME_KEY, "label": hcf_logic.GAME_LABEL, "enabled": True, "tracks_folding": False,
     "bet_types": hcf_logic.BET_TYPES, "hand_labels": hcf_logic.HAND_OUTCOME_LABELS},
    #tracks_folding=False - this is probably the game to start with optimal strategy. 
    {"key": bacc_logic.GAME_KEY, "label": bacc_logic.GAME_LABEL, "enabled": True, "tracks_folding": False,
     "bet_types": bacc_logic.BET_TYPES, "hand_labels": bacc_logic.HAND_OUTCOME_LABELS},
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
        super().__init__(parent, bg=theme.BG)
        self.app = app
        self._section_resets = []  # each section's "back to its default open/closed state" fn

        top_bar = tk.Frame(self, bg=theme.BG_ELEVATED)
        top_bar.pack(fill="x")
        tk.Button(
            top_bar, text="← Back", bg=theme.BG_ELEVATED, fg=theme.FG_DIM, relief="flat",
            font=theme.font(11), padx=12, pady=6, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.BORDER, highlightcolor=theme.ACCENT,
            command=lambda: app.show_frame("menu"),
        ).pack(side="left", padx=(20, 10), pady=12)
        tk.Label(top_bar, text="Stats", bg=theme.BG_ELEVATED, fg=theme.ACCENT,
                 font=theme.font(18, weight="bold")).pack(side="left", padx=10)
        theme.breadcrumb(top_bar, "stats", bg=theme.BG_ELEVATED,
                          player=app.current_player["name"]).pack(side="right", padx=20, pady=12)

        # Scrollable -- lifetime stats plus a growing list of per-game
        # sections easily outgrows the window, especially once more games
        # are added; see ui/scrollable.py.
        scroll = ScrollableFrame(self, bg=theme.BG)
        scroll.pack(fill="both", expand=True)
        self.body = tk.Frame(scroll.inner, bg=theme.BG)
        self.body.pack(fill="both", expand=True, padx=40, pady=20)

        self._build_lifetime_panel()
        self._build_game_sections()

    # ------------------------------------------------------------------ lifetime stats
    def _build_lifetime_panel(self):
        # Expanded by default -- unlike the per-game sections below, this is
        # the one thing worth seeing at a glance every time you open Stats.
        # Still collapsible afterward, and on_show puts it back to expanded
        # on every fresh visit, same as the per-game sections reset to
        # collapsed (see _section_resets).
        inner = make_collapsible(
            self.body, "$ stats --lifetime", pady=(10, 24),
            start_expanded=True, reset_list=self._section_resets,
        )
        grid = tk.Frame(inner, bg=theme.BG_ELEVATED)
        grid.pack(fill="x")

        self.lifetime_labels = {}
        for i, (key, label, _kind) in enumerate(LIFETIME_STAT_ROWS):
            r, c = divmod(i, 2)
            tk.Label(grid, text=label + ":", bg=theme.BG_ELEVATED, fg=theme.FG_DIM,
                     font=theme.font(10), anchor="w").grid(row=r, column=c * 2, sticky="w", padx=(0, 6), pady=4)
            val_lbl = tk.Label(grid, text="-", bg=theme.BG_ELEVATED, fg=theme.FG,
                                font=theme.font(10, weight="bold"), anchor="w")
            val_lbl.grid(row=r, column=c * 2 + 1, sticky="w", padx=(0, 30), pady=4)
            self.lifetime_labels[key] = val_lbl

    def _refresh_lifetime_panel(self):
        f = self.app.finance
        for key, _label, kind in LIFETIME_STAT_ROWS:
            lbl = self.lifetime_labels[key]
            if key == "net":
                net = f.lifetime_net()
                lbl.configure(text=f"£{net:,.2f}", fg=theme.WIN_COLOR if net >= 0 else theme.LOSE_COLOR)
            elif kind == "count":
                lbl.configure(text=str(f.data[key]))
            else:
                lbl.configure(text=f"£{f.data[key]:,.2f}")

    # ------------------------------------------------------------------ per-game breakdown
    def _build_game_sections(self):
        self.game_panels = []  # (section, panel_body) -- refreshed on every on_show
        for section in GAME_SECTIONS:
            # Collapsed by default -- unlike Lifetime Stats above, a game's
            # full breakdown is the kind of thing you click into on demand
            # rather than wanting to see at a glance every visit.
            panel_body = make_collapsible(
                self.body, f"$ stats --game {section['key']}", pady=(0, 20),
                reset_list=self._section_resets,
            )
            self.game_panels.append((section, panel_body))

    def _refresh_game_sections(self):
        for section, panel_body in self.game_panels:
            for w in panel_body.winfo_children():
                w.destroy()
            if not section["enabled"]:
                tk.Label(
                    panel_body, text="Coming soon.", bg=theme.BG_ELEVATED, fg=theme.GREY_BTN_TEXT,
                    font=(theme.mono_family(), 10, "italic"),
                ).pack(anchor="w")
                continue

            bets = self.app.game_stats.game_bets(section["key"])
            hands = self.app.game_stats.game_hand_counts(section["key"])
            if not bets and not hands:
                tk.Label(
                    panel_body, text="No hands played yet.", bg=theme.BG_ELEVATED, fg=theme.FG_DIM,
                    font=(theme.mono_family(), 10, "italic"),
                ).pack(anchor="w")
                continue

            strategy = self.app.game_stats.game_strategy_incorrect_counts(section["key"])
            biggest_win = self.app.game_stats.game_biggest_win(section["key"])
            self._build_hands_summary(panel_body, hands, strategy, section["tracks_folding"], biggest_win)

            # Everything wagered/returned so far, grouped under one house-edge
            # figure per bet type -- previously just an unlabelled table; the
            # heading is what was missing to make clear that's what this
            # whole block is. A running TOTAL row underneath the per-bet
            # ones (see _build_bet_table) replaces the old standalone
            # "Combined across every bet" line that used to sit above it.
            self._section_header(panel_body, "Overall House Edge", pady_top=4)
            self._build_bet_table(panel_body, section["bet_types"], bets)

            self._section_header(panel_body, "Hands Made", pady_top=18)
            self._build_hand_table(panel_body, section["hand_labels"], hands)

    def _build_hands_summary(self, parent, hand_counts, strategy_counts, tracks_folding=True, biggest_win=0.0):
        """Total rounds played and this game's own biggest single-round net
        win -- the per-game equivalent of the Lifetime panel's own
        "Biggest Single-Round Net Win" (see FinanceManager.record_round_
        played), both always shown -- and, only for a game that actually
        has a Fold-style decision (`tracks_folding`), broken down further
        into Played vs Folded plus a "Correctly" strategy line for each. A
        game without a fold concept (e.g. Blackjack) just gets the Total
        Hands/Biggest Win lines and stops there -- rendering "Played 100% /
        Folded 0%" and a "Correctly" line with nothing real behind it would
        be noise, not information, for a game shaped that differently.

        "Folded" is just the "Fold" bucket from hand_counts; every other
        bucket in it (High Card, Pair, ... Royal Flush) is a hand that was
        actually played, so "Played" is simply everything else.

        The "Correctly" line: of those Played/Folded hands, how many were
        the statistically correct call (see logic.py's should_play -- play
        Q-6-4 or better, fold anything worse). strategy_counts only ever
        holds the *incorrect* counts (see GameStatsManager's own docstring
        for why), so "correct" is just the rest of each group."""
        total = sum(hand_counts.values())
        tk.Label(
            parent, text=f"Total Hands: {total}", bg=theme.BG_ELEVATED, fg=theme.FG,
            font=theme.font(11, weight="bold"),
        ).pack(anchor="w", pady=(0, 4))
        tk.Label(
            parent, text=f"Biggest Single-Round Net Win: £{biggest_win:,.2f}",
            bg=theme.BG_ELEVATED, fg=theme.FG, font=theme.font(10),
        ).pack(anchor="w", pady=(0, 4 if tracks_folding else 12))
        if not tracks_folding:
            return

        folded = hand_counts.get("Fold", 0)
        played = total - folded
        played_pct = (played / total * 100) if total else 0.0
        folded_pct = (folded / total * 100) if total else 0.0
        tk.Label(
            parent, text=f"Played: {played} ({played_pct:.1f}%)             Folded: {folded} ({folded_pct:.1f}%)",
            bg=theme.BG_ELEVATED, fg=theme.FG_DIM, font=theme.font(10),
        ).pack(anchor="w", pady=(0, 2))

        played_correct = played - strategy_counts.get("played_incorrectly", 0)
        folded_correct = folded - strategy_counts.get("folded_incorrectly", 0)
        played_correct_pct = (played_correct / played * 100) if played else 0.0
        folded_correct_pct = (folded_correct / folded * 100) if folded else 0.0
        tk.Label(
            parent,
            text=f"Correctly: {played_correct}/{played} [{played_correct_pct:.1f}%]          "
                 f"Correctly: {folded_correct}/{folded} [{folded_correct_pct:.1f}%]",
            bg=theme.BG_ELEVATED, fg=theme.GREY_BTN_TEXT, font=theme.font(9),
        ).pack(anchor="w", pady=(0, 12))

    def _section_header(self, parent, text, pady_top=0):
        tk.Label(
            parent, text=text.upper(), bg=theme.BG_ELEVATED, fg=theme.ACCENT, font=theme.font(10, weight="bold"),
        ).pack(anchor="w", pady=(pady_top, 6))

    def _build_table(self, parent, headers, rows):
        """A compact, left-hugging grid: `rows` is a list of (values, colors)
        -- both same length as `headers`. Deliberately not stretched to the
        panel's full width (no column ever gets grid weight, and the table
        itself is packed at its natural size rather than fill="x") -- with
        weight, the value columns are dragged out to the panel's far right
        edge, opening up a wide, eye-tiring gap between a label and its own
        value; unstretched, every column just hugs its own content."""
        table = tk.Frame(parent, bg=theme.BG_ELEVATED)
        table.pack(anchor="w")
        for c, text in enumerate(headers):
            tk.Label(
                table, text=text, bg=theme.BG_ELEVATED, fg=theme.ACCENT, font=theme.font(9, weight="bold"),
                anchor="w" if c == 0 else "e",
            ).grid(row=0, column=c, sticky="ew", padx=(0 if c == 0 else 18, 0), pady=(0, 6))
        for r, (values, colors) in enumerate(rows, start=1):
            for c, (text, color) in enumerate(zip(values, colors)):
                tk.Label(
                    table, text=text, bg=theme.BG_ELEVATED, fg=color, font=theme.font(9),
                    anchor="w" if c == 0 else "e",
                ).grid(row=r, column=c, sticky="ew", padx=(0 if c == 0 else 18, 0), pady=3)

    def _build_bet_table(self, parent, bet_types, bets):
        headers = ["Bet", "Wagered", "Returned", "Net", "Win / Loss / Push", "House Edge"]
        rows = []
        total_wagered = total_returned = 0.0
        total_wins = total_losses = total_pushes = 0
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
            total_wagered += wagered
            total_returned += returned
            total_wins += wins
            total_losses += losses
            total_pushes += pushes
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
            net_color = theme.WIN_COLOR if net > 0 else (theme.LOSE_COLOR if net < 0 else theme.FG)
            rows.append((values, [theme.FG, theme.FG, theme.FG, net_color, theme.FG, theme.FG]))

        # A running TOTAL row -- Wagered/Returned/Net summed across every
        # bet type above, plus the average house edge realised over all of
        # them combined (the same figure the old standalone "Combined
        # across every bet" line used to show above this table).
        total_net = total_returned - total_wagered
        avg_edge = self.app.game_stats.house_edge(total_wagered, total_returned)
        avg_edge_text = f"{avg_edge:.2f}%" if avg_edge is not None else "-"
        total_values = [
            "TOTAL",
            f"£{total_wagered:,.2f}",
            f"£{total_returned:,.2f}",
            f"{'+' if total_net > 0 else ''}£{total_net:,.2f}" if total_net else "£0.00",
            f"{total_wins} / {total_losses} / {total_pushes}",
            avg_edge_text,
        ]
        total_net_color = theme.WIN_COLOR if total_net > 0 else (theme.LOSE_COLOR if total_net < 0 else theme.FG)
        rows.append((total_values,
                     [theme.ACCENT, theme.ACCENT, theme.ACCENT, total_net_color, theme.ACCENT, theme.ACCENT]))
        self._build_table(parent, headers, rows)

    def _build_hand_table(self, parent, hand_labels, hand_counts):
        total = sum(hand_counts.values())
        headers = ["Hand", "Count", "Percentage"]
        rows = []
        for label in hand_labels:
            count = hand_counts.get(label, 0)
            pct = (count / total * 100) if total else 0.0
            rows.append(([label, str(count), f"{pct:.1f}%"], [theme.FG, theme.FG, theme.FG]))
        self._build_table(parent, headers, rows)

    # ------------------------------------------------------------------ lifecycle
    def on_show(self):
        self._refresh_lifetime_panel()
        self._refresh_game_sections()
        # Every fresh visit starts from the same state: Lifetime Stats open,
        # each game's breakdown collapsed -- regardless of how they were
        # left last time.
        for reset in self._section_resets:
            reset()
