import math
import os
import tkinter as tk
from typing import Optional

from core.persistence import load_json, save_json
from games.mississippi_stud.logic import (
    BONUS_PAYTABLE,
    BONUS_PAYTABLE_MINI_ROYAL,
    BONUS_PAYTABLE_STRAIGHT_FLUSH,
    FIVE_CARD_FLUSH,
    FIVE_CARD_STRAIGHT,
    FIVE_CARD_THREE_OF_A_KIND,
    FLUSH,
    FOUR_OF_A_KIND,
    FULL_HOUSE,
    GAME_KEY,
    hand_outcome_label,
    JACKPOT_BET_AMOUNT,
    JACKPOT_FLUSH_PAYOUT,
    JACKPOT_FOUR_OF_A_KIND_PAYOUT,
    JACKPOT_FULL_HOUSE_PAYOUT,
    JACKPOT_STRAIGHT_PAYOUT,
    JACKPOT_THREE_OF_A_KIND_PAYOUT,
    MAIN_PAYTABLE,
    MAIN_PAYTABLE_PAIR_JACKS_OR_BETTER,
    MAIN_PAYTABLE_ROYAL_FLUSH,
    MAIN_PAYTABLE_STRAIGHT_FLUSH,
    MississippiStudGame,
    PAIR,
    RoundResult,
    STRAIGHT,
    THREE_OF_A_KIND,
    TWO_PAIR,
)
from ui import dialogs, theme
from ui.card_widgets import draw_card, draw_card_back, CARD_HEIGHT, CARD_WIDTH
from ui.chips import (
    CHIP_COLORS_BY_VALUE,
    CHIP_DENOMINATIONS,
    CHIP_LAYER_MAX_R,
    CHIP_SIZE,
    draw_chip_face,
    draw_chip_stack,
)
from ui.jackpot_display import JackpotDisplay

STATE_FILENAME = "mississippi_stud_state.json"
DEFAULT_STATE = {"bets": {"ante": 0, "bonus": 0, "jackpot": 0}, "selected_chip": 5}

# --- Layout constants ------------------------------------------------------
# Same "fixed pixel block, centred in the window" convention as every other
# game -- see three_card_poker/ui.py's own module-level comment for why.
# This game's own canvas is deliberately isolated from that one (and every
# other game's) rather than importing shared constants from it, per the
# "isolated from the other games" instruction this game was commissioned
# under -- some numbers below are chosen to *read* similarly, but nothing is
# actually shared.
CANVAS_WIDTH = 760
# The play screen stacks four rows (dealer/community row, Jackpot+Bonus row,
# 3rd/4th/5th Street row, Ante) instead of the other games' own two -- kept
# to roughly the same overall canvas height as them anyway (rather than
# genuinely taller) by tightening the gap between each row and shrinking the
# spot radii a little, since the window itself is a fixed, non-resizable
# 1200x820 (see main.py) with no room to spare below a canvas this size once
# the caption/buttons/hand/payout panel below it are all accounted for too.
CANVAS_HEIGHT = 400

PAYTABLE_WIDTH = 240
# Tall enough for both sections in full -- 10 MAIN GAME rows (including the
# Pair 6s-10s push) + 6 3 CARD BONUS rows + both section titles + the
# divider between them + the panel's own title, or the last few Bonus rows
# silently render past the canvas widget's own bottom edge and never
# actually show up (caught by testing after the row count grew).
PAYTABLE_HEIGHT = 416
PAYOUT_PANEL_WIDTH = 380
# Up to 6 rows (Ante/3rd/4th/5th/Bonus/Jackpot) plus the Round Net total --
# trimmed to just what that worst case needs (see _draw_payout_panel's own
# tightened row pitch) rather than leaving generous unused space below it.
PAYOUT_PANEL_HEIGHT = 186

JACKPOT_SPOT_R = 26
BONUS_SPOT_R = 32     # the diamond's own "radius" (centre to each point)

CONTENT_TOP_MARGIN = 35

# --- Community-card row (3 slots, one per street, left to right) -----------
CARD_ROW_GAP = CARD_WIDTH + 15
CARD_ROW_WIDTH = 2 * CARD_ROW_GAP + CARD_WIDTH
CARD_ROW_START_X = CANVAS_WIDTH / 2 - CARD_ROW_WIDTH / 2

DEALER_MAT_RADIUS = 12
DEALER_MAT_TOP = 6
DEALER_MAT_LABEL_Y = DEALER_MAT_TOP + 8
DEALER_Y = DEALER_MAT_TOP + 18                   # community cards' top-left y
DEALER_MAT_BOTTOM = DEALER_Y + CARD_HEIGHT + 8
DEALER_MAT_SIDE_MARGIN = 40
DEALER_MAT_X1 = CARD_ROW_START_X - DEALER_MAT_SIDE_MARGIN
DEALER_MAT_X2 = CARD_ROW_START_X + CARD_ROW_WIDTH + DEALER_MAT_SIDE_MARGIN
COMMUNITY_LABELS = ["3RD", "4TH", "5TH"]

# --- Jackpot + 3 Card Bonus row (carried over from the betting screen) -----
GAP_DEALER_TO_JACKPOT_BONUS = 18
JACKPOT_BONUS_CY = DEALER_MAT_BOTTOM + GAP_DEALER_TO_JACKPOT_BONUS + BONUS_SPOT_R
JACKPOT_BONUS_BOTTOM = JACKPOT_BONUS_CY + BONUS_SPOT_R
JACKPOT_STRIP_CX = CANVAS_WIDTH / 2 - 60
BONUS_STRIP_CX = CANVAS_WIDTH / 2 + 60

# --- Player bet area: 3rd/4th/5th Street spots ------------------------------
GAP_TO_STREET_ROW = 26
STREET_ROW_R = 26
STREET_ROW_CY = JACKPOT_BONUS_BOTTOM + GAP_TO_STREET_ROW + STREET_ROW_R
STREET_ROW_BOTTOM = STREET_ROW_CY + STREET_ROW_R
STREET_LABELS = {3: "3RD STREET", 4: "4TH STREET", 5: "5TH STREET"}
STREET_ROW_CX = {3: CANVAS_WIDTH / 2 - 95, 4: CANVAS_WIDTH / 2, 5: CANVAS_WIDTH / 2 + 95}

# --- Ante spot ---------------------------------------------------------
GAP_TO_ANTE = 24
ANTE_R = 34
ANTE_CX = CANVAS_WIDTH / 2
ANTE_CY = STREET_ROW_BOTTOM + GAP_TO_ANTE + ANTE_R

# Settlement/payout "centre" every losing bet's chips slide towards, and every
# winning bet's payout slides out from -- the community-card row's own
# centre, the closest thing this game has to "the house" (there's no
# separate dealer hand the way the other games have one).
SETTLE_CENTER_X = CANVAS_WIDTH / 2
SETTLE_CENTER_Y = DEALER_Y + CARD_HEIGHT / 2
PAYOUT_WIN_LANDING_OFFSET_Y = -20
PAYOUT_CHIP_MOVE_MS = 280

# --- Rules button ------------------------------------------------------
RULES_BUTTON_WIDTH = 106
RULES_BUTTON_HEIGHT = 54
RULES_BUTTON_RADIUS = RULES_BUTTON_HEIGHT // 2

# --- Betting-screen-only spacing -------------------------------------------
BETTING_ACTION_FRAME_PADY = (23, 0)
CHIP_FRAME_PADY = (16, 30)

# --- Player's own hand (2 cards) -- its own small canvas below the action
# buttons, same "separate canvas" convention as every other game's own
# fanned hand (a literal cross-canvas slide isn't possible; see
# _animate_cards_to_rest for the vanish-then-grow trick that fakes one).
# Only ever holds 2 cards (unlike the other games' own 3+-card fans), so its
# own canvas is narrower than the main play canvas -- half its width -- and
# pack()'s default centring puts it in the middle of game_col either way.
FAN_Y = 14
FAN_GAP = 46
FAN_CANVAS_WIDTH = CANVAS_WIDTH / 2
FAN_CANVAS_HEIGHT = FAN_Y + CARD_HEIGHT + 18
FAN_MAT_X1 = 90
FAN_MAT_X2 = FAN_CANVAS_WIDTH - 90
FAN_MAT_TOP = 4
FAN_MAT_BOTTOM = FAN_CANVAS_HEIGHT - 4
FAN_MAT_RADIUS = 12
FAN_MAT_BORDER = theme.FG_DIM

# Cards that come to rest tucked under the Bonus spot on a fold (see
# _tuck_cards_under_bonus) -- reduced scale, same idea as the other games'
# own "resting" cards.
REST_CARD_SCALE = 0.55
REST_CARD_WIDTH = CARD_WIDTH * REST_CARD_SCALE
REST_CARD_HEIGHT = CARD_HEIGHT * REST_CARD_SCALE
REST_CARD_FAN_OFFSET = 22

# --- Animation pacing --------------------------------------------------
DEAL_IN_STAGGER_MS = 110
DEAL_IN_DROP_MS = 220
CHIP_PLACE_MS = 180
COMMUNITY_FLIP_MS = 220
COMMUNITY_FLIP_STAGGER_MS = 300
FOLD_FLIP_MS = 180
FOLD_FLY_MS = 220
FOLD_FLY_STAGGER_MS = 70
FOLD_FLY_TARGET = (FAN_CANVAS_WIDTH + 90, -50)
BONUS_TUCK_VANISH_MS = 150
BONUS_TUCK_GROW_MS = 200


def _ease_out_cubic(t):
    return 1 - (1 - t) ** 3


_lerp_color = theme.lerp_color

# Paytable rows, read straight from logic.py's own constants so the panel can
# never drift out of sync with what's actually paid out.
MAIN_PAYTABLE_ROWS = [
    ("Royal Flush", MAIN_PAYTABLE_ROYAL_FLUSH),
    ("Straight Flush", MAIN_PAYTABLE_STRAIGHT_FLUSH),
    ("Four of a Kind", MAIN_PAYTABLE[FOUR_OF_A_KIND]),
    ("Full House", MAIN_PAYTABLE[FULL_HOUSE]),
    ("Flush", MAIN_PAYTABLE[FIVE_CARD_FLUSH]),
    ("Straight", MAIN_PAYTABLE[FIVE_CARD_STRAIGHT]),
    ("Three of a Kind", MAIN_PAYTABLE[FIVE_CARD_THREE_OF_A_KIND]),
    ("Two Pair", MAIN_PAYTABLE[TWO_PAIR]),
    ("Pair, Jacks+", MAIN_PAYTABLE_PAIR_JACKS_OR_BETTER),
    ("Pair, 6s-10s", "Push"),
]
BONUS_PAYTABLE_ROWS = [
    ("Mini-Royal", BONUS_PAYTABLE_MINI_ROYAL),
    ("Straight Flush", BONUS_PAYTABLE_STRAIGHT_FLUSH),
    ("Three of a Kind", BONUS_PAYTABLE[THREE_OF_A_KIND]),
    ("Straight", BONUS_PAYTABLE[STRAIGHT]),
    ("Flush", BONUS_PAYTABLE[FLUSH]),
    ("Pair", BONUS_PAYTABLE[PAIR]),
]
PAYTABLE_SECTIONS = [("MAIN GAME", MAIN_PAYTABLE_ROWS), ("3 CARD BONUS", BONUS_PAYTABLE_ROWS)]

JACKPOT_PAYTABLE_ROWS = [
    ("Royal Flush", "100% JACKPOT"),
    ("Straight Flush", "10% JACKPOT"),
    ("Four of a Kind", f"£{JACKPOT_FOUR_OF_A_KIND_PAYOUT:.0f}"),
    ("Full House", f"£{JACKPOT_FULL_HOUSE_PAYOUT:.0f}"),
    ("Flush", f"£{JACKPOT_FLUSH_PAYOUT:.0f}"),
    ("Straight", f"£{JACKPOT_STRAIGHT_PAYOUT:.0f}"),
    ("Three of a Kind", f"£{JACKPOT_THREE_OF_A_KIND_PAYOUT:.0f}"),
]
JACKPOT_PAYTABLE_HIGHLIGHT_ROW = 0  # Royal Flush -- now the first row, not the last


def _max_deal_cost(bets):
    """Worst-case total the player is committing to by dealing: the Ante
    could be bet again at up to 3x on every one of the 3 streets, so
    ante*3 plus whatever's on Bonus/Jackpot is what a real casino would
    check balance against before letting the round start -- this is also
    exactly the "balance must be at least 3x the Ante" rule (when Bonus/
    Jackpot are both £0)."""
    return bets["ante"] * 3 + bets["bonus"] + bets["jackpot"]


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


class MississippiStudFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.BG)
        self.app = app
        self.game = MississippiStudGame()
        self.result: Optional[RoundResult] = None
        self.state = "betting"  # betting -> playing -> resolved
        self.street = 3         # 3, 4, or 5 while state == "playing"

        self.save_path = os.path.join(app.data_dir, STATE_FILENAME)
        saved = load_json(self.save_path, DEFAULT_STATE)
        saved_bets = saved.get("bets", DEFAULT_STATE["bets"])
        self.bets = {
            "ante": int(saved_bets.get("ante", 0)),
            "bonus": int(saved_bets.get("bonus", 0)),
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
        tk.Label(top_bar, text="Mississippi Stud", bg=theme.BG_ELEVATED, fg=theme.ACCENT,
                 font=theme.font(16, weight="bold")).pack(side="left", padx=10)
        self.balance_lbl = tk.Label(top_bar, text="£0.00", bg=theme.BG_ELEVATED, fg=theme.WIN_COLOR,
                                     font=theme.font(12, weight="bold"))
        self.balance_lbl.pack(side="right", padx=20)
        theme.breadcrumb(top_bar, "mississippi_stud", bg=theme.BG_ELEVATED,
                          player=self.app.current_player["name"]).pack(side="right", padx=(6, 6))

        body = tk.Frame(self, bg=felt_theme["felt"])
        body.pack(fill="both", expand=True)

        content = tk.Frame(body, bg=felt_theme["felt"])
        content.place(relx=0.5, y=CONTENT_TOP_MARGIN, anchor="n")

        game_col = tk.Frame(content, bg=felt_theme["felt"])
        # anchor="n": without it, pack's default vertical centring shifts
        # game_col (and everything in it -- the canvas, Ante box and all)
        # up/down between states as its own natural height changes (Deal
        # button vs. Bet/Fold row vs. New Deal/Change Bets, fan_canvas
        # shown/hidden, ...) relative to paytable_col's fixed height --
        # pinning it to the top keeps the canvas, and everything drawn on
        # it, at one constant position regardless of round state.
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
        self.bet1_btn = tk.Button(
            self.action_frame, text="BET 1x", font=theme.font(12, weight="bold"), relief="flat",
            padx=18, pady=10, cursor="hand2", highlightthickness=1, command=lambda: self._on_bet(1),
        )
        self.bet2_btn = tk.Button(
            self.action_frame, text="BET 2x", font=theme.font(12, weight="bold"), relief="flat",
            padx=18, pady=10, cursor="hand2", highlightthickness=1, command=lambda: self._on_bet(2),
        )
        self.bet3_btn = tk.Button(
            self.action_frame, text="BET 3x", font=theme.font(12, weight="bold"), relief="flat",
            padx=18, pady=10, cursor="hand2", highlightthickness=1, command=lambda: self._on_bet(3),
        )
        self.fold_btn = tk.Button(
            self.action_frame, text="FOLD", bg=theme.LOSE_DIM_BG, fg=theme.FG,
            font=theme.font(13, weight="bold"), relief="flat", padx=24, pady=10, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.LOSE_COLOR,
            command=self._on_fold,
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

        self.chip_frame = tk.Frame(self.chip_zone, bg=felt_theme["felt"])
        tk.Label(
            self.chip_frame, text="Tap a chip, then tap Ante / 3 Card Bonus / Jackpot to place it",
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

        self.payout_canvas = tk.Canvas(
            self.chip_zone, width=PAYOUT_PANEL_WIDTH, height=PAYOUT_PANEL_HEIGHT,
            bg=felt_theme["felt"], highlightthickness=0,
        )

        # Packed with its real CHIP_FRAME_PADY here (not a bare .pack())
        # before measuring -- chip_zone's fixed size below has to account
        # for that padding too, or the last child (Clear Bets) ends up
        # squeezed into whatever sliver of height is left over once
        # _show_betting_controls() re-packs chip_frame with this same pady.
        self.chip_frame.pack(pady=CHIP_FRAME_PADY)
        self.chip_frame.update_idletasks()
        self.chip_zone.configure(
            width=max(self.chip_zone.winfo_reqwidth(), PAYOUT_PANEL_WIDTH),
            height=max(self.chip_zone.winfo_reqheight(), PAYOUT_PANEL_HEIGHT),
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
        theme.recessed_panel(canvas, 0, 0, w, h, title="PAYTABLE", title_font_size=14,
                              fill=felt_theme["felt_dark"], outline=felt_theme["accent"])
        y = 46
        for i, (title, rows) in enumerate(PAYTABLE_SECTIONS):
            if i:
                canvas.create_line(20, y, w - 20, y, fill=theme.BORDER)
                y += 12
            y = self._draw_paytable_section(canvas, y, title, rows, felt_theme["accent"])

    def _draw_paytable_section(self, canvas, y, title, rows, accent):
        w = PAYTABLE_WIDTH
        canvas.create_text(20, y, text=title, fill=accent,
                            font=theme.font(10, weight="bold"), anchor="w")
        y += 20
        for label, payout in rows:
            text = payout if isinstance(payout, str) else f"{payout}:1"
            canvas.create_text(20, y, text=label, fill=theme.FG, font=theme.font(9), anchor="w")
            canvas.create_text(w - 20, y, text=text, fill=accent,
                                font=theme.font(9, weight="bold"), anchor="e")
            y += 19
        return y

    # ------------------------------------------------------------------ betting table
    def _draw_table(self):
        self.canvas.delete("all")
        w, h = CANVAS_WIDTH, CANVAS_HEIGHT
        cx = w / 2

        ante_r = 55
        bonus_r = 48
        jackpot_r = JACKPOT_SPOT_R
        gap = 50
        content_h = 2 * jackpot_r + gap + 2 * ante_r
        top = (h - content_h) * 0.68
        jp_cy = top + jackpot_r
        ante_cy = jp_cy + jackpot_r + gap + ante_r

        self._draw_spot_jackpot(cx, jp_cy, jackpot_r)
        self._draw_spot_circle("ante", cx, ante_cy, ante_r, "ANTE")
        bonus_cx = cx + ante_r + 85 + bonus_r
        self._draw_spot_diamond("bonus", bonus_cx, ante_cy, bonus_r, "3 CARD BONUS")

        ante_left = cx - ante_r
        self._draw_rules_button(ante_left / 2, ante_cy)

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
            self, "♠ Mississippi Stud -- Rules",
            [
                ("GAMEPLAY", [
                    "**Betting:** Place an Ante (mandatory) plus 3 Card Bonus and Jackpot side "
                    "bets (optional). Your balance must be at least 3x your Ante to deal.",
                    "**Dealing:** You're dealt 2 cards face up; 3 community cards are dealt face "
                    "down in the middle.",
                    "**3rd Street:** Fold (forfeiting the Ante) or bet 1x-3x your Ante -- the first "
                    "community card is then revealed.",
                    "**4th Street:** Fold (forfeiting the Ante and 3rd Street bet) or bet 1x-3x your "
                    "Ante -- the second community card is revealed.",
                    "**5th Street:** Fold or bet 1x-3x your Ante -- the final community card is "
                    "revealed and the hand is settled.",
                    "**Resolution:** Your final hand is your 2 cards plus all 3 community cards. "
                    "Every bet still in play (Ante + whichever streets you played) pays the SAME "
                    "odds, looked up from that hand -- see the paytable. A Pair of 6s-10s pushes; "
                    "anything below that loses.",
                    "**3 Card Bonus:** Settled on the 3 community cards alone, independent of your "
                    "own hand or fold -- it stays in action until all 3 are exposed, even if you "
                    "fold before then.",
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
                 "You always know 2 of your 5 cards up front, and see more of the board with each "
                 "street -- fold as soon as a hand looks unlikely to reach a paying Pair of Jacks "
                 "or better, since every bet you've already placed is forfeited the moment you do."),
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
            draw_chip_stack(self.canvas, tag, cx, cy, amount, max_r=CHIP_LAYER_MAX_R)
        else:
            self.canvas.create_text(cx, cy, text="tap to bet", fill=theme.FG_DIM,
                                     font=theme.font(9, weight="bold"), tags=(tag,))
        self._bind_spot(tag, key)

    def _draw_spot_diamond(self, key, cx, cy, r, label):
        tag = f"spot_{key}"
        amount = self.bets[key]
        felt_theme = self.app.settings.theme()
        theme.diamond(self.canvas, cx, cy, r, fill=felt_theme["felt_dark"],
                       outline=felt_theme["accent"], width=2, tags=(tag,))
        self.canvas.create_text(cx + r + 10, cy, text=label, fill=theme.FG, anchor="w",
                                 font=theme.font(9, weight="bold"), tags=(tag,))
        if amount:
            draw_chip_stack(self.canvas, tag, cx, cy, amount, max_r=CHIP_LAYER_MAX_R * 0.75)
        else:
            self.canvas.create_text(cx, cy, text="tap to\nbet", fill=theme.FG_DIM,
                                     font=theme.font(9, weight="bold"), justify="center", tags=(tag,))
        self._bind_spot(tag, key)

    def _draw_spot_jackpot(self, cx, cy, r):
        """The £1 jackpot side bet -- an on/off spot, same breathing-glow
        treatment every other game's own Jackpot spot uses (see e.g.
        games/three_card_poker/ui.py's own _draw_spot_jackpot, which this
        mirrors -- built independently for this game's own isolation, not
        shared code)."""
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
            face, rim = CHIP_COLORS_BY_VALUE[1]
            token_r = r - 10
            self.canvas.create_oval(cx - token_r, cy - token_r, cx + token_r, cy + token_r,
                                     fill=face, outline=rim, width=2, tags=(tag,))
            self.canvas.create_oval(cx - token_r + 7, cy - token_r + 7, cx + token_r - 7, cy + token_r - 7,
                                     outline="#ffffff", width=1, tags=(tag,))
            self.canvas.create_text(cx, cy, text="£1", fill="#ffffff",
                                     font=theme.font(11, weight="bold"), tags=(tag,))
        else:
            self.canvas.create_text(cx, cy, text="tap to\nbet £1", fill=theme.FG_DIM,
                                     font=theme.font(8, weight="bold"), justify="center", tags=(tag,))
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
    def _show_betting_controls(self):
        for w in self.action_frame.pack_slaves():
            w.pack_forget()
        self.deal_btn.pack()
        self.action_frame.pack(pady=BETTING_ACTION_FRAME_PADY)
        self.payout_canvas.pack_forget()
        self.chip_frame.pack(pady=CHIP_FRAME_PADY)
        self._draw_table()
        self._update_total()

    def _show_street_decision_controls(self):
        self.chip_frame.pack_forget()
        self.payout_canvas.pack_forget()
        for w in self.action_frame.pack_slaves():
            w.pack_forget()
        self.action_frame.pack(pady=(8, 0))
        self.bet1_btn.pack(side="left", padx=6)
        self.bet2_btn.pack(side="left", padx=6)
        self.bet3_btn.pack(side="left", padx=6)
        self.fold_btn.pack(side="left", padx=(18, 0))
        for mult, btn in ((1, self.bet1_btn), (2, self.bet2_btn), (3, self.bet3_btn)):
            self._set_bet_button_enabled(btn, self._street_bet_enabled(mult))

    def _set_bet_button_enabled(self, btn, enabled):
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
        self.action_frame.pack(pady=(8, 0))
        self.new_deal_btn.pack(side="left", padx=8)
        self.change_bets_btn.pack(side="left", padx=8)

    def _show_no_controls(self):
        self.chip_frame.pack_forget()
        self.payout_canvas.pack_forget()
        for w in self.action_frame.pack_slaves():
            w.pack_forget()
        self.action_frame.pack(pady=(8, 0))

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
        if trial_bets["jackpot"] and _max_deal_cost(trial_bets) > self.app.finance.balance + 1e-9:
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
        trial_bets = dict(self.bets)
        trial_bets[key] += delta
        balance = self.app.finance.balance
        if _max_deal_cost(trial_bets) > balance + 1e-9:
            if key == "ante":
                message = (
                    "Your balance must be at least 3x your Ante to deal (so you're able to see "
                    "every street through). Reduce your Ante or add funds."
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
        self.total_lbl.configure(text=f"Total bet: £{sum(self.bets.values())}")

    def _persist_state(self):
        save_json(self.save_path, {"bets": self.bets, "selected_chip": self.selected_chip})

    def _sanitize_bets(self, persist=True):
        if _max_deal_cost(self.bets) > self.app.finance.balance:
            self.bets = {"ante": 0, "bonus": 0, "jackpot": 0}
            if persist:
                self._persist_state()

    # ------------------------------------------------------------------ round flow
    def _on_deal(self):
        ante, bonus, jackpot = self.bets["ante"], self.bets["bonus"], self.bets["jackpot"]
        if ante <= 0:
            dialogs.info(self, "$ deal --require-ante", "You must place an Ante bet to deal.", accent=theme.WARN)
            return

        if not self.app.finance.can_afford(_max_deal_cost(self.bets)):
            choice = dialogs.choice(
                self, "$ deal --check-funds",
                "You don't have enough balance to cover these bets plus the streets ahead "
                "(your balance must be at least 3x your Ante to begin a hand).",
                [("Go Home", "home"), ("Cashier", "cashier")],
            )
            if choice == "home":
                self.app.show_frame("menu")
            elif choice == "cashier":
                self.app.show_frame("finances")
            return

        total_upfront = ante + bonus + jackpot
        self.app.finance.place_wager(total_upfront)
        self._refresh_balance()

        self.result = self.game.deal(ante, bonus_bet=bonus, jackpot_bet=jackpot)
        self.state = "playing"
        self.street = 3

        self.result_lbl.configure(text="Dealing...", fg=theme.FG)
        self._show_no_controls()

        self.fan_canvas.delete("all")
        self.fan_canvas.pack(pady=(14, 0), before=self.chip_zone)
        self._draw_fan_mat()

        self._draw_play_zones()
        self._deal_player_cards()

    def _street_bet_enabled(self, multiplier):
        assert self.result is not None
        ante = self.result.ante_bet
        bet_amount = ante * multiplier
        balance = self.app.finance.balance
        if balance + 1e-9 < bet_amount:
            return False
        if self.street != 5 and multiplier > 1 and balance - bet_amount + 1e-9 < ante:
            return False
        return True

    def _on_bet(self, multiplier):
        if self.state != "playing":
            return
        if not self._street_bet_enabled(multiplier):
            return
        assert self.result is not None
        street = self.street
        ante = self.result.ante_bet
        bet_amount = ante * multiplier
        if not self.app.finance.can_afford(bet_amount):
            dialogs.info(self, "$ bet --check-funds", "You don't have enough balance to place that bet.",
                          accent=theme.WARN)
            return

        self.app.finance.place_wager(bet_amount)
        self._refresh_balance()
        self.game.bet_street(street, multiplier)
        self._show_no_controls()

        cx, cy, r = self._street_spot_layout(street)

        def chips_placed():
            self._reveal_community_cards([street - 3], on_done=self._after_street_bet)

        # Tag matches _payout_chip_items' own spot_tag + "_chips" convention
        # (spot_tag="street_spot_{street}") so the payout animation's
        # _chip_move_away/_chip_move_in can find and clear these chips --
        # see _draw_street_spot for the matching static circle+label tag.
        self._animate_chip_place(f"street_spot_{street}_chips", cx, cy, bet_amount, r * 0.85, on_done=chips_placed)

    def _after_street_bet(self):
        if self.street < 5:
            self.street += 1
            self._show_street_decision_controls()
        else:
            self._settle_round()

    def _on_fold(self):
        if self.state != "playing":
            return
        assert self.result is not None
        street = self.street
        self.game.fold(street)
        self._show_no_controls()
        if self.result.bonus_bet > 0:
            self._fold_with_bonus()
        else:
            self._fold_without_bonus()

    def _fold_with_bonus(self):
        """Cards tuck under the Bonus spot FIRST -- immediately on folding,
        before any still-hidden community card is exposed -- and only then
        does the board get force-revealed to settle the Bonus. Matches the
        real feel of folding: your own hand clears away right away, the
        board is what plays out afterwards."""
        assert self.result is not None
        remaining = list(range(self.result.revealed_count, 3))
        self.game.reveal_remaining_for_bonus()

        def after_tuck():
            if remaining:
                self._reveal_community_cards(remaining, on_done=self._settle_round)
            else:
                self._settle_round()

        self._flip_fan_face_down(lambda: self._tuck_cards_under_bonus(after_tuck))

    def _fold_without_bonus(self):
        self._flip_fan_face_down(lambda: self._fly_cards_away(self._settle_round))

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
        return CARD_ROW_START_X + i * CARD_ROW_GAP

    def _street_spot_layout(self, street):
        return STREET_ROW_CX[street], STREET_ROW_CY, STREET_ROW_R

    def _draw_play_zones(self):
        assert self.result is not None
        self.canvas.delete("all")
        felt_theme = self.app.settings.theme()
        theme.rounded_rect(
            self.canvas, DEALER_MAT_X1, DEALER_MAT_TOP, DEALER_MAT_X2, DEALER_MAT_BOTTOM, radius=DEALER_MAT_RADIUS,
            fill=felt_theme["felt_dark"], outline=felt_theme["accent"], width=2, tags=("zone_bg",),
        )
        for i in range(3):
            x = self._community_slot_x(i) + CARD_WIDTH / 2
            self.canvas.create_text(x, DEALER_MAT_LABEL_Y, text=COMMUNITY_LABELS[i], fill=theme.ACCENT,
                                     font=theme.font(9, weight="bold"), tags=("zone_bg",))
            draw_card_back(self.canvas, self._community_slot_x(i), DEALER_Y, felt_theme["felt"],
                            felt_theme["accent"], tags=(f"community_card_{i}",))

        if self.bets["jackpot"]:
            self._draw_strip_circle("jackpot", JACKPOT_STRIP_CX, JACKPOT_BONUS_CY, JACKPOT_SPOT_R,
                                     "JACKPOT", self.bets["jackpot"])
        if self.bets["bonus"]:
            self._draw_strip_diamond("bonus", BONUS_STRIP_CX, JACKPOT_BONUS_CY, BONUS_SPOT_R,
                                      "3 CARD BONUS", self.bets["bonus"])

        for street in (3, 4, 5):
            self._draw_street_spot(street)

        self._draw_strip_circle("ante", ANTE_CX, ANTE_CY, ANTE_R, "ANTE", self.result.ante_bet)

    def _draw_street_spot(self, street):
        tag = f"street_spot_{street}"
        self.canvas.delete(tag)
        cx, cy, r = self._street_spot_layout(street)
        felt_theme = self.app.settings.theme()
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=felt_theme["felt_dark"],
                                 outline=felt_theme["accent"], width=2, tags=(tag,))
        self.canvas.create_text(cx, cy - r - 12, text=STREET_LABELS[street], fill=theme.FG,
                                 font=theme.font(8, weight="bold"), tags=(tag,))

    def _draw_strip_circle(self, key, cx, cy, r, label, amount):
        tag = f"strip_{key}"
        self.canvas.delete(tag)
        felt_theme = self.app.settings.theme()
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=felt_theme["felt_dark"],
                                 outline=felt_theme["accent"], width=2, tags=(tag,))
        self.canvas.create_text(cx, cy - r - 10, text=label, fill=theme.FG,
                                 font=theme.font(9, weight="bold"), tags=(tag,))
        draw_chip_stack(self.canvas, (tag, f"{tag}_chips"), cx, cy, amount, max_r=20)

    def _draw_strip_diamond(self, key, cx, cy, r, label, amount):
        tag = f"strip_{key}"
        self.canvas.delete(tag)
        felt_theme = self.app.settings.theme()
        theme.diamond(self.canvas, cx, cy, r, fill=felt_theme["felt_dark"],
                       outline=felt_theme["accent"], width=2, tags=(tag,))
        self.canvas.create_text(cx + r + 8, cy, text=label, fill=theme.FG, anchor="w",
                                 font=theme.font(9, weight="bold"), tags=(tag,))
        draw_chip_stack(self.canvas, (tag, f"{tag}_chips"), cx, cy, amount, max_r=18)

    def _draw_player_card_at(self, i, card, x, y, face_up=True):
        tag = f"player_card_{i}"
        self.fan_canvas.delete(tag)
        if face_up:
            draw_card(self.fan_canvas, x, y, card, tags=(tag,))
        else:
            draw_card_back(self.fan_canvas, x, y, self._current_felt,
                            self.app.settings.theme()["accent"], tags=(tag,))

    def _fan_slots(self):
        cx = FAN_CANVAS_WIDTH / 2
        xs = [cx - FAN_GAP / 2 - CARD_WIDTH / 2, cx + FAN_GAP / 2 - CARD_WIDTH / 2]
        return [(x, FAN_Y) for x in xs]

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

    def _animate_chip_place(self, tag, cx, cy, amount, max_r, on_done=None):
        def frame(t):
            self.canvas.delete(tag)
            r = max_r * t
            if r > 2:
                draw_chip_stack(self.canvas, tag, cx, cy, amount, r)

        self._animate(CHIP_PLACE_MS, frame, on_done=on_done)

    # ------------------------------------------------------------------ deal-in / streets / fold
    def _deal_player_cards(self):
        assert self.result is not None
        cards = self.result.player_cards
        fan_slots = self._fan_slots()

        def deal_one(i):
            tx, ty = fan_slots[i]
            sx, sy = tx, ty - 90

            def frame(t, i=i, sx=sx, sy=sy, tx=tx, ty=ty):
                self._draw_player_card_at(i, cards[i], sx + (tx - sx) * t, sy + (ty - sy) * t, face_up=True)

            self._animate(DEAL_IN_DROP_MS, frame, on_done=(self._on_player_cards_dealt if i == 1 else None))

        if self.app.settings.get("animations_enabled"):
            self.after(350, lambda: self._run_staggered(2, DEAL_IN_STAGGER_MS, deal_one))
        else:
            self._run_staggered(2, DEAL_IN_STAGGER_MS, deal_one)

    def _on_player_cards_dealt(self):
        self.result_lbl.configure(text="Your cards are dealt. Play or Fold?", fg=theme.FG)
        self._show_street_decision_controls()

    def _reveal_community_cards(self, indices, on_done):
        """Flips whichever of the 3 community cards are in `indices` face
        up, in order -- either the single card a street bet just revealed,
        or (on a Bonus-active fold) every remaining one at once."""
        result = self.result
        assert result is not None

        def flip_one(pos):
            i = indices[pos]
            cx_slot = self._community_slot_x(i) + CARD_WIDTH / 2
            self._animate_flip(
                self.canvas, f"community_card_{i}", cx_slot, DEALER_Y, result.community_cards[i],
                reveal=True, duration=COMMUNITY_FLIP_MS,
                on_done=(on_done if pos == len(indices) - 1 else None),
            )

        self._run_staggered(len(indices), COMMUNITY_FLIP_STAGGER_MS, flip_one)

    def _flip_fan_face_down(self, on_done):
        assert self.result is not None
        cards = self.result.player_cards
        slots = self._fan_slots()

        def flip_one(i):
            sx, sy = slots[i]
            cx_slot = sx + CARD_WIDTH / 2
            self._animate_flip(
                self.fan_canvas, f"player_card_{i}", cx_slot, sy, cards[i], reveal=False, duration=FOLD_FLIP_MS,
                on_done=(on_done if i == len(slots) - 1 else None),
            )

        self._run_staggered(len(slots), 70, flip_one)

    def _fly_cards_away(self, on_done):
        slots = self._fan_slots()

        def slide_one(i):
            sx, sy = slots[i]

            def frame(t, sx=sx, sy=sy):
                tx, ty = FOLD_FLY_TARGET
                self._draw_player_card_at(i, None, sx + (tx - sx) * t, sy + (ty - sy) * t, face_up=False)

            self._animate(FOLD_FLY_MS, frame, on_done=(on_done if i == len(slots) - 1 else None))

        self._run_staggered(len(slots), FOLD_FLY_STAGGER_MS, slide_one)

    def _tuck_cards_under_bonus(self, on_done):
        """Fold, with an active Bonus bet: the (already face-down) player
        cards slide from the fan up to rest tucked just under the Bonus
        spot -- still visibly "in play" since the Bonus hasn't settled yet.
        A literal cross-canvas slide isn't possible (fan_canvas and
        self.canvas are separate widgets), so like every other game's own
        "tuck under a spot" move, this is really two animations timed to
        read as one: the fan shrinks away to a point, then the cards grow
        back in at the Bonus spot."""
        assert self.result is not None
        cards = self.result.player_cards
        fan_slots = self._fan_slots()
        offsets = [-REST_CARD_FAN_OFFSET / 2, REST_CARD_FAN_OFFSET / 2]
        vanish_cx, vanish_cy = FAN_CANVAS_WIDTH / 2, 0

        def vanish_frame(t):
            for i, (sx, sy) in enumerate(fan_slots):
                scx, scy = sx + CARD_WIDTH / 2, sy + CARD_HEIGHT / 2
                cx = scx + (vanish_cx - scx) * t
                cy = scy + (vanish_cy - scy) * t
                w = CARD_WIDTH * (1 - t)
                h = CARD_HEIGHT * (1 - t)
                tag = f"player_card_{i}"
                self.fan_canvas.delete(tag)
                if w > 3 and h > 3:
                    draw_card_back(self.fan_canvas, cx - w / 2, cy - h / 2, self._current_felt,
                                    self.app.settings.theme()["accent"], width=w, height=h, tags=(tag,))

        def grow_frame(t):
            for i in range(2):
                tcx, tcy = BONUS_STRIP_CX + offsets[i], JACKPOT_BONUS_CY
                w = REST_CARD_WIDTH * t
                h = REST_CARD_HEIGHT * t
                tag = f"player_card_{i}"
                self.canvas.delete(tag)
                if w > 3 and h > 3:
                    draw_card_back(self.canvas, tcx - w / 2, tcy - h / 2, self._current_felt,
                                    self.app.settings.theme()["accent"], width=w, height=h,
                                    tags=(tag, "folded_hand"))
                    self.canvas.tag_lower(tag, "strip_bonus")

        def start_grow():
            self._animate(BONUS_TUCK_GROW_MS, grow_frame, on_done=on_done)

        self._animate(BONUS_TUCK_VANISH_MS, vanish_frame, on_done=start_grow)

    # ------------------------------------------------------------------ settle / payout
    def _settle_round(self):
        assert self.result is not None
        result = self.game.settle(jackpot_amount=self.app.jackpot.amount)

        if result.total_returned > 0:
            self.app.finance.add_return(result.total_returned)
        self.app.finance.record_round_played(result.net_result)
        self.app.game_stats.record_round_net(GAME_KEY, result.net_result)
        for key, bet, ret in self._resolved_bet_totals(result):
            self.app.game_stats.record_bet(GAME_KEY, key, bet, ret)
        self.app.game_stats.record_hand(GAME_KEY, hand_outcome_label(result))
        if result.jackpot_won:
            self.app.jackpot.win()
        elif result.jackpot_pool_partial_fraction:
            self.app.jackpot.set_amount(self.app.jackpot.amount * (1 - result.jackpot_pool_partial_fraction))

        self._show_no_controls()
        self._animate_payouts(result, lambda: self._on_round_settled(result))

    def _resolved_bet_totals(self, result):
        totals = []
        if result.ante_bet:
            totals.append(("ante", result.ante_bet, result.ante_return))
        if result.third_street_bet:
            totals.append(("third_street", result.third_street_bet, result.third_street_return))
        if result.fourth_street_bet:
            totals.append(("fourth_street", result.fourth_street_bet, result.fourth_street_return))
        if result.fifth_street_bet:
            totals.append(("fifth_street", result.fifth_street_bet, result.fifth_street_return))
        if result.bonus_bet:
            totals.append(("bonus", result.bonus_bet, result.bonus_return))
        if result.jackpot_bet:
            totals.append(("jackpot", result.jackpot_bet, result.jackpot_return))
        return totals

    def _payout_chip_items(self, result):
        layout = {
            "ante": (ANTE_CX, ANTE_CY, "strip_ante", 20),
            "third_street": (*self._street_spot_layout(3)[:2], "street_spot_3", STREET_ROW_R * 0.85),
            "fourth_street": (*self._street_spot_layout(4)[:2], "street_spot_4", STREET_ROW_R * 0.85),
            "fifth_street": (*self._street_spot_layout(5)[:2], "street_spot_5", STREET_ROW_R * 0.85),
            "bonus": (BONUS_STRIP_CX, JACKPOT_BONUS_CY, "strip_bonus", 18),
            "jackpot": (JACKPOT_STRIP_CX, JACKPOT_BONUS_CY, "strip_jackpot", 20),
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

    def _animate_payouts(self, result, on_done):
        items = self._payout_chip_items(result)
        losing = [it for it in items if it["ret"] == 0]
        winning = [it for it in items if it["ret"] > it["bet"]]

        stages = (
            [lambda cb, it=it: self._chip_move_away(it, cb) for it in losing]
            + [lambda cb, it=it: self._chip_move_in(it, cb) for it in winning]
        )
        self._run_sequential(stages, on_done)

    def _on_round_settled(self, result):
        # fan_canvas is hidden once resolved -- same convention every other
        # game's own fanned hand follows (and needed here too: the fixed,
        # non-resizable 1200x820 window has no spare room to keep it packed
        # alongside the full play-screen canvas and the payout panel at
        # once). The final hand's own rank is still named in the result
        # caption (see _show_result), and the 3 community cards that made it
        # stay visible on the felt above.
        self.fan_canvas.pack_forget()
        self._refresh_balance()
        self.app.on_balance_changed()
        self._show_result(result)
        self._show_round_over_controls()
        self.state = "resolved"

    def _show_result(self, result):
        headline = {
            "fold": "You folded.",
            "win": "You win!",
            "lose": "No qualifying hand.",
            "push": "Push — stakes returned.",
        }[result.outcome]
        color = {
            "fold": theme.FG_DIM,
            "win": theme.WIN_COLOR,
            "lose": theme.LOSE_COLOR,
            "push": theme.PUSH_COLOR,
        }[result.outcome]

        if result.folded:
            text = headline
        else:
            text = f"{headline}  (Your hand: {result.final_eval[1]})"
        self.result_lbl.configure(text=text, fg=color)

        self.payout_canvas.pack(expand=True)
        self._draw_payout_panel(result)

    def _payout_rows(self, result):
        rows = []
        if result.ante_bet:
            rows.append((f"Ante £{result.ante_bet:.0f}", result.ante_return - result.ante_bet))
        if result.third_street_bet:
            rows.append((f"3rd Street £{result.third_street_bet:.0f}",
                          result.third_street_return - result.third_street_bet))
        if result.fourth_street_bet:
            rows.append((f"4th Street £{result.fourth_street_bet:.0f}",
                          result.fourth_street_return - result.fourth_street_bet))
        if result.fifth_street_bet:
            rows.append((f"5th Street £{result.fifth_street_bet:.0f}",
                          result.fifth_street_return - result.fifth_street_bet))
        if result.bonus_bet:
            label = f"3 Card Bonus £{result.bonus_bet:.0f}"
            if result.bonus_eval is not None:
                label = f"3 Card Bonus ({result.bonus_eval[1]})"
            rows.append((label, result.bonus_return - result.bonus_bet))
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
        y = 38
        for label, net in rows:
            canvas.create_text(24, y, text=label, fill=theme.FG, font=theme.font(10), anchor="w")
            canvas.create_text(w - 24, y, text=_format_signed(net), fill=_net_color(net),
                                font=theme.font(10, weight="bold"), anchor="e")
            y += 16

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
        # _retheme_widget only fixes up plain widget backgrounds -- the fan
        # mat is a *drawn* canvas rectangle (covering nearly all of
        # fan_canvas, drawn once per deal by _draw_fan_mat), so it keeps its
        # stale felt_dark fill after a live theme switch unless it's
        # explicitly redrawn here too. Cheap and harmless to call even when
        # nothing's been dealt yet -- find_withtag comes back empty and it's
        # a no-op.
        if self.fan_canvas.find_withtag("fan_mat_bg"):
            self.fan_canvas.delete("fan_mat_bg")
            self._draw_fan_mat()
            self.fan_canvas.tag_lower("fan_mat_bg")
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
