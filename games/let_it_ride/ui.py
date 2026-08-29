import math
import os
import tkinter as tk
from typing import Optional

from core.persistence import load_json, save_json
from games.let_it_ride.logic import GAME_KEY, hand_outcome_label, LetItRideGame, RoundResult
from games.let_it_ride import logic as lir_logic
from ui import dialogs, theme
from ui.card_widgets import draw_card, draw_card_back, CARD_HEIGHT, CARD_WIDTH
from ui.chips import CHIP_DENOMINATIONS, CHIP_LAYER_MAX_R, CHIP_SIZE, draw_chip_face, draw_chip_stack
from ui.jackpot_display import JackpotDisplay

STATE_FILENAME = "let_it_ride_state.json"
DEFAULT_STATE = {"bets": {"base": 0, "bonus": 0, "three_card": 0, "jackpot": 0}, "selected_chip": 5}

# --- Layout constants ------------------------------------------------------
# Same "fixed pixel block, centred in the window" convention as every other
# game -- see three_card_poker/ui.py's own module-level comment. This game's
# own canvas is deliberately isolated from every sibling game's.
CANVAS_WIDTH = 760
CANVAS_HEIGHT = 400

PAYTABLE_WIDTH = 240
# Taller than most other games' own paytable panel -- this one holds three
# full sections (Base Game/Bonus/3 Card) rather than one or two -- but still
# capped by the fixed 1200x820 window (see main.py), so its own row pitch is
# tighter than every other game's own paytable panel to fit under that cap.
PAYTABLE_HEIGHT = 415
# Narrower than Ultimate Texas Hold'em's own 320 -- this game's fan_canvas
# (3 cards, not 2) starts further left, so the panel needs to stay clear of
# it -- see _show_payout_panel.
PAYOUT_PANEL_WIDTH = 240
# One row taller than Ultimate Texas Hold'em's own 160 -- up to 6 bet types
# can appear here (£/Bet1/Bet2/Bonus/3 Card/Jackpot) rather than 5.
PAYOUT_PANEL_HEIGHT = 190

JACKPOT_SPOT_R = 22
THREE_CARD_SPOT_R = 28   # the diamond's own "radius" (centre to each point)
BONUS_SPOT_R = 28

# The one chip-stack size used for the £/2/1 row on the play screen -- shared
# by their initial display, the Pull Back refund animation, and the payout
# layout below, so a stake chip and its later refund/payout chip are always
# drawn at the identical size instead of drifting between them.
ROW_CHIP_MAX_R = 20
# Bonus/3 Card/Jackpot's own display/payout size -- smaller, matching every
# other game's own side-bet spot convention (e.g. Ultimate Texas Hold'em's
# own Trips/Jackpot strip size).
SIDE_CHIP_MAX_R = 18

CONTENT_TOP_MARGIN = 35

# --- Dealer/community mat -- 2 cards, centred at the top of the canvas.
# There's no separate hidden "dealer hand" mat like Ultimate Texas Hold'em's
# own -- the dealer's 2 cards ARE the community cards here, dealt face down
# and revealed one at a time as the player's two decisions land.
CARD_ROW_GAP = CARD_WIDTH + 15
COMMUNITY_ROW_WIDTH = CARD_ROW_GAP + CARD_WIDTH   # 2 cards, 1 gap between them
COMMUNITY_MAT_MARGIN = 30
COMMUNITY_MAT_WIDTH = COMMUNITY_ROW_WIDTH + 2 * COMMUNITY_MAT_MARGIN
COMMUNITY_MAT_X1 = (CANVAS_WIDTH - COMMUNITY_MAT_WIDTH) / 2
COMMUNITY_MAT_X2 = COMMUNITY_MAT_X1 + COMMUNITY_MAT_WIDTH

DEALER_MAT_RADIUS = 12
DEALER_MAT_TOP = 6
DEALER_MAT_LABEL_Y = DEALER_MAT_TOP + 8
DEALER_Y = DEALER_MAT_TOP + 18                   # every card on this row's top-left y
DEALER_MAT_BOTTOM = DEALER_Y + CARD_HEIGHT + 8

# --- £ / 2 / 1 row -- three equal, linked base spots (see the module
# docstring: tracked internally as a single self.bets["base"] value). "£"
# always plays; "2" is the second decision; "1" is the first decision --
# real-table convention, matching the order the player actually decides them
# in (bet "1" right after seeing their own 3 cards, bet "2" after the first
# community card).
BASE_R = 32
_ROW_BOTTOM_MARGIN = 16
BASE_CY = CANVAS_HEIGHT - _ROW_BOTTOM_MARGIN - BASE_R
BASE_GAP = 26
_BASE_SPACING = 2 * BASE_R + BASE_GAP
BASE_LEFT_CX = CANVAS_WIDTH / 2 - _BASE_SPACING     # "£"
BASE_CENTRE_CX = CANVAS_WIDTH / 2                    # "2"
BASE_RIGHT_CX = CANVAS_WIDTH / 2 + _BASE_SPACING     # "1"

# --- 3 CARD (diamond, above "2") + BONUS (circle, above "1") row.
_MID_R = max(THREE_CARD_SPOT_R, BONUS_SPOT_R)
ROW_GAP = 34
MID_CY = BASE_CY - BASE_R - ROW_GAP - _MID_R
THREE_CARD_CX = BASE_CENTRE_CX
BONUS_CX = BASE_RIGHT_CX

# --- JACKPOT -- one row higher again, centred between 3 CARD and BONUS.
JACKPOT_GAP = 30
JACKPOT_CY = MID_CY - _MID_R - JACKPOT_GAP - JACKPOT_SPOT_R
JACKPOT_CX = (THREE_CARD_CX + BONUS_CX) / 2

# Settlement/payout "centre" -- the community/dealer mat's own centre, the
# closest thing this game has to "the house" (mirrors every other game's own
# SETTLE_CENTER convention).
SETTLE_CENTER_X = (COMMUNITY_MAT_X1 + COMMUNITY_MAT_X2) / 2
SETTLE_CENTER_Y = DEALER_Y + CARD_HEIGHT / 2
PAYOUT_WIN_LANDING_OFFSET_Y = -20
PAYOUT_CHIP_MOVE_MS = 280

# A Pull Back's refund heads toward the bottom edge of the canvas, toward
# the player -- the same off-canvas target convention every other game's own
# end-of-round chip sweep already uses, just triggered mid-round here.
PULL_BACK_TARGET = (CANVAS_WIDTH / 2, CANVAS_HEIGHT)

# --- Rules button ------------------------------------------------------
RULES_BUTTON_WIDTH = 106
RULES_BUTTON_HEIGHT = 54
RULES_BUTTON_RADIUS = RULES_BUTTON_HEIGHT // 2

# --- Betting-screen-only spacing -------------------------------------------
BETTING_ACTION_FRAME_PADY = (23, 0)
CHIP_FRAME_PADY = (16, 30)

# --- Player's own hand (3 cards) -- same narrow (half-width) canvas as
# every sibling game's own fan_canvas, below the action buttons.
FAN_Y = 14
FAN_GAP = 18
FAN_CANVAS_WIDTH = CANVAS_WIDTH / 2
FAN_CANVAS_HEIGHT = FAN_Y + CARD_HEIGHT + 18
_FAN_TOTAL_W = 3 * CARD_WIDTH + 2 * FAN_GAP
_FAN_PAD = 24
FAN_MAT_X1 = (FAN_CANVAS_WIDTH - _FAN_TOTAL_W) / 2 - _FAN_PAD
FAN_MAT_X2 = FAN_CANVAS_WIDTH - FAN_MAT_X1
FAN_MAT_TOP = 4
FAN_MAT_BOTTOM = FAN_CANVAS_HEIGHT - 4
FAN_MAT_RADIUS = 12
FAN_MAT_BORDER = theme.FG_DIM

# --- Animation pacing --------------------------------------------------
DEAL_IN_STAGGER_MS = 110
DEAL_IN_DROP_MS = 220
COMMUNITY_FLIP_MS = 220
COMMUNITY_FLIP_STAGGER_MS = 300
REFUND_MOVE_MS = 320
# "A slight pause" between a decision landing (Pull Back's refund finishing,
# or Let It Ride simply being acknowledged) and the next community card's
# reveal -- applies identically to both decisions and both decision points.
DECISION_TO_REVEAL_PAUSE_MS = 450


def _ease_out_cubic(t):
    return 1 - (1 - t) ** 3


def _format_payout(payout):
    if isinstance(payout, str):
        return payout
    return f"{payout:.0f}:1"


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


# Paytable rows, read straight from logic.py's own constants so the panel
# can never drift out of sync with what's actually paid out.
BASE_PAYTABLE_ROWS = [
    ("Royal Flush", lir_logic.BASIC_GAME_PAYOUT["royal_flush"]),
    ("Straight Flush", lir_logic.BASIC_GAME_PAYOUT["straight_flush"]),
    ("Four of a Kind", lir_logic.BASIC_GAME_PAYOUT["four_of_a_kind"]),
    ("Full House", lir_logic.BASIC_GAME_PAYOUT["full_house"]),
    ("Flush", lir_logic.BASIC_GAME_PAYOUT["flush"]),
    ("Straight", lir_logic.BASIC_GAME_PAYOUT["straight"]),
    ("Three of a Kind", lir_logic.BASIC_GAME_PAYOUT["three_of_a_kind"]),
    ("Two Pair", lir_logic.BASIC_GAME_PAYOUT["two_pair"]),
    ("Pair of 10s+", lir_logic.BASIC_GAME_PAYOUT["pair_tens_or_better"]),
]
BONUS_PAYTABLE_ROWS = [
    ("Royal Flush", lir_logic.BONUS_PAYOUT["royal_flush"]),
    ("Straight Flush", lir_logic.BONUS_PAYOUT["straight_flush"]),
    ("Four of a Kind", lir_logic.BONUS_PAYOUT["four_of_a_kind"]),
    ("Full House", lir_logic.BONUS_PAYOUT["full_house"]),
    ("Flush", lir_logic.BONUS_PAYOUT["flush"]),
    ("Straight", lir_logic.BONUS_PAYOUT["straight"]),
    ("Three of a Kind", lir_logic.BONUS_PAYOUT["three_of_a_kind"]),
]
THREE_CARD_PAYTABLE_ROWS = [
    ("Straight Flush", lir_logic.THREE_CARD_BONUS_PAYOUT["straight_flush"]),
    ("Three of a Kind", lir_logic.THREE_CARD_BONUS_PAYOUT["three_of_a_kind"]),
    ("Straight", lir_logic.THREE_CARD_BONUS_PAYOUT["straight"]),
    ("Flush", lir_logic.THREE_CARD_BONUS_PAYOUT["flush"]),
    ("Pair", lir_logic.THREE_CARD_BONUS_PAYOUT["pair"]),
]
PAYTABLE_SECTIONS = [
    ("BASE GAME (Pair of 10s+)", BASE_PAYTABLE_ROWS),
    ("BONUS (3 of a Kind+)", BONUS_PAYTABLE_ROWS),
    ("3 CARD (Pair+)", THREE_CARD_PAYTABLE_ROWS),
]

JACKPOT_PAYTABLE_ROWS = [
    ("Royal Flush", "100% JACKPOT"),
    ("Straight Flush", "10% JACKPOT"),
    ("Four of a Kind", f"£{lir_logic.JACKPOT_FOUR_OF_A_KIND_PAYOUT:.0f}"),
    ("Full House", f"£{lir_logic.JACKPOT_FULL_HOUSE_PAYOUT:.0f}"),
    ("Flush", f"£{lir_logic.JACKPOT_FLUSH_PAYOUT:.0f}"),
    ("Straight", f"£{lir_logic.JACKPOT_STRAIGHT_PAYOUT:.0f}"),
    ("Three of a Kind", f"£{lir_logic.JACKPOT_THREE_OF_A_KIND_PAYOUT:.0f}"),
]
JACKPOT_PAYTABLE_HIGHLIGHT_ROW = 0  # Royal Flush

# Human-readable names for a RoundResult's own tier-key vocabulary -- kept
# here (not imported from logic.py's own private _TIER_TO_OUTCOME_LABEL)
# since the UI's own wording is free to diverge from the Stats screen's.
_TIER_DISPLAY_NAMES = {
    "royal_flush": "Royal Flush", "straight_flush": "Straight Flush",
    "four_of_a_kind": "Four of a Kind", "full_house": "Full House", "flush": "Flush",
    "straight": "Straight", "three_of_a_kind": "Three of a Kind", "two_pair": "Two Pair",
    "pair_tens_or_better": "Pair of Tens or Better", "low_pair": "Low Pair", "high_card": "High Card",
}
_THREE_CARD_DISPLAY_NAMES = {
    "straight_flush": "Straight Flush", "three_of_a_kind": "Three of a Kind",
    "straight": "Straight", "flush": "Flush", "pair": "Pair", "high_card": "High Card",
}


def _max_deal_cost(bets):
    return lir_logic.total_upfront_cost(bets["base"], bets["bonus"], bets["three_card"], bets["jackpot"])


class LetItRideFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.BG)
        self.app = app
        self.game = LetItRideGame()
        self.result: Optional[RoundResult] = None
        self.state = "betting"      # betting -> playing -> resolved
        self.stage = "decision1"    # decision1 -> decision2, while state == "playing"

        self.save_path = os.path.join(app.data_dir, STATE_FILENAME)
        saved = load_json(self.save_path, DEFAULT_STATE)
        saved_bets = saved.get("bets", DEFAULT_STATE["bets"])
        self.bets = {
            "base": int(saved_bets.get("base", 0)),
            "bonus": int(saved_bets.get("bonus", 0)),
            "three_card": int(saved_bets.get("three_card", 0)),
            "jackpot": int(saved_bets.get("jackpot", 0)),
        }
        self.selected_chip = int(saved.get("selected_chip", DEFAULT_STATE["selected_chip"]))
        self._sanitize_bets(persist=False)

        self.chip_canvases = {}
        self._jackpot_pulse_t = 0.0
        self._bound_spot_tags = set()

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
        tk.Label(top_bar, text="Let It Ride", bg=theme.BG_ELEVATED, fg=theme.ACCENT,
                 font=theme.font(16, weight="bold")).pack(side="left", padx=10)
        self.balance_lbl = tk.Label(top_bar, text="£0.00", bg=theme.BG_ELEVATED, fg=theme.WIN_COLOR,
                                     font=theme.font(12, weight="bold"))
        self.balance_lbl.pack(side="right", padx=20)
        theme.breadcrumb(top_bar, "let_it_ride", bg=theme.BG_ELEVATED,
                          player=self.app.current_player["name"]).pack(side="right", padx=(6, 6))

        body = tk.Frame(self, bg=felt_theme["felt"])
        body.pack(fill="both", expand=True)

        content = tk.Frame(body, bg=felt_theme["felt"])
        content.place(relx=0.5, y=CONTENT_TOP_MARGIN, anchor="n")

        game_col = tk.Frame(content, bg=felt_theme["felt"])
        # anchor="n": pins game_col to the top of its cavity regardless of
        # its own natural height changing between states -- the established
        # fix for the vertical "jump" bug (see Mississippi Stud's own).
        game_col.pack(side="left", anchor="n")

        paytable_col = tk.Frame(content, bg=felt_theme["felt"])
        paytable_col.pack(side="right", fill="y", padx=(10, 24), pady=10)

        self.jackpot_display = JackpotDisplay(
            paytable_col, rows=JACKPOT_PAYTABLE_ROWS, highlight_row=JACKPOT_PAYTABLE_HIGHLIGHT_ROW,
            panel_bg=felt_theme["felt_dark"], border=felt_theme["accent"],
        )
        self.jackpot_display.pack(pady=(0, 14))

        self._build_paytable(paytable_col)

        self.canvas = tk.Canvas(game_col, bg=felt_theme["felt"], highlightthickness=0,
                                 width=CANVAS_WIDTH, height=CANVAS_HEIGHT)
        self.canvas.pack(padx=12, pady=(10, 4))

        self.result_lbl = tk.Label(
            game_col, text="Place your Ante bet to begin.", bg=felt_theme["felt"], fg=theme.FG,
            font=theme.font(13, weight="bold"), wraplength=900, justify="center",
        )
        self.result_lbl.pack(pady=(0, 6))

        self.action_frame = tk.Frame(game_col, bg=felt_theme["felt"])
        self.action_frame.pack(pady=(8, 0))

        self.deal_btn = tk.Button(
            self.action_frame, text="DEAL", bg=theme.ACCENT_DIM_BG, fg=theme.FG,
            font=theme.font(13, weight="bold"), relief="flat", padx=30, pady=10, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.ACCENT,
            command=self._on_deal,
        )
        self.pull_back_btn = tk.Button(
            self.action_frame, text="PULL BACK", bg=theme.GREY_BTN_BG, fg=theme.FG,
            font=theme.font(12, weight="bold"), relief="flat", padx=18, pady=10, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.GREY_BTN_BORDER,
            command=self._on_pull_back,
        )
        self.let_it_ride_btn = tk.Button(
            self.action_frame, text="LET IT RIDE", bg=theme.ACCENT_DIM_BG, fg=theme.FG,
            font=theme.font(12, weight="bold"), relief="flat", padx=18, pady=10, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.ACCENT,
            command=self._on_let_it_ride,
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
        self.chip_zone.pack(pady=(10, 0))

        # The round-result panel floats in the bottom-left corner of the
        # whole screen (see _show_result/_show_payout_panel), same as every
        # other recent game -- parented to `self` so its place() coordinates
        # are relative to the whole game screen, not chip_zone's pack stack.
        self.payout_canvas = tk.Canvas(
            self, width=PAYOUT_PANEL_WIDTH, height=PAYOUT_PANEL_HEIGHT,
            bg=felt_theme["felt"], highlightthickness=0,
        )

        self.chip_frame = tk.Frame(self.chip_zone, bg=felt_theme["felt"])
        tk.Label(
            self.chip_frame, text="Tap a chip, then tap £ / 2 / 1 / 3 Card / Bonus / Jackpot to place it",
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
        self.total_lbl.pack(pady=(8, 0))

        self.clear_btn = tk.Button(
            self.chip_frame, text="Clear Bets", bg=theme.GREY_BTN_BG, fg=theme.FG_DIM,
            font=theme.font(9), relief="flat", padx=10, pady=4, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.GREY_BTN_BORDER,
            command=self._clear_bets,
        )
        self.clear_btn.pack(pady=(6, 0))

        # Packed with its real CHIP_FRAME_PADY here (not a bare .pack())
        # before measuring -- chip_zone's fixed size below has to account
        # for that padding too, or the last child (Clear Bets) ends up
        # squeezed into whatever sliver of height is left over once
        # _show_betting_controls() re-packs chip_frame with this same pady.
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
            y = self._draw_paytable_section(canvas, y, title, rows, felt_theme["accent"])

    def _draw_paytable_section(self, canvas, y, title, rows, accent):
        # Tighter row pitch than every other game's own paytable panel --
        # this one holds three full sections (21 rows total) rather than one
        # or two, and still has to fit under the fixed window height.
        w = PAYTABLE_WIDTH
        canvas.create_text(20, y, text=title, fill=accent,
                            font=theme.font(8, weight="bold"), anchor="w")
        y += 15
        for label, payout in rows:
            canvas.create_text(20, y, text=label, fill=theme.FG, font=theme.font(8), anchor="w")
            canvas.create_text(w - 20, y, text=_format_payout(payout), fill=accent,
                                font=theme.font(8, weight="bold"), anchor="e")
            y += 14
        return y

    # ------------------------------------------------------------------ betting table
    def _draw_table(self):
        """The betting screen's own layout -- generously spaced, computed
        fresh here rather than reusing the play screen's own tighter module
        constants (same convention every prior game's betting screen has
        followed)."""
        self.canvas.delete("all")
        w, h = CANVAS_WIDTH, CANVAS_HEIGHT
        cx = w / 2

        base_r = 50
        bonus_r = 42
        three_card_r = 42
        jackpot_r = 30
        base_gap = 30
        row_gap = 40
        jackpot_gap = 34

        spacing = 2 * base_r + base_gap
        left_cx, centre_cx, right_cx = cx - spacing, cx, cx + spacing

        mid_r = max(bonus_r, three_card_r)
        content_h = jackpot_r * 2 + jackpot_gap + mid_r * 2 + row_gap + base_r * 2
        top = (h - content_h) * 0.55
        jackpot_cy = top + jackpot_r
        mid_cy = jackpot_cy + jackpot_r + jackpot_gap + mid_r
        base_cy = mid_cy + mid_r + row_gap + base_r

        three_card_cx = centre_cx
        bonus_cx = right_cx
        jackpot_cx = (three_card_cx + bonus_cx) / 2

        self._draw_spot_jackpot(jackpot_cx, jackpot_cy, jackpot_r)
        self._draw_spot_diamond("three_card", three_card_cx, mid_cy, three_card_r, "3 CARD")
        self._draw_spot_circle("bonus", bonus_cx, mid_cy, bonus_r, "BONUS")
        self._draw_spot_base_triple(left_cx, centre_cx, right_cx, base_cy, base_r)

        left_edge = left_cx - base_r
        self._draw_rules_button(left_edge / 2, base_cy)

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
            self, "♠ Let It Ride -- Rules",
            [
                ("GAMEPLAY", [
                    "**Betting:** Place three EQUAL bets -- £ (always plays), 2 (second "
                    "decision), and 1 (first decision) -- plus optional Bonus (£1), 3 Card "
                    "(variable) and Jackpot (£1) side bets.",
                    "**Dealing:** You're dealt 3 cards; the dealer's own 2 cards are dealt face "
                    "down and act as shared community cards.",
                    "**First decision:** Right after seeing your own 3 cards, Pull Back bet \"1\" "
                    "(get it back) or Let It Ride -- the first community card is then revealed.",
                    "**Second decision:** After that reveal, Pull Back bet \"2\" or Let It Ride -- "
                    "the second community card is then revealed and your final 5-card hand "
                    "(3 own cards + 2 community cards) is complete.",
                    "**Resolution:** A Pair of Tens or better is needed to win -- every base bet "
                    "still in play (£, plus 1/2 if not pulled back) pays independently at the "
                    "paytable, or loses if the hand doesn't qualify.",
                    "**Bonus:** Same final 5-card hand, needs Three of a Kind or better -- always "
                    "resolves, regardless of what happened to bets 1/2.",
                    "**3 Card:** Your own 3 cards only, needs a Pair or better -- always resolves "
                    "independently.",
                    "**Jackpot:** Same final 5-card hand, needs Three of a Kind or better to win "
                    "anything -- shares the same progressive pool as every other game's own "
                    "Jackpot side bet.",
                ]),
                ("HAND RANKINGS", [
                    ("High Card", [("Q", "h"), ("6", "s"), ("4", "d"), ("9", "c"), ("2", "s")]),
                    ("Pair", [("8", "h"), ("8", "d"), ("K", "c"), ("4", "s"), ("2", "h")]),
                    ("Two Pair", [("9", "h"), ("9", "d"), ("4", "c"), ("4", "s"), ("K", "h")]),
                    ("Three of a Kind", [("7", "h"), ("7", "d"), ("7", "c"), ("K", "s"), ("2", "h")]),
                    ("Straight", [("5", "h"), ("6", "d"), ("7", "s"), ("8", "c"), ("9", "h")]),
                    ("Flush", [("2", "c"), ("6", "c"), ("9", "c"), ("J", "c"), ("K", "c")]),
                    ("Full House", [("Q", "h"), ("Q", "d"), ("Q", "c"), ("4", "s"), ("4", "h")]),
                    ("Four of a Kind", [("9", "h"), ("9", "d"), ("9", "c"), ("9", "s"), ("2", "h")]),
                    ("Straight Flush", [("5", "d"), ("6", "d"), ("7", "d"), ("8", "d"), ("9", "d")]),
                ]),
                ("STRATEGY",
                 "Let it ride with a hand that's already a winner, or that has strong straight/"
                 "flush/pair-improving potential once the community cards land -- pull back "
                 "whenever the extra card(s) are unlikely to turn a currently-losing hand into a "
                 "qualifying one, since a pulled-back bet is refunded in full rather than lost."),
            ],
        )

    def _draw_spot_base_triple(self, left_cx, centre_cx, right_cx, cy, r):
        amount = self.bets["base"]
        felt_theme = self.app.settings.theme()
        for tag, spot_cx, label in (
            ("spot_base_left", left_cx, "£"),
            ("spot_base_centre", centre_cx, "2"),
            ("spot_base_right", right_cx, "1"),
        ):
            self.canvas.create_oval(spot_cx - r, cy - r, spot_cx + r, cy + r,
                                     fill=felt_theme["felt_dark"], outline=felt_theme["accent"], width=2, tags=(tag,))
            self.canvas.create_text(spot_cx, cy - r - 12, text=label, fill=theme.FG,
                                     font=theme.font(11, weight="bold"), tags=(tag,))
            if amount:
                draw_chip_stack(self.canvas, tag, spot_cx, cy, amount, max_r=CHIP_LAYER_MAX_R * 0.7)
            else:
                self.canvas.create_text(spot_cx, cy, text="tap to\nbet", fill=theme.FG_DIM,
                                         font=theme.font(9, weight="bold"), justify="center", tags=(tag,))
            self._bind_spot(tag, "base")

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

    def _draw_spot_diamond(self, key, cx, cy, r, label):
        tag = f"spot_{key}"
        amount = self.bets[key]
        felt_theme = self.app.settings.theme()
        theme.diamond(self.canvas, cx, cy, r, fill=felt_theme["felt_dark"],
                       outline=felt_theme["accent"], width=2, tags=(tag,))
        # Label above, not to the side -- this diamond sits close beside the
        # Bonus circle (unlike Ultimate Texas Hold'em's own Trips diamond,
        # which had open space to its right), so a side label would collide.
        self.canvas.create_text(cx, cy - r - 12, text=label, fill=theme.FG,
                                 font=theme.font(9, weight="bold"), tags=(tag,))
        if amount:
            draw_chip_stack(self.canvas, tag, cx, cy, amount, max_r=CHIP_LAYER_MAX_R * 0.65)
        else:
            self.canvas.create_text(cx, cy, text="tap to\nbet", fill=theme.FG_DIM,
                                     font=theme.font(8, weight="bold"), justify="center", tags=(tag,))
        self._bind_spot(tag, key)

    def _draw_spot_jackpot(self, cx, cy, r):
        """The £1 jackpot side bet -- an on/off spot, same breathing-glow
        treatment every other game's own Jackpot spot uses -- built
        independently for this game's own isolation, not shared code."""
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
        if tag in self._bound_spot_tags:
            return
        self._bound_spot_tags.add(tag)
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
        # Tucked closer into the true bottom-left corner than Ultimate Texas
        # Hold'em's own panel (x=20/y=-20) -- this game's fan_canvas (3
        # cards) starts further left than that game's own (2 cards), so a
        # wider gap here still clipped into it.
        self.payout_canvas.place(x=12, rely=1.0, y=-12, anchor="sw")

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

    def _show_stage_controls(self):
        self.chip_frame.pack_forget()
        self._hide_payout_panel()
        for w in self.action_frame.pack_slaves():
            w.pack_forget()
        self.action_frame.pack(pady=(8, 0))
        self.pull_back_btn.pack(side="left", padx=6)
        self.let_it_ride_btn.pack(side="left", padx=(18, 0))

    def _show_round_over_controls(self):
        self.chip_frame.pack_forget()
        for w in self.action_frame.pack_slaves():
            w.pack_forget()
        self.action_frame.pack(pady=(8, 0))
        self.new_deal_btn.pack(side="left", padx=8)
        self.change_bets_btn.pack(side="left", padx=8)

    def _show_no_controls(self):
        self.chip_frame.pack_forget()
        self._hide_payout_panel()
        for w in self.action_frame.pack_slaves():
            w.pack_forget()
        self.action_frame.pack(pady=(8, 0))

    # ------------------------------------------------------------------ betting
    def _on_place_chip(self, key):
        if self.state != "betting":
            return
        if key in ("bonus", "jackpot"):
            self._toggle_flat_bet(key)
        else:
            self._adjust_bet(key, self.selected_chip)

    def _toggle_flat_bet(self, key):
        amount = lir_logic.BONUS_BET_AMOUNT if key == "bonus" else lir_logic.JACKPOT_BET_AMOUNT
        trial_bets = dict(self.bets)
        trial_bets[key] = 0 if self.bets[key] else int(amount)
        if trial_bets[key] and _max_deal_cost(trial_bets) > self.app.finance.balance + 1e-9:
            label = "Bonus" if key == "bonus" else "Jackpot"
            dialogs.info(
                self, f"$ {key} --check-funds",
                f"You don't have enough balance to place the £{amount:.0f} {label} bet.",
                accent=theme.WARN,
            )
            return
        self.bets = trial_bets
        self._draw_table()
        self._update_total()
        self._persist_state()

    def _adjust_bet(self, key, delta):
        trial_bets = dict(self.bets)
        trial_bets[key] += delta
        balance = self.app.finance.balance
        if _max_deal_cost(trial_bets) > balance + 1e-9:
            if key == "base":
                message = (
                    "Your balance must cover 3 equal bets (£ / 2 / 1) to deal. Reduce your bet "
                    "or add funds."
                )
            else:
                message = "You don't have enough balance to place that chip."
            dialogs.info(self, "$ bet --check-funds", message, accent=theme.WARN)
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
        # "base" counts 3x -- the £/2/1 spots are always equal and all three
        # are placed at deal time (see the module docstring), even though
        # self.bets only stores one number for all three.
        total = 3 * self.bets["base"] + self.bets["bonus"] + self.bets["three_card"] + self.bets["jackpot"]
        self.total_lbl.configure(text=f"Total bet: £{total}")

    def _persist_state(self):
        save_json(self.save_path, {"bets": self.bets, "selected_chip": self.selected_chip})

    def _sanitize_bets(self, persist=True):
        if _max_deal_cost(self.bets) > self.app.finance.balance:
            self.bets = {"base": 0, "bonus": 0, "three_card": 0, "jackpot": 0}
            if persist:
                self._persist_state()

    # ------------------------------------------------------------------ round flow
    def _on_deal(self):
        base, bonus, three_card, jackpot = (
            self.bets["base"], self.bets["bonus"], self.bets["three_card"], self.bets["jackpot"]
        )
        if base <= 0:
            dialogs.info(self, "$ deal --require-bet", "You must place a bet to deal.", accent=theme.WARN)
            return

        if not self.app.finance.can_afford(_max_deal_cost(self.bets)):
            choice = dialogs.choice(
                self, "$ deal --check-funds",
                "You don't have enough balance to cover these bets.",
                [("Go Home", "home"), ("Cashier", "cashier")],
            )
            if choice == "home":
                self.app.show_frame("menu")
            elif choice == "cashier":
                self.app.show_frame("finances")
            return

        total_upfront = lir_logic.total_upfront_cost(base, bonus, three_card, jackpot)
        self.app.finance.place_wager(total_upfront)
        self._refresh_balance()

        self.result = self.game.deal(base, bonus_bet=bonus, three_card_bet=three_card, jackpot_bet=jackpot)
        self.state = "playing"
        self.stage = "decision1"

        self.result_lbl.configure(text="Dealing...", fg=theme.FG)
        self._show_no_controls()

        self.fan_canvas.delete("all")
        self.fan_canvas.pack(pady=(14, 0), before=self.chip_zone)
        self._draw_fan_mat()

        self._draw_play_zones()
        self._deal_player_cards()

    def _on_pull_back(self):
        if self.state != "playing":
            return
        assert self.result is not None
        self._show_no_controls()
        key = "bet1" if self.stage == "decision1" else "bet2"
        decide = self.game.decide_bet1 if key == "bet1" else self.game.decide_bet2
        refund = decide(False)
        self.app.finance.add_return(refund)
        self._refresh_balance()
        cx, cy, spot_tag, max_r = self._base_layout()[key]
        self._animate_chip_refund(spot_tag, refund, cx, cy, max_r, on_done=self._advance_after_decision)

    def _on_let_it_ride(self):
        if self.state != "playing":
            return
        assert self.result is not None
        self._show_no_controls()
        if self.stage == "decision1":
            self.game.decide_bet1(True)
        else:
            self.game.decide_bet2(True)
        self._advance_after_decision()

    def _advance_after_decision(self):
        self._after_delay(DECISION_TO_REVEAL_PAUSE_MS, self._reveal_after_decision)

    def _reveal_after_decision(self):
        if self.stage == "decision1":
            self.game.reveal_first_card()
            self._animate_community_reveal([0], self._enter_decision2)
        else:
            self.game.reveal_second_card()
            self._animate_community_reveal([1], self._settle_round)

    def _enter_decision2(self):
        self.stage = "decision2"
        self._show_stage_controls()

    def _new_deal(self):
        assert self.result is not None, "_new_deal called before a round was ever dealt"
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

    # ------------------------------------------------------------------ card-view rendering
    def _community_slot_x(self, i):
        return COMMUNITY_MAT_X1 + COMMUNITY_MAT_MARGIN + i * CARD_ROW_GAP

    def _base_layout(self):
        return {
            "ante": (BASE_LEFT_CX, BASE_CY, "spot_base_left", ROW_CHIP_MAX_R),
            "bet2": (BASE_CENTRE_CX, BASE_CY, "spot_base_centre", ROW_CHIP_MAX_R),
            "bet1": (BASE_RIGHT_CX, BASE_CY, "spot_base_right", ROW_CHIP_MAX_R),
        }

    def _draw_zone_backgrounds(self):
        """Just the community/dealer mat + its label (tag "zone_bg") --
        split out so a live theme switch mid-round (see _apply_theme) can
        refresh its colours without touching any already-dealt/already-
        revealed card, which a full canvas.delete("all") + redraw would
        otherwise destroy."""
        felt_theme = self.app.settings.theme()
        theme.rounded_rect(
            self.canvas, COMMUNITY_MAT_X1, DEALER_MAT_TOP, COMMUNITY_MAT_X2, DEALER_MAT_BOTTOM,
            radius=DEALER_MAT_RADIUS, fill=felt_theme["felt_dark"], outline=felt_theme["accent"], width=2,
            tags=("zone_bg",),
        )
        self.canvas.create_text((COMMUNITY_MAT_X1 + COMMUNITY_MAT_X2) / 2, DEALER_MAT_LABEL_Y, text="DEALER",
                                 fill=theme.ACCENT, font=theme.font(9, weight="bold"), tags=("zone_bg",))

    def _draw_play_zones(self):
        assert self.result is not None
        self.canvas.delete("all")
        self._draw_zone_backgrounds()

        if self.bets["jackpot"]:
            self._draw_strip_circle("jackpot", JACKPOT_CX, JACKPOT_CY, JACKPOT_SPOT_R,
                                     "JACKPOT", self.bets["jackpot"])
        if self.bets["three_card"]:
            self._draw_strip_diamond("three_card", THREE_CARD_CX, MID_CY, THREE_CARD_SPOT_R,
                                      "3 CARD", self.bets["three_card"])
        if self.bets["bonus"]:
            self._draw_strip_circle("bonus", BONUS_CX, MID_CY, BONUS_SPOT_R, "BONUS", self.bets["bonus"])

        self._draw_strip_base_triple(self.result.ante_bet)

    def _draw_strip_base_triple(self, base_bet):
        felt_theme = self.app.settings.theme()
        for tag, spot_cx, label in (
            ("spot_base_left", BASE_LEFT_CX, "£"),
            ("spot_base_centre", BASE_CENTRE_CX, "2"),
            ("spot_base_right", BASE_RIGHT_CX, "1"),
        ):
            self.canvas.create_oval(spot_cx - BASE_R, BASE_CY - BASE_R, spot_cx + BASE_R, BASE_CY + BASE_R,
                                     fill=felt_theme["felt_dark"], outline=felt_theme["accent"], width=2,
                                     tags=(tag,))
            self.canvas.create_text(spot_cx, BASE_CY - BASE_R - 10, text=label, fill=theme.FG,
                                     font=theme.font(10, weight="bold"), tags=(tag,))
            draw_chip_stack(self.canvas, (tag, f"{tag}_chips"), spot_cx, BASE_CY, base_bet, max_r=ROW_CHIP_MAX_R)

    def _draw_strip_circle(self, key, cx, cy, r, label, amount):
        tag = f"strip_{key}"
        self.canvas.delete(tag)
        felt_theme = self.app.settings.theme()
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=felt_theme["felt_dark"],
                                 outline=felt_theme["accent"], width=2, tags=(tag,))
        self.canvas.create_text(cx, cy - r - 10, text=label, fill=theme.FG,
                                 font=theme.font(9, weight="bold"), tags=(tag,))
        draw_chip_stack(self.canvas, (tag, f"{tag}_chips"), cx, cy, amount, max_r=SIDE_CHIP_MAX_R)

    def _draw_strip_diamond(self, key, cx, cy, r, label, amount):
        tag = f"strip_{key}"
        self.canvas.delete(tag)
        felt_theme = self.app.settings.theme()
        theme.diamond(self.canvas, cx, cy, r, fill=felt_theme["felt_dark"],
                       outline=felt_theme["accent"], width=2, tags=(tag,))
        self.canvas.create_text(cx, cy - r - 10, text=label, fill=theme.FG,
                                 font=theme.font(9, weight="bold"), tags=(tag,))
        draw_chip_stack(self.canvas, (tag, f"{tag}_chips"), cx, cy, amount, max_r=SIDE_CHIP_MAX_R)

    def _draw_player_card_at(self, i, card, x, y, face_up=True):
        tag = f"player_card_{i}"
        self.fan_canvas.delete(tag)
        if face_up:
            draw_card(self.fan_canvas, x, y, card, tags=(tag,))
        else:
            draw_card_back(self.fan_canvas, x, y, self._current_felt,
                            self.app.settings.theme()["accent"], tags=(tag,))

    def _fan_slots(self):
        start_x = FAN_CANVAS_WIDTH / 2 - _FAN_TOTAL_W / 2
        return [(start_x + i * (CARD_WIDTH + FAN_GAP), FAN_Y) for i in range(3)]

    def _draw_fan_mat(self):
        felt_theme = self.app.settings.theme()
        theme.rounded_rect(
            self.fan_canvas, FAN_MAT_X1, FAN_MAT_TOP, FAN_MAT_X2, FAN_MAT_BOTTOM, radius=FAN_MAT_RADIUS,
            fill=felt_theme["felt_dark"], outline=FAN_MAT_BORDER, width=2, tags=("fan_mat_bg",),
        )

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

    def _animate_flip(self, canvas, tag, cx_slot, y, card, reveal, duration, on_done=None):
        def frame(t):
            squeeze = abs(1 - 2 * t)
            w = max(6, CARD_WIDTH * squeeze)
            x = cx_slot - w / 2
            canvas.delete(tag)
            face_up_now = reveal if t >= 0.5 else not reveal
            if squeeze > 0.35:
                if face_up_now:
                    draw_card(canvas, x, y, card, width=w, tags=(tag,))
                else:
                    draw_card_back(canvas, x, y, self._current_felt, self.app.settings.theme()["accent"],
                                    width=w, tags=(tag,))
            else:
                canvas.create_rectangle(x, y, x + w, y + CARD_HEIGHT,
                                         fill="#fdfdf5", outline="#222222", tags=(tag,))

        self._animate(duration, frame, on_done=on_done)

    # ------------------------------------------------------------------ deal-in / reveal / refund
    def _deal_player_cards(self):
        assert self.result is not None
        cards = self.result.player_cards
        fan_slots = self._fan_slots()
        n = len(fan_slots)

        def deal_one(i):
            tx, ty = fan_slots[i]
            sx, sy = tx, ty - 90

            def frame(t, i=i, sx=sx, sy=sy, tx=tx, ty=ty):
                self._draw_player_card_at(i, cards[i], sx + (tx - sx) * t, sy + (ty - sy) * t, face_up=False)

            self._animate(DEAL_IN_DROP_MS, frame, on_done=(self._flip_player_cards_up if i == n - 1 else None))

        if self.app.settings.get("animations_enabled"):
            self.after(350, lambda: self._run_staggered(n, DEAL_IN_STAGGER_MS, deal_one))
        else:
            self._run_staggered(n, DEAL_IN_STAGGER_MS, deal_one)

    def _flip_player_cards_up(self):
        """The player's own 3 cards deal in face down, then immediately
        flip face up so they can actually see their own hand -- the
        dealer's own 2 cards (dealt next) stay face down until each is
        individually revealed by a decision."""
        assert self.result is not None
        cards = self.result.player_cards
        slots = self._fan_slots()
        n = len(slots)

        def flip_one(i):
            sx, sy = slots[i]
            cx_slot = sx + CARD_WIDTH / 2
            self._animate_flip(
                self.fan_canvas, f"player_card_{i}", cx_slot, sy, cards[i], reveal=True,
                duration=COMMUNITY_FLIP_MS, on_done=(self._deal_dealer_cards_facedown if i == n - 1 else None),
            )

        self._run_staggered(n, 90, flip_one)

    def _deal_dealer_cards_facedown(self):
        n = 2

        def deal_one(i):
            tx = self._community_slot_x(i)
            ty = DEALER_Y
            sx, sy = tx, ty - 90

            def frame(t, i=i, sx=sx, sy=sy, tx=tx, ty=ty):
                self.canvas.delete(f"community_card_{i}")
                x = sx + (tx - sx) * t
                y = sy + (ty - sy) * t
                felt_theme = self.app.settings.theme()
                draw_card_back(self.canvas, x, y, felt_theme["felt"], felt_theme["accent"],
                                tags=(f"community_card_{i}",))

            self._animate(DEAL_IN_DROP_MS, frame, on_done=(self._on_deal_complete if i == n - 1 else None))

        self._run_staggered(n, DEAL_IN_STAGGER_MS, deal_one)

    def _on_deal_complete(self):
        self.result_lbl.configure(text="Your cards are dealt. Let it?", fg=theme.FG)
        self._show_stage_controls()

    def _animate_community_reveal(self, indices, on_done):
        assert self.result is not None
        result = self.result

        def flip_one(pos):
            i = indices[pos]
            cx_slot = self._community_slot_x(i) + CARD_WIDTH / 2
            self._animate_flip(
                self.canvas, f"community_card_{i}", cx_slot, DEALER_Y, result.community_cards[i],
                reveal=True, duration=COMMUNITY_FLIP_MS,
                on_done=(on_done if pos == len(indices) - 1 else None),
            )

        self._run_staggered(len(indices), COMMUNITY_FLIP_STAGGER_MS, flip_one)

    def _animate_chip_refund(self, spot_tag, amount, cx, cy, max_r, on_done):
        """A Pull Back's chips shrink and slide away from their own spot
        toward the player (PULL_BACK_TARGET, the same off-canvas-toward-the-
        -player convention every other game's own end-of-round chip sweep
        uses) -- there's no existing precedent for a mid-round, single-spot
        refund elsewhere in this app, so this is built fresh from the same
        _animate-based shrink/slide primitive those sweeps use."""
        chips_tag = f"{spot_tag}_chips"
        self.canvas.delete(chips_tag)
        travel_tag = f"chip_refund_{spot_tag}"
        target_x, target_y = PULL_BACK_TARGET

        def frame(t):
            tx = cx + (target_x - cx) * t
            ty = cy + (target_y - cy) * t
            self.canvas.delete(travel_tag)
            r = max_r * (1 - t)
            if r > 2:
                draw_chip_stack(self.canvas, travel_tag, tx, ty, amount, r)

        def arrived():
            self.canvas.delete(travel_tag)
            if on_done:
                on_done()

        self._animate(REFUND_MOVE_MS, frame, on_done=arrived)

    # ------------------------------------------------------------------ settle / payout
    def _settle_round(self):
        assert self.result is not None
        result = self.game.settle(jackpot_amount=self.app.jackpot.amount)

        for key, bet, ret in self._resolved_bet_totals(result):
            self.app.game_stats.record_bet(GAME_KEY, key, bet, ret)
        self.app.game_stats.record_round_net(GAME_KEY, result.net_result)
        self.app.game_stats.record_hand(GAME_KEY, hand_outcome_label(result))
        if result.jackpot_won:
            self.app.jackpot.win()
        elif result.jackpot_pool_partial_fraction:
            self.app.jackpot.set_amount(self.app.jackpot.amount * (1 - result.jackpot_pool_partial_fraction))
        self.app.finance.record_round_played(result.net_result)

        # bet1/bet2 pulled back mid-round were already credited back to the
        # balance the moment that decision was made (see _on_pull_back) --
        # only whatever's still actually sitting on the table gets credited
        # here, or Pull Back's own refund would be double-counted.
        payout_items = self._payout_chip_items(result)
        remaining_credit = sum(it["ret"] for it in payout_items)
        if remaining_credit > 0:
            self.app.finance.add_return(remaining_credit)

        self._show_no_controls()
        self._animate_payouts(payout_items, lambda: self._on_round_settled(result))

    def _resolved_bet_totals(self, result):
        totals = []
        if result.ante_bet:
            totals.append(("ante", result.ante_bet, result.ante_return))
        if result.bet1_bet:
            totals.append(("bet1", result.bet1_bet, result.bet1_return))
        if result.bet2_bet:
            totals.append(("bet2", result.bet2_bet, result.bet2_return))
        if result.bonus_bet:
            totals.append(("bonus", result.bonus_bet, result.bonus_return))
        if result.three_card_bet:
            totals.append(("three_card", result.three_card_bet, result.three_card_return))
        if result.jackpot_bet:
            totals.append(("jackpot", result.jackpot_bet, result.jackpot_return))
        return totals

    def _payout_chip_items(self, result):
        layout = self._base_layout()
        layout.update({
            "bonus": (BONUS_CX, MID_CY, "strip_bonus", SIDE_CHIP_MAX_R),
            "three_card": (THREE_CARD_CX, MID_CY, "strip_three_card", SIDE_CHIP_MAX_R),
            "jackpot": (JACKPOT_CX, JACKPOT_CY, "strip_jackpot", SIDE_CHIP_MAX_R),
        })
        items = []
        for key, bet, ret in self._resolved_bet_totals(result):
            # A pulled-back bet1/bet2 has no chips left on the table to
            # animate -- they already flew away via _animate_chip_refund.
            if key == "bet1" and not result.bet1_active:
                continue
            if key == "bet2" and not result.bet2_active:
                continue
            cx, cy, spot_tag, max_r = layout[key]
            items.append(dict(key=key, bet=bet, ret=ret, cx=cx, cy=cy, spot_tag=spot_tag, max_r=max_r))
        return items

    def _chip_move_away(self, item, on_done):
        chips_tag = f"{item['spot_tag']}_chips"
        self.canvas.delete(chips_tag)
        travel_tag = f"chip_travel_{item['key']}"
        from_cx, from_cy = item["cx"], item["cy"]

        def frame(t):
            cx = from_cx + (SETTLE_CENTER_X - from_cx) * t
            cy = from_cy + (SETTLE_CENTER_Y - from_cy) * t
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
        to_cx, to_cy = item["cx"], item["cy"] + PAYOUT_WIN_LANDING_OFFSET_Y

        def frame(t):
            cx = SETTLE_CENTER_X + (to_cx - SETTLE_CENTER_X) * t
            cy = SETTLE_CENTER_Y + (to_cy - SETTLE_CENTER_Y) * t
            self.canvas.delete(travel_tag)
            if item["max_r"] * t > 2:
                draw_chip_stack(self.canvas, travel_tag, cx, cy, win_amount, item["max_r"] * t)

        self._animate(PAYOUT_CHIP_MOVE_MS, frame, on_done=on_done)

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

    def _animate_payouts(self, items, on_done):
        losing = [it for it in items if it["ret"] == 0]
        winning = [it for it in items if it["ret"] > it["bet"]]
        stages = (
            [lambda cb, it=it: self._chip_move_away(it, cb) for it in losing]
            + [lambda cb, it=it: self._chip_move_in(it, cb) for it in winning]
        )
        self._run_sequential(stages, on_done)

    def _on_round_settled(self, result):
        # fan_canvas stays visible here even once resolved -- the round-
        # result panel lives in its own floating corner (see
        # _show_payout_panel) rather than taking fan_canvas's old spot.
        self._refresh_balance()
        self.app.on_balance_changed()
        self._show_result(result)
        self._show_round_over_controls()
        self.state = "resolved"

    def _show_result(self, result):
        hand_name = _TIER_DISPLAY_NAMES[result.five_card_tier]
        if result.qualified:
            mult = lir_logic.BASIC_GAME_PAYOUT[result.five_card_tier]
            text = f"{hand_name} - base bet(s) pay {mult}:1."
            color = theme.WIN_COLOR
        else:
            text = f"{hand_name} - below a Pair of Tens, base bet(s) lose."
            color = theme.LOSE_COLOR
        self.result_lbl.configure(text=text, fg=color)

        self._show_payout_panel()
        self._draw_payout_panel(result)

    def _payout_rows(self, result):
        rows = []
        if result.ante_bet:
            rows.append((f"£ Bet £{result.ante_bet:.0f}", result.ante_return - result.ante_bet))
        if result.bet1_bet:
            label = f"Bet 1 £{result.bet1_bet:.0f}" + ("" if result.bet1_active else " (back)")
            rows.append((label, result.bet1_return - result.bet1_bet))
        if result.bet2_bet:
            label = f"Bet 2 £{result.bet2_bet:.0f}" + ("" if result.bet2_active else " (back)")
            rows.append((label, result.bet2_return - result.bet2_bet))
        if result.bonus_bet:
            rows.append((f"Bonus £{result.bonus_bet:.0f}", result.bonus_return - result.bonus_bet))
        if result.three_card_bet:
            label = f"3 Card £{result.three_card_bet:.0f}"
            if result.three_card_tier is not None:
                label = f"3 Card ({_THREE_CARD_DISPLAY_NAMES[result.three_card_tier]})"
            rows.append((label, result.three_card_return - result.three_card_bet))
        if result.jackpot_bet:
            label = "Jackpot \U0001F3B0 WON!" if result.jackpot_won else f"Jackpot £{result.jackpot_bet:.0f}"
            rows.append((label, result.jackpot_return - result.jackpot_bet))
        return rows

    def _draw_payout_panel(self, result):
        canvas = self.payout_canvas
        canvas.delete("all")
        w, h = PAYOUT_PANEL_WIDTH, PAYOUT_PANEL_HEIGHT
        felt_theme = self.app.settings.theme()

        theme.recessed_panel(canvas, 0, 0, w, h, title="ROUND RESULT",
                              fill=felt_theme["felt_dark"], outline=felt_theme["accent"])

        rows = self._payout_rows(result)
        y = 36
        for label, net in rows:
            canvas.create_text(24, y, text=label, fill=theme.FG, font=theme.font(9), anchor="w")
            canvas.create_text(w - 24, y, text=_format_signed(net), fill=_net_color(net),
                                font=theme.font(9, weight="bold"), anchor="e")
            y += 15

        y += 4
        canvas.create_line(24, y, w - 24, y, fill=theme.BORDER)
        y += 14
        canvas.create_text(24, y, text="Round Net", fill=theme.FG, font=theme.font(11, weight="bold"), anchor="w")
        canvas.create_text(w - 24, y, text=_format_signed(result.net_result), fill=_net_color(result.net_result),
                            font=theme.font(12, weight="bold"), anchor="e")

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
        # Same surgical fix for the play screen's own mat -- refreshes just
        # its background rect/label (tag "zone_bg"), never the cards
        # themselves, so a live mid-round switch can't wipe out an already-
        # dealt/already-revealed hand the way a full canvas.delete("all") +
        # _draw_play_zones() redraw would.
        if self.canvas.find_withtag("zone_bg"):
            self.canvas.delete("zone_bg")
            self._draw_zone_backgrounds()
            self.canvas.tag_lower("zone_bg")
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
