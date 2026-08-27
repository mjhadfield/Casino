import os
import tkinter as tk
from typing import Optional

from core.persistence import load_json, save_json
from games.baccarat.logic import (
    BaccaratGame,
    BET_TYPES,
    GAME_KEY,
    RoundResult,
    hand_outcome_label,
)
from games.baccarat import logic as bacc_logic
from ui import dialogs, theme
from ui.card_widgets import draw_card, draw_card_back, CARD_HEIGHT, CARD_WIDTH
from ui.chips import CHIP_DENOMINATIONS, CHIP_SIZE, draw_chip_face, draw_chip_stack

STATE_FILENAME = "baccarat_state.json"
DEFAULT_STATE = {"bets": {key: 0 for key, _ in BET_TYPES}, "selected_chip": 5}

# --- Layout constants -------------------------------------------------------
# Unlike every other game here, Baccarat uses ONE fixed felt throughout
# betting/dealing/resolved -- no canvas resize between a "betting screen"
# and a bigger "play screen". Every bet spot and both hand mats are laid
# out once, right where a real Baccarat felt prints them (bet spots
# directly beside where the cards land), and never move.
CANVAS_WIDTH = 820
CONTENT_TOP_MARGIN = 2

PAYTABLE_WIDTH = 240

# --- Road strip -- a thin row of small dots (blue=Player win, red=Banker
# win, green=Tie) at the very top, appended to after every round. Purely
# decorative, session-only, in-memory bookkeeping (self.history) -- never
# persisted, same "UI-only" status as e.g. High Card Flush's card_zone.
ROAD_STRIP_TOP = 6
ROAD_DOT_R = 4
ROAD_DOT_GAP = 11
ROAD_STRIP_Y = ROAD_STRIP_TOP + ROAD_DOT_R
ROAD_STRIP_BOTTOM = ROAD_STRIP_Y + ROAD_DOT_R + 6
ROAD_MAX_DOTS = 40
ROAD_LEFT_X = 20

# --- Hand mats -- BANKER (left) and PLAYER (right), side by side, each a
# fixed 3-card-wide row (real cards, not fanned -- a hand is at most 3
# cards, so there's no need to overlap them). A 2-card hand simply leaves
# the 3rd slot empty; cards never re-flow when a 3rd card lands.
HAND_CARD_GAP = 10
_HAND_ROW_W = 3 * CARD_WIDTH + 2 * HAND_CARD_GAP
HAND_MAT_MARGIN = 20
HAND_MAT_WIDTH = _HAND_ROW_W + 2 * HAND_MAT_MARGIN
HAND_MAT_GAP = 80  # gap between the two mats

BANKER_MAT_X2 = CANVAS_WIDTH / 2 - HAND_MAT_GAP / 2
BANKER_MAT_X1 = BANKER_MAT_X2 - HAND_MAT_WIDTH
PLAYER_MAT_X1 = CANVAS_WIDTH / 2 + HAND_MAT_GAP / 2
PLAYER_MAT_X2 = PLAYER_MAT_X1 + HAND_MAT_WIDTH
BANKER_MAT_CX = (BANKER_MAT_X1 + BANKER_MAT_X2) / 2
PLAYER_MAT_CX = (PLAYER_MAT_X1 + PLAYER_MAT_X2) / 2

HAND_MAT_TOP = ROAD_STRIP_BOTTOM + 10
HAND_MAT_RADIUS = 10
HAND_LABEL_Y = HAND_MAT_TOP + 10
HAND_CARD_Y = HAND_MAT_TOP + 22
HAND_TOTAL_Y = HAND_CARD_Y + CARD_HEIGHT + 16
HAND_MAT_BOTTOM = HAND_TOTAL_Y + 12


def _hand_card_x(mat_cx, slot):
    return mat_cx - _HAND_ROW_W / 2 + slot * (CARD_WIDTH + HAND_CARD_GAP)


# --- Shoe -- a small face-down card-back stack, purely the deal
# animation's visual origin point (an 8-deck shoe, reshuffled fresh every
# round -- no cut-card/persistence, same per-round convention as every
# other game here). Sits in the canvas's own remaining right-hand margin,
# vertically aligned with the two hand mats.
SHOE_ZONE_W = CARD_WIDTH + 20
SHOE_ZONE_CX = (PLAYER_MAT_X2 + CANVAS_WIDTH) / 2
SHOE_ZONE_X1 = SHOE_ZONE_CX - SHOE_ZONE_W / 2
SHOE_ZONE_X2 = SHOE_ZONE_CX + SHOE_ZONE_W / 2
SHOE_ZONE_TOP = HAND_MAT_TOP
SHOE_LABEL_Y = SHOE_ZONE_TOP + 12
SHOE_Y = SHOE_LABEL_Y + 12
SHOE_ZONE_BOTTOM = SHOE_Y + CARD_HEIGHT + 10

# --- Dragon Bonus rail -- Banker Dragon under the Banker side, Player
# Dragon under the Player side, mirroring the hand mats' own left/right
# split. Sits directly under the hand mats -- the bonus rows as a block
# come first, with the main Banker/Tie/Player row moved below them (see
# MAIN_ROW_CY further down).
DRAGON_ROW_GAP = 24
DRAGON_R = 28
DRAGON_ROW_CY = HAND_MAT_BOTTOM + DRAGON_ROW_GAP + DRAGON_R
BANKER_DRAGON_CX = BANKER_MAT_CX
PLAYER_DRAGON_CX = PLAYER_MAT_CX
DRAGON_ROW_BOTTOM = DRAGON_ROW_CY + DRAGON_R

# --- 5 Treasures rail -- five compact spots in one row, centred.
TREASURE_ROW_GAP = 24
TREASURE_R = 26
TREASURE_ITEM_GAP = 22
TREASURE_ROW_CY = DRAGON_ROW_BOTTOM + TREASURE_ROW_GAP + TREASURE_R
_TREASURE_STEP = TREASURE_R * 2 + TREASURE_ITEM_GAP
_TREASURE_TOTAL_W = 5 * TREASURE_R * 2 + 4 * TREASURE_ITEM_GAP
_TREASURE_START_CX = CANVAS_WIDTH / 2 - _TREASURE_TOTAL_W / 2 + TREASURE_R
TREASURE_CXS = [_TREASURE_START_CX + i * _TREASURE_STEP for i in range(5)]
TREASURE_ROW_BOTTOM = TREASURE_ROW_CY + TREASURE_R

# --- Main bet row -- BANKER (left, under the Banker mat), TIE (centre),
# PLAYER (right, under the Player mat) -- moved below both bonus rows
# (was directly under the hand mats).
MAIN_ROW_GAP = 20
BANKER_BET_R = 45
PLAYER_BET_R = 45
TIE_BET_R = 32
MAIN_ROW_CY = TREASURE_ROW_BOTTOM + MAIN_ROW_GAP + BANKER_BET_R
BANKER_BET_CX = BANKER_MAT_CX
PLAYER_BET_CX = PLAYER_MAT_CX
TIE_BET_CX = CANVAS_WIDTH / 2
TIE_BET_CY = MAIN_ROW_CY
MAIN_ROW_BOTTOM = MAIN_ROW_CY + BANKER_BET_R

CANVAS_HEIGHT = int(MAIN_ROW_BOTTOM + 20)

# (cx, cy, radius, label, chip stack max radius) for every one of the 10
# bet spots -- the one place that knows where each spot actually sits, so
# drawing, click-binding, and the payout-chip animation all read from it.
SPOT_LAYOUT = {
    "banker": (BANKER_BET_CX, MAIN_ROW_CY, BANKER_BET_R, "BANKER", 22),
    "player": (PLAYER_BET_CX, MAIN_ROW_CY, PLAYER_BET_R, "PLAYER", 22),
    "tie": (TIE_BET_CX, TIE_BET_CY, TIE_BET_R, "TIE", 18),
    "banker_dragon": (BANKER_DRAGON_CX, DRAGON_ROW_CY, DRAGON_R, "BANKER DRAGON", 16),
    "player_dragon": (PLAYER_DRAGON_CX, DRAGON_ROW_CY, DRAGON_R, "PLAYER DRAGON", 16),
    "fortune_7": (TREASURE_CXS[0], TREASURE_ROW_CY, TREASURE_R, "FORTUNE 7", 14),
    "golden_8": (TREASURE_CXS[1], TREASURE_ROW_CY, TREASURE_R, "GOLDEN 8", 14),
    "heavenly_9": (TREASURE_CXS[2], TREASURE_ROW_CY, TREASURE_R, "HEAVENLY 9", 14),
    "blazing_7s": (TREASURE_CXS[3], TREASURE_ROW_CY, TREASURE_R, "BLAZING 7'S", 14),
    "cover_all": (TREASURE_CXS[4], TREASURE_ROW_CY, TREASURE_R, "COVER ALL", 14),
}
_MAIN_KEYS = ("banker", "player", "tie")

# --- Round-result panel -- packed in paytable_col, underneath both
# paytable panels, shown once resolved, hidden otherwise. Same width as
# the paytable panels above it so the whole column reads as one aligned
# stack.
PAYOUT_PANEL_WIDTH = PAYTABLE_WIDTH
# Tall enough for up to 10 staked-bet rows plus the Net row, PLUS the
# "Unstaked Bonus Odds" section below it (its own divider/header/up to 4
# rows) -- though in practice those two never both hit their own worst
# case at once, since each of the 4 "spottable" bets only ever occupies
# one line, staked or not (236px of content either way, once any of them
# are unstaked) -- checked against the fixed 1200x820 window's own budget.
PAYOUT_PANEL_HEIGHT = 270

# --- Betting-screen-only spacing (kept even though there's only ever one
# screen here, matching every sibling game's own naming).
BETTING_ACTION_FRAME_PADY = (8, 0)
CHIP_FRAME_PADY = (4, 2)

# --- Animation pacing (doubled throughout, per explicit request, to slow
# the whole round down) --------------------------------------------------
DEAL_IN_DROP_MS = 520
CARD_PAUSE_MS = 250      # held after each card lands, before the next is dealt
NATURAL_PAUSE_MS = 800    # pause after the deal-in lands, before settling
PAYOUT_CHIP_MOVE_MS = 560
PAYOUT_LOSE_CHIP_MOVE_MS = PAYOUT_CHIP_MOVE_MS // 2   # losing chips fly to the dealer at double speed
SWEEP_MOVE_MS = 560       # New Deal's own "sweep the felt clear" animation
BET_REPLACE_MOVE_MS = 500     # New Deal's "re-place the same bets" animation
BET_REPLACE_STAGGER_MS = 140
PAYOUT_WIN_LANDING_OFFSET_Y = -18


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


# Paytable rows, read straight from logic.py's own constants.
DRAGON_PAYTABLE_ROWS = [
    ("Natural Winner (8/9)", "Even Money"),
    ("Natural Tie (8/9)", "Push"),
] + [
    (f"Win by {margin} Points", f"{mult}:1")
    for margin, mult in sorted(bacc_logic.DRAGON_BONUS_MARGIN_PAYTABLE.items(), reverse=True)
]
TREASURES_PAYTABLE_ROWS = [
    ("Fortune 7 (Banker 3-card 7)", f"{bacc_logic.FORTUNE_7_PAYOUT}:1"),
    ("Golden 8 (Player 3-card 8)", f"{bacc_logic.GOLDEN_8_PAYOUT}:1"),
    ("Heavenly 9 (both 3-card 9)", f"{bacc_logic.HEAVENLY_9_PAYOUTS['both']}:1"),
    ("Heavenly 9 (one 3-card 9)", f"{bacc_logic.HEAVENLY_9_PAYOUTS['one']}:1"),
    ("Blazing 7's (both 3-card 7)", f"{bacc_logic.BLAZING_7S_PAYOUTS['both_3card']}:1"),
    ("Blazing 7's (both 2-card 7)", f"{bacc_logic.BLAZING_7S_PAYOUTS['both_2card']}:1"),
    ("Cover All (any of the above)", f"{bacc_logic.COVER_ALL_PAYOUT}:1"),
]


def _max_deal_cost(bets):
    return sum(bets.values())


class BaccaratFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.BG)
        self.app = app
        self.game = BaccaratGame()
        self.result: Optional[RoundResult] = None
        self.state = "betting"   # betting -> playing -> resolved

        self.save_path = os.path.join(app.data_dir, STATE_FILENAME)
        saved = load_json(self.save_path, DEFAULT_STATE)
        saved_bets = saved.get("bets", DEFAULT_STATE["bets"])
        self.bets = {key: int(saved_bets.get(key, 0)) for key, _ in BET_TYPES}
        self.selected_chip = int(saved.get("selected_chip", DEFAULT_STATE["selected_chip"]))
        self._sanitize_bets(persist=False)

        self.chip_canvases = {}
        # Session-only recent-outcomes strip -- see ROAD_STRIP's own note
        # above; never persisted, resets on every app restart.
        self.history = []

        self._build_ui()

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
        tk.Label(top_bar, text="Baccarat", bg=theme.BG_ELEVATED, fg=theme.ACCENT,
                 font=theme.font(16, weight="bold")).pack(side="left", padx=10)
        # No felt real estate to spare with 10 bet spots already crowding
        # it -- Rules lives as a plain top-bar button instead of a
        # canvas-drawn one, unlike every other game's own felt-side button.
        tk.Button(
            top_bar, text="Rules", bg=theme.BG_ELEVATED, fg=theme.FG_DIM, relief="flat",
            font=theme.font(11), padx=12, pady=6, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.BORDER, highlightcolor=theme.ACCENT,
            command=self._show_rules,
        ).pack(side="left", padx=(0, 10), pady=10)
        self.balance_lbl = tk.Label(top_bar, text="£0.00", bg=theme.BG_ELEVATED, fg=theme.WIN_COLOR,
                                     font=theme.font(12, weight="bold"))
        self.balance_lbl.pack(side="right", padx=20)
        theme.breadcrumb(top_bar, "baccarat", bg=theme.BG_ELEVATED).pack(side="right", padx=(6, 6))

        body = tk.Frame(self, bg=felt_theme["felt"])
        body.pack(fill="both", expand=True)

        content = tk.Frame(body, bg=felt_theme["felt"])
        content.place(relx=0.5, y=CONTENT_TOP_MARGIN, anchor="n")

        game_col = tk.Frame(content, bg=felt_theme["felt"])
        game_col.pack(side="left", anchor="n")

        paytable_col = tk.Frame(content, bg=felt_theme["felt"])
        paytable_col.pack(side="right", fill="y", padx=(10, 24), pady=10)

        self._build_paytables(paytable_col)

        self.canvas = tk.Canvas(game_col, bg=felt_theme["felt"], highlightthickness=0,
                                 width=CANVAS_WIDTH, height=CANVAS_HEIGHT)
        self.canvas.pack(padx=12, pady=(2, 2))

        self.result_lbl = tk.Label(
            game_col, text="Place a Player, Banker or Tie bet to begin.", bg=felt_theme["felt"], fg=theme.FG,
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
        self.chip_zone.pack(pady=(8, 0))

        self.chip_frame = tk.Frame(self.chip_zone, bg=felt_theme["felt"])
        tk.Label(
            self.chip_frame, text="Tap a chip, then tap a spot on the table to place it",
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
            width=self.chip_frame.winfo_reqwidth(),
            height=self.chip_frame.winfo_reqheight(),
        )
        self.chip_zone.pack_propagate(False)

        self._draw_felt()
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

    # ------------------------------------------------------------------ paytable panels
    def _build_paytables(self, parent):
        felt_theme = self.app.settings.theme()
        self.dragon_paytable_canvas = tk.Canvas(
            parent, width=PAYTABLE_WIDTH, height=210, bg=felt_theme["felt"], highlightthickness=0,
        )
        self.dragon_paytable_canvas.pack(pady=(0, 10))
        self.treasures_paytable_canvas = tk.Canvas(
            parent, width=PAYTABLE_WIDTH, height=220, bg=felt_theme["felt"], highlightthickness=0,
        )
        self.treasures_paytable_canvas.pack()
        self._draw_paytables()

        # Round result: sits underneath both paytable panels, in the same
        # column -- shown once a round resolves, hidden otherwise.
        self.payout_canvas = tk.Canvas(
            parent, width=PAYOUT_PANEL_WIDTH, height=PAYOUT_PANEL_HEIGHT,
            bg=felt_theme["felt"], highlightthickness=0,
        )

    def _draw_paytables(self):
        felt_theme = self.app.settings.theme()

        canvas = self.dragon_paytable_canvas
        canvas.delete("all")
        w, h = PAYTABLE_WIDTH, 210
        theme.recessed_panel(canvas, 0, 0, w, h, title="DRAGON BONUS", title_font_size=12,
                              fill=felt_theme["felt_dark"], outline=felt_theme["accent"])
        y = 38
        for label, payout in DRAGON_PAYTABLE_ROWS:
            canvas.create_text(20, y, text=label, fill=theme.FG, font=theme.font(8), anchor="w")
            canvas.create_text(w - 20, y, text=payout, fill=felt_theme["accent"],
                                font=theme.font(8, weight="bold"), anchor="e")
            y += 15
        y += 8
        canvas.create_text(
            w / 2, y, anchor="n",
            text="Judged on whichever side (Player or\nBanker) you bet -- independent of\n"
                 "the main Player/Banker/Tie bets.",
            fill=theme.FG_DIM, font=theme.font(7), justify="center",
        )

        canvas = self.treasures_paytable_canvas
        canvas.delete("all")
        w, h = PAYTABLE_WIDTH, 220
        theme.recessed_panel(canvas, 0, 0, w, h, title="5 TREASURES", title_font_size=12,
                              fill=felt_theme["felt_dark"], outline=felt_theme["accent"])
        y = 38
        for label, payout in TREASURES_PAYTABLE_ROWS:
            canvas.create_text(20, y, text=label, fill=theme.FG, font=theme.font(7), anchor="w")
            canvas.create_text(w - 20, y, text=payout, fill=felt_theme["accent"],
                                font=theme.font(8, weight="bold"), anchor="e")
            y += 15
        y += 8
        canvas.create_text(
            w / 2, y, anchor="n",
            text="Each resolves on its own qualifying\nevent -- Cover All pays if any of the\n"
                 "other four fire, staked or not.",
            fill=theme.FG_DIM, font=theme.font(7), justify="center",
        )

    def _show_rules(self):
        dialogs.document(
            self, "♦ Baccarat -- Rules",
            [
                ("GAMEPLAY", [
                    "**Dealt from an 8-deck shoe.** Two cards each go to Player and Banker; a "
                    "third card may follow, decided entirely by fixed rules -- there's no "
                    "decision for you to make once the bet is placed.",
                    "**Card points:** Ace=1, 2-9=face value, 10/J/Q/K=0. A hand's total is the "
                    "sum of its cards, with only the last digit counted (e.g. 7+8=15 -> 5).",
                    "**Natural:** a two-card total of 8 or 9 for either hand ends the round "
                    "immediately -- no more cards to anyone.",
                    "**Player draws** on a two-card total of 0-5, stands on 6-7.",
                    "**Banker draws** on 0-5 if the Player stood, or per a fixed table cross-"
                    "referencing Banker's own total against the Player's third card if the "
                    "Player drew -- always stands on 7.",
                ]),
                ("MAIN BETS", [
                    "**Player:** pays 1:1. **Banker:** pays 1:1 minus a 5% commission (£10 "
                    "staked returns £19.50 on a win). Both push if the round ties.",
                    "**Tie:** pays 8:1 on an actual tie; otherwise loses outright (does not "
                    "push).",
                ]),
                ("SIDE BETS", [
                    "**Dragon Bonus** (Player Dragon / Banker Dragon): your side losing always "
                    "loses; a natural tie pushes, any other tie loses; a natural win pays even "
                    "money regardless of margin; otherwise paid by margin of victory -- see the "
                    "panel alongside the table.",
                    "**5 Treasures** (Fortune 7 / Golden 8 / Heavenly 9 / Blazing 7's / Cover "
                    "All): five independent bets judged purely on qualifying events in the "
                    "round -- see the panel alongside the table.",
                ]),
            ],
        )

    # ------------------------------------------------------------------ static felt
    def _draw_felt(self):
        """Every static/chrome element -- mats, shoe, road strip, bet-spot
        circles+labels -- drawn once, tagged "zone_bg" so a live theme
        switch can refresh colours without wiping dealt cards or placed
        chip stacks."""
        felt_theme = self.app.settings.theme()
        self.canvas.delete("zone_bg")

        theme.rounded_rect(self.canvas, BANKER_MAT_X1, HAND_MAT_TOP, BANKER_MAT_X2, HAND_MAT_BOTTOM,
                            radius=HAND_MAT_RADIUS, fill=felt_theme["felt_dark"], outline=felt_theme["accent"],
                            width=2, tags=("zone_bg", "banker_mat_bg"))
        self.canvas.create_text(BANKER_MAT_CX, HAND_LABEL_Y, text="BANKER", fill=felt_theme["accent"],
                                 font=theme.font(10, weight="bold"), tags=("zone_bg",))

        theme.rounded_rect(self.canvas, PLAYER_MAT_X1, HAND_MAT_TOP, PLAYER_MAT_X2, HAND_MAT_BOTTOM,
                            radius=HAND_MAT_RADIUS, fill=felt_theme["felt_dark"], outline=felt_theme["accent"],
                            width=2, tags=("zone_bg", "player_mat_bg"))
        self.canvas.create_text(PLAYER_MAT_CX, HAND_LABEL_Y, text="PLAYER", fill=felt_theme["accent"],
                                 font=theme.font(10, weight="bold"), tags=("zone_bg",))

        theme.rounded_rect(self.canvas, SHOE_ZONE_X1, SHOE_ZONE_TOP, SHOE_ZONE_X2, SHOE_ZONE_BOTTOM, radius=12,
                            fill=felt_theme["felt_dark"], outline=theme.FG_DIM, width=1, tags=("zone_bg",))
        self.canvas.create_text(SHOE_ZONE_CX, SHOE_LABEL_Y, text="SHOE", fill=theme.FG_DIM,
                                 font=theme.font(9, weight="bold"), tags=("zone_bg",))
        draw_card_back(self.canvas, SHOE_ZONE_CX - CARD_WIDTH / 2, SHOE_Y, felt_theme["felt"],
                        felt_theme["accent"], tags=("zone_bg",))

        for key in SPOT_LAYOUT:
            self._draw_spot_bg(key)
            self._redraw_spot_chips(key)

        self._draw_road_strip()

    def _draw_spot_bg(self, key):
        cx, cy, r, label, _ = SPOT_LAYOUT[key]
        felt_theme = self.app.settings.theme()
        tag = f"spot_bg_{key}"
        self.canvas.delete(tag)
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=felt_theme["felt_dark"],
                                 outline=felt_theme["accent"], width=2, tags=("zone_bg", tag))
        self.canvas.create_text(cx, cy - r - (10 if key in _MAIN_KEYS else 9), text=label, fill=theme.FG,
                                 font=theme.font(9 if key in _MAIN_KEYS else 6, weight="bold"),
                                 tags=("zone_bg", tag))
        hit_tag = f"spot_hit_{key}"
        self.canvas.delete(hit_tag)
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill="", outline="", tags=(hit_tag,))
        self.canvas.tag_bind(hit_tag, "<Button-1>", lambda e, k=key: self._on_place_chip(k))
        self.canvas.tag_bind(hit_tag, "<Enter>", lambda e: self.canvas.configure(cursor="hand2"))
        self.canvas.tag_bind(hit_tag, "<Leave>", lambda e: self.canvas.configure(cursor=""))

    def _redraw_spot_chips(self, key):
        cx, cy, r, _, max_r = SPOT_LAYOUT[key]
        tag = f"spot_chips_{key}"
        self.canvas.delete(tag)
        amount = self.bets[key]
        if amount:
            draw_chip_stack(self.canvas, tag, cx, cy, amount, max_r=max_r)
        elif self.state == "betting":
            self.canvas.create_text(cx, cy, text="tap to\nbet", fill=theme.FG_DIM,
                                     font=theme.font(7, weight="bold"), justify="center", tags=(tag,))
        # The invisible hit-oval (see _draw_spot_bg) needs to stay on top --
        # otherwise whatever was just drawn here (chip stack or the "tap to
        # bet" placeholder) sits above it in stacking order and silently
        # swallows the click instead of ever reaching the hit region.
        self.canvas.tag_raise(f"spot_hit_{key}")

    def _draw_road_strip(self):
        self.canvas.delete("road_dot")
        shown = self.history[-ROAD_MAX_DOTS:]
        colors = {"player": "#3b8fd6", "banker": "#d1362f", "tie": "#2fa860"}
        for i, outcome in enumerate(shown):
            cx = ROAD_LEFT_X + i * ROAD_DOT_GAP + ROAD_DOT_R
            self.canvas.create_oval(cx - ROAD_DOT_R, ROAD_STRIP_Y - ROAD_DOT_R,
                                     cx + ROAD_DOT_R, ROAD_STRIP_Y + ROAD_DOT_R,
                                     fill=colors[outcome], outline="", tags=("road_dot",))

    # ------------------------------------------------------------------ state transitions
    def _show_betting_controls(self):
        for w in self.action_frame.pack_slaves():
            w.pack_forget()
        self.deal_btn.pack()
        self.action_frame.pack(pady=BETTING_ACTION_FRAME_PADY)
        self.payout_canvas.pack_forget()
        self.chip_frame.pack(pady=CHIP_FRAME_PADY)
        self._update_total()

    def _show_round_over_controls(self):
        self.chip_frame.pack_forget()
        for w in self.action_frame.pack_slaves():
            w.pack_forget()
        self.action_frame.pack(pady=(4, 0))
        self.new_deal_btn.pack(side="left", padx=8)
        self.change_bets_btn.pack(side="left", padx=8)
        # Always start enabled here -- _new_deal() disables both for the
        # duration of its own sweep/re-place animation, and this is the
        # one place that always runs again once a fresh round is ready to
        # be acted on, so it's the natural place to guarantee they're back
        # to normal.
        self._style_round_over_btns(enabled=True)

    def _style_round_over_btns(self, enabled):
        if enabled:
            self.new_deal_btn.configure(state="normal", bg=theme.ACCENT_DIM_BG, fg=theme.FG,
                                         highlightbackground=theme.ACCENT)
            self.change_bets_btn.configure(state="normal", bg=theme.GREY_BTN_BG, fg=theme.FG_DIM,
                                            highlightbackground=theme.GREY_BTN_BORDER)
        else:
            self.new_deal_btn.configure(state="disabled", bg=theme.GREY_BTN_BG, fg=theme.GREY_BTN_TEXT,
                                         highlightbackground=theme.GREY_BTN_BORDER)
            self.change_bets_btn.configure(state="disabled", fg=theme.GREY_BTN_TEXT)

    def _show_no_controls(self):
        self.chip_frame.pack_forget()
        self.payout_canvas.pack_forget()
        for w in self.action_frame.pack_slaves():
            w.pack_forget()
        self.action_frame.pack(pady=(4, 0))

    # ------------------------------------------------------------------ betting
    def _on_place_chip(self, key):
        if self.state != "betting":
            return
        trial_bets = dict(self.bets)
        trial_bets[key] += self.selected_chip
        if _max_deal_cost(trial_bets) > self.app.finance.balance + 1e-9:
            dialogs.info(self, "$ bet --check-funds", "You don't have enough balance to place that chip.",
                         accent=theme.WARN)
            return
        self.bets = trial_bets
        self._redraw_spot_chips(key)
        self._update_total()
        self._persist_state()

    def _clear_bets(self):
        if self.state != "betting":
            return
        for key in self.bets:
            self.bets[key] = 0
            self._redraw_spot_chips(key)
        self._update_total()
        self._persist_state()

    def _update_total(self):
        self.total_lbl.configure(text=f"Total bet: £{sum(self.bets.values())}")

    def _persist_state(self):
        save_json(self.save_path, {"bets": self.bets, "selected_chip": self.selected_chip})

    def _sanitize_bets(self, persist=True):
        if _max_deal_cost(self.bets) > self.app.finance.balance:
            self.bets = {key: 0 for key, _ in BET_TYPES}
            if persist:
                self._persist_state()

    # ------------------------------------------------------------------ round flow
    def _on_deal(self):
        if self.bets["player"] + self.bets["banker"] + self.bets["tie"] <= 0:
            dialogs.info(self, "$ deal --require-bet",
                         "You must place a Player, Banker or Tie bet to deal.", accent=theme.WARN)
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

        self.app.finance.place_wager(_max_deal_cost(self.bets))
        self._refresh_balance()

        self.result = self.game.deal(dict(self.bets))
        self.state = "playing"
        self.result_lbl.configure(text="Dealing...", fg=theme.FG)
        self._show_no_controls()

        self.canvas.delete("hand_card")
        self.canvas.delete("hand_total")
        self.canvas.delete("natural_flash")

        self._deal_in()

    # ------------------------------------------------------------------ card-view rendering
    def _draw_hand_card_at(self, side, slot, card, x, y, face_up=True):
        tag = f"{side}_card_{slot}"
        self.canvas.delete(tag)
        if face_up:
            draw_card(self.canvas, x, y, card, tags=(tag, "hand_card"))
        else:
            draw_card_back(self.canvas, x, y, self._current_felt, self.app.settings.theme()["accent"],
                            tags=(tag, "hand_card"))

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

    # ------------------------------------------------------------------ deal-in
    def _deal_in(self):
        """Deals every card in the real order -- Player, Banker, Player,
        Banker, then (if drawn) the Player's third, then (if drawn) the
        Banker's third -- all already known, since BaccaratGame.deal()
        resolves the whole round in one call; this purely replays it.
        Every card lands face up -- there's no hidden information on
        either side in Baccarat, unlike a dealer's hand in every other
        game here.

        Dealt strictly one at a time (not staggered/overlapping) -- each
        card's own drop finishes, that side's running total updates the
        instant the post-card pause begins (so the total visibly builds up
        live rather than only appearing once the whole hand is down), then
        CARD_PAUSE_MS is held before the next card starts falling."""
        assert self.result is not None
        result = self.result
        steps = [("player", 0), ("banker", 0), ("player", 1), ("banker", 1)]
        if len(result.player_cards) == 3:
            steps.append(("player", 2))
        if len(result.banker_cards) == 3:
            steps.append(("banker", 2))

        def deal_one(i, callback):
            side, slot = steps[i]
            cards = result.player_cards if side == "player" else result.banker_cards
            mat_cx = PLAYER_MAT_CX if side == "player" else BANKER_MAT_CX
            card = cards[slot]
            tx, ty = _hand_card_x(mat_cx, slot), HAND_CARD_Y
            sx, sy = SHOE_ZONE_CX - CARD_WIDTH / 2, SHOE_Y

            def frame(t, side=side, slot=slot, card=card, sx=sx, sy=sy, tx=tx, ty=ty):
                self._draw_hand_card_at(side, slot, card, sx + (tx - sx) * t, sy + (ty - sy) * t)

            def landed(side=side, cards=cards, slot=slot):
                self._draw_hand_total(side, bacc_logic.hand_total(cards[:slot + 1]))
                self._after_delay(CARD_PAUSE_MS, callback)

            self._animate(DEAL_IN_DROP_MS, frame, on_done=landed)

        self._run_sequential(
            [lambda cb, i=i: deal_one(i, cb) for i in range(len(steps))],
            self._on_deal_complete,
        )

    def _on_deal_complete(self):
        assert self.result is not None
        result = self.result
        # Re-drawn one final time, now in the outcome-coloured style --
        # the running totals during dealing (see deal_one's own landed())
        # always show plain/neutral, since the winner isn't "announced"
        # until the whole hand is actually down.
        self._draw_hand_total("banker", result.banker_total, result.outcome)
        self._draw_hand_total("player", result.player_total, result.outcome)
        if result.player_natural or result.banker_natural:
            self.canvas.create_text(
                CANVAS_WIDTH / 2, (HAND_LABEL_Y + HAND_MAT_TOP) / 2 + 4, text="NATURAL!",
                fill=theme.WARN, font=theme.font(13, weight="bold"), tags=("natural_flash",),
            )
        self.history.append(result.outcome)
        self._draw_road_strip()
        self.result_lbl.configure(text=result.summary, fg=theme.FG)
        self._after_delay(NATURAL_PAUSE_MS, self._settle_and_pay)

    def _draw_hand_total(self, side, total, outcome=None):
        # Colour signals the winner directly on the number itself rather
        # than the mat's own border -- WIN_COLOR is the app's one fixed
        # global accent, which can sit too close to some table felts' own
        # accent colour (see TABLE_THEMES) to read as a highlight there;
        # dim vs bright vs amber reads clearly regardless of felt hue.
        if outcome is None:
            color = theme.ACCENT
        elif outcome == "tie":
            color = theme.PUSH_COLOR
        elif outcome == side:
            color = theme.WIN_COLOR
        else:
            color = theme.FG_DIM
        cx = BANKER_MAT_CX if side == "banker" else PLAYER_MAT_CX
        tag = f"{side}_total"
        self.canvas.delete(tag)
        self.canvas.create_text(cx, HAND_TOTAL_Y, text=str(total), fill=color,
                                 font=theme.font(16, weight="bold"), tags=(tag, "hand_total"))

    # ------------------------------------------------------------------ settle / payout
    def _settle_and_pay(self):
        assert self.result is not None
        result = self.result

        for key, _, bet, ret in result.bet_lines():
            if bet > 0:
                self.app.game_stats.record_bet(GAME_KEY, key, bet, ret)
        self.app.game_stats.record_round_net(GAME_KEY, result.net_result)
        self.app.game_stats.record_hand(GAME_KEY, hand_outcome_label(result))
        self.app.finance.record_round_played(result.net_result)

        payout_items = self._payout_chip_items(result)
        credit = sum(it["ret"] for it in payout_items)
        if credit > 0:
            self.app.finance.add_return(credit)

        self._animate_payouts(payout_items, lambda: self._on_round_settled(result))

    def _payout_chip_items(self, result):
        items = []
        for key, _, bet, ret in result.bet_lines():
            if bet <= 0:
                continue
            cx, cy, _, _, max_r = SPOT_LAYOUT[key]
            items.append(dict(key=key, bet=bet, ret=ret, cx=cx, cy=cy, spot_tag=f"spot_chips_{key}", max_r=max_r))
        return items

    def _chip_move_away(self, item, on_done):
        """A losing bet's stake is swept away to the dealer -- the shoe is
        the closest thing to a dealer's own position on this felt (it's
        literally where they deal from) -- at PAYOUT_LOSE_CHIP_MOVE_MS,
        double the speed of a winning payout's own chip animation."""
        chips_tag = item["spot_tag"]
        self.canvas.delete(chips_tag)
        travel_tag = f"chip_travel_{item['key']}"
        dealer_cx, dealer_cy = SHOE_ZONE_CX, (SHOE_ZONE_TOP + SHOE_ZONE_BOTTOM) / 2

        def frame(t):
            cx = item["cx"] + (dealer_cx - item["cx"]) * t
            cy = item["cy"] + (dealer_cy - item["cy"]) * t
            self.canvas.delete(travel_tag)
            r = item["max_r"] * (1 - t)
            if r > 2:
                draw_chip_stack(self.canvas, travel_tag, cx, cy, item["bet"], r)

        def arrived():
            self.canvas.delete(travel_tag)
            if on_done:
                on_done()

        self._animate(PAYOUT_LOSE_CHIP_MOVE_MS, frame, on_done=arrived)

    def _chip_move_in(self, item, on_done):
        win_amount = item["ret"] - item["bet"]
        travel_tag = f"chip_travel_{item['key']}"
        settle_cx, settle_cy = CANVAS_WIDTH / 2, (HAND_MAT_TOP + HAND_MAT_BOTTOM) / 2
        to_cx, to_cy = item["cx"], item["cy"] + PAYOUT_WIN_LANDING_OFFSET_Y

        def frame(t):
            cx = settle_cx + (to_cx - settle_cx) * t
            cy = settle_cy + (to_cy - settle_cy) * t
            self.canvas.delete(travel_tag)
            if item["max_r"] * t > 2:
                draw_chip_stack(self.canvas, travel_tag, cx, cy, win_amount, item["max_r"] * t)

        self._animate(PAYOUT_CHIP_MOVE_MS, frame, on_done=on_done)

    def _animate_payouts(self, items, on_done):
        # Pushes (ret == bet, e.g. a Player/Banker bet on a tie) keep their
        # chip stack sitting exactly where it already is -- nothing to
        # animate away or grow.
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
                base_tag = it["spot_tag"]
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
                self.canvas.delete(it["spot_tag"])
                self.canvas.delete(f"chip_travel_{it['key']}")
            if on_done:
                on_done()

        self._animate(SWEEP_MOVE_MS, frame, on_done=finish)

    def _replace_bets(self, on_done):
        """New Deal keeps the same bets, but the sweep above only ever
        clears a spot's chip stack if last round returned something on it
        -- a spot that simply lost was never touched and is still showing
        the right stake, but every spot that won or pushed is now blank
        even though self.bets still holds the same amount for it. Rather
        than silently leaving that inconsistent, every staked spot's chip
        stack is re-placed here from scratch, animated flying in from
        wherever the New Deal button itself sits (still visible, just
        disabled, at this point -- see _new_deal) -- so it reads as "the
        chips you just committed to by pressing New Deal are the ones
        landing back on the table" -- so the table always reads correctly
        for the round that's actually about to be played."""
        keys = [key for key, amount in self.bets.items() if amount > 0]
        if not keys:
            on_done()
            return
        stage_cx = (self.new_deal_btn.winfo_rootx() + self.new_deal_btn.winfo_width() / 2
                    - self.canvas.winfo_rootx())
        stage_cy = (self.new_deal_btn.winfo_rooty() + self.new_deal_btn.winfo_height() / 2
                    - self.canvas.winfo_rooty())
        remaining = [len(keys)]

        def one_done():
            remaining[0] -= 1
            if remaining[0] <= 0:
                on_done()

        def place_one(i):
            key = keys[i]
            cx, cy, r, _, max_r = SPOT_LAYOUT[key]
            tag = f"spot_chips_{key}"
            self.canvas.delete(tag)

            def frame(t, cx=cx, cy=cy, max_r=max_r, tag=tag, amount=self.bets[key]):
                self.canvas.delete(tag)
                x = stage_cx + (cx - stage_cx) * t
                y = stage_cy + (cy - stage_cy) * t
                if max_r * t > 2:
                    draw_chip_stack(self.canvas, tag, x, y, amount, max_r * t)

            def done(key=key):
                self._redraw_spot_chips(key)
                one_done()

            self._animate(BET_REPLACE_MOVE_MS, frame, on_done=done)

        self._run_staggered(len(keys), BET_REPLACE_STAGGER_MS, place_one)

    def _new_deal(self):
        assert self.result is not None
        if not self.app.finance.can_afford(_max_deal_cost(self.bets)):
            self._on_deal()
            return
        # Kept visible but disabled (rather than hidden outright, as
        # _show_no_controls would do) for the duration of the sweep +
        # re-place animation below -- a clear "something's happening,
        # don't click again yet" signal. _on_deal() itself hides the whole
        # action_frame once the animation hands off to it and the real
        # deal-in begins.
        self._style_round_over_btns(enabled=False)
        self.canvas.delete("hand_card")
        self.canvas.delete("hand_total")
        self.canvas.delete("natural_flash")
        self._sweep_remaining_chips(
            self._payout_chip_items(self.result),
            lambda: self._replace_bets(self._on_deal),
        )

    def _new_round(self):
        # Any chip stack still sitting in the play area (a win or a push
        # -- a loss was already swept to the dealer at settle time) is
        # returned to the player first, same sweep-toward-the-player-area
        # animation New Deal's own felt-clearing step uses, and only once
        # that's finished does the chip tray actually appear.
        self._style_round_over_btns(enabled=False)
        items = self._payout_chip_items(self.result) if self.result is not None else []
        self._sweep_remaining_chips(items, self._finish_new_round)

    def _finish_new_round(self):
        self.state = "betting"
        self.canvas.delete("hand_card")
        self.canvas.delete("hand_total")
        self.canvas.delete("natural_flash")
        self.result_lbl.configure(text="Place a Player, Banker or Tie bet to begin.", fg=theme.FG)
        self._sanitize_bets()
        for key in SPOT_LAYOUT:
            self._redraw_spot_chips(key)
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
        self.payout_canvas.pack(pady=(10, 0))
        self._draw_payout_panel(result)

    def _draw_payout_panel(self, result):
        canvas = self.payout_canvas
        canvas.delete("all")
        w, h = PAYOUT_PANEL_WIDTH, PAYOUT_PANEL_HEIGHT
        felt_theme = self.app.settings.theme()
        theme.recessed_panel(canvas, 0, 0, w, h, title="RESULT", title_font_size=11,
                              fill=felt_theme["felt_dark"], outline=felt_theme["accent"])
        rows = [(label, bet, ret) for _, label, bet, ret in result.bet_lines() if bet > 0]
        y = 30
        for label, bet, ret in rows:
            canvas.create_text(14, y, text=label, fill=theme.FG, font=theme.font(8), anchor="w")
            canvas.create_text(w - 14, y, text=_format_signed(ret - bet), fill=_net_color(ret - bet),
                                font=theme.font(8, weight="bold"), anchor="e")
            y += 14
        y += 4
        canvas.create_line(14, y, w - 14, y, fill=theme.BORDER)
        y += 13
        canvas.create_text(14, y, text="Net", fill=theme.FG, font=theme.font(9, weight="bold"), anchor="w")
        canvas.create_text(w - 14, y, text=_format_signed(result.net_result), fill=_net_color(result.net_result),
                            font=theme.font(10, weight="bold"), anchor="e")

        # Below the Net: whichever of the four "spottable" 5 Treasures
        # bets weren't actually staked this round -- purely informational
        # (Win/Lose, no £ amount, since nothing was wagered on them) so a
        # player can learn to recognise these patterns without having to
        # bet every one of them every round. Player/Banker/Tie and Cover
        # All are deliberately left out -- every round trivially resolves
        # the former, and Cover All is only ever a derived echo of these
        # same four events, not its own spottable pattern.
        spottable = [
            ("fortune_7", "Fortune 7", result.fortune_7_hit),
            ("golden_8", "Golden 8", result.golden_8_hit),
            ("heavenly_9", "Heavenly 9", result.heavenly_9_tier > 0),
            ("blazing_7s", "Blazing 7's", result.blazing_7s_tier > 0),
        ]
        unstaked = [(label, hit) for key, label, hit in spottable if getattr(result, f"{key}_bet") <= 0]
        if unstaked:
            y += 20
            canvas.create_line(14, y, w - 14, y, fill=theme.BORDER)
            y += 13
            canvas.create_text(w / 2, y, text="UNSTAKED BONUS ODDS", fill=theme.FG_DIM,
                                font=theme.font(8, weight="bold"))
            y += 16
            for label, hit in unstaked:
                canvas.create_text(14, y, text=label, fill=theme.FG, font=theme.font(8), anchor="w")
                canvas.create_text(w - 14, y, text="WIN" if hit else "LOSE",
                                    fill=theme.WIN_COLOR if hit else theme.LOSE_COLOR,
                                    font=theme.font(8, weight="bold"), anchor="e")
                y += 14

    # ------------------------------------------------------------------ lifecycle
    def on_show(self):
        self._apply_theme()
        self._refresh_balance()
        if self.state == "betting":
            self._sanitize_bets()
            # Redraws every spot's chip stack from self.bets -- matches
            # every other game's own "_draw_table() on show" convention.
            # Without this, self.bets changing while this screen isn't
            # visible (insufficient funds sanitising it just above, or a
            # Settings-driven bet reset) would leave stale chip stacks on
            # the felt until some other interaction happened to redraw them.
            for key in SPOT_LAYOUT:
                self._redraw_spot_chips(key)
            self._update_total()

    def _apply_theme(self):
        felt_theme = self.app.settings.theme()
        new_felt = felt_theme["felt"]
        if new_felt == self._current_felt:
            return
        old_felt = self._current_felt
        self._current_felt = new_felt
        self._retheme_widget(self, old_felt, new_felt)
        self._draw_felt()
        self._draw_paytables()
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
