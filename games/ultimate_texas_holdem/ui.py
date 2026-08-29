import math
import os
import tkinter as tk
from typing import Optional

from core.persistence import load_json, save_json
from games.ultimate_texas_holdem.logic import (
    BLIND_PAYTABLE,
    BLIND_ROYAL_FLUSH,
    BLIND_STRAIGHT_FLUSH,
    FIVE_CARD_FLUSH,
    FIVE_CARD_HIGH_CARD,
    FIVE_CARD_STRAIGHT,
    FIVE_CARD_STRAIGHT_FLUSH,
    FIVE_CARD_THREE_OF_A_KIND,
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
    RoundResult,
    TRIPS_PAYTABLE,
    TRIPS_ROYAL_FLUSH,
    TRIPS_STRAIGHT_FLUSH,
    UltimateTexasHoldemGame,
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

STATE_FILENAME = "ultimate_texas_holdem_state.json"
DEFAULT_STATE = {"bets": {"ante": 0, "trips": 0, "jackpot": 0}, "selected_chip": 5}

# --- Layout constants ------------------------------------------------------
# Same "fixed pixel block, centred in the window" convention as every other
# game -- see three_card_poker/ui.py's own module-level comment. This game's
# own canvas is deliberately isolated from every sibling game's, per the
# "isolated from the other games" instruction it was commissioned under.
CANVAS_WIDTH = 760
# Actually a bit shorter than Mississippi Stud's own now that Play shares a
# row with Ante/Blind instead of needing a separate one underneath -- the
# window itself is a fixed, non-resizable 1200x820 (see main.py) with no
# room to spare regardless.
CANVAS_HEIGHT = 368

PAYTABLE_WIDTH = 240
PAYTABLE_HEIGHT = 360
# Scaled down from the other games' own ~380x186 -- this one floats in a
# corner of the screen (see _show_payout_panel) rather than owning a
# dedicated, generously-sized zone of its own, so it's sized to fit
# comfortably there instead. Still fits up to 5 rows (Ante/Blind/Play/
# Trips/Jackpot) plus the Round Net total at a slightly tighter pitch.
PAYOUT_PANEL_WIDTH = 300
PAYOUT_PANEL_HEIGHT = 160

JACKPOT_SPOT_R = 22
TRIPS_SPOT_R = 28     # the diamond's own "radius" (centre to each point)

# The one chip-stack size used for Ante/Blind/Play on the play screen --
# shared by their initial display, the Play bet's own placement animation,
# and the payout layout below, so a stake chip and its later payout chip
# are always drawn at the identical size instead of drifting between them.
ROW_CHIP_MAX_R = 20

CONTENT_TOP_MARGIN = 35

# --- Dealer area: a 5-card community mat, with a smaller 2-card mat (the
# Dealer's own hidden hand) to its left, matching the felt language of the
# player's own fan_canvas mat rather than the community mat's own accent
# border -- see _draw_play_zones.
CARD_ROW_GAP = CARD_WIDTH + 15
COMMUNITY_ROW_WIDTH = 4 * CARD_ROW_GAP + CARD_WIDTH
COMMUNITY_MAT_MARGIN = 30
COMMUNITY_MAT_WIDTH = COMMUNITY_ROW_WIDTH + 2 * COMMUNITY_MAT_MARGIN

DEALER_HAND_GAP = 20
DEALER_HAND_WIDTH = 2 * CARD_WIDTH + DEALER_HAND_GAP
DEALER_HAND_MAT_MARGIN = 20
DEALER_HAND_MAT_WIDTH = DEALER_HAND_WIDTH + 2 * DEALER_HAND_MAT_MARGIN

GAP_BETWEEN_MATS = 16
_TOTAL_DEALER_AREA_WIDTH = DEALER_HAND_MAT_WIDTH + GAP_BETWEEN_MATS + COMMUNITY_MAT_WIDTH
_DEALER_AREA_LEFT = (CANVAS_WIDTH - _TOTAL_DEALER_AREA_WIDTH) / 2

DEALER_HAND_MAT_X1 = _DEALER_AREA_LEFT
DEALER_HAND_MAT_X2 = DEALER_HAND_MAT_X1 + DEALER_HAND_MAT_WIDTH
COMMUNITY_MAT_X1 = DEALER_HAND_MAT_X2 + GAP_BETWEEN_MATS
COMMUNITY_MAT_X2 = COMMUNITY_MAT_X1 + COMMUNITY_MAT_WIDTH

DEALER_MAT_RADIUS = 12
DEALER_MAT_TOP = 6
DEALER_MAT_LABEL_Y = DEALER_MAT_TOP + 8
DEALER_Y = DEALER_MAT_TOP + 18                   # every card on this row's top-left y
DEALER_MAT_BOTTOM = DEALER_Y + CARD_HEIGHT + 8

# --- Ante = Blind's own X positions, computed first since Trips/Jackpot
# now align directly above them (Trips above Ante, Jackpot above Blind) --
# one combined Play-Ante-Blind row, Play sitting to Ante's LEFT the same
# distance Blind sits to its right (no "=" glyph on that side -- Play isn't
# part of the linked Ante/Blind figure, just laid out at matching spacing).
# Ante and Blind are one linked figure -- internally tracked as a single
# bets["ante"] value, Blind simply mirrors it, so the two can never drift
# apart (see the module docstring below).
ANTE_R = 32
BLIND_R = ANTE_R
PLAY_R = ANTE_R
ANTE_CX = CANVAS_WIDTH / 2
EQUALS_CX = ANTE_CX + ANTE_R + 25
BLIND_CX = EQUALS_CX + 25 + BLIND_R
PLAY_CX = ANTE_CX - (BLIND_CX - ANTE_CX)

# Pushed down close to the canvas's own bottom edge (leaving just a small
# margin) rather than leaving a large empty gap between this row and the
# caption below the canvas -- makes full use of the vertical room the old
# separate Play row used to eat into (see git history).
_ROW_BOTTOM_MARGIN = 16
ANTE_CY = CANVAS_HEIGHT - _ROW_BOTTOM_MARGIN - ANTE_R

# --- Jackpot + Trips -- a row of their own, mirroring the Ante/Blind row
# below: Trips sits directly above Ante, Jackpot directly above Blind (not
# diagonally offset -- "in line with" Trips, same height). Centred in the
# gap between the dealer mat and the Ante/Blind/Play row, rather than
# hugging the dealer mat and leaving a big empty gap below itself.
ROW1_CY = (DEALER_MAT_BOTTOM + (ANTE_CY - ANTE_R)) / 2
TRIPS_CX = ANTE_CX
TRIPS_CY = ROW1_CY
JACKPOT_CX = BLIND_CX
JACKPOT_CY = ROW1_CY
PLAY_CY = ANTE_CY

# Settlement/payout "centre" -- the community mat's own centre, the closest
# thing this game has to "the house" (mirrors Mississippi Stud's own
# SETTLE_CENTER convention).
SETTLE_CENTER_X = (COMMUNITY_MAT_X1 + COMMUNITY_MAT_X2) / 2
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

# --- Player's own hand (2 cards) -- same narrow (half-width) canvas as
# Mississippi Stud's own fan_canvas, below the action buttons.
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

# --- Animation pacing --------------------------------------------------
DEAL_IN_STAGGER_MS = 110
DEAL_IN_DROP_MS = 220
CHIP_PLACE_MS = 180
COMMUNITY_FLIP_MS = 220
COMMUNITY_FLIP_STAGGER_MS = 300
# A beat of stillness after each street's own reveal finishes -- flop, then
# turn, then river -- before the next one starts (or, after the river, the
# Dealer's own cards) -- see _reveal_to_river. Applies whether the cascade
# was triggered by a Play bet or by folding; a fold still shows the whole
# board and the Dealer's hand out, just without a Play bet ever landing.
STREET_REVEAL_PAUSE_MS = 650        # turn -> river
FLOP_TO_TURN_PAUSE_MS = 700         # flop (first 3) -> turn (4th)
RIVER_TO_DEALER_PAUSE_MS = 700      # river (5th) -> Dealer's own cards
# Beat of stillness after the Dealer's own 2 cards finish flipping, before
# the round is settled and payouts animate in -- see _reveal_dealer_cards.
DEALER_TO_PAYOUT_PAUSE_MS = 600
FOLD_FLIP_MS = 180
FOLD_FLY_MS = 220
FOLD_FLY_STAGGER_MS = 70
FOLD_FLY_TARGET = (FAN_CANVAS_WIDTH + 90, -50)


def _ease_out_cubic(t):
    return 1 - (1 - t) ** 3


_lerp_color = theme.lerp_color


def _format_payout(payout):
    """3:2 for the Blind Flush's own fractional multiplier, N:1 for every
    other numeric payout, or the string as-is (e.g. "Push")."""
    if isinstance(payout, str):
        return payout
    if payout == 1.5:
        return "3:2"
    return f"{payout:.0f}:1"


# Paytable rows, read straight from logic.py's own constants so the panel can
# never drift out of sync with what's actually paid out.
TRIPS_PAYTABLE_ROWS = [
    ("Royal Flush", TRIPS_ROYAL_FLUSH),
    ("Straight Flush", TRIPS_STRAIGHT_FLUSH),
    ("Four of a Kind", TRIPS_PAYTABLE[FOUR_OF_A_KIND]),
    ("Full House", TRIPS_PAYTABLE[FULL_HOUSE]),
    ("Flush", TRIPS_PAYTABLE[FIVE_CARD_FLUSH]),
    ("Straight", TRIPS_PAYTABLE[FIVE_CARD_STRAIGHT]),
    ("Three of a Kind", TRIPS_PAYTABLE[FIVE_CARD_THREE_OF_A_KIND]),
]
BLIND_PAYTABLE_ROWS = [
    ("Royal Flush", BLIND_ROYAL_FLUSH),
    ("Straight Flush", BLIND_STRAIGHT_FLUSH),
    ("Four of a Kind", BLIND_PAYTABLE[FOUR_OF_A_KIND]),
    ("Full House", BLIND_PAYTABLE[FULL_HOUSE]),
    ("Flush", BLIND_PAYTABLE[FIVE_CARD_FLUSH]),
    ("Straight", BLIND_PAYTABLE[FIVE_CARD_STRAIGHT]),
]
PAYTABLE_SECTIONS = [("TRIPS", TRIPS_PAYTABLE_ROWS), ("BLIND (must beat dealer)", BLIND_PAYTABLE_ROWS)]

JACKPOT_PAYTABLE_ROWS = [
    ("Royal Flush", "100% JACKPOT"),
    ("Straight Flush", "10% JACKPOT"),
    ("Four of a Kind", f"£{JACKPOT_FOUR_OF_A_KIND_PAYOUT:.0f}"),
    ("Full House", f"£{JACKPOT_FULL_HOUSE_PAYOUT:.0f}"),
    ("Flush", f"£{JACKPOT_FLUSH_PAYOUT:.0f}"),
    ("Straight", f"£{JACKPOT_STRAIGHT_PAYOUT:.0f}"),
    ("Three of a Kind", f"£{JACKPOT_THREE_OF_A_KIND_PAYOUT:.0f}"),
]
JACKPOT_PAYTABLE_HIGHLIGHT_ROW = 0  # Royal Flush


def _max_deal_cost(bets):
    """Worst-case upfront total the player is committing to by dealing --
    Ante + the always-equal Blind, plus Trips/Jackpot -- OR 3x the Ante
    alone, whichever is larger. The 3x-Ante figure is the literal validation
    rule ("balance must contain at least 3x the Ante to begin a hand"); the
    upfront-total figure is just plain affordability of what's actually
    about to be deducted -- taking the max of the two means a large Trips/
    Jackpot bet can never sneak past the 3x-Ante rule's own headroom."""
    upfront = bets["ante"] * 2 + bets["trips"] + bets["jackpot"]
    return max(bets["ante"] * 3, upfront)


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


_RANK_WORDS = {14: "Ace", 13: "King", 12: "Queen", 11: "Jack"}


def _rank_word(value):
    return _RANK_WORDS.get(value, str(value))


def _hand_description(hand_eval):
    """A short, human-readable description of a hand for the round-result
    caption -- just the rank name for anything descriptive enough on its
    own ("Flush", "Two Pair", ...), but High Card additionally names its
    own top card, since "High Card" alone says almost nothing on its own."""
    rank, name, tiebreak = hand_eval
    if rank == FIVE_CARD_STRAIGHT_FLUSH and tiebreak[0] == 14:
        return "Royal Flush"
    if rank == FIVE_CARD_HIGH_CARD:
        return f"High Card, {_rank_word(tiebreak[0])}"
    return name


class UltimateTexasHoldemFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.BG)
        self.app = app
        self.game = UltimateTexasHoldemGame()
        self.result: Optional[RoundResult] = None
        self.state = "betting"    # betting -> playing -> resolved
        self.stage = "preflop"    # preflop -> postflop -> postturn, while state == "playing"

        self.save_path = os.path.join(app.data_dir, STATE_FILENAME)
        saved = load_json(self.save_path, DEFAULT_STATE)
        saved_bets = saved.get("bets", DEFAULT_STATE["bets"])
        self.bets = {
            "ante": int(saved_bets.get("ante", 0)),
            "trips": int(saved_bets.get("trips", 0)),
            "jackpot": int(saved_bets.get("jackpot", 0)),
        }
        self.selected_chip = int(saved.get("selected_chip", DEFAULT_STATE["selected_chip"]))
        self._sanitize_bets(persist=False)

        self.chip_canvases = {}
        self._jackpot_pulse_t = 0.0

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
        tk.Label(top_bar, text="Ultimate Texas Hold'em", bg=theme.BG_ELEVATED, fg=theme.ACCENT,
                 font=theme.font(16, weight="bold")).pack(side="left", padx=10)
        self.balance_lbl = tk.Label(top_bar, text="£0.00", bg=theme.BG_ELEVATED, fg=theme.WIN_COLOR,
                                     font=theme.font(12, weight="bold"))
        self.balance_lbl.pack(side="right", padx=20)
        theme.breadcrumb(top_bar, "ultimate_texas_holdem", bg=theme.BG_ELEVATED,
                          player=self.app.current_player["name"]).pack(side="right", padx=(6, 6))

        body = tk.Frame(self, bg=felt_theme["felt"])
        body.pack(fill="both", expand=True)

        content = tk.Frame(body, bg=felt_theme["felt"])
        content.place(relx=0.5, y=CONTENT_TOP_MARGIN, anchor="n")

        game_col = tk.Frame(content, bg=felt_theme["felt"])
        # anchor="n": pins game_col (the canvas, Ante box and all) to the
        # top of its cavity regardless of its own natural height changing
        # between states -- see Mississippi Stud's own identical fix for
        # the "jump" bug this exact omission caused there.
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
            game_col, text="Place your Ante and Blind bets to begin.", bg=felt_theme["felt"], fg=theme.FG,
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
        self.bet4_btn = tk.Button(
            self.action_frame, text="BET 4x", font=theme.font(12, weight="bold"), relief="flat",
            padx=18, pady=10, cursor="hand2", highlightthickness=1, command=lambda: self._on_bet(4),
        )
        self.bet3_btn = tk.Button(
            self.action_frame, text="BET 3x", font=theme.font(12, weight="bold"), relief="flat",
            padx=18, pady=10, cursor="hand2", highlightthickness=1, command=lambda: self._on_bet(3),
        )
        self.bet2_btn = tk.Button(
            self.action_frame, text="BET 2x", font=theme.font(12, weight="bold"), relief="flat",
            padx=18, pady=10, cursor="hand2", highlightthickness=1, command=lambda: self._on_bet(2),
        )
        self.bet1_btn = tk.Button(
            self.action_frame, text="BET", font=theme.font(12, weight="bold"), relief="flat",
            padx=18, pady=10, cursor="hand2", highlightthickness=1, command=lambda: self._on_bet(1),
        )
        self.check_btn = tk.Button(
            self.action_frame, text="CHECK", bg=theme.GREY_BTN_BG, fg=theme.FG,
            font=theme.font(12, weight="bold"), relief="flat", padx=18, pady=10, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.GREY_BTN_BORDER,
            command=self._on_check,
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

        # The round-result panel lives in the bottom-left corner of the
        # whole screen (see _show_result/_on_round_settled) rather than in
        # chip_zone's own reserved spot -- so, unlike every other game in
        # this app, the player's own fan_canvas hand never has to be hidden
        # to make room for it once a round resolves; it just stays on
        # screen throughout. Parented to `self` (not game_col) so its
        # place() coordinates are relative to the whole game screen.
        self.payout_canvas = tk.Canvas(
            self, width=PAYOUT_PANEL_WIDTH, height=PAYOUT_PANEL_HEIGHT,
            bg=felt_theme["felt"], highlightthickness=0,
        )

        self.chip_frame = tk.Frame(self.chip_zone, bg=felt_theme["felt"])
        tk.Label(
            self.chip_frame, text="Tap a chip, then tap Ante / Blind / Trips / Jackpot to place it",
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
            canvas.create_text(20, y, text=label, fill=theme.FG, font=theme.font(9), anchor="w")
            canvas.create_text(w - 20, y, text=_format_payout(payout), fill=accent,
                                font=theme.font(9, weight="bold"), anchor="e")
            y += 19
        return y

    # ------------------------------------------------------------------ betting table
    def _draw_table(self):
        """The betting screen's own layout -- generously spaced (matching
        Three Card Poker's/Mississippi Stud's own betting screens), unlike
        the play screen's tightly-packed one: reused nothing but the spot-
        drawing *methods* from the play-screen constants above, computing
        its own bigger radii/gaps fresh here rather than inheriting the
        play canvas's own cramped budget."""
        self.canvas.delete("all")
        w, h = CANVAS_WIDTH, CANVAS_HEIGHT
        cx = w / 2

        ante_r = 52
        blind_r = 52
        trips_r = 44
        jackpot_r = 30
        gap_trips_ante = 46
        diagonal_x = 78
        diagonal_y = 62

        content_h = jackpot_r + diagonal_y + trips_r + gap_trips_ante + 2 * ante_r
        top = (h - content_h) * 0.6
        jackpot_cy = top + jackpot_r
        trips_cy = jackpot_cy + diagonal_y
        ante_cy = trips_cy + trips_r + gap_trips_ante + ante_r

        trips_cx = cx
        jackpot_cx = cx + diagonal_x
        ante_cx = cx
        equals_cx = ante_cx + ante_r + 25
        blind_cx = equals_cx + 25 + blind_r

        self._draw_spot_jackpot(jackpot_cx, jackpot_cy, jackpot_r)
        self._draw_spot_diamond("trips", trips_cx, trips_cy, trips_r, "TRIPS")
        self._draw_spot_ante_blind(ante_cx, blind_cx, equals_cx, ante_cy, ante_r, blind_r)

        ante_left = ante_cx - ante_r
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
            self, "♠ Ultimate Texas Hold'em -- Rules",
            [
                ("GAMEPLAY", [
                    "**Betting:** Place equal Ante and Blind bets (linked together) plus Trips "
                    "and Jackpot side bets (optional). Your balance must be at least 3x your "
                    "Ante to deal.",
                    "**Dealing:** You and the dealer are each dealt 2 cards; 5 shared community "
                    "cards are dealt face down.",
                    "**Pre-flop:** Bet 4x or 3x your Ante into Play, or Check -- the flop (first "
                    "3 community cards) is then revealed.",
                    "**Post-flop:** If you haven't bet yet, bet 2x your Ante or Check -- the turn "
                    "is then revealed.",
                    "**Post-turn:** If you still haven't bet, bet 1x your Ante or Fold (forfeiting "
                    "Ante, Blind and Trips) -- the river is then revealed.",
                    "**Resolution:** Your hand and the dealer's are each the best 5 of your own "
                    "2 cards plus all 5 community cards. The dealer needs a Pair or better to "
                    "qualify -- if they don't, the Ante pushes but Play and Blind still settle by "
                    "the actual comparison. A win pays Ante and Play 1:1; the Blind only pays "
                    "(see paytable) if you win with a Straight or better, otherwise it pushes.",
                    "**Trips:** Settled on your own best 7-card hand alone, Three of a Kind or "
                    "better -- independent of beating the dealer, forfeited on a Fold.",
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
                 "Betting early (4x/3x) commits more money but locks in your best odds against "
                 "the dealer's own unknown hand -- checking costs nothing but forfeits that "
                 "extra leverage, so it pays to bet big with a strong starting hand and check "
                 "along with a weak one, folding only once the board makes it clearly hopeless."),
            ],
        )

    def _draw_spot_ante_blind(self, ante_cx, blind_cx, equals_cx, cy, ante_r, blind_r):
        amount = self.bets["ante"]
        felt_theme = self.app.settings.theme()

        tag = "spot_ante"
        self.canvas.create_oval(ante_cx - ante_r, cy - ante_r, ante_cx + ante_r, cy + ante_r,
                                 fill=felt_theme["felt_dark"], outline=felt_theme["accent"], width=2, tags=(tag,))
        self.canvas.create_text(ante_cx, cy - ante_r - 12, text="ANTE", fill=theme.FG,
                                 font=theme.font(9, weight="bold"), tags=(tag,))
        if amount:
            draw_chip_stack(self.canvas, tag, ante_cx, cy, amount, max_r=CHIP_LAYER_MAX_R * 0.7)
        else:
            self.canvas.create_text(ante_cx, cy, text="tap to\nbet", fill=theme.FG_DIM,
                                     font=theme.font(9, weight="bold"), justify="center", tags=(tag,))
        self._bind_spot(tag, "ante")

        self.canvas.create_text(equals_cx, cy, text="=", fill=theme.FG_DIM,
                                 font=theme.font(22, weight="bold"), tags=("equals_glyph",))

        tag2 = "spot_blind"
        self.canvas.create_oval(blind_cx - blind_r, cy - blind_r, blind_cx + blind_r, cy + blind_r,
                                 fill=felt_theme["felt_dark"], outline=felt_theme["accent"], width=2, tags=(tag2,))
        self.canvas.create_text(blind_cx, cy - blind_r - 12, text="BLIND", fill=theme.FG,
                                 font=theme.font(9, weight="bold"), tags=(tag2,))
        if amount:
            draw_chip_stack(self.canvas, tag2, blind_cx, cy, amount, max_r=CHIP_LAYER_MAX_R * 0.7)
        else:
            self.canvas.create_text(blind_cx, cy, text="tap to\nbet", fill=theme.FG_DIM,
                                     font=theme.font(9, weight="bold"), justify="center", tags=(tag2,))
        # Blind mirrors Ante -- tapping it adjusts the SAME "ante" bet key,
        # per the module docstring: there's no separate way to place them
        # unequal, so they're tracked as one figure, not two.
        self._bind_spot(tag2, "ante")

    def _draw_spot_diamond(self, key, cx, cy, r, label):
        tag = f"spot_{key}"
        amount = self.bets[key]
        felt_theme = self.app.settings.theme()
        theme.diamond(self.canvas, cx, cy, r, fill=felt_theme["felt_dark"],
                       outline=felt_theme["accent"], width=2, tags=(tag,))
        self.canvas.create_text(cx + r + 10, cy, text=label, fill=theme.FG, anchor="w",
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
            outline_color = _lerp_color(felt_theme["felt_dark"], felt_theme["accent"], t)
        else:
            outline_color = felt_theme["accent"]
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=felt_theme["felt_dark"],
                                 outline=outline_color, width=3, tags=(tag,))
        self.canvas.create_text(cx, cy - r - 12, text="JACKPOT", fill=theme.FG,
                                 font=theme.font(9, weight="bold"), tags=(tag,))
        if placed:
            face, rim = CHIP_COLORS_BY_VALUE[1]
            token_r = r - 8
            self.canvas.create_oval(cx - token_r, cy - token_r, cx + token_r, cy + token_r,
                                     fill=face, outline=rim, width=2, tags=(tag,))
            self.canvas.create_oval(cx - token_r + 6, cy - token_r + 6, cx + token_r - 6, cy + token_r - 6,
                                     outline="#ffffff", width=1, tags=(tag,))
            self.canvas.create_text(cx, cy, text="£1", fill="#ffffff",
                                     font=theme.font(10, weight="bold"), tags=(tag,))
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
        """The round-result panel floats in the bottom-left corner of the
        whole game screen -- placed relative to `self`, independent of
        game_col's own pack stack, so the player's fan_canvas hand above it
        never has to move or hide to make room for it."""
        self.payout_canvas.place(x=20, rely=1.0, y=-20, anchor="sw")

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
        if self.stage == "preflop":
            self.bet4_btn.pack(side="left", padx=6)
            self.bet3_btn.pack(side="left", padx=6)
            self.check_btn.pack(side="left", padx=(18, 0))
            self._set_bet_button_enabled(self.bet4_btn, self._play_bet_enabled(4))
            self._set_bet_button_enabled(self.bet3_btn, self._play_bet_enabled(3))
        elif self.stage == "postflop":
            self.bet2_btn.pack(side="left", padx=6)
            self.check_btn.pack(side="left", padx=(18, 0))
            self._set_bet_button_enabled(self.bet2_btn, self._play_bet_enabled(2))
        else:  # postturn
            self.bet1_btn.pack(side="left", padx=6)
            self.fold_btn.pack(side="left", padx=(18, 0))
            self._set_bet_button_enabled(self.bet1_btn, self._play_bet_enabled(1))

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
        self._hide_payout_panel()
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
                    "Your balance must be at least 3x your Ante to deal (Ante and Blind are "
                    "equal, linked bets). Reduce your Ante or add funds."
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
        # The linked Blind bet (always == Ante, never separately stored --
        # see the module docstring) still counts toward what's actually
        # being wagered, so it's added in here even though self.bets has no
        # "blind" key of its own.
        self.total_lbl.configure(text=f"Total bet: £{sum(self.bets.values()) + self.bets['ante']}")

    def _persist_state(self):
        save_json(self.save_path, {"bets": self.bets, "selected_chip": self.selected_chip})

    def _sanitize_bets(self, persist=True):
        if _max_deal_cost(self.bets) > self.app.finance.balance:
            self.bets = {"ante": 0, "trips": 0, "jackpot": 0}
            if persist:
                self._persist_state()

    # ------------------------------------------------------------------ round flow
    def _on_deal(self):
        ante, trips, jackpot = self.bets["ante"], self.bets["trips"], self.bets["jackpot"]
        if ante <= 0:
            dialogs.info(self, "$ deal --require-ante", "You must place an Ante bet to deal.", accent=theme.WARN)
            return

        if not self.app.finance.can_afford(_max_deal_cost(self.bets)):
            choice = dialogs.choice(
                self, "$ deal --check-funds",
                "You don't have enough balance to cover these bets (your balance must be at "
                "least 3x your Ante to begin a hand).",
                [("Go Home", "home"), ("Cashier", "cashier")],
            )
            if choice == "home":
                self.app.show_frame("menu")
            elif choice == "cashier":
                self.app.show_frame("finances")
            return

        total_upfront = ante * 2 + trips + jackpot  # Ante + the equal Blind + side bets
        self.app.finance.place_wager(total_upfront)
        self._refresh_balance()

        self.result = self.game.deal(ante, trips_bet=trips, jackpot_bet=jackpot)
        self.state = "playing"
        self.stage = "preflop"

        self.result_lbl.configure(text="Dealing...", fg=theme.FG)
        self._show_no_controls()

        self.fan_canvas.delete("all")
        self.fan_canvas.pack(pady=(14, 0), before=self.chip_zone)
        self._draw_fan_mat()

        self._draw_play_zones()
        self._deal_player_cards()

    def _play_bet_enabled(self, multiplier):
        assert self.result is not None
        bet_amount = self.result.ante_bet * multiplier
        return self.app.finance.balance + 1e-9 >= bet_amount

    def _on_bet(self, multiplier):
        if self.state != "playing":
            return
        assert self.result is not None
        if not self._play_bet_enabled(multiplier):
            return
        bet_amount = self.result.ante_bet * multiplier
        if not self.app.finance.can_afford(bet_amount):
            dialogs.info(self, "$ bet --check-funds", "You don't have enough balance to place that bet.",
                          accent=theme.WARN)
            return

        self.app.finance.place_wager(bet_amount)
        self._refresh_balance()
        self.game.bet_play(multiplier)
        self._show_no_controls()

        def chips_placed():
            self._reveal_to_river(self._after_full_reveal)

        self._animate_chip_place("spot_play_chips", PLAY_CX, PLAY_CY, bet_amount, ROW_CHIP_MAX_R,
                                  on_done=chips_placed)

    def _on_check(self):
        if self.state != "playing":
            return
        assert self.result is not None
        self._show_no_controls()
        if self.stage == "preflop":
            self.game.reveal_flop()
            self._animate_community_reveal([0, 1, 2], self._after_preflop_check)
        else:  # postflop
            self.game.reveal_turn()
            self._animate_community_reveal([3], self._after_postflop_check)

    def _after_preflop_check(self):
        self.stage = "postflop"
        self._show_stage_controls()

    def _after_postflop_check(self):
        self.stage = "postturn"
        self._show_stage_controls()

    def _reveal_to_river(self, on_done):
        """Reveals whatever's left of the 5 community cards, one stage at a
        time (flop, then turn, then river) -- called after a Play bet lands
        at any of the 3 decision points, so it may need to reveal anywhere
        from 3 cards down to just the river alone -- or after a Fold, which
        shows the whole board out the same way. Each stage gets its own
        pause (STREET_REVEAL_PAUSE_MS) once its own cards have finished
        flipping before the next one starts, so the flop/turn/river (and,
        once `on_done` runs, the Dealer's own hand) each get their own
        distinct beat rather than cascading straight through."""
        assert self.result is not None
        revealed = self.result.revealed_count

        if revealed == 0:
            self.game.reveal_flop()
            self._animate_community_reveal(
                [0, 1, 2],
                lambda: self._after_delay(FLOP_TO_TURN_PAUSE_MS, lambda: self._reveal_to_river(on_done)),
            )
        elif revealed == 3:
            self.game.reveal_turn()
            self._animate_community_reveal(
                [3],
                lambda: self._after_delay(STREET_REVEAL_PAUSE_MS, lambda: self._reveal_to_river(on_done)),
            )
        elif revealed == 4:
            self.game.reveal_river()
            self._animate_community_reveal([4], lambda: self._after_delay(RIVER_TO_DEALER_PAUSE_MS, on_done))
        else:
            on_done()

    def _after_full_reveal(self):
        self._reveal_dealer_cards(self._settle_round)

    def _on_fold(self):
        """Folding still reveals the rest of the board and the Dealer's own
        hand -- what you'd have been up against -- before your own cards
        turn down and fly away. This is purely a visual courtesy: the
        engine's settle() already resolves a fold without ever evaluating
        either hand (the outcome doesn't depend on hand strength), so
        nothing here changes what actually gets paid out."""
        if self.state != "playing":
            return
        assert self.result is not None
        self.game.fold()
        self._show_no_controls()

        def after_board_reveal():
            self._reveal_dealer_cards(lambda: self._flip_fan_face_down(lambda: self._fly_cards_away(
                self._settle_round)))

        self._reveal_to_river(after_board_reveal)

    def _new_deal(self):
        assert self.result is not None, "_new_deal called before a round was ever dealt"
        if not self.app.finance.can_afford(_max_deal_cost(self.bets)):
            self._on_deal()
            return
        self._show_no_controls()
        self._sweep_remaining_chips(self._payout_chip_items(self.result), self._on_deal)

    def _new_round(self):
        self.state = "betting"
        self.result_lbl.configure(text="Place your Ante and Blind bets to begin.", fg=theme.FG)
        self._sanitize_bets()
        self._show_betting_controls()

    # ------------------------------------------------------------------ card-view rendering
    def _community_slot_x(self, i):
        return COMMUNITY_MAT_X1 + COMMUNITY_MAT_MARGIN + i * CARD_ROW_GAP

    def _dealer_hand_slot_x(self, i):
        return DEALER_HAND_MAT_X1 + DEALER_HAND_MAT_MARGIN + i * (CARD_WIDTH + DEALER_HAND_GAP)

    def _draw_zone_backgrounds(self):
        """Just the two static mats + their labels (tag "zone_bg") -- split
        out from _draw_play_zones so a live theme switch mid-round (see
        _apply_theme) can refresh their colours without touching any
        already-dealt/already-revealed card, which a full canvas.delete
        ("all") + redraw would otherwise destroy."""
        felt_theme = self.app.settings.theme()

        # Dealer's own 2-card mat -- neutral border, matching the felt used
        # for the player's own fan_canvas mat rather than the community
        # mat's own accent border, so it reads as "the same kind of hidden
        # hand" as the player's.
        theme.rounded_rect(
            self.canvas, DEALER_HAND_MAT_X1, DEALER_MAT_TOP, DEALER_HAND_MAT_X2, DEALER_MAT_BOTTOM,
            radius=DEALER_MAT_RADIUS, fill=felt_theme["felt_dark"], outline=FAN_MAT_BORDER, width=2,
            tags=("zone_bg",),
        )
        self.canvas.create_text((DEALER_HAND_MAT_X1 + DEALER_HAND_MAT_X2) / 2, DEALER_MAT_LABEL_Y, text="DEALER",
                                 fill=theme.ACCENT, font=theme.font(9, weight="bold"), tags=("zone_bg",))

        # Community mat.
        theme.rounded_rect(
            self.canvas, COMMUNITY_MAT_X1, DEALER_MAT_TOP, COMMUNITY_MAT_X2, DEALER_MAT_BOTTOM,
            radius=DEALER_MAT_RADIUS, fill=felt_theme["felt_dark"], outline=felt_theme["accent"], width=2,
            tags=("zone_bg",),
        )

    def _draw_play_zones(self):
        assert self.result is not None
        self.canvas.delete("all")
        felt_theme = self.app.settings.theme()

        self._draw_zone_backgrounds()
        for i in range(2):
            draw_card_back(self.canvas, self._dealer_hand_slot_x(i), DEALER_Y, felt_theme["felt"],
                            felt_theme["accent"], tags=(f"dealer_card_{i}",))
        for i in range(5):
            draw_card_back(self.canvas, self._community_slot_x(i), DEALER_Y, felt_theme["felt"],
                            felt_theme["accent"], tags=(f"community_card_{i}",))

        if self.bets["jackpot"]:
            self._draw_strip_circle("jackpot", JACKPOT_CX, JACKPOT_CY, JACKPOT_SPOT_R,
                                     "JACKPOT", self.bets["jackpot"])
        if self.bets["trips"]:
            self._draw_strip_diamond("trips", TRIPS_CX, TRIPS_CY, TRIPS_SPOT_R, "TRIPS", self.bets["trips"])

        self._draw_strip_ante_blind(self.result.ante_bet)
        self._draw_play_spot()

    def _draw_play_spot(self, amount=0.0):
        tag = "spot_play"
        self.canvas.delete(tag)
        felt_theme = self.app.settings.theme()
        self.canvas.create_oval(PLAY_CX - PLAY_R, PLAY_CY - PLAY_R, PLAY_CX + PLAY_R, PLAY_CY + PLAY_R,
                                 fill=felt_theme["felt_dark"], outline=felt_theme["accent"], width=2, tags=(tag,))
        # Label above, same convention as Ante/Blind now that Play shares
        # their row -- empty until a Play bet actually lands.
        self.canvas.create_text(PLAY_CX, PLAY_CY - PLAY_R - 12, text="PLAY", fill=theme.FG,
                                 font=theme.font(9, weight="bold"), tags=(tag,))
        if amount:
            draw_chip_stack(self.canvas, (tag, f"{tag}_chips"), PLAY_CX, PLAY_CY, amount, max_r=ROW_CHIP_MAX_R)

    def _draw_strip_ante_blind(self, ante_bet):
        felt_theme = self.app.settings.theme()

        self.canvas.create_oval(ANTE_CX - ANTE_R, ANTE_CY - ANTE_R, ANTE_CX + ANTE_R, ANTE_CY + ANTE_R,
                                 fill=felt_theme["felt_dark"], outline=felt_theme["accent"], width=2,
                                 tags=("strip_ante",))
        self.canvas.create_text(ANTE_CX, ANTE_CY - ANTE_R - 10, text="ANTE", fill=theme.FG,
                                 font=theme.font(9, weight="bold"), tags=("strip_ante",))
        draw_chip_stack(self.canvas, ("strip_ante", "strip_ante_chips"), ANTE_CX, ANTE_CY, ante_bet,
                         max_r=ROW_CHIP_MAX_R)

        self.canvas.create_text(EQUALS_CX, ANTE_CY, text="=", fill=theme.FG_DIM,
                                 font=theme.font(20, weight="bold"), tags=("equals_glyph",))

        self.canvas.create_oval(BLIND_CX - BLIND_R, ANTE_CY - BLIND_R, BLIND_CX + BLIND_R, ANTE_CY + BLIND_R,
                                 fill=felt_theme["felt_dark"], outline=felt_theme["accent"], width=2,
                                 tags=("strip_blind",))
        self.canvas.create_text(BLIND_CX, ANTE_CY - BLIND_R - 10, text="BLIND", fill=theme.FG,
                                 font=theme.font(9, weight="bold"), tags=("strip_blind",))
        draw_chip_stack(self.canvas, ("strip_blind", "strip_blind_chips"), BLIND_CX, ANTE_CY, ante_bet,
                         max_r=ROW_CHIP_MAX_R)

    def _draw_strip_circle(self, key, cx, cy, r, label, amount):
        tag = f"strip_{key}"
        self.canvas.delete(tag)
        felt_theme = self.app.settings.theme()
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=felt_theme["felt_dark"],
                                 outline=felt_theme["accent"], width=2, tags=(tag,))
        self.canvas.create_text(cx, cy - r - 10, text=label, fill=theme.FG,
                                 font=theme.font(9, weight="bold"), tags=(tag,))
        draw_chip_stack(self.canvas, (tag, f"{tag}_chips"), cx, cy, amount, max_r=18)

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
                self._draw_player_card_at(i, cards[i], sx + (tx - sx) * t, sy + (ty - sy) * t, face_up=False)

            self._animate(DEAL_IN_DROP_MS, frame, on_done=(self._flip_player_cards_up if i == 1 else None))

        if self.app.settings.get("animations_enabled"):
            self.after(350, lambda: self._run_staggered(2, DEAL_IN_STAGGER_MS, deal_one))
        else:
            self._run_staggered(2, DEAL_IN_STAGGER_MS, deal_one)

    def _flip_player_cards_up(self):
        """The player's own 2 cards deal in face down (like every card),
        then immediately flip face up so they can actually see their own
        hand -- the Dealer's own 2 cards, and all 5 community cards, stay
        face down until their own proper reveal step."""
        assert self.result is not None
        cards = self.result.player_cards
        slots = self._fan_slots()

        def flip_one(i):
            sx, sy = slots[i]
            cx_slot = sx + CARD_WIDTH / 2
            self._animate_flip(
                self.fan_canvas, f"player_card_{i}", cx_slot, sy, cards[i], reveal=True,
                duration=COMMUNITY_FLIP_MS, on_done=(self._on_player_cards_dealt if i == 1 else None),
            )

        self._run_staggered(2, 90, flip_one)

    def _on_player_cards_dealt(self):
        self.result_lbl.configure(text="Your cards are dealt. Bet or fold?", fg=theme.FG)
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

    def _reveal_dealer_cards(self, on_done):
        assert self.result is not None
        result = self.result
        result.dealer_revealed = True

        def after_flip():
            self._after_delay(DEALER_TO_PAYOUT_PAUSE_MS, on_done)

        def flip_one(i):
            cx_slot = self._dealer_hand_slot_x(i) + CARD_WIDTH / 2
            self._animate_flip(
                self.canvas, f"dealer_card_{i}", cx_slot, DEALER_Y, result.dealer_cards[i],
                reveal=True, duration=COMMUNITY_FLIP_MS,
                on_done=(after_flip if i == 1 else None),
            )

        # Both dealer cards flip together (not staggered like the community
        # cards) -- the Dealer's hand is revealed as a single beat.
        flip_one(0)
        flip_one(1)

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
        if result.blind_bet:
            totals.append(("blind", result.blind_bet, result.blind_return))
        if result.play_bet:
            totals.append(("play", result.play_bet, result.play_return))
        if result.trips_bet:
            totals.append(("trips", result.trips_bet, result.trips_return))
        if result.jackpot_bet:
            totals.append(("jackpot", result.jackpot_bet, result.jackpot_return))
        return totals

    def _payout_chip_items(self, result):
        layout = {
            "ante": (ANTE_CX, ANTE_CY, "strip_ante", ROW_CHIP_MAX_R),
            "blind": (BLIND_CX, ANTE_CY, "strip_blind", ROW_CHIP_MAX_R),
            "play": (PLAY_CX, PLAY_CY, "spot_play", ROW_CHIP_MAX_R),
            "trips": (TRIPS_CX, TRIPS_CY, "strip_trips", 18),
            "jackpot": (JACKPOT_CX, JACKPOT_CY, "strip_jackpot", 18),
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
        # Unlike every other game in this app, fan_canvas stays visible
        # here even once resolved -- the round-result panel lives in its
        # own floating corner (see _show_payout_panel) rather than taking
        # fan_canvas's old spot, so there's no need to hide the player's
        # hand to make room for it.
        self._refresh_balance()
        self.app.on_balance_changed()
        self._show_result(result)
        self._show_round_over_controls()
        self.state = "resolved"

    def _show_result(self, result):
        headline = {
            "fold": "You folded.",
            "win": "You win",
            "lose": "Dealer wins",
            "push": "Push",
        }[result.outcome]
        color = {
            "fold": theme.FG_DIM,
            "win": theme.WIN_COLOR,
            "lose": theme.LOSE_COLOR,
            "push": theme.PUSH_COLOR,
        }[result.outcome]

        if result.folded:
            text = headline
        elif not result.dealer_qualified:
            text = f"{headline} - dealer doesn't qualify."
        elif result.outcome == "lose":
            text = f"{headline} - {_hand_description(result.dealer_eval)}"
        else:  # win or push -- the player's own hand is the one that matters
            text = f"{headline} - {_hand_description(result.player_eval)}"
        self.result_lbl.configure(text=text, fg=color)

        self._show_payout_panel()
        self._draw_payout_panel(result)

    def _payout_rows(self, result):
        rows = []
        if result.ante_bet:
            rows.append((f"Ante £{result.ante_bet:.0f}", result.ante_return - result.ante_bet))
        if result.blind_bet:
            rows.append((f"Blind £{result.blind_bet:.0f}", result.blind_return - result.blind_bet))
        if result.play_bet:
            rows.append((f"Play £{result.play_bet:.0f}", result.play_return - result.play_bet))
        if result.trips_bet:
            label = f"Trips £{result.trips_bet:.0f}"
            if result.player_eval is not None:
                label = f"Trips ({result.player_eval[1]})"
            rows.append((label, result.trips_return - result.trips_bet))
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
        # mat (and, here, the Dealer's own matching 2-card mat) are *drawn*
        # canvas rectangles, so they keep their stale felt_dark fill after a
        # live theme switch unless explicitly redrawn too. Cheap/harmless to
        # call even when nothing's been dealt yet.
        if self.fan_canvas.find_withtag("fan_mat_bg"):
            self.fan_canvas.delete("fan_mat_bg")
            self._draw_fan_mat()
            self.fan_canvas.tag_lower("fan_mat_bg")
        # Same surgical fix for the play screen's own two mats -- refreshes
        # just their background rects/labels (tag "zone_bg"), never the
        # cards themselves, so a live mid-round switch can't wipe out an
        # already-dealt/already-revealed hand the way a full canvas.delete
        # ("all") + _draw_play_zones() redraw would.
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
