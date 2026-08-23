import os
import tkinter as tk
from tkinter import messagebox
from typing import Optional

from core.hand_evaluator import HAND_NAMES
from core.persistence import load_json, save_json
from games.three_card_poker.logic import (
    ANTE_BONUS_MULTIPLIERS,
    PAIR_PLUS_MULTIPLIERS,
    PRIME_SAME_COLOUR_3_MULTIPLIER,
    PRIME_SAME_COLOUR_6_MULTIPLIER,
    RoundResult,
    ThreeCardPokerGame,
)
from ui.card_widgets import draw_card, draw_card_back, CARD_HEIGHT, CARD_WIDTH

STATE_FILENAME = "three_card_poker_state.json"
DEFAULT_STATE = {"bets": {"ante": 0, "pair_plus": 0, "prime": 0}, "selected_chip": 5}

# Classic casino chip palette: (denomination, face colour, rim colour).
CHIP_DENOMINATIONS = [
    (1, "#1f6fd6", "#0d3c85"),     # blue
    (5, "#d1362f", "#8f211d"),     # red
    (25, "#1f8a4c", "#125c32"),    # green
    (100, "#1c1c1c", "#000000"),   # black
    (500, "#d6389f", "#8f1f68"),   # pink
]
# --- Layout constants ------------------------------------------------------
# The whole game area (table canvas + paytable) is built at these fixed pixel
# sizes and centred as one block in the window, rather than stretching to
# fill it -- see `_build_ui`. That also means a future "UI scale" setting can
# be added later just by multiplying this block of constants by a factor
# before building/drawing, without restructuring the layout itself.
CHIP_COLORS_BY_VALUE = {value: (face, rim) for value, face, rim in CHIP_DENOMINATIONS}
CHIP_SIZE = 58
CANVAS_WIDTH = 760
CANVAS_HEIGHT = 360

# A single chip's on-table size -- identical everywhere it's placed (Ante,
# Pair Plus, Prime) so a £25 chip looks the same size on every spot. Sized to
# nearly fill the Pair Plus/Prime circles (radius 40), leaving a thin ring of
# felt showing.
CHIP_LAYER_MAX_R = 36

PAYTABLE_WIDTH = 240
PAYTABLE_HEIGHT = 340
PAYOUT_PANEL_WIDTH = 380
PAYOUT_PANEL_HEIGHT = 190

# Fixed gap between the top bar and the table -- half of what plain vertical
# centring in the window used to leave there.
CONTENT_TOP_MARGIN = 35

# --- Card-view (post-Deal) geometry ----------------------------------------
# A row of 3 cards, centred on the canvas -- shared by the dealer's row, the
# player's settled/sorted row, and used as the x-baseline for the player's fan.
CARD_ROW_GAP = CARD_WIDTH + 15
CARD_ROW_WIDTH = 2 * CARD_ROW_GAP + CARD_WIDTH
CARD_ROW_START_X = CANVAS_WIDTH / 2 - CARD_ROW_WIDTH / 2

DEALER_Y = 54                                    # dealer cards' top-left y
DEALER_ZONE_TOP = DEALER_Y - 34
DEALER_ZONE_BOTTOM = DEALER_Y + CARD_HEIGHT + 16
DEALER_ZONE_X1 = CARD_ROW_START_X - 26
DEALER_ZONE_X2 = CARD_ROW_START_X + CARD_ROW_WIDTH + 26

# Player zone: same width/height as the dealer's (matched pair), but a
# rounded rectangle instead of an oval so it reads as "similar, but different".
PLAYER_ZONE_TOP = DEALER_ZONE_BOTTOM + 20
PLAYER_ZONE_BOTTOM = PLAYER_ZONE_TOP + (DEALER_ZONE_BOTTOM - DEALER_ZONE_TOP)
PLAYER_ZONE_X1 = DEALER_ZONE_X1
PLAYER_ZONE_X2 = DEALER_ZONE_X2
PLAYER_ZONE_CY = (PLAYER_ZONE_TOP + PLAYER_ZONE_BOTTOM) / 2
PLAYER_Y_SETTLED = PLAYER_ZONE_CY - CARD_HEIGHT / 2   # the flat, sorted resting row

# The fan the player's cards land in while Play/Fold is being decided:
# overlapping, with the outer two cards riding slightly lower than the middle
# one, like a hand of cards held with a gentle arc.
FAN_GAP = 42
FAN_ARC_OFFSET = 14
FAN_Y = PLAYER_ZONE_CY - CARD_HEIGHT / 2


def _ease_out_cubic(t):
    return 1 - (1 - t) ** 3


# Paytable rows, read straight from the game rules in logic.py/hand_evaluator.py
# so the panel can never drift out of sync with what actually gets paid out.
_ANTE_BONUS_ROWS = sorted(
    ((HAND_NAMES[rank], mult) for rank, mult in ANTE_BONUS_MULTIPLIERS.items()),
    key=lambda row: -row[1],
)
_PAIR_PLUS_ROWS = sorted(PAIR_PLUS_MULTIPLIERS.items(), key=lambda row: -row[1])
_PRIME_ROWS = [
    ("6 Cards Same Colour", PRIME_SAME_COLOUR_6_MULTIPLIER),
    ("3 Cards Same Colour", PRIME_SAME_COLOUR_3_MULTIPLIER),
]
PAYTABLE_SECTIONS = [
    ("ANTE BONUS", _ANTE_BONUS_ROWS),
    ("PAIR PLUS", _PAIR_PLUS_ROWS),
    ("PRIME", _PRIME_ROWS),
]


def _chip_breakdown(amount):
    """Greedy denomination breakdown of `amount` -- e.g. £30 -> [(25, 1), (5, 1)].
    Since £1 chips exist this always accounts for the full amount exactly, and
    it's recomputed from the total every draw, so five £1 chips on a spot
    render as a single £5 chip rather than five separate ones."""
    breakdown = []
    remaining = amount
    for value, _, _ in sorted(CHIP_DENOMINATIONS, reverse=True):
        if remaining <= 0:
            break
        count, remaining = divmod(remaining, value)
        if count:
            breakdown.append((value, count))
    return breakdown


def _max_round_cost(bets):
    """Worst-case total the player could end up committing this round: the
    upfront wager plus a Play bet equal to the Ante if they choose to play
    (the Play bet always matches the Ante -- see ThreeCardPokerGame.resolve).
    A real casino would never let you place an Ante you couldn't back up with
    a matching Play bet, so bet placement is checked against this, not just
    the upfront total."""
    return bets["ante"] * 2 + bets["pair_plus"] + bets["prime"]


def _format_signed(amount):
    """£6 as +£6, -£6, or £0 -- amounts here are always whole pounds since
    every bet and payout multiplier in this game is a whole number."""
    if amount > 0:
        return f"+£{amount:.0f}"
    if amount < 0:
        return f"-£{abs(amount):.0f}"
    return "£0"


def _net_color(amount):
    if amount > 0:
        return "#4be36b"
    if amount < 0:
        return "#e05555"
    return "#f0f0f0"


class ThreeCardPokerFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg="#0b3d24")
        self.app = app
        self.game = ThreeCardPokerGame()
        self.result: Optional[RoundResult] = None
        self.state = "betting"  # betting -> dealt -> resolved

        self.save_path = os.path.join(app.data_dir, STATE_FILENAME)
        saved = load_json(self.save_path, DEFAULT_STATE)
        saved_bets = saved.get("bets", DEFAULT_STATE["bets"])
        self.bets = {
            "ante": int(saved_bets.get("ante", 0)),
            "pair_plus": int(saved_bets.get("pair_plus", 0)),
            "prime": int(saved_bets.get("prime", 0)),
        }
        self.selected_chip = int(saved.get("selected_chip", DEFAULT_STATE["selected_chip"]))
        self._sanitize_bets(persist=False)

        self.chip_canvases = {}  # value -> (canvas, face colour, rim colour)

        self._build_ui()

    # ------------------------------------------------------------------ UI build
    def _build_ui(self):
        theme = self.app.settings.theme()
        self._current_felt = theme["felt"]
        self.configure(bg=theme["felt"])

        top_bar = tk.Frame(self, bg="#111111")
        top_bar.pack(fill="x")
        tk.Button(
            top_bar, text="← Menu", bg="#1c1c1c", fg="#cccccc", relief="flat",
            font=("Helvetica", 11), padx=12, pady=6, cursor="hand2",
            command=lambda: self.app.show_frame("menu"),
        ).pack(side="left", padx=20, pady=10)
        tk.Label(top_bar, text="Three Card Poker", bg="#111111", fg="#d4af37",
                 font=("Georgia", 16, "bold")).pack(side="left", padx=10)
        self.balance_lbl = tk.Label(top_bar, text="£0.00", bg="#111111", fg="#4be36b",
                                     font=("Helvetica", 12, "bold"))
        self.balance_lbl.pack(side="right", padx=20)

        # `body` is the full-window stage; `content` is the actual UI at its
        # fixed base size, centred horizontally within it as one block rather
        # than stretching -- so resizing the window never changes the table's
        # own proportions or shifts the table and paytable apart. Anchored to
        # a fixed offset from the top (not vertically centred) so any extra
        # window height becomes slack at the bottom instead of pushing the
        # whole table down and leaving a big gap under the top bar.
        body = tk.Frame(self, bg=theme["felt"])
        body.pack(fill="both", expand=True)

        content = tk.Frame(body, bg=theme["felt"])
        content.place(relx=0.5, y=CONTENT_TOP_MARGIN, anchor="n")

        game_col = tk.Frame(content, bg=theme["felt"])
        game_col.pack(side="left")

        paytable_col = tk.Frame(content, bg=theme["felt"])
        paytable_col.pack(side="right", fill="y", padx=(10, 24), pady=10)
        self._build_paytable(paytable_col)

        self.canvas = tk.Canvas(game_col, bg=theme["felt"], highlightthickness=0,
                                 width=CANVAS_WIDTH, height=CANVAS_HEIGHT)
        self.canvas.pack(padx=12, pady=(10, 4))

        self.result_lbl = tk.Label(
            game_col, text="Place your Ante bet to begin.", bg=theme["felt"], fg="#f0f0f0",
            font=("Helvetica", 13, "bold"), wraplength=900, justify="center",
        )
        self.result_lbl.pack(pady=(0, 6))

        # --- action buttons (contents swapped by state) -- sits right under the
        # instructions text, with only a small, constant gap: Deal, Play+Fold and
        # New Round are all single-row layouts of the same height, so this needs
        # no space reservation of its own to stay put between states.
        self.action_frame = tk.Frame(game_col, bg=theme["felt"])
        self.action_frame.pack(pady=(8, 0))

        self.deal_btn = tk.Button(
            self.action_frame, text="DEAL", bg="#d4af37", fg="#111111",
            font=("Helvetica", 13, "bold"), relief="flat", padx=30, pady=10, cursor="hand2",
            command=self._on_deal,
        )
        self.play_btn = tk.Button(
            self.action_frame, text="PLAY", bg="#215a2b", fg="#ffffff",
            font=("Helvetica", 13, "bold"), relief="flat", padx=30, pady=10, cursor="hand2",
            command=lambda: self._finish_round(folded=False),
        )
        self.fold_btn = tk.Button(
            self.action_frame, text="FOLD", bg="#5a1c1c", fg="#ffffff",
            font=("Helvetica", 13, "bold"), relief="flat", padx=30, pady=10, cursor="hand2",
            command=lambda: self._finish_round(folded=True),
        )
        self.new_round_btn = tk.Button(
            self.action_frame, text="New Round", bg="#d4af37", fg="#111111",
            font=("Helvetica", 13, "bold"), relief="flat", padx=30, pady=10, cursor="hand2",
            command=self._new_round,
        )

        # --- below the action row: chip tray (betting) or the round result
        # (resolved) -- never both, so they share one reserved zone. `chip_zone`
        # stays packed (and its footprint reserved) in every state even though
        # its contents are state-specific -- so switching between them never
        # changes `content`'s overall size. `content` is centred as a block, so
        # an actual size change there would re-centre (and shift) everything,
        # undoing the Deal <-> Play/Fold alignment -- but because the reserved
        # space sits below the buttons rather than between them and the
        # instructions, there's no visible gap where it matters.
        self.chip_zone = tk.Frame(game_col, bg=theme["felt"])
        self.chip_zone.pack(pady=(10, 0))

        # Chip tray: pick a denomination, then tap a betting spot on the table.
        # Total bet and Clear Bets are grouped into it too.
        self.chip_frame = tk.Frame(self.chip_zone, bg=theme["felt"])
        tk.Label(
            self.chip_frame, text="Tap a chip, then tap Ante / Pair Plus / Prime to place it",
            bg=theme["felt"], fg="#999999", font=("Helvetica", 9),
        ).pack(pady=(0, 6))
        self.chip_row = tk.Frame(self.chip_frame, bg=theme["felt"])
        self.chip_row.pack()
        for value, face, rim in CHIP_DENOMINATIONS:
            self._make_chip_button(self.chip_row, value, face, rim)

        self.total_lbl = tk.Label(
            self.chip_frame, text="Total bet: £0", bg=theme["felt"], fg="#d4af37",
            font=("Helvetica", 12, "bold"),
        )
        self.total_lbl.pack(pady=(8, 0))

        self.clear_btn = tk.Button(
            self.chip_frame, text="Clear Bets", bg="#333333", fg="#cccccc",
            font=("Helvetica", 9), relief="flat", padx=10, pady=4, cursor="hand2",
            command=self._clear_bets,
        )
        self.clear_btn.pack(pady=(6, 0))

        # Round result: shown once a round resolves, in place of the chip tray.
        self.payout_canvas = tk.Canvas(
            self.chip_zone, width=PAYOUT_PANEL_WIDTH, height=PAYOUT_PANEL_HEIGHT,
            bg=theme["felt"], highlightthickness=0,
        )

        self.chip_frame.pack()
        self.chip_frame.update_idletasks()
        self.chip_zone.configure(
            width=max(self.chip_frame.winfo_reqwidth(), PAYOUT_PANEL_WIDTH),
            height=max(self.chip_frame.winfo_reqheight(), PAYOUT_PANEL_HEIGHT),
        )
        self.chip_zone.pack_propagate(False)

        self._show_betting_controls()

    # ------------------------------------------------------------------ chip tray
    def _make_chip_button(self, parent, value, face, rim):
        theme = self.app.settings.theme()
        canvas = tk.Canvas(parent, width=CHIP_SIZE + 10, height=CHIP_SIZE + 10,
                            bg=theme["felt"], highlightthickness=0, cursor="hand2")
        canvas.pack(side="left", padx=6)
        canvas.bind("<Button-1>", lambda e, v=value: self._select_chip(v))
        self.chip_canvases[value] = (canvas, face, rim)
        self._draw_chip(value)

    def _draw_chip(self, value):
        canvas, face, rim = self.chip_canvases[value]
        canvas.delete("all")
        pad = 5
        r = CHIP_SIZE / 2
        cx = cy = r + pad
        if value == self.selected_chip:
            canvas.create_oval(cx - r - 4, cy - r - 4, cx + r + 4, cy + r + 4,
                                outline="#d4af37", width=3)
        canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=face, outline=rim, width=3)
        canvas.create_oval(cx - r + 7, cy - r + 7, cx + r - 7, cy + r - 7,
                            outline="#ffffff", width=1)
        canvas.create_text(cx, cy, text=f"£{value}", fill="#ffffff", font=("Helvetica", 10, "bold"))

    def _select_chip(self, value):
        self.selected_chip = value
        for v in self.chip_canvases:
            self._draw_chip(v)
        self._persist_state()

    # ------------------------------------------------------------------ paytable panel
    def _build_paytable(self, parent):
        theme = self.app.settings.theme()
        canvas = tk.Canvas(parent, width=PAYTABLE_WIDTH, height=PAYTABLE_HEIGHT,
                            bg=theme["felt"], highlightthickness=0)
        canvas.pack(expand=True)
        self.paytable_canvas = canvas
        self._draw_paytable()

    def _draw_paytable(self):
        canvas = self.paytable_canvas
        canvas.delete("all")
        w, h = PAYTABLE_WIDTH, PAYTABLE_HEIGHT

        canvas.create_rectangle(3, 3, w - 3, h - 3, fill="#0e2a1a", outline="#d4af37", width=2)
        canvas.create_rectangle(8, 8, w - 8, h - 8, outline="#3a6b4c", width=1)
        canvas.create_text(w / 2, 24, text="PAYTABLE", fill="#d4af37", font=("Georgia", 14, "bold"))

        y = 46
        for i, (title, rows) in enumerate(PAYTABLE_SECTIONS):
            if i:
                canvas.create_line(20, y, w - 20, y, fill="#3a6b4c")
                y += 12
            y = self._draw_paytable_section(canvas, y, title, rows)

    def _draw_paytable_section(self, canvas, y, title, rows):
        w = PAYTABLE_WIDTH
        canvas.create_text(20, y, text=title, fill="#8fd6a8",
                            font=("Helvetica", 10, "bold"), anchor="w")
        y += 20
        for label, multiplier in rows:
            canvas.create_text(20, y, text=label, fill="#f0f0f0", font=("Helvetica", 9), anchor="w")
            canvas.create_text(w - 20, y, text=f"{multiplier}:1", fill="#4be36b",
                                font=("Helvetica", 9, "bold"), anchor="e")
            y += 19
        return y

    # ------------------------------------------------------------------ betting table
    def _draw_table(self):
        self.canvas.delete("all")
        w, h = CANVAS_WIDTH, CANVAS_HEIGHT
        cx = w / 2

        # Ante spot is proportioned like a playing card (CARD_WIDTH:CARD_HEIGHT, scaled up).
        ante_w = CARD_WIDTH * 1.6
        ante_h = CARD_HEIGHT * 1.6

        # Pair Plus / Prime sit close together above the Ante, mirroring a real
        # layout. The whole group sits a little below vertical centre, so the
        # Ante box (and the chips on it) stay close to the instructions text
        # right below the canvas rather than leaving a dead gap there.
        side_r = 40
        side_offset = 85
        gap = 14
        content_h = 2 * side_r + gap + ante_h
        top = (h - content_h) * 0.68
        side_cy = top + side_r
        ante_cx, ante_cy = cx, top + 2 * side_r + gap + ante_h / 2
        pp_cx = cx - side_offset
        pr_cx = cx + side_offset

        self._draw_spot_circle("pair_plus", pp_cx, side_cy, side_r, "PAIR PLUS")
        self._draw_spot_circle("prime", pr_cx, side_cy, side_r, "PRIME")
        self._draw_spot_rect("ante", ante_cx, ante_cy, ante_w, ante_h, "ANTE")

    def _draw_spot_circle(self, key, cx, cy, r, label):
        tag = f"spot_{key}"
        amount = self.bets[key]
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                 fill="#0e4a2c", outline="#d4af37", width=2, tags=(tag,))
        self.canvas.create_text(cx, cy - r - 12, text=label, fill="#cfead9",
                                 font=("Helvetica", 9, "bold"), tags=(tag,))
        if amount:
            self._draw_chip_stack(tag, cx, cy, amount, max_r=CHIP_LAYER_MAX_R, budget=r * 1.9)
        else:
            self.canvas.create_text(cx, cy, text="tap to bet", fill="#6f9c82",
                                     font=("Helvetica", 9, "bold"), tags=(tag,))
        self._bind_spot(tag, key)

    def _draw_spot_rect(self, key, cx, cy, width, height, label):
        tag = f"spot_{key}"
        amount = self.bets[key]
        x1, y1, x2, y2 = cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2
        self.canvas.create_rectangle(x1, y1, x2, y2, fill="#0e4a2c", outline="#d4af37",
                                      width=2, tags=(tag,))
        self.canvas.create_text(cx, y1 + 18, text=label, fill="#cfead9",
                                 font=("Helvetica", 11, "bold"), tags=(tag,))
        stack_cy = cy + 16
        if amount:
            self._draw_chip_stack(tag, cx, stack_cy, amount, max_r=CHIP_LAYER_MAX_R, budget=110)
        else:
            self.canvas.create_text(cx, stack_cy, text="tap to bet", fill="#6f9c82",
                                     font=("Helvetica", 10, "bold"), tags=(tag,))
        self._bind_spot(tag, key)

    def _draw_chip_stack(self, tag, cx, cy, amount, max_r, budget):
        """Draws `amount` as a stack of chip icons (largest denomination at the
        base), each carrying a ×N badge if more than one of that chip is on the
        spot. Recomputed from the total each time, so e.g. five £1 chips are
        shown as a single £5 chip once the total reaches £5.

        `budget` is the vertical space available for the stack; the chip
        radius shrinks below `max_r` if needed so a stack of several different
        denominations never overflows a small spot."""
        breakdown = _chip_breakdown(amount)  # largest denomination first
        n = len(breakdown)
        layer_r = min(max_r, budget / (2 + 0.85 * (n - 1)))
        dy = layer_r * 0.85
        base_cy = cy + dy * (len(breakdown) - 1) / 2
        for i, (value, count) in enumerate(breakdown):
            layer_cy = base_cy - i * dy
            face, rim = CHIP_COLORS_BY_VALUE[value]
            self.canvas.create_oval(cx - layer_r, layer_cy - layer_r, cx + layer_r, layer_cy + layer_r,
                                     fill=face, outline=rim, width=2, tags=(tag,))
            self.canvas.create_oval(cx - layer_r + 4, layer_cy - layer_r + 4, cx + layer_r - 4, layer_cy + layer_r - 4,
                                     outline="#ffffff", width=1, tags=(tag,))
            self.canvas.create_text(cx, layer_cy, text=f"£{value}", fill="#ffffff",
                                     font=("Helvetica", max(7, int(layer_r * 0.38)), "bold"), tags=(tag,))
            if count > 1:
                badge_r = max(7, layer_r * 0.42)
                bx, by = cx + layer_r * 0.62, layer_cy + layer_r * 0.62
                self.canvas.create_oval(bx - badge_r, by - badge_r, bx + badge_r, by + badge_r,
                                         fill="#111111", outline="#d4af37", width=1, tags=(tag,))
                self.canvas.create_text(bx, by, text=f"×{count}", fill="#ffffff",
                                         font=("Helvetica", max(7, int(badge_r * 0.85)), "bold"), tags=(tag,))

    def _bind_spot(self, tag, key):
        self.canvas.tag_bind(tag, "<Button-1>", lambda e, k=key: self._on_place_chip(k))
        self.canvas.tag_bind(tag, "<Enter>", lambda e: self.canvas.configure(cursor="hand2"))
        self.canvas.tag_bind(tag, "<Leave>", lambda e: self.canvas.configure(cursor=""))

    # ------------------------------------------------------------------ state transitions
    def _show_betting_controls(self):
        for w in self.action_frame.pack_slaves():
            w.pack_forget()
        self.deal_btn.pack()
        self.payout_canvas.pack_forget()
        self.chip_frame.pack(expand=True)
        self._draw_table()
        self._update_total()

    def _show_decision_controls(self):
        self.chip_frame.pack_forget()
        self.payout_canvas.pack_forget()
        for w in self.action_frame.pack_slaves():
            w.pack_forget()
        self.play_btn.pack(side="left", padx=8)
        self.fold_btn.pack(side="left", padx=8)

    def _show_new_round_control(self):
        self.chip_frame.pack_forget()
        for w in self.action_frame.pack_slaves():
            w.pack_forget()
        self.new_round_btn.pack(side="left", padx=8)

    def _show_no_controls(self):
        """No action buttons visible -- used during the brief pause/animation
        between Deal and the cards actually landing, and between Play/Fold
        and the dealer's reveal, so nothing can be clicked mid-animation."""
        self.chip_frame.pack_forget()
        self.payout_canvas.pack_forget()
        for w in self.action_frame.pack_slaves():
            w.pack_forget()

    # ------------------------------------------------------------------ betting
    def _on_place_chip(self, key):
        if self.state != "betting":
            return
        self._adjust_bet(key, self.selected_chip)

    def _adjust_bet(self, key, delta):
        trial_bets = dict(self.bets)
        trial_bets[key] += delta
        balance = self.app.finance.balance
        if _max_round_cost(trial_bets) > balance + 1e-9:
            upfront = trial_bets["ante"] + trial_bets["pair_plus"] + trial_bets["prime"]
            if upfront <= balance + 1e-9:
                # They could afford to place it, just not to also match it with
                # a Play bet later -- a casino wouldn't let you place an Ante
                # you can't back up.
                messagebox.showwarning(
                    "Insufficient Balance",
                    "You wouldn't have enough left to match this Ante with a Play bet "
                    "if you choose to play. Reduce your bet or add funds.",
                )
            else:
                messagebox.showwarning("Insufficient Balance", "You don't have enough balance to place that chip.")
            return
        self.bets = trial_bets
        self._draw_table()
        self._update_total()
        self._persist_state()

    def _clear_bets(self):
        if self.state != "betting":
            return
        for key in self.bets:
            self.bets[key] = 0
        self._draw_table()
        self._update_total()
        self._persist_state()

    def _update_total(self):
        self.total_lbl.configure(text=f"Total bet: £{sum(self.bets.values())}")

    def _persist_state(self):
        save_json(self.save_path, {"bets": self.bets, "selected_chip": self.selected_chip})

    def _sanitize_bets(self, persist=True):
        """Zeroes the remembered bets if they (including a potential matching
        Play bet) now exceed the balance -- keeps the player from being stuck
        with a remembered Ante they could no longer afford to play."""
        if _max_round_cost(self.bets) > self.app.finance.balance:
            self.bets = {"ante": 0, "pair_plus": 0, "prime": 0}
            if persist:
                self._persist_state()

    # ------------------------------------------------------------------ round flow
    def _on_deal(self):
        ante, pair_plus, prime = self.bets["ante"], self.bets["pair_plus"], self.bets["prime"]
        if ante <= 0:
            messagebox.showwarning("Ante Required", "You must place an Ante bet to deal.")
            return

        # Checked against the worst case (this wager plus a matching Play bet),
        # not just the upfront total -- _adjust_bet already enforces this on
        # every chip placement, so this is a defensive re-check, not the
        # primary guard (see _adjust_bet and _sanitize_bets).
        if not self.app.finance.can_afford(_max_round_cost(self.bets)):
            messagebox.showwarning(
                "Insufficient Balance",
                "You don't have enough balance for these bets and a matching Play bet.",
            )
            return

        total_upfront = ante + pair_plus + prime
        self.app.finance.place_wager(total_upfront)
        self._refresh_balance()

        self.result = self.game.play_round(ante, pair_plus, prime)
        self.state = "dealt"

        self.result_lbl.configure(text="Dealing...", fg="#f0f0f0")
        self._show_no_controls()

        # Only the play area appears at first: the dealer's cards (face down)
        # and an empty zone where the player's hand will land.
        self._draw_card_zones()
        for i in range(3):
            self._draw_dealer_slot(i, face_up=False)

        self._deal_player_cards()

    def _finish_round(self, folded):
        assert self.result is not None, "_finish_round called before a round was dealt"
        if not folded:
            play_bet = self.result.ante_bet
            if not self.app.finance.can_afford(play_bet):
                messagebox.showwarning(
                    "Insufficient Balance",
                    "You don't have enough balance to match the Play bet. Folding instead.",
                )
                folded = True
            else:
                self.app.finance.place_wager(play_bet)

        result = self.game.resolve(folded)
        if result.total_returned > 0:
            self.app.finance.add_return(result.total_returned)
        self.app.finance.record_round_played(result.net_result)
        self._refresh_balance()

        self._show_no_controls()
        on_settled = lambda: self._reveal_dealer(result)
        if folded:
            self._fold_player_cards(on_settled)
        else:
            self._sort_player_cards(on_settled)

    def _new_round(self):
        self.state = "betting"
        self.result_lbl.configure(text="Place your Ante bet to begin.", fg="#f0f0f0")
        # Bets carry over for a quick rebet -- Clear Bets is there if they want £0 instead.
        self._sanitize_bets()
        self._show_betting_controls()

    # ------------------------------------------------------------------ card-view rendering
    def _draw_card_zones(self):
        """Draws the static dealer + player felt zones and their labels for
        the post-Deal view -- once per round. Individual cards are separate,
        tagged canvas items drawn/animated on top of this background."""
        self.canvas.delete("all")
        cx = CANVAS_WIDTH / 2

        # Dealer zone: an oval, matching the betting screen's felt-and-gold look.
        self.canvas.create_oval(
            DEALER_ZONE_X1, DEALER_ZONE_TOP, DEALER_ZONE_X2, DEALER_ZONE_BOTTOM,
            fill="#0e4a2c", outline="#d4af37", width=2, tags=("zone_bg",),
        )
        self.canvas.create_text(cx, DEALER_Y - 16, text="DEALER", fill="#dddddd",
                                 font=("Helvetica", 10, "bold"), tags=("zone_bg",))

        # Player zone: a rounded rectangle -- same felt/gold language and the
        # same size as the dealer's, but a different shape so the two read as
        # a matched pair rather than a plain duplicate.
        self._draw_rounded_rect(
            PLAYER_ZONE_X1, PLAYER_ZONE_TOP, PLAYER_ZONE_X2, PLAYER_ZONE_BOTTOM, radius=34,
            fill="#0e4a2c", outline="#d4af37", width=2, tags=("zone_bg",),
        )
        self.canvas.create_text(cx, PLAYER_ZONE_TOP + 18, text="YOUR HAND", fill="#dddddd",
                                 font=("Helvetica", 10, "bold"), tags=("zone_bg",))

    def _draw_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        points = [
            x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
            x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
        ]
        return self.canvas.create_polygon(points, smooth=True, **kwargs)

    def _dealer_slot_x(self, i):
        return CARD_ROW_START_X + i * CARD_ROW_GAP

    def _draw_dealer_slot(self, i, face_up):
        assert self.result is not None
        tag = f"dealer_card_{i}"
        self.canvas.delete(tag)
        x = self._dealer_slot_x(i)
        if face_up:
            draw_card(self.canvas, x, DEALER_Y, self.result.dealer_cards[i], tags=(tag,))
        else:
            draw_card_back(self.canvas, x, DEALER_Y, tags=(tag,))

    def _draw_player_card_at(self, i, card, x, y, face_up=True):
        tag = f"player_card_{i}"
        self.canvas.delete(tag)
        if face_up:
            draw_card(self.canvas, x, y, card, tags=(tag,))
        else:
            draw_card_back(self.canvas, x, y, tags=(tag,))

    def _fan_slots(self):
        """Top-left (x, y) for each of the player's 3 cards, in dealt order,
        overlapping in a gentle arc -- the resting spot while Play/Fold is
        being decided."""
        cx = CANVAS_WIDTH / 2
        centers_x = [cx - FAN_GAP, cx, cx + FAN_GAP]
        ys = [FAN_Y + FAN_ARC_OFFSET, FAN_Y, FAN_Y + FAN_ARC_OFFSET]
        return [(x - CARD_WIDTH / 2, y) for x, y in zip(centers_x, ys)]

    def _flat_slots(self):
        """Top-left (x, y) for the player's settled, sorted row of 3 cards."""
        return [(CARD_ROW_START_X + i * CARD_ROW_GAP, PLAYER_Y_SETTLED) for i in range(3)]

    # ------------------------------------------------------------------ animation engine
    def _animate(self, duration_ms, on_frame, on_done=None):
        """Calls on_frame(eased_t) across `duration_ms` at ~30fps, t easing
        0 -> 1. Skips straight to on_frame(1.0) + on_done() when the user has
        turned animations off in Settings."""
        if not self.app.settings.get("animations_enabled"):
            on_frame(1.0)
            if on_done:
                on_done()
            return
        fps = 30
        total_steps = max(1, round(duration_ms / (1000 / fps)))

        def tick(step):
            on_frame(_ease_out_cubic(step / total_steps))
            if step < total_steps:
                self.after(round(1000 / fps), tick, step + 1)
            elif on_done:
                on_done()

        tick(0)

    def _run_staggered(self, count, stagger_ms, fn):
        """Calls fn(i) for i in range(count), staggered by `stagger_ms` via
        `after` -- or immediately back-to-back if animations are off (fn is
        expected to use self._animate internally, which self-collapses to an
        instant call in that case too, so the whole chain ends up synchronous)."""
        if self.app.settings.get("animations_enabled"):
            for i in range(count):
                self.after(i * stagger_ms, fn, i)
        else:
            for i in range(count):
                fn(i)

    def _animate_flip(self, tag, cx_slot, y, card, reveal, duration, on_done=None):
        """Flips a card in place by narrowing it to a sliver and back out,
        swapping the face at the midpoint. `reveal=True` turns a face-down
        card face up (the dealer's reveal); `reveal=False` turns a face-up
        card face down (folding, before it's mucked away)."""
        def frame(t):
            squeeze = abs(1 - 2 * t)
            w = max(6, CARD_WIDTH * squeeze)
            x = cx_slot - w / 2
            self.canvas.delete(tag)
            face_up_now = reveal if t >= 0.5 else not reveal
            if squeeze > 0.35:
                if face_up_now:
                    draw_card(self.canvas, x, y, card, width=w, tags=(tag,))
                else:
                    draw_card_back(self.canvas, x, y, width=w, tags=(tag,))
            else:
                self.canvas.create_rectangle(x, y, x + w, y + CARD_HEIGHT,
                                              fill="#fdfdf5", outline="#222222", tags=(tag,))

        self._animate(duration, frame, on_done=on_done)

    # ------------------------------------------------------------------ deal-in / decision / reveal
    def _deal_player_cards(self):
        assert self.result is not None
        cards = self.result.player_cards
        fan_slots = self._fan_slots()

        def deal_one(i):
            tx, ty = fan_slots[i]
            sx, sy = tx, ty - 90  # drop in from just above its own fan slot

            def frame(t, i=i, sx=sx, sy=sy, tx=tx, ty=ty):
                self._draw_player_card_at(i, cards[i], sx + (tx - sx) * t, sy + (ty - sy) * t, face_up=True)

            self._animate(220, frame, on_done=(self._on_player_cards_dealt if i == 2 else None))

        if self.app.settings.get("animations_enabled"):
            self.after(350, lambda: self._run_staggered(3, 90, deal_one))
        else:
            self._run_staggered(3, 90, deal_one)

    def _on_player_cards_dealt(self):
        self.result_lbl.configure(text="Your cards are dealt. Play or Fold?", fg="#f0f0f0")
        self._show_decision_controls()

    def _sort_player_cards(self, on_done):
        assert self.result is not None
        cards = self.result.player_cards
        order = sorted(range(3), key=lambda i: -cards[i].value)  # highest first, left to right
        fan_slots = self._fan_slots()
        flat_slots = self._flat_slots()

        def frame(t):
            for new_pos, orig_i in enumerate(order):
                sx, sy = fan_slots[orig_i]
                tx, ty = flat_slots[new_pos]
                self._draw_player_card_at(orig_i, cards[orig_i], sx + (tx - sx) * t, sy + (ty - sy) * t)

        self._animate(260, frame, on_done=on_done)

    def _fold_player_cards(self, on_done):
        assert self.result is not None
        cards = self.result.player_cards
        fan_slots = self._fan_slots()

        def muck_one(i):
            sx, sy = fan_slots[i]
            cx_slot = sx + CARD_WIDTH / 2

            def slide(t, sx=sx, sy=sy):
                tx, ty = CANVAS_WIDTH + 90, sy - 40  # forwards (up) and off to the side
                self._draw_player_card_at(i, None, sx + (tx - sx) * t, sy + (ty - sy) * t, face_up=False)

            self._animate_flip(
                f"player_card_{i}", cx_slot, sy, cards[i], reveal=False, duration=180,
                on_done=lambda: self._animate(220, slide, on_done=(on_done if i == 2 else None)),
            )

        self._run_staggered(3, 70, muck_one)

    def _reveal_dealer(self, result):
        def flip_one(i):
            cx_slot = self._dealer_slot_x(i) + CARD_WIDTH / 2
            self._animate_flip(
                f"dealer_card_{i}", cx_slot, DEALER_Y, result.dealer_cards[i], reveal=True, duration=200,
                on_done=(lambda: self._on_round_settled(result)) if i == 2 else None,
            )

        self._run_staggered(3, 130, flip_one)

    def _on_round_settled(self, result):
        self._show_result(result)
        self._show_new_round_control()
        self.state = "resolved"

    def _show_result(self, result):
        headline = {
            "fold": "You folded.",
            "dealer_no_qualify": "Dealer doesn't qualify",
            "win": "You win!",
            "lose": "Dealer wins.",
            "push": "Push — stakes returned.",
        }[result.outcome]
        color = {
            "fold": "#cccccc",
            "dealer_no_qualify": "#4be36b",
            "win": "#4be36b",
            "lose": "#e05555",
            "push": "#d4af37",
        }[result.outcome]

        player_hand_name = result.player_eval[1]
        dealer_hand_name = result.dealer_eval[1]
        self.result_lbl.configure(
            text=f"{headline}  (You: {player_hand_name}  |  Dealer: {dealer_hand_name})",
            fg=color,
        )

        self.payout_canvas.pack(expand=True)
        self._draw_payout_panel(result)

    def _payout_rows(self, result):
        """(label, net) pairs for the round -- net is what that bet actually
        made or lost (return minus stake), not the raw amount returned."""
        player_hand_name = result.player_eval[1]
        rows = []
        if result.ante_bet:
            rows.append((f"Ante £{result.ante_bet:.0f}", result.ante_return - result.ante_bet))
        if not result.folded:
            rows.append((f"Play £{result.play_bet:.0f}", result.play_return - result.play_bet))
        if result.ante_bonus_return:
            rows.append((f"Ante Bonus ({player_hand_name})", result.ante_bonus_return))
        if result.pair_plus_bet:
            rows.append((f"Pair Plus £{result.pair_plus_bet:.0f}", result.pair_plus_return - result.pair_plus_bet))
        if result.prime_bet:
            rows.append((f"Prime £{result.prime_bet:.0f}", result.prime_return - result.prime_bet))
        return rows

    def _draw_payout_panel(self, result):
        canvas = self.payout_canvas
        canvas.delete("all")
        w, h = PAYOUT_PANEL_WIDTH, PAYOUT_PANEL_HEIGHT

        canvas.create_rectangle(3, 3, w - 3, h - 3, fill="#0e2a1a", outline="#d4af37", width=2)
        canvas.create_rectangle(8, 8, w - 8, h - 8, outline="#3a6b4c", width=1)
        canvas.create_text(w / 2, 22, text="ROUND RESULT", fill="#d4af37", font=("Georgia", 12, "bold"))

        rows = self._payout_rows(result)
        y = 46
        for label, net in rows:
            canvas.create_text(24, y, text=label, fill="#f0f0f0", font=("Helvetica", 10), anchor="w")
            canvas.create_text(w - 24, y, text=_format_signed(net), fill=_net_color(net),
                                font=("Helvetica", 10, "bold"), anchor="e")
            y += 20

        y += 6
        canvas.create_line(24, y, w - 24, y, fill="#3a6b4c")
        y += 20
        canvas.create_text(24, y, text="Round Net", fill="#f0f0f0", font=("Helvetica", 11, "bold"), anchor="w")
        canvas.create_text(w - 24, y, text=_format_signed(result.net_result), fill=_net_color(result.net_result),
                            font=("Helvetica", 12, "bold"), anchor="e")

    # ------------------------------------------------------------------ lifecycle
    def on_show(self):
        self._apply_theme()
        self._refresh_balance()
        if self.state == "betting":
            self._sanitize_bets()
            self._draw_table()
            self._update_total()

    def _apply_theme(self):
        """Re-applies the felt colour everywhere it was set from the theme at
        build time. Settings can change `table_theme` after this frame was
        already built (frames are built once and reused), so a plain one-off
        `self.configure(bg=...)` at build time never actually took effect
        anywhere but this outer frame -- which every visible widget sits on
        top of, so the change was invisible until a full app restart rebuilt
        everything from scratch."""
        new_felt = self.app.settings.theme()["felt"]
        if new_felt == self._current_felt:
            return
        old_felt = self._current_felt
        self._current_felt = new_felt
        self._retheme_widget(self, old_felt, new_felt)

    def _retheme_widget(self, widget, old_felt, new_felt):
        try:
            if widget.cget("bg") == old_felt:
                widget.configure(bg=new_felt)
        except tk.TclError:
            pass  # a widget type with no "bg" option -- nothing to do
        for child in widget.winfo_children():
            self._retheme_widget(child, old_felt, new_felt)

    def _refresh_balance(self):
        self.balance_lbl.configure(text=f"£{self.app.finance.balance:,.2f}")