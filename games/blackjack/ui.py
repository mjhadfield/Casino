import math
import os
import tkinter as tk
import tkinter.font as tkfont
from typing import Optional

from core.persistence import load_json, save_json
from games.blackjack.logic import (
    BET_TYPES,
    BlackjackGame,
    GAME_KEY,
    JACKPOT_BET_AMOUNT,
    JACKPOT_FLUSH_PAYOUT,
    JACKPOT_STRAIGHT_FLUSH_PAYOUT,
    JACKPOT_STRAIGHT_PAYOUT,
    JACKPOT_THREE_OF_A_KIND_OFFSUIT_PAYOUT,
    JACKPOT_THREE_OF_A_KIND_SUITED_PAYOUT,
    RoundSummary,
    SUPER_PAIRS_ANY_PAIR_MULTIPLIER,
    SUPER_PAIRS_PRIME_PAIR_MULTIPLIER,
    SUPER_PAIRS_SUITED_PAIR_MULTIPLIER,
    SUPER_PAIRS_SUITED_TRIPS_MULTIPLIER,
    TOP_THREE_STRAIGHT_FLUSH_MULTIPLIER,
    TOP_THREE_THREE_OF_A_KIND_MULTIPLIER,
    TOP_THREE_THREE_OF_A_KIND_SUITED_MULTIPLIER,
    TWENTY_ONE_PLUS_THREE_MULTIPLIER,
)
from ui import dialogs, theme
from ui.card_widgets import CARD_HEIGHT, CARD_WIDTH, draw_card, draw_card_back
from ui.chips import CHIP_COLORS_BY_VALUE, CHIP_DENOMINATIONS, CHIP_LAYER_MAX_R, CHIP_SIZE, draw_chip_face, draw_chip_stack
from ui.jackpot_display import JackpotDisplay

STATE_FILENAME = "blackjack_state.json"
BET_KEYS = ("blackjack", "super_pairs", "twenty_one_plus_three", "top_three", "jackpot")
DEFAULT_STATE = {"bets": {k: 0 for k in BET_KEYS}, "selected_chip": 5, "num_boxes": 1}

# --- Layout constants -------------------------------------------------------
# Taller than Three Card Poker's canvas (384) to leave room for a box's split
# hands to cascade/stack vertically on the play screen -- the betting screen
# just gets a little extra breathing room above/below its spots as a result,
# same "reserved footprint used in every state" idea Three Card Poker's own
# chip_zone already relies on.
CANVAS_WIDTH = 760
CANVAS_HEIGHT = 460

PAYTABLE_WIDTH = 240
PAYTABLE_HEIGHT = 320
PAYOUT_PANEL_WIDTH = 380
PAYOUT_PANEL_HEIGHT = 240

CONTENT_TOP_MARGIN = 14

# result_lbl sits right below the canvas in every state, but only the
# betting state needs the extra top gap -- it shares the canvas's dead space
# below the spot row with the caption/Boxes/Deal row (see BETTING_CANVAS_
# HEIGHT), while the play states already fill the canvas edge-to-edge.
BETTING_RESULT_LBL_PADY = (50, 3)
PLAY_RESULT_LBL_PADY = (0, 3)
BETTING_ACTION_FRAME_PADY = (8, 0)
CHIP_FRAME_PADY = (6, 30)

RULES_BUTTON_WIDTH = 106
RULES_BUTTON_HEIGHT = 54
RULES_BUTTON_RADIUS = RULES_BUTTON_HEIGHT // 2
# Fixed, rather than "halfway to the main spot" the way Three Card Poker
# places its own Rules button -- Super Pairs sits much further out from the
# Blackjack spot (SIDE_OFFSET) than Pair Plus does from Ante, so that same
# halfway formula would collide with it. This just clears Super Pairs'
# circle with margin to spare (see the layout screenshot check).
RULES_BUTTON_CX = 70

# --- Betting-screen spot geometry -------------------------------------------
# The main Blackjack bet sits centre, card-shaped, bottom-aligned with the
# Super Pairs/21+3/Rules row below (SIDE_SPOT_CY) rather than sharing their
# centre -- it's a taller shape than those circles, so lining up centres left
# it hanging well below them. Jackpot/Top 3 are the smaller flag-style bets
# stacked directly above their partner on each side.
BLACKJACK_SPOT_W = CARD_WIDTH * 1.6
BLACKJACK_SPOT_H = CARD_HEIGHT * 1.6

SIDE_OFFSET = 165        # Super Pairs / 21+3 distance from centre
MAIN_SIDE_R = 36         # Super Pairs / 21+3 circle radius
FLAG_R = 24              # Jackpot / Top 3 circle radius
STACK_GAP = 28           # vertical gap between a flag spot and its partner below
                         # (clears the flag spot's own label, drawn just above
                         # the partner spot's circle -- STACK_GAP=16 let that
                         # label clip into the flag spot's circle above it)

LEFT_CX = CANVAS_WIDTH / 2 - SIDE_OFFSET
RIGHT_CX = CANVAS_WIDTH / 2 + SIDE_OFFSET
SIDE_SPOT_CY = 275
SUPER_PAIRS_CY = SIDE_SPOT_CY
TWENTY_ONE_PLUS_THREE_CY = SIDE_SPOT_CY
JACKPOT_CY = SUPER_PAIRS_CY - MAIN_SIDE_R - STACK_GAP - FLAG_R
TOP_THREE_CY = TWENTY_ONE_PLUS_THREE_CY - MAIN_SIDE_R - STACK_GAP - FLAG_R
BLACKJACK_SPOT_CY = SIDE_SPOT_CY + MAIN_SIDE_R - BLACKJACK_SPOT_H / 2
RULES_BUTTON_CY = SIDE_SPOT_CY + MAIN_SIDE_R - RULES_BUTTON_HEIGHT / 2

# The canvas is fixed at CANVAS_HEIGHT (460) so a dealt round has room for a
# box's split hands to cascade -- but the betting screen only ever draws down
# to the spot row's bottom edge (SIDE_SPOT_CY + MAIN_SIDE_R), so left at full
# height it trails ~150px of empty felt below the spots before the caption/
# Deal controls (packed right after the canvas) even start. Betting state
# shrinks the canvas to just past that row instead; _show_no_controls sets it
# back to CANVAS_HEIGHT the moment a round is dealt.
BETTING_CANVAS_HEIGHT = int(SIDE_SPOT_CY + MAIN_SIDE_R + 40)

_lerp_color = theme.lerp_color

_SUPER_PAIRS_ROWS = [
    ("Suited Trips", SUPER_PAIRS_SUITED_TRIPS_MULTIPLIER),
    ("Suited Pair", SUPER_PAIRS_SUITED_PAIR_MULTIPLIER),
    ("Prime Pair", SUPER_PAIRS_PRIME_PAIR_MULTIPLIER),
    ("Any Pair", SUPER_PAIRS_ANY_PAIR_MULTIPLIER),
]
_TOP_THREE_ROWS = [
    ("3oaK Suited", TOP_THREE_THREE_OF_A_KIND_SUITED_MULTIPLIER),
    ("Straight Flush", TOP_THREE_STRAIGHT_FLUSH_MULTIPLIER),
    ("Three of a Kind", TOP_THREE_THREE_OF_A_KIND_MULTIPLIER),
]
_TWENTY_ONE_PLUS_THREE_ROWS = [("Flush or better", TWENTY_ONE_PLUS_THREE_MULTIPLIER)]
PAYTABLE_SECTIONS = [
    ("21+3", _TWENTY_ONE_PLUS_THREE_ROWS),
    ("TOP 3", _TOP_THREE_ROWS),
    ("SUPER PAIRS", _SUPER_PAIRS_ROWS),
]

JACKPOT_PAYTABLE_ROWS = [
    ("Flush", f"£{JACKPOT_FLUSH_PAYOUT:.0f}"),
    ("Straight", f"£{JACKPOT_STRAIGHT_PAYOUT:.0f}"),
    ("3oaK (off-suit)", f"£{JACKPOT_THREE_OF_A_KIND_OFFSUIT_PAYOUT:.0f}"),
    ("Straight Flush", f"£{JACKPOT_STRAIGHT_FLUSH_PAYOUT:.0f}"),
    ("3oaK (suited)", f"£{JACKPOT_THREE_OF_A_KIND_SUITED_PAYOUT:.0f}"),
    ("3oaK (A/K/Q)", "100% JACKPOT"),
]
JACKPOT_PAYTABLE_HIGHLIGHT_ROW = len(JACKPOT_PAYTABLE_ROWS) - 1

# --- Play-screen geometry ---------------------------------------------------
# Everything below is read only once a round's actually been dealt -- the
# betting screen above never touches it. Unlike Three Card Poker's fixed
# 3-card fan, a box here can hold anywhere from 1 to 5 hands (via Split), so
# nothing about a box's own height is a fixed constant -- see
# _hand_positions, which compresses each hand's row height to fit however
# many that box currently has.
CARD_SCALE = 0.6
HAND_CARD_W = CARD_WIDTH * CARD_SCALE
HAND_CARD_H = CARD_HEIGHT * CARD_SCALE
HAND_CARD_OVERLAP_X = HAND_CARD_W * 0.55

DEALER_MAT_RADIUS = 14
DEALER_MAT_TOP = 10
DEALER_MAT_LABEL_Y = DEALER_MAT_TOP + 9
DEALER_Y = DEALER_MAT_TOP + 26
DEALER_MAT_BOTTOM = DEALER_Y + CARD_HEIGHT + 18
DEALER_MAT_X1 = 40
DEALER_MAT_X2 = CANVAS_WIDTH - 40
DEALER_CENTER_X = CANVAS_WIDTH / 2
DEALER_CENTER_Y = DEALER_Y + CARD_HEIGHT / 2
DEALER_CARD_GAP_MAX = CARD_WIDTH + 12

# Two box regions side by side -- always both drawn (per the brief), even
# when only 1 box is in play, so the table's shape doesn't jump between
# rounds. Play order is Box 1 before Box 2 -- see _after_insurance_decided.
BOX_MARGIN_X = 30
BOX_GAP = 24
BOX_W = (CANVAS_WIDTH - 2 * BOX_MARGIN_X - BOX_GAP) / 2
BOX_TOP = DEALER_MAT_BOTTOM + 22
BOX_HEIGHT = CANVAS_HEIGHT - BOX_TOP - 14
BOX_HEADER_H = 30
BOX_RADIUS = 12
BOX_SIDE_BET_ROW_H = 38  # only reserved when the round actually has side bets

HAND_ROW_H = 62       # a hand's row height when there's room to spare
HAND_CHIP_R = 20

SIDE_BET_TOKEN_R = 13
SIDE_BET_LABELS = {"jackpot": "JP", "super_pairs": "SP", "top_three": "T3", "twenty_one_plus_three": "21+3"}
SIDE_BET_ORDER = ("jackpot", "super_pairs", "top_three", "twenty_one_plus_three")

PAYOUT_WIN_LANDING_OFFSET_Y = -18


_BET_LABELS = dict(BET_TYPES)


def _ease_out_cubic(t):
    return 1 - (1 - t) ** 3


def _format_signed(amount):
    """£6 as +£6, -£6, or £0 -- fractional only if the amount actually has
    pence (a jackpot pool win can), same convention as Three Card Poker's
    own result panel."""
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
    return theme.FG


def _round_upfront_cost(bets, num_boxes):
    """Every bet placed is duplicated across however many boxes are in
    play -- see the box-count toggle -- so the upfront cost is simply the
    per-box total times the box count. Unlike Three Card Poker's Ante/Play
    relationship, nothing here needs a worst-case "could this be doubled
    later" reservation: Double/Split affordability is checked in the moment
    those actions are offered, not reserved for upfront (see the play
    screen, Phase 3)."""
    return sum(bets.values()) * num_boxes


class BlackjackFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.BG)
        self.app = app
        self.game = BlackjackGame()
        self.state = "betting"  # betting -> dealt -> resolved

        self.save_path = os.path.join(app.data_dir, STATE_FILENAME)
        saved = load_json(self.save_path, DEFAULT_STATE)
        saved_bets = saved.get("bets", DEFAULT_STATE["bets"])
        self.bets = {k: int(saved_bets.get(k, 0)) for k in BET_KEYS}
        self.selected_chip = int(saved.get("selected_chip", DEFAULT_STATE["selected_chip"]))
        self.num_boxes = int(saved.get("num_boxes", 1)) if saved.get("num_boxes") in (1, 2) else 1

        self.chip_canvases = {}
        self._jackpot_pulse_t = 0.0

        # Per-round play state -- reset fresh by _on_deal each round, read
        # by the play-screen drawing/animation methods below.
        self.round_bets = {}          # bets snapshot at deal time (self.bets can't change mid-round)
        self.num_boxes_in_round = 1
        self.active_box_idx = 0
        self.turn_queue = []
        self.summary: Optional[RoundSummary] = None
        self._reveal_count = None            # deal-in stagger position, or None once fully dealt
        self._deal_reveal_order = []
        self._dealer_display_count = None    # None during deal-in; set once the reveal/settle phase starts
        self._hole_revealed = False
        # True only for the actual span between deal-in+Insurance finishing
        # and the Dealer's turn starting -- gates the active-box highlight so
        # it doesn't flash on early, e.g. while cards are still dropping in.
        self._turns_active = False
        # Side bets (Super Pairs/21+3/Top 3/Jackpot) settle and pay out right
        # after the deal, before any action is offered -- same as a real
        # table. Once that animation's played, _draw_header_tokens stops
        # redrawing their chips (they're done, not still "live" bets) --
        # Insurance is unaffected, it's decided afterwards and drawn as its
        # own token regardless of this flag.
        self._side_bets_swept = False

        self._build_ui()
        self.app.jackpot.add_listener(self._on_jackpot_changed)
        self.jackpot_display.set_value(self.app.jackpot.raw_amount)
        self._pulse_jackpot()
        self._sanitize_bets(persist=False)
        self._show_betting_controls()

    # ------------------------------------------------------------------ build
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
        tk.Label(top_bar, text="Blackjack", bg=theme.BG_ELEVATED, fg=theme.ACCENT,
                 font=theme.font(16, weight="bold")).pack(side="left", padx=10)
        self.balance_lbl = tk.Label(top_bar, text="£0.00", bg=theme.BG_ELEVATED, fg=theme.WIN_COLOR,
                                     font=theme.font(12, weight="bold"))
        self.balance_lbl.pack(side="right", padx=20)
        theme.breadcrumb(top_bar, "blackjack", bg=theme.BG_ELEVATED).pack(side="right", padx=(6, 6))

        body = tk.Frame(self, bg=felt_theme["felt"])
        body.pack(fill="both", expand=True)

        content = tk.Frame(body, bg=felt_theme["felt"])
        content.place(relx=0.5, y=CONTENT_TOP_MARGIN, anchor="n")

        game_col = tk.Frame(content, bg=felt_theme["felt"])
        game_col.pack(side="left")

        paytable_col = tk.Frame(content, bg=felt_theme["felt"])
        paytable_col.pack(side="right", fill="y", padx=(10, 24), pady=10)

        self.jackpot_display = JackpotDisplay(
            paytable_col, rows=JACKPOT_PAYTABLE_ROWS, highlight_row=JACKPOT_PAYTABLE_HIGHLIGHT_ROW,
        )
        self.jackpot_display.pack(pady=(0, 14))
        self._build_paytable(paytable_col)

        self.canvas = tk.Canvas(game_col, bg=felt_theme["felt"], highlightthickness=0,
                                 width=CANVAS_WIDTH, height=CANVAS_HEIGHT)
        self.canvas.pack(padx=12, pady=(6, 2))

        self.result_lbl = tk.Label(
            game_col, text="Place your bets to continue.", bg=felt_theme["felt"], fg=theme.FG,
            font=theme.font(13, weight="bold"), wraplength=900, justify="center",
        )
        self.result_lbl.pack(pady=(0, 3))

        self.action_frame = tk.Frame(game_col, bg=felt_theme["felt"])
        self.action_frame.pack(pady=(8, 0))

        # --- betting-state controls: box-count toggle + Deal, side by side ---
        self.box_count_frame = tk.Frame(self.action_frame, bg=felt_theme["felt"])
        tk.Label(self.box_count_frame, text="Boxes:", bg=felt_theme["felt"], fg=theme.FG_DIM,
                 font=theme.font(9)).pack(side="left", padx=(0, 6))
        self.box1_btn = tk.Button(
            self.box_count_frame, text="1", font=theme.font(11, weight="bold"), relief="flat",
            padx=12, pady=6, cursor="hand2", highlightthickness=1, command=lambda: self._set_num_boxes(1),
        )
        self.box1_btn.pack(side="left", padx=(0, 4))
        self.box2_btn = tk.Button(
            self.box_count_frame, text="2", font=theme.font(11, weight="bold"), relief="flat",
            padx=12, pady=6, cursor="hand2", highlightthickness=1, command=lambda: self._set_num_boxes(2),
        )
        self.box2_btn.pack(side="left")

        self.deal_btn = tk.Button(
            self.action_frame, text="DEAL", bg=theme.ACCENT_DIM_BG, fg=theme.FG,
            font=theme.font(13, weight="bold"), relief="flat", padx=30, pady=10, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.ACCENT,
            command=self._on_deal,
        )

        # --- decision-state / round-over-state controls (Phase 3 wires these up) ---
        self.hit_btn = tk.Button(
            self.action_frame, text="HIT", bg=theme.ACCENT_DIM_BG, fg=theme.FG,
            font=theme.font(12, weight="bold"), relief="flat", padx=20, pady=9, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.ACCENT,
            command=self._on_hit,
        )
        self.stand_btn = tk.Button(
            self.action_frame, text="STAND", bg=theme.GREY_BTN_BG, fg=theme.FG,
            font=theme.font(12, weight="bold"), relief="flat", padx=20, pady=9, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.GREY_BTN_BORDER,
            command=self._on_stand,
        )
        self.double_btn = tk.Button(
            self.action_frame, text="DOUBLE", bg=theme.WARN_DIM_BG, fg=theme.FG,
            font=theme.font(12, weight="bold"), relief="flat", padx=20, pady=9, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.WARN,
            command=self._on_double,
        )
        self.split_btn = tk.Button(
            self.action_frame, text="SPLIT", bg=theme.ACCENT_DIM_BG, fg=theme.FG,
            font=theme.font(12, weight="bold"), relief="flat", padx=20, pady=9, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.ACCENT,
            command=self._on_split,
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

        self.chip_zone = tk.Frame(game_col, bg=felt_theme["felt"])
        self.chip_zone.pack(pady=(61, 0))

        self.chip_frame = tk.Frame(self.chip_zone, bg=felt_theme["felt"])
        tk.Label(
            self.chip_frame, text="Tap a chip, then tap a spot on the table to place it",
            bg=felt_theme["felt"], fg=theme.FG_DIM, font=theme.font(9),
        ).pack(pady=(0, 3))
        self.chip_row = tk.Frame(self.chip_frame, bg=felt_theme["felt"])
        self.chip_row.pack()
        for value, face, rim in CHIP_DENOMINATIONS:
            self._make_chip_button(self.chip_row, value, face, rim)

        self.total_frame = tk.Frame(self.chip_frame, bg=felt_theme["felt"])
        self.total_frame.pack(pady=(4, 0))
        self._total_normal_font = theme.font(12, weight="bold")
        self._total_strike_font = tkfont.Font(
            family=theme.mono_family(), size=12, weight="bold", overstrike=True,
        )
        self.total_lbl = tk.Label(
            self.total_frame, text="Total bet: £0", bg=felt_theme["felt"], fg=theme.ACCENT,
            font=self._total_normal_font,
        )
        self.total_lbl.pack(side="left")
        self.total_doubled_lbl = tk.Label(
            self.total_frame, text="", bg=felt_theme["felt"], fg=theme.ACCENT,
            font=self._total_normal_font,
        )
        self.total_doubled_lbl.pack(side="left", padx=(6, 0))

        self.clear_btn = tk.Button(
            self.chip_frame, text="Clear Bets", bg=theme.GREY_BTN_BG, fg=theme.FG_DIM,
            font=theme.font(9), relief="flat", padx=10, pady=4, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.GREY_BTN_BORDER,
            command=self._clear_bets,
        )
        self.clear_btn.pack(pady=(3, 0))

        self.payout_canvas = tk.Canvas(
            self.chip_zone, width=PAYOUT_PANEL_WIDTH, height=PAYOUT_PANEL_HEIGHT,
            bg=felt_theme["felt"], highlightthickness=0,
        )

        self.chip_frame.pack()
        self.chip_frame.update_idletasks()
        self.chip_zone.configure(
            width=max(self.chip_frame.winfo_reqwidth(), PAYOUT_PANEL_WIDTH),
            height=max(self.chip_frame.winfo_reqheight(), PAYOUT_PANEL_HEIGHT),
        )
        self.chip_zone.pack_propagate(False)

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
        theme.recessed_panel(canvas, 0, 0, w, h, title="PAYTABLE", title_font_size=14)

        y = 40
        canvas.create_text(20, y, text="Blackjack", fill=theme.FG, font=theme.font(9), anchor="w")
        canvas.create_text(w - 20, y, text="3:2", fill=theme.WIN_COLOR,
                            font=theme.font(9, weight="bold"), anchor="e")
        y += 22
        canvas.create_line(20, y, w - 20, y, fill=theme.BORDER)
        y += 12

        for i, (title, rows) in enumerate(PAYTABLE_SECTIONS):
            if i:
                canvas.create_line(20, y, w - 20, y, fill=theme.BORDER)
                y += 12
            y = self._draw_paytable_section(canvas, y, title, rows)

    def _draw_paytable_section(self, canvas, y, title, rows):
        w = PAYTABLE_WIDTH
        canvas.create_text(20, y, text=title, fill=theme.ACCENT,
                            font=theme.font(10, weight="bold"), anchor="w")
        y += 20
        for label, multiplier in rows:
            canvas.create_text(20, y, text=label, fill=theme.FG, font=theme.font(9), anchor="w")
            canvas.create_text(w - 20, y, text=f"{multiplier}:1", fill=theme.WIN_COLOR,
                                font=theme.font(9, weight="bold"), anchor="e")
            y += 19
        return y

    # ------------------------------------------------------------------ betting table
    def _draw_table(self):
        self.canvas.delete("all")
        cx = CANVAS_WIDTH / 2

        self._draw_spot_rect(
            "blackjack", cx, BLACKJACK_SPOT_CY, BLACKJACK_SPOT_W, BLACKJACK_SPOT_H,
            "BLACKJACK", textured=True,
        )
        self._draw_spot_circle("super_pairs", LEFT_CX, SUPER_PAIRS_CY, MAIN_SIDE_R, "SUPER PAIRS")
        self._draw_spot_circle("twenty_one_plus_three", RIGHT_CX, TWENTY_ONE_PLUS_THREE_CY, MAIN_SIDE_R, "21+3")
        self._draw_spot_jackpot(LEFT_CX, JACKPOT_CY, FLAG_R)
        self._draw_spot_top_three(RIGHT_CX, TOP_THREE_CY, FLAG_R)

        self._draw_rules_button(RULES_BUTTON_CX, RULES_BUTTON_CY)

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
            self, "♠ Blackjack -- Rules",
            [
                ("GAMEPLAY", [
                    "**Betting:** Place a Blackjack wager (mandatory) plus Super Pairs, 21+3, "
                    "Top 3 (needs a 21+3 bet in play) and Jackpot side bets (optional). "
                    "Choose 1 or 2 boxes -- 2 boxes plays identical bets on two independent hands.",
                    "**Dealing:** Each box gets 2 cards; the Dealer gets an up-card and a hidden "
                    "hole card. Side bets settle immediately off the Dealer's up-card.",
                    "**Peek:** An Ace or 10-value up-card checks the Dealer's hole card. An "
                    "immediate Dealer Blackjack ends the round before any box acts. An Ace "
                    "up-card also offers Insurance (up to half your bet, pays 2:1).",
                    "**Your turn:** Hit, Stand, Double (first two cards only), or Split (equal-"
                    "value first two cards, up to 4 splits). Split Aces get exactly one more "
                    "card each and then stand automatically.",
                    "**Dealer:** Draws to 17, stands on all 17s, then every hand is settled.",
                    "**Payouts:** Blackjack pays 3:2. A win pays 1:1. A push returns your stake.",
                ]),
                ("SIDE BETS", [
                    "**Super Pairs:** your own first two cards -- Any Pair 5:1, Prime Pair "
                    "(same colour) 10:1, Suited Pair 25:1, Suited Trips 50:1.",
                    "**21+3:** your first two cards plus the Dealer's up-card, as a Three Card "
                    "Poker hand -- Flush or better pays a flat 9:1.",
                    "**Top 3:** the same three cards -- Three of a Kind 90:1, Straight Flush "
                    "180:1, Three of a Kind Suited 270:1.",
                    "**Jackpot:** flat £1, shares the same progressive pool as Three Card Poker "
                    "-- see the paytable panel for what wins it.",
                ]),
            ],
        )

    def _draw_spot_circle(self, key, cx, cy, r, label):
        tag = f"spot_{key}"
        amount = self.bets[key]
        felt_theme = self.app.settings.theme()
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                 fill=felt_theme["felt_dark"], outline=felt_theme["accent"], width=2, tags=(tag,))
        self.canvas.create_text(cx, cy - r - 12, text=label, fill=theme.FG,
                                 font=theme.font(9, weight="bold"), tags=(tag,))
        if amount:
            draw_chip_stack(self.canvas, tag, cx, cy, amount, CHIP_LAYER_MAX_R)
        else:
            self.canvas.create_text(cx, cy, text="tap to bet", fill=theme.FG_DIM,
                                     font=theme.font(9, weight="bold"), tags=(tag,))
        self._bind_spot(tag, key)

    def _draw_spot_rect(self, key, cx, cy, width, height, label, textured=False):
        tag = f"spot_{key}"
        amount = self.bets[key]
        felt_theme = self.app.settings.theme()
        x1, y1, x2, y2 = cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2
        theme.rounded_rect(self.canvas, x1, y1, x2, y2, radius=10, fill=felt_theme["felt_dark"],
                            outline=felt_theme["accent"], width=2, tags=(tag,))
        if textured:
            self._draw_felt_texture(x1, y1, x2, y2, felt_theme, tag)
        self.canvas.create_text(cx, y1 + 18, text=label, fill=theme.FG,
                                 font=theme.font(11, weight="bold"), tags=(tag,))
        stack_cy = cy + 16
        if amount:
            draw_chip_stack(self.canvas, tag, cx, stack_cy, amount, CHIP_LAYER_MAX_R)
        else:
            self.canvas.create_text(cx, stack_cy, text="tap to bet", fill=theme.FG_DIM,
                                     font=theme.font(10, weight="bold"), tags=(tag,))
        self._bind_spot(tag, key)

    def _draw_felt_texture(self, x1, y1, x2, y2, felt_theme, tag):
        inset = 9
        step = 9
        color = _lerp_color(felt_theme["felt_dark"], felt_theme["felt"], 0.4)
        ix1, iy1, ix2, iy2 = x1 + inset, y1 + inset, x2 - inset, y2 - inset
        c = ix1 - iy2
        c_max = ix2 - iy1
        while c <= c_max:
            xs = max(ix1, iy1 + c)
            xe = min(ix2, iy2 + c)
            if xs < xe:
                self.canvas.create_line(xs, xs - c, xe, xe - c, fill=color, width=1, tags=(tag,))
            c += step

    def _draw_spot_jackpot(self, cx, cy, r):
        """Flat £1 on/off toggle, identical in look/behaviour to Three Card
        Poker's own jackpot spot (same breathing-glow pulse) -- makes sense
        visually, since it's literally the same shared pool."""
        tag = "spot_jackpot"
        felt_theme = self.app.settings.theme()
        placed = bool(self.bets["jackpot"])
        if placed:
            t = 0.5 + 0.5 * math.sin(self._jackpot_pulse_t)
            outline_color = _lerp_color(felt_theme["felt_dark"], felt_theme["accent"], t)
        else:
            outline_color = felt_theme["accent"]
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=felt_theme["felt_dark"],
                                 outline=outline_color, width=3, tags=(tag,))
        self.canvas.create_text(cx, cy - r - 12, text="JACKPOT", fill=theme.FG,
                                 font=theme.font(9, weight="bold"), tags=(tag,))
        if placed:
            from ui.chips import CHIP_COLORS_BY_VALUE
            face, rim = CHIP_COLORS_BY_VALUE[1]
            token_r = r - 8
            self.canvas.create_oval(cx - token_r, cy - token_r, cx + token_r, cy + token_r,
                                     fill=face, outline=rim, width=2, tags=(tag,))
            self.canvas.create_text(cx, cy, text="£1", fill="#ffffff",
                                     font=theme.font(10, weight="bold"), tags=(tag,))
        else:
            self.canvas.create_text(cx, cy, text="tap\n£1", fill=theme.FG_DIM,
                                     font=theme.font(8, weight="bold"), justify="center", tags=(tag,))
        self._bind_spot(tag, "jackpot")

    def _draw_spot_top_three(self, cx, cy, r):
        """Top 3 can only be played alongside a 21+3 bet -- drawn dim/dashed
        and unclickable until 21+3 has something on it, per the reference
        rules ("to play this bet, a player must have a 21+3 wager")."""
        tag = "spot_top_three"
        felt_theme = self.app.settings.theme()
        enabled = self.bets["twenty_one_plus_three"] > 0
        amount = self.bets["top_three"]
        if enabled:
            theme.rounded_rect(self.canvas, cx - r, cy - r, cx + r, cy + r, radius=r,
                                fill=felt_theme["felt_dark"], outline=felt_theme["accent"], width=2, tags=(tag,))
        else:
            theme.dashed_rect(self.canvas, cx - r, cy - r, cx + r, cy + r, radius=r,
                               fill=felt_theme["felt_dark"], outline=theme.GREY_BTN_BORDER, tags=(tag,))
        self.canvas.create_text(cx, cy - r - 12, text="TOP 3", fill=theme.FG if enabled else theme.GREY_BTN_TEXT,
                                 font=theme.font(9, weight="bold"), tags=(tag,))
        if amount:
            draw_chip_stack(self.canvas, tag, cx, cy, amount, FLAG_R - 2)
        else:
            label = "tap to\nbet" if enabled else "needs\n21+3"
            fg = theme.FG_DIM if enabled else theme.GREY_BTN_TEXT
            self.canvas.create_text(cx, cy, text=label, fill=fg,
                                     font=theme.font(8, weight="bold"), justify="center", tags=(tag,))
        if enabled:
            self._bind_spot(tag, "top_three")

    def _bind_spot(self, tag, key):
        self.canvas.tag_bind(tag, "<Button-1>", lambda e, k=key: self._on_place_chip(k))
        self.canvas.tag_bind(tag, "<Enter>", lambda e: self.canvas.configure(cursor="hand2"))
        self.canvas.tag_bind(tag, "<Leave>", lambda e: self.canvas.configure(cursor=""))

    def _on_jackpot_changed(self, raw_amount):
        self.jackpot_display.set_value(raw_amount)

    def _pulse_jackpot(self):
        if self.state == "betting" and self.bets.get("jackpot"):
            self._jackpot_pulse_t += 0.06
            self._draw_table()
        self.after(33, self._pulse_jackpot)

    # ------------------------------------------------------------------ state transitions
    def _show_betting_controls(self):
        self.canvas.configure(height=BETTING_CANVAS_HEIGHT)
        self.result_lbl.pack(pady=BETTING_RESULT_LBL_PADY)
        for w in self.action_frame.pack_slaves():
            w.pack_forget()
        self.box_count_frame.pack(side="left", padx=(0, 16))
        self.deal_btn.pack(side="left")
        self._refresh_box_buttons()
        self.action_frame.pack(pady=BETTING_ACTION_FRAME_PADY)
        self.payout_canvas.pack_forget()
        self.chip_frame.pack(pady=CHIP_FRAME_PADY)
        self._draw_table()
        self._update_total()

    def _show_no_controls(self):
        self.canvas.configure(height=CANVAS_HEIGHT)
        self.result_lbl.pack(pady=PLAY_RESULT_LBL_PADY)
        self.chip_frame.pack_forget()
        self.payout_canvas.pack_forget()
        for w in self.action_frame.pack_slaves():
            w.pack_forget()
        self.action_frame.pack(pady=(8, 0))

    def _show_round_over_controls(self):
        self.chip_frame.pack_forget()
        for w in self.action_frame.pack_slaves():
            w.pack_forget()
        self.action_frame.pack(pady=(8, 0))
        self.new_deal_btn.pack(side="left", padx=8)
        self.change_bets_btn.pack(side="left", padx=8)
        self.payout_canvas.pack(pady=(10, 0))

    def _show_decision_controls(self):
        self.chip_frame.pack_forget()
        self.payout_canvas.pack_forget()
        for w in self.action_frame.pack_slaves():
            w.pack_forget()
        self.action_frame.pack(pady=(8, 0))

        box = self.game.boxes[self.active_box_idx]
        hand = box.active_hand()
        # Only ever called from _advance_turn/_continue_after_action once
        # they've already confirmed this box has a live hand -- narrows the
        # type for everything below rather than actually guarding anything.
        assert hand is not None
        self.hit_btn.pack(side="left", padx=6)
        self.stand_btn.pack(side="left", padx=6)

        if hand.can_double:
            affordable = self.app.finance.can_afford(hand.bet)
            self.double_btn.pack(side="left", padx=6)
            self.double_btn.configure(
                state="normal" if affordable else "disabled",
                bg=theme.WARN_DIM_BG if affordable else theme.GREY_BTN_BG,
                fg=theme.FG if affordable else theme.GREY_BTN_TEXT,
            )
        if hand.can_split(box.split_count()):
            affordable = self.app.finance.can_afford(hand.bet)
            self.split_btn.pack(side="left", padx=6)
            self.split_btn.configure(
                state="normal" if affordable else "disabled",
                bg=theme.ACCENT_DIM_BG if affordable else theme.GREY_BTN_BG,
                fg=theme.FG if affordable else theme.GREY_BTN_TEXT,
            )

    def _refresh_box_buttons(self):
        for n, btn in ((1, self.box1_btn), (2, self.box2_btn)):
            selected = n == self.num_boxes
            btn.configure(
                bg=theme.ACCENT_DIM_BG if selected else theme.GREY_BTN_BG,
                fg=theme.ACCENT if selected else theme.FG_DIM,
                highlightbackground=theme.ACCENT if selected else theme.GREY_BTN_BORDER,
            )

    def _set_num_boxes(self, n):
        if n == self.num_boxes:
            return
        if _round_upfront_cost(self.bets, n) > self.app.finance.balance + 1e-9:
            dialogs.info(
                self, "$ boxes --check-funds",
                "You don't have enough balance to duplicate these bets across 2 boxes.",
                accent=theme.WARN,
            )
            return
        self.num_boxes = n
        self._refresh_box_buttons()
        self._update_total()
        self._persist_state()

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
        trial_bets["jackpot"] = 0 if self.bets["jackpot"] else int(JACKPOT_BET_AMOUNT)
        if trial_bets["jackpot"] and _round_upfront_cost(trial_bets, self.num_boxes) > self.app.finance.balance + 1e-9:
            dialogs.info(
                self, "$ jackpot --check-funds",
                "You don't have enough balance to place the £1 Jackpot bet.",
                accent=theme.WARN,
            )
            return
        self.bets = trial_bets
        self._draw_table()
        self._update_total()
        self._persist_state()

    def _adjust_bet(self, key, delta):
        if key == "top_three" and self.bets["twenty_one_plus_three"] == 0:
            dialogs.info(
                self, "$ top3 --require-21+3",
                "Top 3 needs a 21+3 bet in play first.", accent=theme.WARN,
            )
            return
        trial_bets = dict(self.bets)
        trial_bets[key] += delta
        if _round_upfront_cost(trial_bets, self.num_boxes) > self.app.finance.balance + 1e-9:
            dialogs.info(
                self, "$ bet --check-funds", "You don't have enough balance to place that chip.",
                accent=theme.WARN,
            )
            return
        self.bets = trial_bets
        if key == "twenty_one_plus_three" and trial_bets[key] == 0:
            # Dependent bet -- Top 3 can't stay in play without 21+3 under it.
            self.bets["top_three"] = 0
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
        single = sum(self.bets.values())
        if self.num_boxes == 2:
            self.total_lbl.configure(text=f"Total bet: £{single}", font=self._total_strike_font, fg=theme.FG_DIM)
            self.total_doubled_lbl.configure(text=f"→ £{single * 2}", font=self._total_normal_font, fg=theme.ACCENT)
        else:
            self.total_lbl.configure(text=f"Total bet: £{single}", font=self._total_normal_font, fg=theme.ACCENT)
            self.total_doubled_lbl.configure(text="")

    def _persist_state(self):
        save_json(self.save_path, {"bets": self.bets, "selected_chip": self.selected_chip, "num_boxes": self.num_boxes})

    def _sanitize_bets(self, persist=True):
        changed = False
        if _round_upfront_cost(self.bets, self.num_boxes) > self.app.finance.balance:
            self.bets = {k: 0 for k in BET_KEYS}
            changed = True
        if self.bets["twenty_one_plus_three"] == 0 and self.bets["top_three"] != 0:
            self.bets["top_three"] = 0
            changed = True
        if changed and persist:
            self._persist_state()

    # ------------------------------------------------------------------ dealing
    def _on_deal(self):
        if sum(self.bets.values()) <= 0:
            dialogs.info(self, "$ deal --require-bet", "You must place a Blackjack bet to deal.", accent=theme.WARN)
            return
        if not self.app.finance.can_afford(_round_upfront_cost(self.bets, self.num_boxes)):
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

        self.round_bets = dict(self.bets)
        self.num_boxes_in_round = self.num_boxes
        total_upfront = _round_upfront_cost(self.bets, self.num_boxes)
        self.app.finance.place_wager(total_upfront)
        self._refresh_balance()

        side = dict(
            super_pairs_bet=self.bets["super_pairs"],
            twenty_one_plus_three_bet=self.bets["twenty_one_plus_three"],
            top_three_bet=self.bets["top_three"],
            jackpot_bet=self.bets["jackpot"],
        )
        main_bets = [self.bets["blackjack"]] * self.num_boxes
        side_bets_per_box = [dict(side) for _ in range(self.num_boxes)]
        self.game.deal(main_bets, side_bets_per_box, jackpot_amount=self.app.jackpot.amount)

        self.state = "dealt"
        self.summary = None
        self.active_box_idx = 0
        self.turn_queue = []
        self._turns_active = False
        self._side_bets_swept = False
        self._dealer_display_count = None
        self._hole_revealed = False
        self.result_lbl.configure(text="Dealing...", fg=theme.FG)
        self._show_no_controls()
        self._animate_deal_in()

    # ------------------------------------------------------------------ deal-in
    def _build_deal_order(self):
        """Player-first-card, player-first-card, ... Dealer-up-card, then
        the same for everyone's second card -- the Dealer's own second card
        (the hole card) is dealt face-down in this pass too, just not
        flipped up until _flip_hole_card, well after betting/dealing."""
        order = []
        for c in range(2):
            for b in range(self.num_boxes_in_round):
                order.append(("box", b, c))
            order.append(("dealer", None, c))
        return order

    def _card_revealed(self, kind, box_idx, card_idx):
        if self._reveal_count is None:
            return True
        target = (kind, box_idx, card_idx)
        try:
            idx = self._deal_reveal_order.index(target)
        except ValueError:
            return True  # a card dealt after deal-in finished (a hit/split/double) -- always shown
        return idx < self._reveal_count

    def _animate_deal_in(self):
        self._deal_reveal_order = self._build_deal_order()
        self._reveal_count = 0
        self._redraw_play_table()

        def reveal(i):
            self._reveal_count = i + 1
            self._redraw_play_table()

        total = len(self._deal_reveal_order)
        self._run_staggered(total, 110, reveal)
        animated = self.app.settings.get("animations_enabled")
        delay = total * 110 + 260 if animated else 30
        self.after(delay, self._on_deal_in_done)

    def _on_deal_in_done(self):
        self._reveal_count = None
        self._redraw_play_table()
        self._animate_side_bet_payouts()

    # ------------------------------------------------------------------ side-bet payout (immediate)
    def _side_bet_payout_items(self):
        """Super Pairs/21+3/Top 3/Jackpot all settle on the initial deal
        alone (see BlackjackGame._resolve_side_bets), so unlike the main
        hands they're already fully resolved the instant dealing finishes --
        this pays them out right here, before Insurance or any action, the
        same way a real table would. Insurance itself isn't included: it
        isn't even decided yet at this point in the flow."""
        items = []
        for box_idx, box in enumerate(self.game.boxes):
            for i, (key, _label) in enumerate(self._header_tokens(box_idx)):
                if key == "insurance":
                    continue
                cx, cy = self._header_token_pos(box_idx, i)
                bet = getattr(box, f"{key}_bet")
                ret = box.side_bet_results.get(key, 0.0)
                items.append(dict(cx=cx, cy=cy, bet=bet, ret=ret, max_r=SIDE_BET_TOKEN_R,
                                   tag=f"tokenchip_{box_idx}_{key}"))
        return items

    def _animate_side_bet_payouts(self):
        items = self._side_bet_payout_items()
        losers = [it for it in items if it["bet"] > 0 and it["ret"] < it["bet"] - 1e-9]
        winners = [it for it in items if it["ret"] > it["bet"] + 1e-9]

        def after_losers():
            self._side_bets_swept = True
            fns = [(lambda cb, it=it: self._chip_move_in(it, cb)) for it in winners]
            if not fns:
                self._offer_insurance_for_box(0)
                return
            self._run_sequential(fns, lambda: self._offer_insurance_for_box(0))

        if not losers:
            after_losers()
            return
        # "All losing bets are taken simultaneously" -- every losing side
        # bet slides away at once, not one after another (contrast with the
        # winners just below, paid out individually/sequentially).
        self._run_parallel([(lambda cb, it=it: self._chip_move_away(it, cb)) for it in losers], after_losers)

    # ------------------------------------------------------------------ insurance
    def _offer_insurance_for_box(self, idx):
        if not self.game.insurance_offered or idx >= self.num_boxes_in_round:
            self._after_insurance_decided()
            return
        box = self.game.boxes[idx]
        amount = round(box.main_bet / 2, 2)
        if not self.app.finance.can_afford(amount):
            self._offer_insurance_for_box(idx + 1)
            return
        which = f"Box {idx + 1}" if self.num_boxes_in_round == 2 else "your hand"
        take = dialogs.confirm(
            self, "$ insurance --offer",
            f"The Dealer is showing an Ace. Insure {which} for £{amount:.2f}? "
            "Pays 2:1 if the Dealer has Blackjack, otherwise it's lost.",
            confirm_text="Insure",
        )
        if take:
            self.app.finance.place_wager(amount)
            self.game.take_insurance(idx, amount)
            self._refresh_balance()
            self._redraw_play_table()
        self._offer_insurance_for_box(idx + 1)

    def _after_insurance_decided(self):
        if self.game.dealer_blackjack:
            self._begin_dealer_turn()
        else:
            # Box 1 plays before Box 2.
            self.turn_queue = [0, 1] if self.num_boxes_in_round == 2 else [0]
            self._advance_turn()

    # ------------------------------------------------------------------ turns
    def _advance_turn(self):
        while self.turn_queue:
            idx = self.turn_queue[0]
            if self.game.boxes[idx].all_done():
                self.turn_queue.pop(0)
                continue
            self.active_box_idx = idx
            self._turns_active = True
            which = f"Box {idx + 1}'s" if self.num_boxes_in_round == 2 else "Your"
            self.result_lbl.configure(text=f"{which} turn.", fg=theme.FG)
            self._redraw_play_table()
            self._show_decision_controls()
            return
        self._turns_active = False
        self._begin_dealer_turn()

    def _continue_after_action(self):
        box = self.game.boxes[self.active_box_idx]
        if box.all_done():
            if self.turn_queue and self.turn_queue[0] == self.active_box_idx:
                self.turn_queue.pop(0)
            self._redraw_play_table()
            self._advance_turn()
        else:
            self._redraw_play_table()
            self._show_decision_controls()

    def _on_hit(self):
        self.game.hit(self.active_box_idx)
        self._continue_after_action()

    def _on_stand(self):
        self.game.stand(self.active_box_idx)
        self._continue_after_action()

    def _on_double(self):
        hand = self.game.boxes[self.active_box_idx].active_hand()
        # Only reachable via double_btn, which _show_decision_controls only
        # ever packs while there's a live active hand to double.
        assert hand is not None
        if not self.app.finance.can_afford(hand.bet):
            dialogs.info(self, "$ double --check-funds",
                         "You don't have enough balance to double this hand.", accent=theme.WARN)
            return
        self.app.finance.place_wager(hand.bet)
        self.game.double(self.active_box_idx)
        self._refresh_balance()
        self._continue_after_action()

    def _on_split(self):
        hand = self.game.boxes[self.active_box_idx].active_hand()
        # Only reachable via split_btn, which _show_decision_controls only
        # ever packs while there's a live active hand to split.
        assert hand is not None
        if not self.app.finance.can_afford(hand.bet):
            dialogs.info(self, "$ split --check-funds",
                         "You don't have enough balance to split this hand.", accent=theme.WARN)
            return
        self.app.finance.place_wager(hand.bet)
        self.game.split(self.active_box_idx)
        self._refresh_balance()
        self._continue_after_action()

    # ------------------------------------------------------------------ dealer reveal / settle
    def _begin_dealer_turn(self):
        self._show_no_controls()
        self.result_lbl.configure(text="Dealer's turn.", fg=theme.FG)
        self.summary = self.game.settle()  # plays the Dealer out synchronously; animated below after the fact
        self._dealer_display_count = 2
        self._hole_revealed = False
        self._redraw_play_table()
        self._flip_hole_card()

    def _flip_hole_card(self):
        hole_card = self.game.dealer_cards[1]
        n = self._dealer_display_count

        def done():
            self._hole_revealed = True
            self.canvas.delete("hole_flip")
            self._redraw_play_table()
            self.after(200, self._reveal_extra_dealer_cards)

        if not self.app.settings.get("animations_enabled"):
            done()
            return

        cx = self._dealer_card_x(1, n) + CARD_WIDTH / 2

        def frame(t):
            squeeze = abs(1 - 2 * t)
            w = max(6, CARD_WIDTH * squeeze)
            x = cx - w / 2
            self.canvas.delete("hole_flip")
            if squeeze > 0.35:
                if t >= 0.5:
                    draw_card(self.canvas, x, DEALER_Y, hole_card, width=w, tags=("hole_flip",))
                else:
                    draw_card_back(self.canvas, x, DEALER_Y, self._current_felt,
                                    self.app.settings.theme()["accent"], width=w, tags=("hole_flip",))
            else:
                self.canvas.create_rectangle(x, DEALER_Y, x + w, DEALER_Y + CARD_HEIGHT,
                                              fill="#fdfdf5", outline="#222222", tags=("hole_flip",))

        self.canvas.delete("dealer_card_1")
        self._animate(360, frame, on_done=done)

    def _reveal_extra_dealer_cards(self):
        # Only ever reached after _begin_dealer_turn has already set this to
        # an int (2) -- never called while it's still None (that's only true
        # during deal-in, well before the Dealer's own turn starts).
        assert self._dealer_display_count is not None
        total = len(self.game.dealer_cards)
        remaining = total - self._dealer_display_count
        if remaining <= 0:
            self._start_payout_sequence()
            return

        def reveal_next(i):
            # Re-asserted here too -- a nested closure, so the outer assert's
            # narrowing doesn't carry into it.
            assert self._dealer_display_count is not None
            self._dealer_display_count += 1
            self._redraw_play_table()

        self._run_staggered(remaining, 260, reveal_next)
        animated = self.app.settings.get("animations_enabled")
        delay = remaining * 260 + 220 if animated else 30
        self.after(delay, self._start_payout_sequence)

    # ------------------------------------------------------------------ payout animation
    def _payout_items(self):
        """Hand stakes + Insurance only -- the side bets (Super Pairs/21+3/
        Top 3/Jackpot) already settled and paid out right after the deal
        (see _animate_side_bet_payouts), well before this end-of-round
        sequence runs, so they don't appear here a second time."""
        # Only ever called from _start_payout_sequence, itself only reached
        # after _begin_dealer_turn has already set this via game.settle().
        assert self.summary is not None
        items = []
        for box_idx in range(len(self.game.boxes)):
            box_result = self.summary.boxes[box_idx]
            _, x2, _, ys = self._hand_positions(box_idx)
            chip_cx = x2 - 56
            for hand_idx, hand_result in enumerate(box_result.hands):
                items.append(dict(
                    cx=chip_cx, cy=ys[hand_idx], bet=hand_result.bet, ret=hand_result.payout,
                    max_r=HAND_CHIP_R, tag=f"handchip_{box_idx}_{hand_idx}",
                ))
            if box_result.insurance_bet > 0:
                i = len(self._active_side_bet_keys())  # Insurance is always the last header token, see _header_tokens
                cx, cy = self._header_token_pos(box_idx, i)
                items.append(dict(cx=cx, cy=cy, bet=box_result.insurance_bet, ret=box_result.insurance_return,
                                   max_r=SIDE_BET_TOKEN_R, tag=f"tokenchip_{box_idx}_insurance"))
        return items

    def _chip_move_away(self, item, on_done):
        travel_tag = f"travel_{item['tag']}"

        def frame(t):
            cx = item["cx"] + (DEALER_CENTER_X - item["cx"]) * t
            cy = item["cy"] + (DEALER_CENTER_Y - item["cy"]) * t
            r = item["max_r"] * (1 - t)
            self.canvas.delete(travel_tag)
            if r > 1:
                draw_chip_stack(self.canvas, travel_tag, cx, cy, item["bet"], r)

        def done():
            self.canvas.delete(travel_tag)
            self.canvas.delete(item["tag"])
            on_done()

        self.canvas.delete(item["tag"])
        self._animate(420, frame, on_done=done)

    def _chip_move_in(self, item, on_done):
        win_amount = item["ret"] - item["bet"]
        if win_amount <= 0:
            on_done()
            return
        travel_tag = f"travelwin_{item['tag']}"
        landing_cy = item["cy"] + PAYOUT_WIN_LANDING_OFFSET_Y

        def frame(t):
            cx = DEALER_CENTER_X + (item["cx"] - DEALER_CENTER_X) * t
            cy = DEALER_CENTER_Y + (landing_cy - DEALER_CENTER_Y) * t
            r = item["max_r"] * t
            self.canvas.delete(travel_tag)
            if r > 1:
                draw_chip_stack(self.canvas, travel_tag, cx, cy, win_amount, r)

        # Deliberately doesn't delete travel_tag once it lands -- like Three
        # Card Poker's own win chips, it stays sitting there (the grown-in
        # win amount, just above the original stake) until whatever redraws
        # next reconstructs the resting state itself (see _draw_header_tokens
        # for side bets, or a fresh deal for hands) -- not because this tag
        # is expected to survive indefinitely on its own.
        self._animate(420, frame, on_done=on_done)

    def _animate_payouts(self, on_done):
        items = self._payout_items()
        losers = [it for it in items if it["bet"] > 0 and it["ret"] < it["bet"] - 1e-9]
        winners = [it for it in items if it["ret"] > it["bet"] + 1e-9]
        fns = [(lambda cb, it=it: self._chip_move_away(it, cb)) for it in losers]
        fns += [(lambda cb, it=it: self._chip_move_in(it, cb)) for it in winners]
        if not fns:
            on_done()
            return
        self._run_sequential(fns, on_done)

    def _start_payout_sequence(self):
        self._show_no_controls()
        self._animate_payouts(self._on_round_settled)

    # ------------------------------------------------------------------ settle / result
    def _record_stats(self, summary):
        gs = self.app.game_stats
        for box_result in summary.boxes:
            for hand in box_result.hands:
                gs.record_bet(GAME_KEY, "blackjack", hand.bet, hand.payout)
                gs.record_hand(GAME_KEY, hand.outcome)
            if box_result.insurance_bet > 0:
                gs.record_bet(GAME_KEY, "insurance", box_result.insurance_bet, box_result.insurance_return)
            for key, ret in box_result.side_bet_results.items():
                gs.record_bet(GAME_KEY, key, getattr(box_result, f"{key}_bet"), ret)

    def _on_round_settled(self):
        # Only ever reached at the end of the payout-animation chain kicked
        # off by _begin_dealer_turn, which has already set this.
        assert self.summary is not None
        summary = self.summary
        self._record_stats(summary)
        self.app.finance.add_return(summary.total_returned)
        self.app.finance.record_round_played(summary.net_result)
        self.app.game_stats.record_round_net(GAME_KEY, summary.net_result)
        if summary.jackpot_pool_won:
            self.app.jackpot.win()
        self._refresh_balance()
        self.app.on_balance_changed()
        self._show_result(summary)
        self._draw_payout_panel(summary)
        self._show_round_over_controls()
        self.state = "resolved"

    def _show_result(self, summary):
        parts = []
        for i, box_result in enumerate(summary.boxes):
            prefix = f"Box {i + 1}: " if self.num_boxes_in_round == 2 else ""
            parts.append(prefix + "/".join(h.outcome for h in box_result.hands))
        headline = ("Dealer Blackjack -- " if summary.dealer_blackjack else "") + "   ".join(parts)
        self.result_lbl.configure(text=headline, fg=_net_color(summary.net_result))

    def _payout_rows(self, summary):
        rows = []
        for i, box_result in enumerate(summary.boxes):
            prefix = f"Box {i + 1} " if self.num_boxes_in_round == 2 else ""
            for h_i, hand in enumerate(box_result.hands):
                suffix = f" (hand {h_i + 1})" if len(box_result.hands) > 1 else ""
                rows.append((f"{prefix}Blackjack{suffix}", hand.payout - hand.bet))
            if box_result.insurance_bet > 0:
                rows.append((f"{prefix}Insurance", box_result.insurance_return - box_result.insurance_bet))
            for key, ret in box_result.side_bet_results.items():
                wagered = getattr(box_result, f"{key}_bet")
                rows.append((f"{prefix}{_BET_LABELS.get(key, key)}", ret - wagered))
        return rows

    def _draw_payout_panel(self, summary):
        canvas = self.payout_canvas
        canvas.delete("all")
        w, h = PAYOUT_PANEL_WIDTH, PAYOUT_PANEL_HEIGHT
        theme.recessed_panel(canvas, 0, 0, w, h, title="ROUND RESULT")
        y = 42
        for label, net in self._payout_rows(summary):
            canvas.create_text(20, y, text=label, fill=theme.FG, font=theme.font(10), anchor="w")
            canvas.create_text(w - 20, y, text=_format_signed(net), fill=_net_color(net),
                                font=theme.font(10, weight="bold"), anchor="e")
            y += 19
        y += 8
        canvas.create_line(20, y, w - 20, y, fill=theme.BORDER)
        y += 20
        canvas.create_text(20, y, text="Round Net", fill=theme.FG, font=theme.font(11, weight="bold"), anchor="w")
        canvas.create_text(w - 20, y, text=_format_signed(summary.net_result), fill=_net_color(summary.net_result),
                            font=theme.font(11, weight="bold"), anchor="e")

    def _new_deal(self):
        """New Deal: re-deals immediately with the same bets/box count as
        last round -- _on_deal reads straight from self.bets/self.num_boxes,
        which round-over never clears, and does its own affordability check."""
        self._on_deal()

    def _new_round(self):
        self.state = "betting"
        self.result_lbl.configure(text="Place your bets to continue.", fg=theme.FG)
        self._sanitize_bets()
        self._show_betting_controls()

    # ------------------------------------------------------------------ play-screen drawing
    def _box_x1x2(self, idx):
        x1 = BOX_MARGIN_X + idx * (BOX_W + BOX_GAP)
        return x1, x1 + BOX_W

    def _active_side_bet_keys(self):
        return [k for k in SIDE_BET_ORDER if self.round_bets.get(k, 0) > 0]

    def _header_tokens(self, box_idx):
        """Ordered list of (key, label) for every side-bet/insurance token
        this box's header row needs this round -- shared by the drawing code
        and by _payout_items, so the two positions can never drift apart."""
        tokens = [(k, SIDE_BET_LABELS[k]) for k in self._active_side_bet_keys()]
        if box_idx < len(self.game.boxes) and self.game.boxes[box_idx].insurance_bet > 0:
            tokens.append(("insurance", "INS"))
        return tokens

    def _header_token_pos(self, box_idx, i):
        # 44px apart -- wide enough that even the widest label ("21+3")
        # clears its neighbour's chip, with all 5 possible tokens (4 side
        # bets + Insurance) still comfortably inside BOX_W.
        x1, _ = self._box_x1x2(box_idx)
        return x1 + 26 + i * 44, BOX_TOP + BOX_HEADER_H + 16

    def _hand_positions(self, box_idx):
        x1, x2 = self._box_x1x2(box_idx)
        box = self.game.boxes[box_idx] if box_idx < len(self.game.boxes) else None
        n = len(box.hands) if box else 1
        has_tokens = bool(self._header_tokens(box_idx))
        header_bottom = BOX_TOP + BOX_HEADER_H + (BOX_SIDE_BET_ROW_H if has_tokens else 0)
        available = BOX_TOP + BOX_HEIGHT - header_bottom - 6
        row_h = min(HAND_ROW_H, max(34, available / n))
        ys = [header_bottom + row_h * (i + 0.5) for i in range(n)]
        return x1, x2, row_h, ys

    def _draw_dealer_mat(self):
        felt_theme = self.app.settings.theme()
        theme.rounded_rect(self.canvas, DEALER_MAT_X1, DEALER_MAT_TOP, DEALER_MAT_X2, DEALER_MAT_BOTTOM,
                            radius=DEALER_MAT_RADIUS, fill=felt_theme["felt_dark"], outline=felt_theme["accent"],
                            width=2, tags=("dealer_mat",))
        self.canvas.create_text(CANVAS_WIDTH / 2, DEALER_MAT_LABEL_Y, text="DEALER", fill=theme.ACCENT,
                                 font=theme.font(9, weight="bold"), tags=("dealer_mat",))

    def _dealer_card_x(self, pos, n):
        gap = min(DEALER_CARD_GAP_MAX, max(30, (DEALER_MAT_X2 - DEALER_MAT_X1 - 40) / max(1, n)))
        total_w = gap * (n - 1) + CARD_WIDTH
        start_x = CANVAS_WIDTH / 2 - total_w / 2
        return start_x + pos * gap

    def _draw_dealer_card_at(self, pos, n, card, face_up):
        tag = f"dealer_card_{pos}"
        self.canvas.delete(tag)
        x = self._dealer_card_x(pos, n)
        if face_up:
            draw_card(self.canvas, x, DEALER_Y, card, tags=(tag,))
        else:
            draw_card_back(self.canvas, x, DEALER_Y, self._current_felt,
                            self.app.settings.theme()["accent"], tags=(tag,))

    def _draw_dealer_cards(self):
        cards = self.game.dealer_cards
        if not cards:
            return
        if self._dealer_display_count is None:
            indices = [i for i in range(min(2, len(cards))) if self._card_revealed("dealer", None, i)]
        else:
            indices = list(range(min(self._dealer_display_count, len(cards))))
        n = len(indices)
        for pos, i in enumerate(indices):
            face_up = (i == 0) or (i >= 2) or (i == 1 and self._hole_revealed)
            self._draw_dealer_card_at(pos, n, cards[i], face_up)

    def _draw_box_skeleton(self, idx):
        felt_theme = self.app.settings.theme()
        x1, x2 = self._box_x1x2(idx)
        in_play = idx < self.num_boxes_in_round
        is_active = self._turns_active and in_play and idx == self.active_box_idx
        if is_active:
            outline, width = theme.ACCENT, 3
        elif in_play:
            outline, width = felt_theme["accent"], 1
        else:
            outline, width = theme.GREY_BTN_BORDER, 1
        theme.rounded_rect(self.canvas, x1, BOX_TOP, x2, BOX_TOP + BOX_HEIGHT, radius=BOX_RADIUS,
                            fill=felt_theme["felt_dark"], outline=outline, width=width, tags=("box_bg",))
        self.canvas.create_text((x1 + x2) / 2, BOX_TOP + 16, text=f"BOX {idx + 1}",
                                 fill=theme.ACCENT if is_active else theme.FG_DIM,
                                 font=theme.font(10, weight="bold"), tags=("box_bg",))
        if not in_play:
            self.canvas.create_text((x1 + x2) / 2, BOX_TOP + BOX_HEIGHT / 2, text="(not in play)",
                                     fill=theme.GREY_BTN_TEXT, font=theme.font(9), tags=("box_bg",))

    def _draw_header_tokens(self, box_idx):
        if box_idx >= len(self.game.boxes):
            return
        box = self.game.boxes[box_idx]
        for i, (key, label) in enumerate(self._header_tokens(box_idx)):
            cx, cy = self._header_token_pos(box_idx, i)
            label_tag = f"tokenlabel_{box_idx}_{key}"
            chip_tag = f"tokenchip_{box_idx}_{key}"
            self.canvas.delete(label_tag)
            self.canvas.delete(chip_tag)
            if key == "insurance":
                amount = box.insurance_bet
            elif self._side_bets_swept:
                # Already paid out (see _animate_side_bet_payouts) -- shows
                # its resting amount from here on: 0 (nothing drawn) if it
                # lost, or its full return (stake + winnings together) if it
                # won, since the separate win-chip animation that grew that
                # in doesn't survive this method's own redraw.
                amount = box.side_bet_results.get(key, 0.0)
            else:
                amount = getattr(box, f"{key}_bet")
            if amount:
                draw_chip_stack(self.canvas, chip_tag, cx, cy, amount, SIDE_BET_TOKEN_R)
            self.canvas.create_text(cx, cy + SIDE_BET_TOKEN_R + 8, text=label, fill=theme.FG_DIM,
                                     font=theme.font(7, weight="bold"), tags=(label_tag,))

    def _draw_hand(self, box_idx, hand_idx):
        box = self.game.boxes[box_idx]
        hand = box.hands[hand_idx]
        x1, x2, row_h, ys = self._hand_positions(box_idx)
        cy = ys[hand_idx]
        hand_tag = f"hand_{box_idx}_{hand_idx}"
        chip_tag = f"handchip_{box_idx}_{hand_idx}"
        self.canvas.delete(hand_tag)
        self.canvas.delete(chip_tag)

        is_active = self._turns_active and box_idx == self.active_box_idx and box.active_hand() is hand
        if is_active:
            self.canvas.create_rectangle(x1 + 8, cy - row_h / 2 + 2, x2 - 8, cy + row_h / 2 - 2,
                                          outline=theme.ACCENT, width=2, tags=(hand_tag,))

        cards_x_start = x1 + 22
        shown = 0
        for i, card in enumerate(hand.cards):
            if hand_idx == 0 and i < 2 and not self._card_revealed("box", box_idx, i):
                continue
            cx = cards_x_start + shown * HAND_CARD_OVERLAP_X
            draw_card(self.canvas, cx, cy - HAND_CARD_H / 2, card, width=int(HAND_CARD_W), height=int(HAND_CARD_H),
                      tags=(hand_tag,))
            shown += 1
        if not shown:
            return

        if hand.bet:
            draw_chip_stack(self.canvas, chip_tag, x2 - 56, cy, hand.bet, HAND_CHIP_R)

        self.canvas.create_text(x2 - 12, cy - row_h / 2 + 10, text=str(hand.total), fill=theme.FG,
                                 font=theme.font(9, weight="bold"), anchor="e", tags=(hand_tag,))

        status = None
        if hand.outcome:
            status = hand.outcome.upper()
        elif hand.is_bust:
            status = "BUST"
        elif hand.is_blackjack and hand.done:
            status = "BLACKJACK"
        if status:
            color = {"BUST": theme.LOSE_COLOR, "LOSE": theme.LOSE_COLOR, "WIN": theme.WIN_COLOR,
                     "BLACKJACK": theme.WIN_COLOR, "PUSH": theme.PUSH_COLOR}.get(status, theme.FG)
            self.canvas.create_text(x1 + 22 + HAND_CARD_W / 2, cy + row_h / 2 - 8, text=status, fill=color,
                                     font=theme.font(8, weight="bold"), tags=(hand_tag,))

    def _redraw_play_table(self):
        self.canvas.delete("all")
        self._draw_dealer_mat()
        self._draw_dealer_cards()
        for idx in range(2):
            self._draw_box_skeleton(idx)
            if idx < len(self.game.boxes):
                self._draw_header_tokens(idx)
                for hand_idx in range(len(self.game.boxes[idx].hands)):
                    self._draw_hand(idx, hand_idx)

    # ------------------------------------------------------------------ animation engine
    def _animate(self, duration_ms, on_frame, on_done=None):
        """Calls on_frame(eased_t) across `duration_ms` at ~30fps, t easing
        0 -> 1. Skips straight to on_frame(1.0) + on_done() when animations
        are off in Settings -- see Three Card Poker's identical helper."""
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

    def _run_parallel(self, fns, on_done=None):
        """Starts every fn(cb) at once rather than chaining them -- used for
        "all losing side bets taken simultaneously" (contrast
        _run_sequential, used right after for "wins paid out
        individually")."""
        if not fns:
            if on_done:
                on_done()
            return
        remaining = [len(fns)]

        def one_done():
            remaining[0] -= 1
            if remaining[0] == 0 and on_done:
                on_done()

        for fn in fns:
            fn(one_done)

    # ------------------------------------------------------------------ theme / lifecycle
    def on_show(self):
        self._apply_theme()
        self._refresh_balance()
        if self.state == "betting":
            self._sanitize_bets()
            self._draw_table()
            self._update_total()

    def _apply_theme(self):
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
            pass
        for child in widget.winfo_children():
            self._retheme_widget(child, old_felt, new_felt)

    def _refresh_balance(self):
        self.balance_lbl.configure(text=f"£{self.app.finance.balance:,.2f}")
