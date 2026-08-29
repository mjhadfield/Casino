import math
import os
import tkinter as tk
from typing import Optional

from core.persistence import load_json, save_json
from games.high_card_flush.logic import (
    GAME_KEY,
    HighCardFlushGame,
    RoundResult,
    auto_place,
    hand_outcome_label,
    max_raise_multiplier,
)
from games.high_card_flush import logic as hcf_logic
from ui import dialogs, theme
from ui.card_widgets import draw_card, draw_card_back, CARD_HEIGHT, CARD_WIDTH
from ui.chips import CHIP_DENOMINATIONS, CHIP_LAYER_MAX_R, CHIP_SIZE, draw_chip_face, draw_chip_stack
from ui.jackpot_display import JackpotDisplay

STATE_FILENAME = "high_card_flush_state.json"
DEFAULT_STATE = {"bets": {"ante": 0, "flush": 0, "straight_flush": 0, "jackpot": 0}, "selected_chip": 5}

# --- Layout constants ------------------------------------------------------
CANVAS_WIDTH = 820
CONTENT_TOP_MARGIN = 2

PAYTABLE_WIDTH = 240
PAYTABLE_HEIGHT = 430
# Sized and positioned below, once DEALER_MAT_X2 exists -- see the "Round-
# result panel" block further down.
PAYOUT_PANEL_WIDTH = 260
# Up to 5 bet types (Ante/Raise/Flush/Straight Flush/Jackpot) can appear.
PAYOUT_PANEL_HEIGHT = 195

# The one chip-stack size shared by every betting-box spot's own display,
# refund-free (no pull-back in this game), and payout animation, so a stake
# chip and its later payout chip are always the identical size.
ROW_CHIP_MAX_R = 18

# --- Dealer zones -- two stacked mats (dealt, then placed), a genuinely new
# pattern for this app (every other game's own dealer mat is a single box);
# cards here are drawn at a reduced scale (DEALER_CARD_SCALE) purely to fit
# both zones, plus the betting cluster and the play area below them, inside
# the app's fixed, non-resizable 1200x820 window.
DEALER_CARD_SCALE = 0.6
DEALER_CARD_W = CARD_WIDTH * DEALER_CARD_SCALE
DEALER_CARD_H = CARD_HEIGHT * DEALER_CARD_SCALE
DEALER_CARD_OVERLAP = DEALER_CARD_W * 0.55

DEALT_MAT_RADIUS = 10
DEALT_MAT_TOP = 4
DEALT_LABEL_Y = DEALT_MAT_TOP + 8
DEALT_Y = DEALT_MAT_TOP + 12
DEALT_MAT_BOTTOM = DEALT_Y + DEALER_CARD_H + 6

_DEALER_ROW_W = 6 * DEALER_CARD_OVERLAP + DEALER_CARD_W
DEALER_MAT_MARGIN = 26
DEALER_MAT_WIDTH = _DEALER_ROW_W + 2 * DEALER_MAT_MARGIN
DEALER_MAT_X1 = CANVAS_WIDTH / 2 - DEALER_MAT_WIDTH / 2
DEALER_MAT_X2 = CANVAS_WIDTH / 2 + DEALER_MAT_WIDTH / 2

# --- Round-result panel -- floats over the canvas's own otherwise-empty
# right-hand gap (between Dealer's two mats and the canvas's own right
# edge), rather than a bottom-left corner overlay -- that used to clip into
# the 7-card felt below it, and had to be squeezed narrower than every
# other game's own result panel to avoid it. Parented to game_col (not
# self) and placed in game_col's own local coordinates, offset by the
# canvas's own padx/pady within it, so this lines up with canvas-space
# constants (DEALER_MAT_X2, DEALT_MAT_TOP) directly.
CANVAS_PADX = 12
CANVAS_PADY = 2
PAYOUT_PANEL_MARGIN = 12
PAYOUT_PANEL_X = CANVAS_PADX + DEALER_MAT_X2 + PAYOUT_PANEL_MARGIN
PAYOUT_PANEL_Y = CANVAS_PADY + DEALT_MAT_TOP

GAP_DEALT_TO_PLACED = 8
PLACED_MAT_TOP = DEALT_MAT_BOTTOM + GAP_DEALT_TO_PLACED
PLACED_LABEL_Y = PLACED_MAT_TOP + 8
PLACED_Y = PLACED_MAT_TOP + 12
PLACED_MAT_BOTTOM = PLACED_Y + DEALER_CARD_H + 6


def _dealer_cluster_x(pos, n=7):
    fan_w = (n - 1) * DEALER_CARD_OVERLAP + DEALER_CARD_W if n > 1 else DEALER_CARD_W
    start_x = CANVAS_WIDTH / 2 - fan_w / 2
    return start_x + pos * DEALER_CARD_OVERLAP


# --- Betting cluster -- carried over unmoved between the betting screen and
# the play screen, same "carry the whole cluster over" convention as every
# other recent game. Internal order (bottom to top: Ante+Raise, then
# Flush/Straight Flush) mirrors the betting screen's own vertical stack;
# Jackpot sits off to the right of that pair of rows -- beside Straight
# Flush/Raise, its own two right-hand spots -- rather than in a row of its
# own above them.
ANTE_R = 22
RAISE_R = ANTE_R
FLUSH_R = 20
STRAIGHT_FLUSH_R = 20
JACKPOT_R = 16
ROW_GAP = 12
SIDE_GAP = 20  # half-distance between Flush/Straight Flush, and between Ante/Raise
JACKPOT_GAP = 20  # gap between Jackpot and whichever of Straight Flush/Raise it sits beside

# The whole betting cluster (and the Deck beside it) is vertically centred
# in the empty gap between DEALER'S FLUSH above and "YOUR FLUSH" below,
# rather than hugging either one -- so it reads as its own row sitting
# between the two, not crowded against whichever mat happens to be closer.
GAP_PLACED_TO_ZONE = 180
ZONE_TOP = PLACED_MAT_BOTTOM + GAP_PLACED_TO_ZONE

_MID_R = max(FLUSH_R, STRAIGHT_FLUSH_R)
_CLUSTER_HEIGHT = 2 * ANTE_R + ROW_GAP + 2 * _MID_R
_CLUSTER_MARGIN = ((ZONE_TOP - PLACED_MAT_BOTTOM) - _CLUSTER_HEIGHT) / 2
CLUSTER_TOP = PLACED_MAT_BOTTOM + _CLUSTER_MARGIN
ANTE_CY = CLUSTER_TOP + _CLUSTER_HEIGHT - ANTE_R
MID_CY = ANTE_CY - ANTE_R - ROW_GAP - _MID_R

FLUSH_CX = CANVAS_WIDTH / 2 - (FLUSH_R + SIDE_GAP)
STRAIGHT_FLUSH_CX = CANVAS_WIDTH / 2 + (STRAIGHT_FLUSH_R + SIDE_GAP)
ANTE_CX = CANVAS_WIDTH / 2 - (ANTE_R + SIDE_GAP)
RAISE_CX = CANVAS_WIDTH / 2 + (RAISE_R + SIDE_GAP)

# To the right of whichever of Straight Flush/Raise reaches furthest right,
# vertically centred between their two rows.
JACKPOT_CX = max(STRAIGHT_FLUSH_CX + STRAIGHT_FLUSH_R, RAISE_CX + RAISE_R) + JACKPOT_GAP + JACKPOT_R
JACKPOT_CY = (MID_CY + ANTE_CY) / 2

CLUSTER_BOTTOM = ANTE_CY + ANTE_R

# The face-down shoe every dealt card visibly flies out of -- a small zone
# to the left of the betting cluster, bottom-anchored to line up with the
# cluster's own bottom row rather than its top row: the deck card needs
# more vertical room than the two betting rows do, so aligning top edges
# (as this used to) left its own bottom edge sticking out below the
# cluster, forcing a gap in between the cluster and the play area beneath.
DECK_ZONE_W = CARD_WIDTH + 30
DECK_ZONE_CX = (CANVAS_WIDTH / 2 - (ANTE_R + SIDE_GAP + ANTE_R)) / 2 - 30
DECK_ZONE_X1 = DECK_ZONE_CX - DECK_ZONE_W / 2
DECK_ZONE_X2 = DECK_ZONE_CX + DECK_ZONE_W / 2
DECK_X1 = DECK_ZONE_CX - CARD_WIDTH / 2
DECK_Y = CLUSTER_BOTTOM - 5 - CARD_HEIGHT
DECK_ZONE_TOP = DECK_Y - 22
DECK_LABEL_Y = DECK_ZONE_TOP + 12
# The mat's bottom border extends the same distance below the card as its
# top border leaves above it (that top margin is what the "DECK" label
# sits in) -- kept visually symmetric top-to-bottom, rather than the
# card's own bottom edge nearly touching the mat's border.
DECK_ZONE_BOTTOM = DECK_Y + CARD_HEIGHT + (DECK_Y - DECK_ZONE_TOP)

# --- Player's play area ("YOUR FLUSH") -- a single zone (Pai Gow's own Back
# zone, minus the Front zone and its foul-check machinery).
ZONE_LABEL_Y_OFFSET = 14
ZONE_ROW_Y = ZONE_TOP + ZONE_LABEL_Y_OFFSET + 10
ZONE_H = ZONE_ROW_Y - ZONE_TOP + CARD_HEIGHT + 8
ZONE_BOTTOM = ZONE_TOP + ZONE_H
ZONE_CX = CANVAS_WIDTH / 2
ZONE_CARD_OVERLAP = CARD_WIDTH * 0.55
# Sized to fit exactly a 7-card fanned hand (the most this zone can ever
# hold) plus a small margin either side -- not the near-full canvas width
# it used to span, since the cards inside always overlap/stack rather than
# spreading out to fill whatever room is available.
_ZONE_MAX_FAN_W = 6 * ZONE_CARD_OVERLAP + CARD_WIDTH
ZONE_SIDE_MARGIN = 26
ZONE_WIDTH = _ZONE_MAX_FAN_W + 2 * ZONE_SIDE_MARGIN
# Rounded to a whole pixel -- landing on a .5 x-coordinate otherwise (odd
# ZONE_WIDTH split around an even ZONE_CX) makes Tk's smooth rounded-rect
# render a visibly jagged, sawtoothed edge down the tall straight left/
# right sides (same pitfall as Pai Gow Poker's own DECK_ZONE_CX rounding).
ZONE_X1 = round(ZONE_CX - ZONE_WIDTH / 2)
ZONE_X2 = round(ZONE_CX + ZONE_WIDTH / 2)

CANVAS_HEIGHT = int(ZONE_BOTTOM + 16)

# --- Player's own 7-card hand ("YOUR CARDS") -- a separate, wider canvas
# below the button row, same "second canvas below the buttons" convention
# every sibling game's own fan_canvas follows, just wide enough for 7 cards.
FAN_Y = 14
FAN_GAP = 16
# As wide as the main canvas -- not just wide enough for the 7 cards --
# so its own widget boundary starts flush with the main canvas's own left
# edge; the cards themselves stay centred within it either way, but this
# leaves the ROUND RESULT panel (see PAYOUT_PANEL_WIDTH/_show_payout_panel)
# a strip of genuinely empty background to sit in front of at the bottom
# left, rather than clipping into the leftmost dealt card.
FAN_CANVAS_WIDTH = CANVAS_WIDTH
FAN_CANVAS_HEIGHT = FAN_Y + CARD_HEIGHT + 18
_FAN_TOTAL_W = 7 * CARD_WIDTH + 6 * FAN_GAP
FAN_MAT_X1 = (FAN_CANVAS_WIDTH - _FAN_TOTAL_W) / 2 - 30
FAN_MAT_X2 = FAN_CANVAS_WIDTH - FAN_MAT_X1
FAN_MAT_TOP = 4
FAN_MAT_BOTTOM = FAN_CANVAS_HEIGHT - 4
FAN_MAT_RADIUS = 12
FAN_MAT_BORDER = theme.FG_DIM


def _felt_card_x(pos, n=7):
    return FAN_CANVAS_WIDTH / 2 - _FAN_TOTAL_W / 2 + pos * (CARD_WIDTH + FAN_GAP)


# --- Rules button ------------------------------------------------------
RULES_BUTTON_WIDTH = 106
RULES_BUTTON_HEIGHT = 54
RULES_BUTTON_RADIUS = RULES_BUTTON_HEIGHT // 2

# --- Betting-screen-only spacing -------------------------------------------
BETTING_ACTION_FRAME_PADY = (8, 0)
CHIP_FRAME_PADY = (4, 2)

# --- Animation pacing --------------------------------------------------
DEAL_IN_STAGGER_MS = 90
DEAL_IN_DROP_MS = 200
SORT_MOVE_MS = 240
AUTO_PLACE_STEP_MS = 220
REVEAL_STAGGER_MS = 220
REVEAL_FLIP_MS = 200
SEPARATE_MOVE_MS = 240
PAYOUT_CHIP_MOVE_MS = 280
PAYOUT_WIN_LANDING_OFFSET_Y = -18

# Cards being discarded -- either the leftover felt cards once Confirm
# locks in the flush zone (a normal-speed flip), or the player's whole
# hand on a real Fold (turned over "rapidly", per spec -- a shorter flip
# than anything else in this game). Both share the same fly-away beat.
DISCARD_FLIP_MS = 200
FOLD_FLIP_MS = 120
FOLD_FLY_MS = 220
FOLD_FLY_STAGGER_MS = 70
FOLD_FLY_TARGET = (FAN_CANVAS_WIDTH + 90, -50)


def _ease_out_cubic(t):
    return 1 - (1 - t) ** 3


def _format_signed(amount):
    magnitude = abs(amount)
    text = f"£{magnitude:,.0f}" if magnitude == int(magnitude) else f"£{magnitude:,.2f}"
    if amount > 0:
        return f"+{text}"
    if amount < 0:
        return f"-{text}"
    return "£0"


def _net_color(amount):
    if amount > 0:
        return theme.WIN_COLOR
    if amount < 0:
        return theme.LOSE_COLOR
    return theme.PUSH_COLOR


def _sort_key(card):
    return (card.suit.value, -card.value)


# Paytable rows, read straight from logic.py's own constants.
FLUSH_PAYTABLE_ROWS = [(f"{n}-Card Flush", f"{m}:1") for n, m in sorted(hcf_logic.FLUSH_BONUS_PAYTABLE.items(), reverse=True)]
STRAIGHT_FLUSH_PAYTABLE_ROWS = [
    (f"{n}-Card Straight Flush", f"{m}:1")
    for n, m in sorted(hcf_logic.STRAIGHT_FLUSH_BONUS_PAYTABLE.items(), reverse=True)
]
PAYTABLE_SECTIONS = [
    ("MAIN GAME (Ante/Raise)", [("Win", "1:1")]),
    ("FLUSH BONUS", FLUSH_PAYTABLE_ROWS),
    ("STRAIGHT FLUSH BONUS", STRAIGHT_FLUSH_PAYTABLE_ROWS),
]

JACKPOT_PAYTABLE_ROWS = [
    ("7-Card Straight Flush", "100% JACKPOT"),
    ("6-Card Straight Flush", "50% JACKPOT"),
    ("5-Card Straight Flush", f"£{hcf_logic.JACKPOT_FLAT_PAYOUTS[5]:.0f}"),
    ("4-Card Straight Flush", f"£{hcf_logic.JACKPOT_FLAT_PAYOUTS[4]:.0f}"),
    ("3-Card Straight Flush", f"£{hcf_logic.JACKPOT_FLAT_PAYOUTS[3]:.0f}"),
]
JACKPOT_PAYTABLE_HIGHLIGHT_ROW = 0


def _max_deal_cost(bets):
    return bets["ante"] + bets["flush"] + bets["straight_flush"] + bets["jackpot"]


class HighCardFlushFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.BG)
        self.app = app
        self.game = HighCardFlushGame()
        self.result: Optional[RoundResult] = None
        self.state = "betting"      # betting -> playing -> resolved
        self.stage = "arranging"    # arranging -> raising, while state == "playing"

        self.save_path = os.path.join(app.data_dir, STATE_FILENAME)
        saved = load_json(self.save_path, DEFAULT_STATE)
        saved_bets = saved.get("bets", DEFAULT_STATE["bets"])
        self.bets = {
            "ante": int(saved_bets.get("ante", 0)),
            "flush": int(saved_bets.get("flush", 0)),
            "straight_flush": int(saved_bets.get("straight_flush", 0)),
            "jackpot": int(saved_bets.get("jackpot", 0)),
        }
        self.selected_chip = int(saved.get("selected_chip", DEFAULT_STATE["selected_chip"]))
        self._sanitize_bets(persist=False)

        self.chip_canvases = {}
        self._jackpot_pulse_t = 0.0

        # Per-round card-placement state -- see the module docstring's own
        # "play area is cosmetic" note: none of this is ever read by
        # logic.py's own settle(), only by this file's own drawing code.
        self.card_zone = {}       # dealt-index -> "felt" | "flush"
        self.flush_order = []     # dealt-order indices, placement order
        self.felt_slot_order = list(range(7))
        self._hover_tag = None
        self._setting_locked = False
        self._dealer_revealed = False

        self._build_ui()
        self.app.jackpot.add_listener(self._on_jackpot_changed)
        self.jackpot_display.set_value(self.app.jackpot.raw_amount)
        self._pulse_jackpot()

    # ------------------------------------------------------------------ UI build
    def _build_ui(self):
        felt_theme = self.app.settings.theme()
        self._current_felt = felt_theme["felt"]
        self.configure(bg=felt_theme["felt"])

        top_bar = tk.Frame(self, bg=theme.BG_ELEVATED)
        top_bar.pack(fill="x")
        tk.Button(
            top_bar, text="← Menu", bg=theme.BG_ELEVATED, fg=theme.FG_DIM, relief="flat",
            font=theme.font(11), padx=12, pady=6, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.BORDER, highlightcolor=theme.ACCENT,
            command=lambda: self.app.show_frame("menu"),
        ).pack(side="left", padx=(20, 10), pady=10)
        tk.Label(top_bar, text="High Card Flush", bg=theme.BG_ELEVATED, fg=theme.ACCENT,
                 font=theme.font(16, weight="bold")).pack(side="left", padx=10)
        self.balance_lbl = tk.Label(top_bar, text="£0.00", bg=theme.BG_ELEVATED, fg=theme.WIN_COLOR,
                                     font=theme.font(12, weight="bold"))
        self.balance_lbl.pack(side="right", padx=20)
        theme.breadcrumb(top_bar, "high_card_flush", bg=theme.BG_ELEVATED,
                          player=self.app.current_player["name"]).pack(side="right", padx=(6, 6))

        body = tk.Frame(self, bg=felt_theme["felt"])
        body.pack(fill="both", expand=True)

        content = tk.Frame(body, bg=felt_theme["felt"])
        content.place(relx=0.5, y=CONTENT_TOP_MARGIN, anchor="n")

        game_col = tk.Frame(content, bg=felt_theme["felt"])
        game_col.pack(side="left", anchor="n")

        paytable_col = tk.Frame(content, bg=felt_theme["felt"])
        paytable_col.pack(side="right", fill="y", padx=(10, 24), pady=10)

        self.jackpot_display = JackpotDisplay(
            paytable_col, rows=JACKPOT_PAYTABLE_ROWS, highlight_row=JACKPOT_PAYTABLE_HIGHLIGHT_ROW,
            panel_bg=felt_theme["felt_dark"], border=felt_theme["accent"],
        )
        self.jackpot_display.pack(pady=(0, 10))
        self._build_paytable(paytable_col)

        self.canvas = tk.Canvas(game_col, bg=felt_theme["felt"], highlightthickness=0,
                                 width=CANVAS_WIDTH, height=CANVAS_HEIGHT)
        self.canvas.pack(padx=12, pady=(2, 2))

        self.result_lbl = tk.Label(
            game_col, text="Place your Ante bet to begin.", bg=felt_theme["felt"], fg=theme.FG,
            font=theme.font(12, weight="bold"), wraplength=900, justify="center",
        )
        self.result_lbl.pack(pady=(0, 4))

        self.action_frame = tk.Frame(game_col, bg=felt_theme["felt"])
        self.action_frame.pack(pady=(4, 0))

        self.deal_btn = tk.Button(
            self.action_frame, text="DEAL", bg=theme.ACCENT_DIM_BG, fg=theme.FG,
            font=theme.font(13, weight="bold"), relief="flat", padx=30, pady=10, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.ACCENT,
            command=self._on_deal,
        )
        self.sort_btn = tk.Button(
            self.action_frame, text="SORT", bg=theme.GREY_BTN_BG, fg=theme.FG,
            font=theme.font(11, weight="bold"), relief="flat", padx=14, pady=8, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.GREY_BTN_BORDER,
            command=self._on_sort,
        )
        self.auto_place_btn = tk.Button(
            self.action_frame, text="AUTO PLACE", bg=theme.WARN_DIM_BG, fg=theme.FG,
            font=theme.font(11, weight="bold"), relief="flat", padx=14, pady=8, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.WARN,
            command=self._on_auto_place,
        )
        self.confirm_btn = tk.Button(
            self.action_frame, text="CONFIRM", bg=theme.ACCENT_DIM_BG, fg=theme.FG,
            font=theme.font(11, weight="bold"), relief="flat", width=9, pady=8, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.ACCENT,
            command=self._on_confirm,
        )
        self.fold_btn = tk.Button(
            self.action_frame, text="FOLD", bg=theme.LOSE_DIM_BG, fg=theme.FG,
            font=theme.font(11, weight="bold"), relief="flat", padx=14, pady=8, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.LOSE_COLOR,
            command=self._on_fold,
        )
        self.raise1_btn = tk.Button(
            self.action_frame, text="RAISE 1x", font=theme.font(11, weight="bold"), relief="flat",
            padx=14, pady=8, cursor="hand2", highlightthickness=1, command=lambda: self._on_raise(1),
        )
        self.raise2_btn = tk.Button(
            self.action_frame, text="RAISE 2x", font=theme.font(11, weight="bold"), relief="flat",
            padx=14, pady=8, cursor="hand2", highlightthickness=1, command=lambda: self._on_raise(2),
        )
        self.raise3_btn = tk.Button(
            self.action_frame, text="RAISE 3x", font=theme.font(11, weight="bold"), relief="flat",
            padx=14, pady=8, cursor="hand2", highlightthickness=1, command=lambda: self._on_raise(3),
        )
        self.new_deal_btn = tk.Button(
            self.action_frame, text="New Deal", bg=theme.ACCENT_DIM_BG, fg=theme.FG,
            font=theme.font(13, weight="bold"), relief="flat", padx=30, pady=10, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.ACCENT,
            command=self._new_deal,
        )
        self.change_bets_btn = tk.Button(
            self.action_frame, text="Change Bets", bg=theme.GREY_BTN_BG, fg=theme.FG_DIM,
            font=theme.font(13, weight="bold"), relief="flat", padx=30, pady=10, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.GREY_BTN_BORDER,
            command=self._new_round,
        )

        self.fan_canvas = tk.Canvas(game_col, bg=felt_theme["felt"], highlightthickness=0,
                                     width=FAN_CANVAS_WIDTH, height=FAN_CANVAS_HEIGHT)

        self.chip_zone = tk.Frame(game_col, bg=felt_theme["felt"])
        self.chip_zone.pack(pady=(8, 0))

        self.payout_canvas = tk.Canvas(
            game_col, width=PAYOUT_PANEL_WIDTH, height=PAYOUT_PANEL_HEIGHT,
            bg=felt_theme["felt"], highlightthickness=0,
        )

        self.chip_frame = tk.Frame(self.chip_zone, bg=felt_theme["felt"])
        tk.Label(
            self.chip_frame, text="Tap a chip, then tap Ante / Flush / Straight Flush / Jackpot to place it",
            bg=felt_theme["felt"], fg=theme.FG_DIM, font=theme.font(9),
        ).pack(pady=(0, 6))
        self.chip_row = tk.Frame(self.chip_frame, bg=felt_theme["felt"])
        self.chip_row.pack()
        for value, face, rim in CHIP_DENOMINATIONS:
            self._make_chip_button(self.chip_row, value, face, rim)

        self.total_lbl = tk.Label(
            self.chip_frame, text="Total bet: £0", bg=felt_theme["felt"], fg=theme.ACCENT,
            font=theme.font(12, weight="bold"),
        )
        self.total_lbl.pack(pady=(6, 0))

        self.clear_btn = tk.Button(
            self.chip_frame, text="Clear Bets", bg=theme.GREY_BTN_BG, fg=theme.FG_DIM,
            font=theme.font(9), relief="flat", padx=10, pady=4, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.GREY_BTN_BORDER,
            command=self._clear_bets,
        )
        self.clear_btn.pack(pady=(6, 0))

        self.chip_frame.pack(pady=CHIP_FRAME_PADY)
        self.chip_frame.update_idletasks()
        self.chip_zone.configure(
            width=self.chip_zone.winfo_reqwidth(),
            height=self.chip_zone.winfo_reqheight(),
        )
        self.chip_zone.pack_propagate(False)

        self._show_betting_controls()

    # ------------------------------------------------------------------ chip tray
    def _make_chip_button(self, parent, value, face, rim):
        felt_theme = self.app.settings.theme()
        canvas = tk.Canvas(parent, width=CHIP_SIZE + 10, height=CHIP_SIZE + 10,
                            bg=felt_theme["felt"], highlightthickness=0, cursor="hand2")
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
        draw_chip_face(canvas, cx, cy, value, face, rim, r=r, selected=value == self.selected_chip)

    def _select_chip(self, value):
        self.selected_chip = value
        for v in self.chip_canvases:
            self._draw_chip(v)
        self._persist_state()

    # ------------------------------------------------------------------ paytable panel
    def _build_paytable(self, parent):
        felt_theme = self.app.settings.theme()
        canvas = tk.Canvas(parent, width=PAYTABLE_WIDTH, height=PAYTABLE_HEIGHT,
                            bg=felt_theme["felt"], highlightthickness=0)
        canvas.pack()
        self.paytable_canvas = canvas
        self._draw_paytable()

    def _draw_paytable(self):
        canvas = self.paytable_canvas
        canvas.delete("all")
        w, h = PAYTABLE_WIDTH, PAYTABLE_HEIGHT
        felt_theme = self.app.settings.theme()
        theme.recessed_panel(canvas, 0, 0, w, h, title="PAYTABLE", title_font_size=13,
                              fill=felt_theme["felt_dark"], outline=felt_theme["accent"])
        y = 38
        for i, (title, rows) in enumerate(PAYTABLE_SECTIONS):
            if i:
                canvas.create_line(20, y, w - 20, y, fill=theme.BORDER)
                y += 8
            canvas.create_text(20, y, text=title, fill=felt_theme["accent"],
                                font=theme.font(8, weight="bold"), anchor="w")
            y += 15
            for label, payout in rows:
                canvas.create_text(20, y, text=label, fill=theme.FG, font=theme.font(8), anchor="w")
                canvas.create_text(w - 20, y, text=payout, fill=felt_theme["accent"],
                                    font=theme.font(8, weight="bold"), anchor="e")
                y += 14
        y += 12
        canvas.create_text(
            w / 2, y, anchor="n",
            text="Dealer qualifies with a 3-card, 9-high\nflush or better -- otherwise Ante pays\n"
                 "1:1 and Raise pushes.",
            fill=theme.FG_DIM, font=theme.font(7), justify="center",
        )

    # ------------------------------------------------------------------ betting table
    def _draw_table(self):
        """The betting screen's own layout -- generously spaced, computed
        fresh here rather than reusing the play screen's own tighter module
        constants (same convention every prior game's betting screen has
        followed). Jackpot sits to the right of Straight Flush -- beside
        the row pair, vertically centred between them -- mirroring the
        play screen's own Jackpot placement beside Straight Flush/Raise."""
        self.canvas.delete("all")
        w, h = CANVAS_WIDTH, CANVAS_HEIGHT
        cx = w / 2

        ante_r = 50
        side_r = 40
        jackpot_r = 30
        side_gap = 40
        row_gap = 40
        jackpot_gap = 34

        content_h = side_r * 2 + row_gap + ante_r * 2
        top = (h - content_h) * 0.55
        side_cy = top + side_r
        ante_cy = side_cy + side_r + row_gap + ante_r

        straight_flush_cx = cx + (side_r + side_gap)
        jackpot_cx = straight_flush_cx + side_r + jackpot_gap + jackpot_r
        jackpot_cy = (side_cy + ante_cy) / 2

        self._draw_spot_jackpot(jackpot_cx, jackpot_cy, jackpot_r)
        self._draw_spot_circle("flush", cx - (side_r + side_gap), side_cy, side_r, "FLUSH")
        self._draw_spot_circle("straight_flush", straight_flush_cx, side_cy, side_r, "STRAIGHT FLUSH")
        self._draw_spot_circle("ante", cx, ante_cy, ante_r, "ANTE")

        left_edge = cx - ante_r
        self._draw_rules_button(left_edge / 2, ante_cy)

    def _draw_rules_button(self, cx, cy):
        tag = "rules_button"
        felt_theme = self.app.settings.theme()
        x1, y1 = cx - RULES_BUTTON_WIDTH / 2, cy - RULES_BUTTON_HEIGHT / 2
        x2, y2 = cx + RULES_BUTTON_WIDTH / 2, cy + RULES_BUTTON_HEIGHT / 2
        theme.rounded_rect(self.canvas, x1, y1, x2, y2, radius=RULES_BUTTON_RADIUS,
                            fill=felt_theme["felt_dark"], outline=felt_theme["accent"], width=2, tags=(tag,))
        self.canvas.create_text(cx, cy - 12, text="♠", fill=felt_theme["accent"],
                                 font=theme.font(15, weight="bold"), tags=(tag,))
        self.canvas.create_text(cx, cy + 10, text="RULES", fill=theme.FG,
                                 font=theme.font(9, weight="bold"), tags=(tag,))
        self.canvas.tag_bind(tag, "<Button-1>", lambda _e: self._show_rules())
        self.canvas.tag_bind(tag, "<Enter>", lambda _e: self.canvas.configure(cursor="hand2"))
        self.canvas.tag_bind(tag, "<Leave>", lambda _e: self.canvas.configure(cursor=""))

    def _show_rules(self):
        dialogs.document(
            self, "♠ High Card Flush -- Rules",
            [
                ("GAMEPLAY", [
                    "**Not poker:** your hand's rank is purely how many of your 7 cards share "
                    "one suit -- that's your \"flush\". Longer always beats shorter, no matter "
                    "the rank; equal length is broken by comparing ranks card by card.",
                    "**Betting:** place an Ante, plus optional Flush / Straight Flush / Jackpot "
                    "side bets. You and the dealer are each dealt 7 cards face down.",
                    "**Your turn:** arrange your cards (Sort/Auto Place are purely visual -- "
                    "your real payout always uses your true best flush, whatever you place), "
                    "then Fold (forfeit the Ante) or Raise -- normally 1x the Ante, or up to 2x "
                    "with a 5-flush, up to 3x with a 6- or 7-flush.",
                    "**Dealer qualifies** with a 3-card, 9-high flush or better (any 4+ card "
                    "flush always qualifies too).",
                    "**Dealer doesn't qualify:** Ante pays 1:1, Raise pushes.",
                    "**Dealer qualifies:** win pays both 1:1; lose loses both; tie pushes both.",
                ]),
                ("SIDE BETS", [
                    "**Flush:** your own best flush, paid on its own paytable regardless of "
                    "the Ante's outcome or a fold -- see the panel alongside the table.",
                    "**Straight Flush:** your longest consecutive-rank same-suit run (Ace high "
                    "or low) -- independent too, see its own paytable.",
                    "**Jackpot:** flat £1, shares the same progressive pool as every other "
                    "table -- pays only on a genuine Straight Flush, see the jackpot panel for "
                    "its own paytable.",
                ]),
            ],
        )

    def _draw_spot_circle(self, key, cx, cy, r, label):
        tag = f"spot_{key}"
        amount = self.bets[key]
        felt_theme = self.app.settings.theme()
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=felt_theme["felt_dark"],
                                 outline=felt_theme["accent"], width=2, tags=(tag,))
        self.canvas.create_text(cx, cy - r - 12, text=label, fill=theme.FG,
                                 font=theme.font(9, weight="bold"), tags=(tag,))
        if amount:
            draw_chip_stack(self.canvas, tag, cx, cy, amount, max_r=CHIP_LAYER_MAX_R * 0.65)
        else:
            self.canvas.create_text(cx, cy, text="tap to\nbet", fill=theme.FG_DIM,
                                     font=theme.font(8, weight="bold"), justify="center", tags=(tag,))
        self._bind_spot(tag, key)

    def _draw_spot_jackpot(self, cx, cy, r):
        tag = "spot_jackpot"
        felt_theme = self.app.settings.theme()
        placed = bool(self.bets["jackpot"])
        if placed:
            t = 0.5 + 0.5 * math.sin(self._jackpot_pulse_t)
            outline_color = theme.lerp_color(felt_theme["felt_dark"], felt_theme["accent"], t)
        else:
            outline_color = felt_theme["accent"]
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=felt_theme["felt_dark"],
                                 outline=outline_color, width=3, tags=(tag,))
        self.canvas.create_text(cx, cy - r - 12, text="JACKPOT", fill=theme.FG,
                                 font=theme.font(9, weight="bold"), tags=(tag,))
        if placed:
            draw_chip_stack(self.canvas, tag, cx, cy, self.bets["jackpot"], max_r=CHIP_LAYER_MAX_R * 0.6)
        else:
            self.canvas.create_text(cx, cy, text="tap to\nbet £1", fill=theme.FG_DIM,
                                     font=theme.font(7, weight="bold"), justify="center", tags=(tag,))
        self._bind_spot(tag, "jackpot")

    def _bind_spot(self, tag, key):
        self.canvas.tag_bind(tag, "<Button-1>", lambda e, k=key: self._on_place_chip(k))
        self.canvas.tag_bind(tag, "<Enter>", lambda e: self.canvas.configure(cursor="hand2"))
        self.canvas.tag_bind(tag, "<Leave>", lambda e: self.canvas.configure(cursor=""))

    # ------------------------------------------------------------------ jackpot meter / glow
    def _on_jackpot_changed(self, raw_amount):
        self.jackpot_display.set_value(raw_amount)

    def _pulse_jackpot(self):
        if self.state == "betting" and self.bets.get("jackpot"):
            self._jackpot_pulse_t += 0.06
            self._draw_table()
        self.after(33, self._pulse_jackpot)

    # ------------------------------------------------------------------ state transitions
    def _show_payout_panel(self):
        # Floats in the canvas's own empty right-hand gap, between Dealer's
        # mats and the canvas's own right edge -- not a bottom-left corner
        # overlay any more, which used to clip into the 7-card felt below.
        self.payout_canvas.place(x=PAYOUT_PANEL_X, y=PAYOUT_PANEL_Y, anchor="nw")

    def _hide_payout_panel(self):
        self.payout_canvas.place_forget()

    def _show_betting_controls(self):
        for w in self.action_frame.pack_slaves():
            w.pack_forget()
        self.deal_btn.pack()
        self.action_frame.pack(pady=BETTING_ACTION_FRAME_PADY)
        self._hide_payout_panel()
        self.fan_canvas.pack_forget()
        self.chip_frame.pack(pady=CHIP_FRAME_PADY)
        self._draw_table()
        self._update_total()

    def _show_arranging_controls(self):
        self.chip_frame.pack_forget()
        self._hide_payout_panel()
        for w in self.action_frame.pack_slaves():
            w.pack_forget()
        self.action_frame.pack(pady=(4, 0))
        self.sort_btn.pack(side="left", padx=4)
        self.fold_btn.pack(side="left", padx=4)
        self.auto_place_btn.pack(side="left", padx=4)
        self.confirm_btn.pack(side="left", padx=4)
        self._refresh_confirm_state()

    def _show_raising_controls(self):
        # No Fold here -- Confirm already committed the player to playing
        # this hand; Fold only ever appears earlier, in the arranging
        # stage. Only reached at all when there's a genuine choice of
        # amount (max_raise_multiplier > 1) -- see _on_confirm, which
        # places a flat 1x Raise and skips straight to the dealer's reveal
        # otherwise.
        self.chip_frame.pack_forget()
        self._hide_payout_panel()
        for w in self.action_frame.pack_slaves():
            w.pack_forget()
        self.action_frame.pack(pady=(4, 0))
        assert self.result is not None
        allowed = max_raise_multiplier(self.result.player_flush_count)
        self.raise1_btn.pack(side="left", padx=4)
        self._style_raise_btn(self.raise1_btn, self._raise_bet_enabled(1))
        if allowed >= 2:
            self.raise2_btn.pack(side="left", padx=4)
            self._style_raise_btn(self.raise2_btn, self._raise_bet_enabled(2))
        if allowed >= 3:
            self.raise3_btn.pack(side="left", padx=4)
            self._style_raise_btn(self.raise3_btn, self._raise_bet_enabled(3))

    def _raise_bet_enabled(self, multiplier):
        assert self.result is not None
        return self.app.finance.balance + 1e-9 >= self.result.ante_bet * multiplier

    def _style_raise_btn(self, btn, enabled=True):
        if enabled:
            btn.configure(state="normal", bg=theme.ACCENT_DIM_BG, fg=theme.FG,
                          highlightbackground=theme.ACCENT)
        else:
            btn.configure(state="disabled", bg=theme.GREY_BTN_BG, fg=theme.GREY_BTN_TEXT,
                          highlightbackground=theme.GREY_BTN_BORDER)

    def _show_round_over_controls(self):
        self.chip_frame.pack_forget()
        for w in self.action_frame.pack_slaves():
            w.pack_forget()
        self.action_frame.pack(pady=(4, 0))
        self.new_deal_btn.pack(side="left", padx=8)
        self.change_bets_btn.pack(side="left", padx=8)

    def _show_no_controls(self):
        self.chip_frame.pack_forget()
        self._hide_payout_panel()
        for w in self.action_frame.pack_slaves():
            w.pack_forget()
        self.action_frame.pack(pady=(4, 0))

    # ------------------------------------------------------------------ betting
    def _on_place_chip(self, key):
        if self.state != "betting":
            return
        if key == "jackpot":
            self._toggle_jackpot_bet()
        else:
            self._adjust_bet(key, self.selected_chip)

    def _toggle_jackpot_bet(self):
        trial_bets = dict(self.bets)
        trial_bets["jackpot"] = 0 if self.bets["jackpot"] else int(hcf_logic.JACKPOT_BET_AMOUNT)
        if trial_bets["jackpot"] and _max_deal_cost(trial_bets) > self.app.finance.balance + 1e-9:
            dialogs.info(self, "$ jackpot --check-funds",
                         "You don't have enough balance to place the £1 Jackpot bet.", accent=theme.WARN)
            return
        self.bets = trial_bets
        self._draw_table()
        self._update_total()
        self._persist_state()

    def _adjust_bet(self, key, delta):
        trial_bets = dict(self.bets)
        trial_bets[key] += delta
        if _max_deal_cost(trial_bets) > self.app.finance.balance + 1e-9:
            dialogs.info(self, "$ bet --check-funds", "You don't have enough balance to place that chip.",
                         accent=theme.WARN)
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
        if _max_deal_cost(self.bets) > self.app.finance.balance:
            self.bets = {"ante": 0, "flush": 0, "straight_flush": 0, "jackpot": 0}
            if persist:
                self._persist_state()

    # ------------------------------------------------------------------ round flow
    def _on_deal(self):
        ante, flush, sflush, jackpot = (
            self.bets["ante"], self.bets["flush"], self.bets["straight_flush"], self.bets["jackpot"]
        )
        if ante <= 0:
            dialogs.info(self, "$ deal --require-bet", "You must place an Ante bet to deal.", accent=theme.WARN)
            return
        if not self.app.finance.can_afford(_max_deal_cost(self.bets)):
            choice = dialogs.choice(
                self, "$ deal --check-funds", "You don't have enough balance to cover these bets.",
                [("Go Home", "home"), ("Cashier", "cashier")],
            )
            if choice == "home":
                self.app.show_frame("menu")
            elif choice == "cashier":
                self.app.show_frame("finances")
            return

        total_upfront = ante + flush + sflush + jackpot
        self.app.finance.place_wager(total_upfront)
        self._refresh_balance()

        self.result = self.game.deal(ante, flush_bet=flush, straight_flush_bet=sflush, jackpot_bet=jackpot)
        self.state = "playing"
        self.stage = "arranging"
        self.card_zone = {i: "felt" for i in range(7)}
        self.flush_order = []
        self.felt_slot_order = list(range(7))
        self._dealer_revealed = False

        self.result_lbl.configure(text="Dealing...", fg=theme.FG)
        self._show_no_controls()

        self.fan_canvas.delete("all")
        self.fan_canvas.pack(pady=(10, 0), before=self.chip_zone)
        self._draw_fan_mat()

        self._draw_play_zones()
        self._deal_in()

    # ------------------------------------------------------------------ card-view rendering
    def _draw_zone_backgrounds(self):
        """Static mats/labels only (tag "zone_bg") -- split out so a live
        theme switch mid-round can refresh colours without wiping any
        already-dealt/already-placed card."""
        felt_theme = self.app.settings.theme()
        theme.rounded_rect(self.canvas, DEALER_MAT_X1, DEALT_MAT_TOP, DEALER_MAT_X2, DEALT_MAT_BOTTOM,
                            radius=DEALT_MAT_RADIUS, fill=felt_theme["felt_dark"], outline=felt_theme["accent"],
                            width=2, tags=("zone_bg",))
        self.canvas.create_text(CANVAS_WIDTH / 2, DEALT_LABEL_Y, text="DEALER'S HAND", fill=theme.ACCENT,
                                 font=theme.font(8, weight="bold"), tags=("zone_bg",))

        theme.rounded_rect(self.canvas, DEALER_MAT_X1, PLACED_MAT_TOP, DEALER_MAT_X2, PLACED_MAT_BOTTOM,
                            radius=DEALT_MAT_RADIUS, fill=felt_theme["felt_dark"], outline=theme.FG_DIM,
                            width=2, tags=("zone_bg",))
        self.canvas.create_text(CANVAS_WIDTH / 2, PLACED_LABEL_Y, text="DEALER'S FLUSH", fill=theme.FG_DIM,
                                 font=theme.font(8, weight="bold"), tags=("zone_bg",))

        theme.rounded_rect(self.canvas, DECK_ZONE_X1, DECK_ZONE_TOP, DECK_ZONE_X2, DECK_ZONE_BOTTOM, radius=12,
                            fill=felt_theme["felt_dark"], outline=theme.FG_DIM, width=1, tags=("zone_bg",))
        self.canvas.create_text(DECK_ZONE_CX, DECK_LABEL_Y, text="DECK", fill=theme.FG_DIM,
                                 font=theme.font(9, weight="bold"), tags=("zone_bg",))

        active = self.stage == "arranging" and self.state == "playing"
        theme.rounded_rect(self.canvas, ZONE_X1, ZONE_TOP, ZONE_X2, ZONE_BOTTOM, radius=12,
                            fill=felt_theme["felt_dark"], outline=theme.ACCENT if active else theme.FG_DIM,
                            width=3 if active else 1, tags=("zone_bg",))
        self.canvas.create_text(ZONE_CX, ZONE_TOP + ZONE_LABEL_Y_OFFSET, text="YOUR FLUSH",
                                 fill=theme.ACCENT if active else theme.FG_DIM,
                                 font=theme.font(10, weight="bold"), tags=("zone_bg",))

    def _draw_play_zones(self):
        assert self.result is not None
        self.canvas.delete("all")
        self._draw_zone_backgrounds()
        draw_card_back(self.canvas, DECK_X1, DECK_Y, self._current_felt, self.app.settings.theme()["accent"],
                        tags=("zone_bg",))

        if self.bets["jackpot"]:
            self._draw_strip_circle("jackpot", JACKPOT_CX, JACKPOT_CY, JACKPOT_R, "JACKPOT", self.bets["jackpot"])
        if self.bets["flush"]:
            self._draw_strip_circle("flush", FLUSH_CX, MID_CY, FLUSH_R, "FLUSH", self.bets["flush"])
        if self.bets["straight_flush"]:
            self._draw_strip_circle("straight_flush", STRAIGHT_FLUSH_CX, MID_CY, STRAIGHT_FLUSH_R,
                                     "STR8 FLUSH", self.bets["straight_flush"])
        self._draw_strip_circle("ante", ANTE_CX, ANTE_CY, ANTE_R, "ANTE", self.result.ante_bet)
        if self.result.raise_bet:
            self._draw_strip_circle("raise", RAISE_CX, ANTE_CY, RAISE_R, "RAISE", self.result.raise_bet)

        # The felt and flush zone deliberately start empty here -- _deal_in
        # is about to deal every card into the felt itself, one at a time;
        # pre-drawing them now would just mean immediately covering them
        # back up with the deal-in animation's own (redundant) first frame.

    def _draw_strip_circle(self, key, cx, cy, r, label, amount):
        tag = f"strip_{key}"
        self.canvas.delete(tag)
        felt_theme = self.app.settings.theme()
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=felt_theme["felt_dark"],
                                 outline=felt_theme["accent"], width=2, tags=(tag,))
        self.canvas.create_text(cx, cy - r - 10, text=label, fill=theme.FG,
                                 font=theme.font(8, weight="bold"), tags=(tag,))
        draw_chip_stack(self.canvas, (tag, f"{tag}_chips"), cx, cy, amount, max_r=ROW_CHIP_MAX_R)

    def _draw_player_card_at(self, i, card, x, y, face_up=True, width=CARD_WIDTH, height=CARD_HEIGHT):
        tag = f"player_card_{i}"
        self.fan_canvas.delete(tag)
        if face_up:
            draw_card(self.fan_canvas, x, y, card, width=width, height=height, tags=(tag,))
        else:
            draw_card_back(self.fan_canvas, x, y, self._current_felt, self.app.settings.theme()["accent"],
                            width=width, height=height, tags=(tag,))

    def _draw_fan_mat(self):
        felt_theme = self.app.settings.theme()
        theme.rounded_rect(
            self.fan_canvas, FAN_MAT_X1, FAN_MAT_TOP, FAN_MAT_X2, FAN_MAT_BOTTOM, radius=FAN_MAT_RADIUS,
            fill=felt_theme["felt_dark"], outline=FAN_MAT_BORDER, width=2, tags=("fan_mat_bg",),
        )
        self.fan_canvas.create_text(FAN_CANVAS_WIDTH / 2, FAN_Y - 4, text="", tags=("fan_mat_bg",))

    def _redraw_felt(self):
        assert self.result is not None
        for i, card in enumerate(self.result.player_cards):
            tag = f"player_card_{i}"
            self.fan_canvas.delete(tag)
            self.fan_canvas.delete(f"hit_{i}")
            if self.card_zone.get(i) != "felt":
                continue
            pos = self.felt_slot_order.index(i) if i in self.felt_slot_order else i
            x = _felt_card_x(pos)
            draw_card(self.fan_canvas, x, FAN_Y, card, tags=(tag, f"cardidx_{i}"))
            self.fan_canvas.tag_bind(tag, "<Button-1>", lambda e, idx=i: self._on_felt_card_click(idx))
            self.fan_canvas.tag_bind(
                tag, "<Enter>",
                lambda e, idx=i, xx=x: self._on_card_hover(self.fan_canvas, idx, xx, FAN_Y, CARD_WIDTH, CARD_HEIGHT)
            )
            self.fan_canvas.tag_bind(tag, "<Leave>", lambda e: self._on_card_unhover())

    def _redraw_flush_zone(self):
        assert self.result is not None
        cards = self.result.player_cards
        # Clear every possible card's own tag first, not just the ones
        # still in flush_order -- a card just removed from the zone (see
        # _on_zone_card_click) isn't in that list any more, so the loop
        # below would never touch its old item, leaving a stale copy
        # behind in the zone even after it's moved back to the felt.
        for i in range(7):
            self.canvas.delete(f"flushcard_{i}")
            self.canvas.delete(f"hit_{i}")
        n = len(self.flush_order)
        fan_w = (n - 1) * ZONE_CARD_OVERLAP + CARD_WIDTH if n else 0
        start_x = ZONE_CX - fan_w / 2
        for pos, idx in enumerate(self.flush_order):
            tag = f"flushcard_{idx}"
            x = start_x + pos * ZONE_CARD_OVERLAP
            draw_card(self.canvas, x, ZONE_ROW_Y, cards[idx], tags=(tag, f"cardidx_{idx}"))
            exposed_w = ZONE_CARD_OVERLAP if pos < n - 1 else CARD_WIDTH
            self._bind_zone_card_hit(idx, x, ZONE_ROW_Y, exposed_w, CARD_HEIGHT)

    def _bind_zone_card_hit(self, idx, x, y, exposed_w, exposed_h):
        hit_tag = f"hit_{idx}"
        self.canvas.delete(hit_tag)
        self.canvas.create_rectangle(x, y, x + exposed_w, y + exposed_h, fill="", outline="", tags=(hit_tag,))
        self.canvas.tag_bind(hit_tag, "<Button-1>", lambda e, i=idx: self._on_zone_card_click(i))
        self.canvas.tag_bind(
            hit_tag, "<Enter>",
            lambda e, i=idx, xx=x, yy=y: self._on_card_hover(self.canvas, i, xx, yy, CARD_WIDTH, CARD_HEIGHT)
        )
        self.canvas.tag_bind(hit_tag, "<Leave>", lambda e: self._on_card_unhover())

    def _on_card_hover(self, canvas, idx, x, y, w, h):
        # `canvas` is the one the triggering binding actually lives on --
        # NOT re-derived from self.card_zone[idx]'s current value, which
        # can have moved on since the binding was set up (a redeal resets
        # it, a click moves a card between zones): using a stale lookup
        # here previously caused tag_lower to hunt for "cardidx_N" on the
        # wrong canvas and raise a TclError.
        if self._hover_tag:
            self.canvas.delete(self._hover_tag)
            self.fan_canvas.delete(self._hover_tag)
        if not canvas.find_withtag(f"cardidx_{idx}"):
            # Tk queues <Enter> events -- this one was already in flight
            # when a click (this card being moved to/from the flush zone,
            # a Sort, an Auto Place, ...) redrew the felt/zone and deleted
            # the very card it was queued for. Nothing left to highlight.
            return
        tag = "hover_highlight"
        canvas.create_rectangle(x - 3, y - 3, x + w + 3, y + h + 3, outline=theme.ACCENT, width=2, tags=(tag,))
        canvas.tag_lower(tag, f"cardidx_{idx}")
        self._hover_tag = tag
        canvas.configure(cursor="hand2")

    def _on_card_unhover(self):
        if self._hover_tag:
            self.canvas.delete(self._hover_tag)
            self.fan_canvas.delete(self._hover_tag)
            self._hover_tag = None
        self.canvas.configure(cursor="")
        self.fan_canvas.configure(cursor="")

    # ------------------------------------------------------------------ animation engine
    def _animate(self, duration_ms, on_frame, on_done=None):
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
        if self.app.settings.get("animations_enabled"):
            for i in range(count):
                self.after(i * stagger_ms, fn, i)
        else:
            for i in range(count):
                fn(i)

    def _run_sequential(self, fns, on_done=None):
        def step(i):
            if i >= len(fns):
                if on_done:
                    on_done()
                return
            fns[i](lambda: step(i + 1))
        step(0)

    def _after_delay(self, ms, fn):
        if self.app.settings.get("animations_enabled"):
            self.after(ms, fn)
        else:
            fn()

    def _animate_flip(self, canvas, tag, cx_slot, y, card, reveal, duration, width=CARD_WIDTH, height=CARD_HEIGHT,
                       on_done=None):
        def frame(t):
            squeeze = abs(1 - 2 * t)
            w = max(6, width * squeeze)
            x = cx_slot - w / 2
            canvas.delete(tag)
            face_up_now = reveal if t >= 0.5 else not reveal
            if squeeze > 0.35:
                if face_up_now:
                    draw_card(canvas, x, y, card, width=w, height=height, tags=(tag,))
                else:
                    draw_card_back(canvas, x, y, self._current_felt, self.app.settings.theme()["accent"],
                                    width=w, height=height, tags=(tag,))
            else:
                canvas.create_rectangle(x, y, x + w, y + height, fill="#fdfdf5", outline="#222222", tags=(tag,))

        self._animate(duration, frame, on_done=on_done)

    # ------------------------------------------------------------------ deal-in
    def _deal_in(self):
        """Deals every card in one interleaved player/dealer pass -- the
        player's own cards drop straight in FACE UP, one at a time (there's
        no hidden information on the player's own side of the table to
        protect), while the dealer's stay face down until their own later
        reveal."""
        assert self.result is not None
        order = []
        for i in range(7):
            order.append(("player", i))
            order.append(("dealer", i))
        is_last_slot = len(order) - 1

        def deal_one(slot):
            kind, i = order[slot]
            on_done = self._on_deal_complete if slot == is_last_slot else None
            if kind == "player":
                tx, ty = _felt_card_x(i), FAN_Y
                sx, sy = tx, ty - 90

                def frame(t, i=i, sx=sx, sy=sy, tx=tx, ty=ty):
                    self._draw_player_card_at(i, self.result.player_cards[i],
                                               sx + (tx - sx) * t, sy + (ty - sy) * t, face_up=True)

                self._animate(DEAL_IN_DROP_MS, frame, on_done=on_done)
            else:
                tx, ty = _dealer_cluster_x(i), DEALT_Y
                sx, sy = tx, ty - 60

                def frame(t, i=i, sx=sx, sy=sy, tx=tx, ty=ty):
                    self.canvas.delete(f"dealer_card_{i}")
                    x = sx + (tx - sx) * t
                    y = sy + (ty - sy) * t
                    felt_theme = self.app.settings.theme()
                    draw_card_back(self.canvas, x, y, felt_theme["felt"], felt_theme["accent"],
                                    width=DEALER_CARD_W, height=DEALER_CARD_H, tags=(f"dealer_card_{i}",))

                self._animate(DEAL_IN_DROP_MS, frame, on_done=on_done)

        self._run_staggered(len(order), DEAL_IN_STAGGER_MS, deal_one)

    def _on_deal_complete(self):
        # The deal-in animation's own drawing calls (_draw_player_card_at/
        # _animate_flip) never bind hover/click -- only _redraw_felt does
        # that -- so the felt needs one real redraw here to make the now-
        # settled cards actually interactive. Purely a rebind: the cards
        # are already face up in their final positions, this doesn't move
        # or change anything visually.
        self._redraw_felt()
        self.result_lbl.configure(text="Arrange your flush, then Fold or Confirm.", fg=theme.FG)
        self._show_arranging_controls()

    # ------------------------------------------------------------------ card placement
    def _play_area_confirmable(self):
        if len(self.flush_order) < 2:
            return False
        assert self.result is not None
        suits = {self.result.player_cards[i].suit for i in self.flush_order}
        return len(suits) == 1

    def _refresh_confirm_state(self):
        if self._play_area_confirmable():
            self.confirm_btn.configure(state="normal", bg=theme.ACCENT_DIM_BG, fg=theme.FG,
                                        highlightbackground=theme.ACCENT)
        else:
            self.confirm_btn.configure(state="disabled", bg=theme.GREY_BTN_BG, fg=theme.GREY_BTN_TEXT,
                                        highlightbackground=theme.GREY_BTN_BORDER)

    def _on_felt_card_click(self, idx):
        if self.state != "playing" or self.stage != "arranging" or self._setting_locked:
            return
        self.card_zone[idx] = "flush"
        self.flush_order.append(idx)
        self._on_card_unhover()
        self._redraw_felt()
        self._redraw_flush_zone()
        self._refresh_confirm_state()

    def _on_zone_card_click(self, idx):
        if self.state != "playing" or self.stage != "arranging" or self._setting_locked:
            return
        if idx in self.flush_order:
            self.flush_order.remove(idx)
        self.card_zone[idx] = "felt"
        self._on_card_unhover()
        self._redraw_felt()
        self._redraw_flush_zone()
        self._refresh_confirm_state()

    def _flip_and_fly_away(self, felt_indices, zone_indices, flip_duration, on_done):
        """Turns the given cards face down and flies them off screen to
        the right -- felt_indices from the fan_canvas felt, zone_indices
        from the flush zone on self.canvas (either list may be empty).
        Used both for the leftover felt cards once Confirm locks in the
        flush zone (see _on_confirm) and for the player's whole hand on a
        real Fold (see _on_fold, which passes a much shorter
        flip_duration -- "turned over rapidly", per spec)."""
        assert self.result is not None
        cards = self.result.player_cards
        total = len(felt_indices) + len(zone_indices)
        if total == 0:
            on_done()
            return
        remaining = [total]

        def one_done():
            remaining[0] -= 1
            if remaining[0] <= 0:
                on_done()

        def fly_felt(pos_in_list):
            idx = felt_indices[pos_in_list]
            slot = self.felt_slot_order.index(idx) if idx in self.felt_slot_order else idx
            x = _felt_card_x(slot)
            cx_slot = x + CARD_WIDTH / 2

            def after_flip():
                def frame(t, x=x):
                    tx, ty = FOLD_FLY_TARGET
                    self._draw_player_card_at(idx, None, x + (tx - x) * t, FAN_Y + (ty - FAN_Y) * t, face_up=False)
                self._animate(FOLD_FLY_MS, frame, on_done=one_done)

            self._animate_flip(self.fan_canvas, f"player_card_{idx}", cx_slot, FAN_Y, cards[idx],
                                reveal=False, duration=flip_duration, on_done=after_flip)

        def fly_zone(pos_in_list):
            idx = zone_indices[pos_in_list]
            n = len(zone_indices)
            fan_w = (n - 1) * ZONE_CARD_OVERLAP + CARD_WIDTH if n > 1 else CARD_WIDTH
            start_x = ZONE_CX - fan_w / 2
            x = start_x + pos_in_list * ZONE_CARD_OVERLAP
            cx_slot = x + CARD_WIDTH / 2

            def after_flip():
                def frame(t, x=x):
                    tx, ty = CANVAS_WIDTH + 90, ZONE_ROW_Y - 60
                    tag = f"flushcard_{idx}"
                    self.canvas.delete(tag)
                    draw_card_back(self.canvas, x + (tx - x) * t, ZONE_ROW_Y + (ty - ZONE_ROW_Y) * t,
                                    self._current_felt, self.app.settings.theme()["accent"], tags=(tag,))
                self._animate(FOLD_FLY_MS, frame, on_done=one_done)

            self._animate_flip(self.canvas, f"flushcard_{idx}", cx_slot, ZONE_ROW_Y, cards[idx], reveal=False,
                                duration=flip_duration, on_done=after_flip)

        self._run_staggered(len(felt_indices), FOLD_FLY_STAGGER_MS, fly_felt)
        self._run_staggered(len(zone_indices), FOLD_FLY_STAGGER_MS, fly_zone)

    def _lock_setting_buttons(self):
        self._setting_locked = True
        for btn in (self.sort_btn, self.auto_place_btn, self.confirm_btn):
            btn.configure(state="disabled")

    def _unlock_setting_buttons(self):
        self._setting_locked = False
        self.sort_btn.configure(state="normal")
        self.auto_place_btn.configure(state="normal")
        self._refresh_confirm_state()

    def _on_sort(self):
        if self.state != "playing" or self.stage != "arranging" or self._setting_locked:
            return
        assert self.result is not None
        felt_indices = [i for i in range(7) if self.card_zone[i] == "felt"]
        if len(felt_indices) < 2:
            return
        cards = self.result.player_cards
        new_order = sorted(felt_indices, key=lambda i: _sort_key(cards[i]))
        old_order = list(self.felt_slot_order)
        self._lock_setting_buttons()

        def frame(t):
            for slot, idx in enumerate(new_order):
                old_slot = old_order.index(idx)
                x0 = _felt_card_x(old_slot)
                x1 = _felt_card_x(slot)
                x = x0 + (x1 - x0) * t
                tag = f"player_card_{idx}"
                self.fan_canvas.delete(tag)
                draw_card(self.fan_canvas, x, FAN_Y, cards[idx], tags=(tag,))

        def done():
            # Rebuild felt_slot_order: cards already moved to the flush
            # zone keep their old slot positions untouched, only the
            # still-on-felt cards' own slots get reordered.
            placed_positions = sorted(old_order.index(i) for i in felt_indices)
            rebuilt = list(old_order)
            for pos, idx in zip(placed_positions, new_order):
                rebuilt[pos] = idx
            self.felt_slot_order = rebuilt
            self._unlock_setting_buttons()
            self._redraw_felt()

        self._animate(SORT_MOVE_MS, frame, on_done=done)

    def _on_auto_place(self):
        if self.state != "playing" or self.stage != "arranging" or self._setting_locked:
            return
        assert self.result is not None
        cards = self.result.player_cards
        best_cards = auto_place(cards)
        best_indices = [i for i, c in enumerate(cards) if c in best_cards]

        self.flush_order = []
        self.card_zone = {i: "felt" for i in range(7)}
        self._redraw_felt()
        self._redraw_flush_zone()
        self._lock_setting_buttons()

        def place_next(remaining):
            if not remaining:
                self._unlock_setting_buttons()
                self._refresh_confirm_state()
                return
            idx = remaining[0]
            self.card_zone[idx] = "flush"
            self.flush_order.append(idx)
            self._redraw_felt()
            self._redraw_flush_zone()
            self._after_delay(AUTO_PLACE_STEP_MS, lambda: place_next(remaining[1:]))

        self._after_delay(AUTO_PLACE_STEP_MS, lambda: place_next(best_indices))

    def _on_confirm(self):
        """Confirm means "I'm happy with this hand, place the bet" -- not
        a separate step before betting. If there's only one legal Raise
        amount (max_raise_multiplier == 1), Confirm places it outright and
        heads straight into the dealer's reveal, with no button stage in
        between. A stronger hand (5+/6+/7-card flush) still gets an actual
        choice of amount afterward -- but Fold is never offered again once
        Confirm's been clicked; that decision was already made."""
        if not self._play_area_confirmable():
            return
        self._show_no_controls()
        leftover = [i for i in range(7) if self.card_zone.get(i) == "felt"]

        def after_discard():
            assert self.result is not None
            allowed = max_raise_multiplier(self.result.player_flush_count)
            if allowed == 1:
                if not self._raise_bet_enabled(1):
                    choice = dialogs.choice(
                        self, "$ raise --check-funds",
                        "You don't have enough balance to cover the Raise needed to continue "
                        "this hand.",
                        [("Go Home", "home"), ("Cashier", "cashier")],
                    )
                    if choice == "home":
                        self.app.show_frame("menu")
                    elif choice == "cashier":
                        self.app.show_frame("finances")
                    return
                self.game.raise_bet(1)
                self.app.finance.place_wager(self.result.raise_bet)
                self._refresh_balance()
                self._draw_strip_circle("raise", RAISE_CX, ANTE_CY, RAISE_R, "RAISE", self.result.raise_bet)
                self.result_lbl.configure(text="Dealer's turn.", fg=theme.FG)
                self._reveal_dealer_and_settle()
            else:
                self.stage = "raising"
                self.result_lbl.configure(text="Choose your Raise.", fg=theme.FG)
                self._show_raising_controls()

        # The cards not placed in the flush zone play no further part in
        # the round -- folded away here rather than just left sitting on
        # the felt for the rest of it.
        self._flip_and_fly_away(leftover, [], DISCARD_FLIP_MS, after_discard)

    def _on_fold(self):
        if self.state != "playing":
            return
        assert self.result is not None
        self.game.fold()
        self._show_no_controls()
        felt_indices = [i for i in range(7) if self.card_zone.get(i) == "felt"]
        zone_indices = list(self.flush_order)

        def after_fold_away():
            self._draw_zone_backgrounds_refresh()
            self._reveal_dealer_and_settle()

        self._flip_and_fly_away(felt_indices, zone_indices, FOLD_FLIP_MS, after_fold_away)

    def _on_raise(self, multiplier):
        if self.state != "playing" or self.stage != "raising":
            return
        assert self.result is not None
        if not self._raise_bet_enabled(multiplier):
            return
        try:
            self.game.raise_bet(multiplier)
        except ValueError:
            return
        self.app.finance.place_wager(self.result.raise_bet)
        self._refresh_balance()
        self._show_no_controls()
        self._draw_strip_circle("raise", RAISE_CX, ANTE_CY, RAISE_R, "RAISE", self.result.raise_bet)
        self._reveal_dealer_and_settle()

    def _draw_zone_backgrounds_refresh(self):
        self.canvas.delete("zone_bg")
        self._draw_zone_backgrounds()
        self.canvas.tag_lower("zone_bg")

    # ------------------------------------------------------------------ dealer reveal / settle
    def _reveal_dealer_and_settle(self):
        assert self.result is not None
        result = self.result

        def flip_one(i):
            x = _dealer_cluster_x(i)
            cx_slot = x + DEALER_CARD_W / 2
            self._animate_flip(
                self.canvas, f"dealer_card_{i}", cx_slot, DEALT_Y, result.dealer_cards[i], reveal=True,
                duration=REVEAL_FLIP_MS, width=DEALER_CARD_W, height=DEALER_CARD_H,
                on_done=(self._settle_round if i == 6 else None),
            )

        self._run_staggered(7, REVEAL_STAGGER_MS, flip_one)

    def _settle_round(self):
        assert self.result is not None
        result = self.game.settle(jackpot_amount=self.app.jackpot.amount)
        self._dealer_revealed = True
        self._move_dealer_flush_to_placed()

        for key, bet, ret in self._resolved_bet_totals(result):
            self.app.game_stats.record_bet(GAME_KEY, key, bet, ret)
        self.app.game_stats.record_round_net(GAME_KEY, result.net_result)
        self.app.game_stats.record_hand(GAME_KEY, hand_outcome_label(result))
        if result.jackpot_won:
            self.app.jackpot.win()
        elif result.jackpot_pool_partial_fraction:
            self.app.jackpot.set_amount(self.app.jackpot.amount * (1 - result.jackpot_pool_partial_fraction))
        self.app.finance.record_round_played(result.net_result)

        payout_items = self._payout_chip_items(result)
        credit = sum(it["ret"] for it in payout_items)
        if credit > 0:
            self.app.finance.add_return(credit)

        self._after_delay(300, lambda: self._animate_payouts(payout_items, lambda: self._on_round_settled(result)))

    def _move_dealer_flush_to_placed(self):
        """Slides the dealer's own flush-suit cards down out of DEALER'S
        HAND into DEALER'S FLUSH -- removed from the former, not just
        duplicated into the latter, mirroring the player's own flush zone
        (only the cards actually forming the flush ever leave the dealt
        hand). The dealer's other, non-flush cards stay in DEALER'S HAND
        (their full 7-card hand stays visible for comparison), but slide
        together to fill the gap the departing cards leave behind, rather
        than sitting frozen in their original, now-uneven 7-card spacing."""
        assert self.result is not None
        result = self.result
        flush_indices = [i for i, c in enumerate(result.dealer_cards) if c in result.dealer_flush_cards]
        nonflush_indices = [i for i in range(7) if i not in flush_indices]
        n = len(flush_indices)
        if n == 0:
            return
        fan_w = (n - 1) * DEALER_CARD_OVERLAP + DEALER_CARD_W if n > 1 else DEALER_CARD_W
        start_x = CANVAS_WIDTH / 2 - fan_w / 2

        def move_one(pos):
            idx = flush_indices[pos]
            sx, sy = _dealer_cluster_x(idx), DEALT_Y
            tx, ty = start_x + pos * DEALER_CARD_OVERLAP, PLACED_Y
            self.canvas.delete(f"dealer_card_{idx}")

            def frame(t, idx=idx, sx=sx, sy=sy, tx=tx, ty=ty):
                self.canvas.delete(f"dealer_placed_{idx}")
                x, y = sx + (tx - sx) * t, sy + (ty - sy) * t
                draw_card(self.canvas, x, y, result.dealer_cards[idx], width=DEALER_CARD_W, height=DEALER_CARD_H,
                          tags=(f"dealer_placed_{idx}", "dealer_placed"))

            self._animate(SEPARATE_MOVE_MS, frame)

        def close_gap(new_pos):
            idx = nonflush_indices[new_pos]
            sx = _dealer_cluster_x(idx)
            tx = _dealer_cluster_x(new_pos, n=len(nonflush_indices))
            if sx == tx:
                return

            def frame(t, idx=idx, sx=sx, tx=tx):
                self.canvas.delete(f"dealer_card_{idx}")
                x = sx + (tx - sx) * t
                draw_card(self.canvas, x, DEALT_Y, result.dealer_cards[idx], width=DEALER_CARD_W,
                          height=DEALER_CARD_H, tags=(f"dealer_card_{idx}",))

            self._animate(SEPARATE_MOVE_MS, frame)

        for new_pos in range(len(nonflush_indices)):
            close_gap(new_pos)

        self._run_staggered(n, 60, move_one)

    def _resolved_bet_totals(self, result):
        totals = []
        if result.ante_bet:
            totals.append(("ante", result.ante_bet, result.ante_return))
        if result.raise_bet:
            totals.append(("raise", result.raise_bet, result.raise_return))
        if result.flush_bet:
            totals.append(("flush", result.flush_bet, result.flush_return))
        if result.straight_flush_bet:
            totals.append(("straight_flush", result.straight_flush_bet, result.straight_flush_return))
        if result.jackpot_bet:
            totals.append(("jackpot", result.jackpot_bet, result.jackpot_return))
        return totals

    def _payout_chip_items(self, result):
        layout = {
            "ante": (ANTE_CX, ANTE_CY, "strip_ante", ROW_CHIP_MAX_R),
            "raise": (RAISE_CX, ANTE_CY, "strip_raise", ROW_CHIP_MAX_R),
            "flush": (FLUSH_CX, MID_CY, "strip_flush", ROW_CHIP_MAX_R),
            "straight_flush": (STRAIGHT_FLUSH_CX, MID_CY, "strip_straight_flush", ROW_CHIP_MAX_R),
            "jackpot": (JACKPOT_CX, JACKPOT_CY, "strip_jackpot", ROW_CHIP_MAX_R),
        }
        items = []
        for key, bet, ret in self._resolved_bet_totals(result):
            cx, cy, spot_tag, max_r = layout[key]
            items.append(dict(key=key, bet=bet, ret=ret, cx=cx, cy=cy, spot_tag=spot_tag, max_r=max_r))
        return items

    def _chip_move_away(self, item, on_done):
        chips_tag = f"{item['spot_tag']}_chips"
        self.canvas.delete(chips_tag)
        travel_tag = f"chip_travel_{item['key']}"
        settle_cx, settle_cy = CANVAS_WIDTH / 2, (DEALT_Y + PLACED_Y) / 2

        def frame(t):
            cx = item["cx"] + (settle_cx - item["cx"]) * t
            cy = item["cy"] + (settle_cy - item["cy"]) * t
            self.canvas.delete(travel_tag)
            r = item["max_r"] * (1 - t)
            if r > 2:
                draw_chip_stack(self.canvas, travel_tag, cx, cy, item["bet"], r)

        def arrived():
            self.canvas.delete(travel_tag)
            if on_done:
                on_done()

        self._animate(PAYOUT_CHIP_MOVE_MS, frame, on_done=arrived)

    def _chip_move_in(self, item, on_done):
        win_amount = item["ret"] - item["bet"]
        travel_tag = f"chip_travel_{item['key']}"
        settle_cx, settle_cy = CANVAS_WIDTH / 2, (DEALT_Y + PLACED_Y) / 2
        to_cx, to_cy = item["cx"], item["cy"] + PAYOUT_WIN_LANDING_OFFSET_Y

        def frame(t):
            cx = settle_cx + (to_cx - settle_cx) * t
            cy = settle_cy + (to_cy - settle_cy) * t
            self.canvas.delete(travel_tag)
            if item["max_r"] * t > 2:
                draw_chip_stack(self.canvas, travel_tag, cx, cy, win_amount, item["max_r"] * t)

        self._animate(PAYOUT_CHIP_MOVE_MS, frame, on_done=on_done)

    def _animate_payouts(self, items, on_done):
        losing = [it for it in items if it["ret"] == 0]
        winning = [it for it in items if it["ret"] > it["bet"]]
        stages = (
            [lambda cb, it=it: self._chip_move_away(it, cb) for it in losing]
            + [lambda cb, it=it: self._chip_move_in(it, cb) for it in winning]
        )
        self._run_sequential(stages, on_done)

    def _sweep_remaining_chips(self, items, on_done):
        remaining = [it for it in items if it["ret"] > 0]
        if not remaining:
            if on_done:
                on_done()
            return
        target_x, target_y = CANVAS_WIDTH / 2, CANVAS_HEIGHT

        def frame(t):
            for it in remaining:
                r = it["max_r"] * (1 - t)
                base_tag = f"{it['spot_tag']}_chips"
                bcx, bcy = it["cx"], it["cy"]
                ncx, ncy = bcx + (target_x - bcx) * t, bcy + (target_y - bcy) * t
                self.canvas.delete(base_tag)
                if r > 2:
                    draw_chip_stack(self.canvas, base_tag, ncx, ncy, it["bet"], r)
                win_amount = it["ret"] - it["bet"]
                if win_amount > 0:
                    travel_tag = f"chip_travel_{it['key']}"
                    wcx, wcy = it["cx"], it["cy"] + PAYOUT_WIN_LANDING_OFFSET_Y
                    nwcx, nwcy = wcx + (target_x - wcx) * t, wcy + (target_y - wcy) * t
                    self.canvas.delete(travel_tag)
                    if r > 2:
                        draw_chip_stack(self.canvas, travel_tag, nwcx, nwcy, win_amount, r)

        def finish():
            for it in remaining:
                self.canvas.delete(f"{it['spot_tag']}_chips")
                self.canvas.delete(f"chip_travel_{it['key']}")
            if on_done:
                on_done()

        self._animate(280, frame, on_done=finish)

    def _new_deal(self):
        assert self.result is not None
        if not self.app.finance.can_afford(_max_deal_cost(self.bets)):
            self._on_deal()
            return
        self._show_no_controls()
        self._sweep_remaining_chips(self._payout_chip_items(self.result), self._on_deal)

    def _new_round(self):
        self.state = "betting"
        self.result_lbl.configure(text="Place your Ante bet to begin.", fg=theme.FG)
        self._sanitize_bets()
        self._show_betting_controls()

    def _on_round_settled(self, result):
        self._refresh_balance()
        self.app.on_balance_changed()
        self._show_result(result)
        self._show_round_over_controls()
        self.state = "resolved"

    def _show_result(self, result):
        self.result_lbl.configure(text=result.summary,
                                   fg=_net_color(result.net_result) if result.net_result else theme.FG)
        self._show_payout_panel()
        self._draw_payout_panel(result)

    def _payout_rows(self, result):
        # Short labels -- this panel is narrower than every other game's own
        # (see PAYOUT_PANEL_WIDTH), no room for a longer "(N-card)" suffix
        # on the same line as a signed £ value.
        rows = []
        if result.ante_bet:
            rows.append(("Ante", result.ante_return - result.ante_bet))
        if result.raise_bet:
            rows.append(("Raise", result.raise_return - result.raise_bet))
        if result.flush_bet:
            rows.append((f"Flush ({result.player_flush_count})", result.flush_return - result.flush_bet))
        if result.straight_flush_bet:
            rows.append((f"SF ({result.player_straight_flush_count})",
                          result.straight_flush_return - result.straight_flush_bet))
        if result.jackpot_bet:
            label = "Jackpot WON!" if result.jackpot_won else "Jackpot"
            rows.append((label, result.jackpot_return - result.jackpot_bet))
        return rows

    def _draw_payout_panel(self, result):
        canvas = self.payout_canvas
        canvas.delete("all")
        w, h = PAYOUT_PANEL_WIDTH, PAYOUT_PANEL_HEIGHT
        felt_theme = self.app.settings.theme()
        theme.recessed_panel(canvas, 0, 0, w, h, title="RESULT", title_font_size=11,
                              fill=felt_theme["felt_dark"], outline=felt_theme["accent"])
        rows = self._payout_rows(result)
        y = 30
        for label, net in rows:
            canvas.create_text(14, y, text=label, fill=theme.FG, font=theme.font(8), anchor="w")
            canvas.create_text(w - 14, y, text=_format_signed(net), fill=_net_color(net),
                                font=theme.font(8, weight="bold"), anchor="e")
            y += 14
        y += 4
        canvas.create_line(14, y, w - 14, y, fill=theme.BORDER)
        y += 13
        canvas.create_text(14, y, text="Net", fill=theme.FG, font=theme.font(9, weight="bold"), anchor="w")
        canvas.create_text(w - 14, y, text=_format_signed(result.net_result), fill=_net_color(result.net_result),
                            font=theme.font(10, weight="bold"), anchor="e")

    # ------------------------------------------------------------------ lifecycle
    def on_show(self):
        self._apply_theme()
        self._refresh_balance()
        if self.state == "betting":
            self._sanitize_bets()
            self._draw_table()
            self._update_total()

    def _apply_theme(self):
        felt_theme = self.app.settings.theme()
        new_felt = felt_theme["felt"]
        if new_felt == self._current_felt:
            return
        old_felt = self._current_felt
        self._current_felt = new_felt
        self._retheme_widget(self, old_felt, new_felt)
        if self.fan_canvas.find_withtag("fan_mat_bg"):
            self.fan_canvas.delete("fan_mat_bg")
            self._draw_fan_mat()
            self.fan_canvas.tag_lower("fan_mat_bg")
        if self.canvas.find_withtag("zone_bg"):
            self._draw_zone_backgrounds_refresh()
        self.jackpot_display.retheme(felt_theme["felt_dark"], felt_theme["accent"])
        self._draw_paytable()
        if self.state == "resolved" and self.result is not None:
            self._draw_payout_panel(self.result)

    def _retheme_widget(self, widget, old_felt, new_felt):
        try:
            if widget.cget("bg") == old_felt:
                widget.configure(bg=new_felt)
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            self._retheme_widget(child, old_felt, new_felt)

    def _refresh_balance(self):
        self.balance_lbl.configure(text=f"£{self.app.finance.balance:,.2f}")
