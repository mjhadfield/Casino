import os
import tkinter as tk
from typing import Optional

from core.hand_evaluator import compare_hands
from core.persistence import load_json, save_json
from games.pai_gow_poker.logic import (
    FORTUNE_MULTIPLIERS,
    FIVE_ACES,
    FLUSH_TIER,
    FOUR_OF_A_KIND_TIER,
    FULL_HOUSE_TIER,
    GAME_KEY,
    JACKPOT_BET_AMOUNT,
    JACKPOT_TIERS,
    PaiGowPokerGame,
    ROYAL_FLUSH,
    ROYAL_FLUSH_ROYAL_MATCH,
    RoundResult,
    SEVEN_CARD_STRAIGHT_FLUSH,
    SEVEN_CARD_STRAIGHT_FLUSH_JOKER,
    STRAIGHT_FLUSH_TIER,
    STRAIGHT_TIER,
    THREE_OF_A_KIND_TIER,
    best_five_card_eval_with_joker,
    evaluate_two_card_hand,
    hand_outcome_label,
    house_way_set,
)
from ui import dialogs, theme
from ui.card_widgets import CARD_HEIGHT, CARD_WIDTH, draw_card, draw_card_back
from ui.chips import CHIP_DENOMINATIONS, CHIP_LAYER_MAX_R, CHIP_SIZE, draw_chip_face, draw_chip_stack
from ui.jackpot_display import JackpotDisplay

STATE_FILENAME = "pai_gow_poker_state.json"
BET_KEYS = ("ante", "fortune", "jackpot")
DEFAULT_STATE = {"bets": {k: 0 for k in BET_KEYS}, "selected_chip": 5}
CANVAS_WIDTH = 920

# --- Betting-screen spot geometry -------------------------------------------
# Each spot's felt size and its own chip-stack radius are independent knobs
# -- a _R constant sizes the felt only; a _CHIP_R constant sizes the chips
# drawn on top of it. Nothing forces them to match, so a felt can be made
# larger or smaller than its own chips without moving the other.
ANTE_BAR_W = CARD_WIDTH * 2
ANTE_BAR_H = 80
ANTE_CHIP_R = 30
FORTUNE_R = 35
FORTUNE_CHIP_R = 30
JACKPOT_R = 35
JACKPOT_CHIP_R = 30
SIDE_SPOT_GAP = 95  # half-distance between the Fortune/Jackpot centres

STACK_CX = CANVAS_WIDTH / 2

ANTE_BAR_BOTTOM = 300
ANTE_BAR_TOP = ANTE_BAR_BOTTOM - ANTE_BAR_H
ANTE_BAR_CY = ANTE_BAR_TOP + ANTE_BAR_H / 2

# A clear, deliberate gap (not just barely clearing) above Ante's own top --
# measured off Fortune's own (larger) radius so it's the true worst-case
# clearance.
TOP_SPOT_CY = ANTE_BAR_TOP - FORTUNE_R - 30
FORTUNE_CX = STACK_CX - SIDE_SPOT_GAP
JACKPOT_CX = STACK_CX + SIDE_SPOT_GAP

BETTING_CANVAS_HEIGHT = int(ANTE_BAR_BOTTOM + 40)

RULES_BUTTON_WIDTH = 106
RULES_BUTTON_HEIGHT = 54
RULES_BUTTON_RADIUS = RULES_BUTTON_HEIGHT // 2
# Centred in the gap between the canvas's own left border and the Ante
# spot's own left edge, rather than a fixed (and too-tight) margin off the
# border alone. Vertically dead-centred on the Ante spot specifically (not
# the whole cluster, which would drift as Ante's own size changes).
RULES_BUTTON_CX = (STACK_CX - ANTE_BAR_W / 2) / 2
RULES_BUTTON_CY = ANTE_BAR_CY

# --- Play-screen geometry ----------------------------------------------------
# Dealer mat: wide enough for 7 full-size cards side by side (per the brief --
# not shrunk to fit, the same size as every other table's Dealer cards).
DEALER_MAT_RADIUS = 14
# "DEALER" sits above the mat rather than inside it, unlike every other
# box's own label -- a deliberate exception, not an oversight -- so
# DEALER_MAT_TOP leaves room above itself for that label. The box's own
# internal top padding (DEALER_Y's offset from it) still has to clear a
# label drawn *inside* the box, though -- once the hand's settled, FRONT/
# BACK appear there, above their own card groups (see
# _draw_dealer_group_labels) -- so this can't shrink as far as "DEALER"
# alone moving outside would suggest.
DEALER_MAT_TOP = 26
DEALER_MAT_LABEL_Y = DEALER_MAT_TOP - 12
DEALER_Y = DEALER_MAT_TOP + 20
DEALER_MAT_BOTTOM = DEALER_Y + CARD_HEIGHT + 18
# Left margin matches the DECK zone's own width (see DECK_ZONE_X1/W below,
# defined once ZONE_TOP exists) -- kept as a plain margin here rather than
# still sitting beside the DECK spot itself, which now lives in its own row
# in-line with Front/Back instead of up here beside the Dealer.
DEALER_MAT_X1 = 120
DEALER_CENTER_X = CANVAS_WIDTH / 2
# Symmetric around DEALER_CENTER_X, matching DEALER_MAT_X1's own margin --
# the cards inside (see _dealer_cluster_x/_dealer_group_layout) are always
# centred on DEALER_CENTER_X too, so equal margins either side of it is
# what actually keeps the left/right padding around them visually even.
DEALER_MAT_X2 = 2 * DEALER_CENTER_X - DEALER_MAT_X1
DEALER_CENTER_Y = DEALER_Y + CARD_HEIGHT / 2

# Front (2 cards) / Back (5 cards) hand zones -- both fanned horizontally,
# in line with the rest of the play area (Dealer row, felt row, Back's own
# fan) -- directly under the Dealer, with the open felt ("YOUR CARDS", the
# still-unplaced cards) below *them* -- setting your hand is the immediate,
# active thing happening on this screen, so it sits right under the Dealer
# rather than underneath a full row of cards you haven't acted on yet.
ZONE_TOP = DEALER_MAT_BOTTOM + 14
# Sized for a single horizontal row of cards, since Front fans the same way
# Back does -- kept tight so the round-result panel below the canvas (see
# ROUND_RESULT_PANEL_H) has the room it needs within the app's fixed,
# non-resizable 1200x820 window.
ZONE_H = 165
ZONE_LABEL_Y_OFFSET = 16

FRONT_ZONE_W = 160
BACK_ZONE_W = 300
ZONE_GAP = 30
_ZONES_TOTAL_W = FRONT_ZONE_W + ZONE_GAP + BACK_ZONE_W
FRONT_ZONE_X1 = CANVAS_WIDTH / 2 - _ZONES_TOTAL_W / 2
FRONT_ZONE_X2 = FRONT_ZONE_X1 + FRONT_ZONE_W
BACK_ZONE_X1 = FRONT_ZONE_X2 + ZONE_GAP
BACK_ZONE_X2 = BACK_ZONE_X1 + BACK_ZONE_W
ZONE_BOTTOM = ZONE_TOP + ZONE_H

FRONT_ZONE_CX = (FRONT_ZONE_X1 + FRONT_ZONE_X2) / 2
BACK_ZONE_CX = (BACK_ZONE_X1 + BACK_ZONE_X2) / 2
FRONT_CARD_OVERLAP_X = CARD_WIDTH * 0.55    # horizontal overlap between the 2 fanned front cards -- same ratio as Back's
BACK_CARD_OVERLAP_X = CARD_WIDTH * 0.55     # horizontal overlap between the 5 fanned back cards

# The face-down shoe (DECK) -- its own small zone, same row and visual
# treatment (bordered box + label) as Front/Back. Centred between the
# window's own left edge and the Front zone, rather than pinned to a fixed
# left margin. Rounded to a whole pixel -- FRONT_ZONE_X1/2 lands on a .5
# value otherwise, and Tk's smooth-polygon rounded-rect rendering (see
# theme.rounded_rect) draws a visibly jagged, sawtoothed edge down a tall
# straight side sitting at a fractional x-coordinate.
DECK_ZONE_W = CARD_WIDTH + 40
DECK_ZONE_CX = round(FRONT_ZONE_X1 / 2)
DECK_ZONE_X1 = DECK_ZONE_CX - DECK_ZONE_W / 2
DECK_ZONE_X2 = DECK_ZONE_CX + DECK_ZONE_W / 2
DECK_X1 = DECK_ZONE_CX - CARD_WIDTH / 2
DECK_Y = ZONE_TOP + ZONE_LABEL_Y_OFFSET + 24  # same row_y Front/Back's own cards sit on

# The Fortune/Ante/Jackpot bet tokens (only shown once the hand's settled --
# see _draw_side_stakes), arranged in a triangle in the space between the
# Back zone and the canvas's own right margin (same convention as the
# betting screen's own Fortune/Jackpot-above-Ante triangle). Deliberately
# not tied to DEALER_MAT_X2 -- that box is now sized to fit its own
# (centred) card content, not to also mark out how much room this triangle
# gets.
SIDE_STAKES_X1 = BACK_ZONE_X2 + 15
SIDE_STAKES_X2 = CANVAS_WIDTH - 30
SIDE_STAKES_CX = (SIDE_STAKES_X1 + SIDE_STAKES_X2) / 2
SIDE_STAKE_GAP = 42  # half-distance between the Fortune/Jackpot tokens (top row)
FORTUNE_CX_PLAY = SIDE_STAKES_CX - SIDE_STAKE_GAP
JACKPOT_CX_PLAY = SIDE_STAKES_CX + SIDE_STAKE_GAP
ANTE_TOKEN_CX = SIDE_STAKES_CX
SIDE_STAKE_TOP_CY = ZONE_TOP + 45
SIDE_STAKE_BOTTOM_CY = ZONE_TOP + 125

# The player's open felt -- their 7 dealt cards, laid out in fixed slots
# (0-6, dealt order), below the Front/Back zones (see above). A card's own
# slot goes visually blank once it's placed -- not re-flowed -- so a
# card's position is always easy to track.
FELT_TOP = ZONE_BOTTOM + 14
FELT_LABEL_Y = FELT_TOP + 9
FELT_Y = FELT_TOP + 18
FELT_MAT_BOTTOM = FELT_Y + CARD_HEIGHT + 14

# 7 cards, same dynamic-gap approach Blackjack's own Dealer row uses --
# comfortably spaced at full card width within the mat.
FELT_CARD_GAP_MAX = CARD_WIDTH + 12

# Sized to fit exactly 7 cards at FELT_CARD_GAP_MAX's own spacing plus a
# modest border, rather than the full (much wider) Dealer mat width -- the
# Dealer mat is that wide to leave room for the DECK spot beside it, but the
# felt has no such neighbour, so reusing that width left it looking sized
# for 9 cards. Centred under the Front/Back zones above it (same axis they
# themselves are centred on) rather than the Dealer mat's own, DECK-offset
# centre.
FELT_BOX_W = (7 - 1) * FELT_CARD_GAP_MAX + CARD_WIDTH + 60
FELT_MAT_X1 = CANVAS_WIDTH / 2 - FELT_BOX_W / 2
FELT_MAT_X2 = CANVAS_WIDTH / 2 + FELT_BOX_W / 2


def _felt_card_x(pos, n, x1, x2):
    gap = min(FELT_CARD_GAP_MAX, max(30, (x2 - x1 - 40) / max(1, n - 1) if n > 1 else 0))
    total_w = gap * (n - 1) + CARD_WIDTH
    start_x = (x1 + x2) / 2 - total_w / 2
    return start_x + pos * gap


# The Dealer's 7 cards, before the House Way split -- a compact, gently
# fanned group centred in the Dealer mat (same overlap ratio Back's own fan
# uses), not spread edge-to-edge across the mat's full width. Shared by the
# deal-in landing spot, the face-down resting position, and the flip-reveal
# position, so all three always agree on where the cluster sits.
DEALER_CLUSTER_OVERLAP = CARD_WIDTH * 0.55

# The gap between the Dealer's own settled Front and Back groups (see
# _dealer_group_layout) -- deliberately generous so the two hands read as
# clearly separate at a glance, not just a wider space in one continuous row.
DEALER_GROUP_GAP = 70


def _dealer_cluster_x(pos, n=7):
    fan_w = (n - 1) * DEALER_CLUSTER_OVERLAP + CARD_WIDTH
    start_x = DEALER_CENTER_X - fan_w / 2
    return start_x + pos * DEALER_CLUSTER_OVERLAP


CANVAS_HEIGHT = int(FELT_MAT_BOTTOM + 20)

#Animation time and speed.
DEAL_FLIGHT_MS = 220
DEAL_CARD_STAGGER_MS = 260
SORT_MOVE_MS = 260
HOUSE_WAY_FLIGHT_MS = 260
REVEAL_FLIP_MS = 200
REVEAL_STAGGER_MS = 260
SEPARATE_MOVE_MS = 260

# Payout animation speed and landing position. 
PAYOUT_CHIP_MOVE_MS = 420
PAYOUT_WIN_LANDING_OFFSET_X = 10
PAYOUT_WIN_LANDING_OFFSET_Y = 10

CHIP_R = 20
# The felt circle drawn under each side-stake token (see _draw_side_stakes)
# -- just a few px of felt showing past the chip stack's own edge, same
# "clear the chip, not much more" sizing the betting screen's own spots use.
SIDE_STAKE_FELT_R = CHIP_R + 6

# How long a bet's own chips take to fly onto their felt spot once DEAL/New
# Deal is pressed (see _place_stakes_then) -- a touch snappier than a
# payout's own PAYOUT_CHIP_MOVE_MS since this one has to finish, in full,
# before the per-card deal-in sequence is allowed to start.
STAKE_PLACE_MS = 320

# The "ROUND RESULT" panel -- a bordered recessed_panel (same look Three
# Card Poker's own round-result panel uses): title, up to 3 bet rows
# (Ante/Fortune/Jackpot), a divider, Round Net, a second divider, then the
# Your Front/Back/Fortune hand summary -- all one unified box, all the same
# row styling (see _draw_round_result_panel). Stretched down close to the
# app's fixed, non-resizable window's own bottom edge (measured empirically
# against its actual position -- there's ~223px available below the panel's
# own top before the window ends).
ROUND_RESULT_PANEL_W = 320
ROUND_RESULT_PANEL_H = 215
# Fixed height for round_over_frame -- its two halves (center_col,
# results_col) are positioned with .place(), which (unlike .pack()) doesn't
# feed back into the parent's own size, so this needs to be tall enough for
# the taller of the two (results_col, i.e. the panel) up front.
ROUND_OVER_FRAME_H = 215

PAYTABLE_WIDTH = 250
PAYTABLE_HEIGHT = 300

CONTENT_TOP_MARGIN = 14

# The top value pushes the whole "Place your ante..."/Deal/chip-tray group
# down to sit near the bottom of the (fixed, non-resizable) window, rather
# than immediately under the betting spots with a large unused gap below.
BETTING_RESULT_LBL_PADY = (28, 3)
PLAY_RESULT_LBL_PADY = (0, 3)
BETTING_ACTION_FRAME_PADY = (8, 0)
CHIP_FRAME_PADY = (6, 20)

TIER_LABELS = {
    SEVEN_CARD_STRAIGHT_FLUSH: "7-Card Straight Flush",
    ROYAL_FLUSH_ROYAL_MATCH: "Royal Flush + Match",
    SEVEN_CARD_STRAIGHT_FLUSH_JOKER: "7-Card SF (w/ Joker)",
    FIVE_ACES: "Five Aces",
    ROYAL_FLUSH: "Royal Flush",
    STRAIGHT_FLUSH_TIER: "Straight Flush",
    FOUR_OF_A_KIND_TIER: "Four of a Kind",
    FULL_HOUSE_TIER: "Full House",
    FLUSH_TIER: "Flush",
    THREE_OF_A_KIND_TIER: "Three of a Kind",
    STRAIGHT_TIER: "Straight",
}

FORTUNE_PAYTABLE_ROWS = [(TIER_LABELS[k], f"{v}:1") for k, v in FORTUNE_MULTIPLIERS.items()]


def _jackpot_tier_text(fixed, fraction):
    if fraction is not None:
        return "JACKPOT" if fraction >= 1.0 else f"{int(fraction * 100)}% JACKPOT"
    return f"£{fixed:.0f}"


JACKPOT_PAYTABLE_ROWS = [(TIER_LABELS[k], _jackpot_tier_text(*v)) for k, v in JACKPOT_TIERS.items()]
JACKPOT_PAYTABLE_HIGHLIGHT_ROW = 0

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
    # The second element must stay the same type (str) whether or not the
    # card's a Joker -- Suit.value is a string ("Hearts", "Spades", ...),
    # and tuple comparison only reaches this element when two cards tie on
    # the first (which the Joker, pinned to rank 14, always will whenever
    # an Ace is also in the felt).
    return (14 if card.is_joker else card.value, "" if card.is_joker else card.suit.value)


def _back_display_rank(card):
    return 14 if card.is_joker else card.value


def _back_display_key(card, counts):
    """Arranges a 5-card hand the way a made poker hand naturally reads --
    any pair/trips/quads shown together as a block, the bigger group
    first (ties broken by rank), then the remaining singles by rank
    descending. A straight or flush has no rank repeats at all, so it
    falls out of the very same rule as a plain descending run -- no
    separate straight/flush-specific case needed. `counts` is each rank's
    own count within the 5 cards (build once per hand, not per card)."""
    r = _back_display_rank(card)
    return (counts[r], r)


class PaiGowPokerFrame(tk.Frame):
    # Overridable per-variant identity (see games/pai_gow_poker_face_up/ui.py,
    # whose PaiGowFaceUpFrame subclasses this and swaps every one of these):
    # what state-save file to use, which game engine/GAME_KEY to record
    # stats under (used via self.GAME_KEY rather than the bare module
    # global -- a subclass overriding it as a class attribute is enough to
    # redirect every stats call below without touching their bodies), the
    # top bar's title/breadcrumb, and the paytable panel's own Ante
    # commission note.
    STATE_FILENAME = STATE_FILENAME
    GAME_KEY = GAME_KEY
    GAME_TITLE = "Pai Gow Poker"
    BREADCRUMB = "pai_gow_poker"
    ANTE_COMMISSION_NOTE = "(5% commission on a win)"

    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.BG)
        self.app = app
        self.game = self._make_game()
        self.state = "betting"  # betting -> dealt -> setting -> revealing -> resolved

        self.save_path = os.path.join(app.data_dir, self.STATE_FILENAME)
        saved = load_json(self.save_path, DEFAULT_STATE)
        saved_bets = saved.get("bets", DEFAULT_STATE["bets"])
        self.bets = {k: int(saved_bets.get(k, 0)) for k in BET_KEYS}
        self.selected_chip = int(saved.get("selected_chip", DEFAULT_STATE["selected_chip"]))

        self.chip_canvases = {}
        self._jackpot_pulse_t = 0.0
        self._bound_spot_tags = set()

        # Per-round play state.
        self.round_bets = {}
        self.result: Optional[RoundResult] = None
        # True for the brief window between a deal starting and this
        # round's stake chips finishing their fly-in (see
        # _place_stakes_then) -- _redraw_felt skips drawing the stake
        # chips (though not their felt/label shells) while this holds, so
        # the deal-in's own repeated _redraw_felt calls don't stomp the
        # in-flight animation with the finished, full-size stack.
        self._side_stakes_animating = False
        self.card_zone = {}       # card index (0-6, dealt order) -> "felt" | "front" | "back"
        self.front_order = []     # card indices, in the order placed
        self.back_order = []
        self.active_zone = "front"
        self._hover_tag = None
        self._player_cards_revealed = 0   # how many of the 7 have actually landed on the felt -- see _animate_deal_in
        self._dealer_dealt_count = 0      # how many of the Dealer's 7 have actually landed (face down) -- ditto
        self._dealer_revealed = 0         # how many of the Dealer's cards are face *up* -- only set once Confirmed
        self._dealer_separated = False
        # True for the duration of a card-placement animation (Sort, House
        # Way, or the SET shortcut) -- see _lock_setting_buttons. Checked at
        # the top of each of those three handlers, not just relied on via
        # the buttons' own disabled state: a disabled Tk button blocks a
        # real click, but a re-entrant *call* to the handler (a fast
        # double-click racing the very first dispatch, or any other path)
        # isn't stopped by that alone.
        self._setting_locked = False

        self._build_ui()
        self.app.jackpot.add_listener(self._on_jackpot_changed)
        self.jackpot_display.set_value(self.app.jackpot.raw_amount)
        self._pulse_jackpot()
        self._sanitize_bets(persist=False)
        self._show_betting_controls()

    def _make_game(self):
        """Factory for the game engine instance -- see the class-level
        docstring above; games/pai_gow_poker_face_up/ui.py overrides this
        to return a PaiGowFaceUpGame instead."""
        return PaiGowPokerGame()

    def _make_middle_btn(self):
        """Factory for the action_frame's middle button (between Sort and
        Confirm) -- "HOUSE WAY" here, gold/WARN-styled. Overridden by Face
        Up Pai Gow to be a red "FOLD" button instead: seeing the Dealer's
        hand before you set your own makes House Way much less useful
        there (you already know whether it's beatable), so Fold -- forfeit
        the Ante immediately rather than bothering to set a hand you know
        can't win -- takes its place in the same slot."""
        return tk.Button(
            self.action_frame, text="HOUSE WAY", bg=theme.WARN_DIM_BG, fg=theme.FG,
            font=theme.font(12, weight="bold"), relief="flat", padx=18, pady=9, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.WARN,
            command=self._on_house_way,
        )

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
        tk.Label(top_bar, text=self.GAME_TITLE, bg=theme.BG_ELEVATED, fg=theme.ACCENT,
                 font=theme.font(16, weight="bold")).pack(side="left", padx=10)
        self.balance_lbl = tk.Label(top_bar, text="£0.00", bg=theme.BG_ELEVATED, fg=theme.WIN_COLOR,
                                     font=theme.font(12, weight="bold"))
        self.balance_lbl.pack(side="right", padx=20)
        theme.breadcrumb(top_bar, self.BREADCRUMB, bg=theme.BG_ELEVATED,
                          player=self.app.current_player["name"]).pack(side="right", padx=(6, 6))

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
            panel_bg=felt_theme["felt_dark"], border=felt_theme["accent"],
        )
        self.jackpot_display.pack(pady=(0, 14))
        self._build_paytable(paytable_col)

        self.canvas = tk.Canvas(game_col, bg=felt_theme["felt"], highlightthickness=0,
                                 width=CANVAS_WIDTH, height=CANVAS_HEIGHT)
        self.canvas.pack(padx=12, pady=(6, 2))

        self.result_lbl = tk.Label(
            game_col, text="Place your ante to begin.", bg=felt_theme["felt"], fg=theme.FG,
            font=theme.font(13, weight="bold"), wraplength=900, justify="center",
        )
        self.result_lbl.pack(pady=(0, 3))

        self.action_frame = tk.Frame(game_col, bg=felt_theme["felt"])
        self.action_frame.pack(pady=(8, 0))

        self.deal_btn = tk.Button(
            self.action_frame, text="DEAL", bg=theme.ACCENT_DIM_BG, fg=theme.FG,
            font=theme.font(13, weight="bold"), relief="flat", padx=30, pady=10, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.ACCENT,
            command=self._on_deal,
        )

        self.sort_btn = tk.Button(
            self.action_frame, text="SORT", bg=theme.GREY_BTN_BG, fg=theme.FG,
            font=theme.font(12, weight="bold"), relief="flat", padx=18, pady=9, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.GREY_BTN_BORDER,
            command=self._on_sort,
        )
        # The slot between Sort and Confirm -- "HOUSE WAY" here, overridden
        # by Face Up Pai Gow to be a red "FOLD" button instead (see
        # _make_middle_btn's own docstring and
        # games/pai_gow_poker_face_up/ui.py).
        self.middle_btn = self._make_middle_btn()
        # Doubles as "SET" (while the hand's still being placed -- see
        # _refresh_confirm_state) and "CONFIRM" (once it is) rather than two
        # separate buttons. A fixed character width keeps its on-screen size
        # the same either way, so neither label swap nor the Sort/House Way
        # buttons beside it ever shift.
        self.confirm_btn = tk.Button(
            self.action_frame, text="CONFIRM", bg=theme.ACCENT_DIM_BG, fg=theme.FG,
            font=theme.font(12, weight="bold"), relief="flat", width=9, pady=9, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.ACCENT,
            command=self._on_confirm,
        )

        # Round-over layout: New Deal/Change Bets centred under the canvas,
        # with a "ROUND RESULT" panel -- the same bordered recessed_panel
        # look, titling, and Ante/Fortune/Jackpot-then-Round-Net row format
        # Three Card Poker's own round-result panel uses -- in the bottom
        # left corner, the Your Front/Back/Fortune hand summary grouped
        # directly beneath it. Built on a fixed-size frame (matching the
        # canvas's own width) with .place() rather than .pack() for its two
        # halves, so the centred half is genuinely centred on the whole
        # play area, not just centred relative to whatever width the
        # results panel happens to have.
        self.round_over_frame = tk.Frame(game_col, bg=felt_theme["felt"], width=CANVAS_WIDTH,
                                          height=ROUND_OVER_FRAME_H)
        self.round_over_frame.pack_propagate(False)

        center_col = tk.Frame(self.round_over_frame, bg=felt_theme["felt"])
        center_col.place(relx=0.5, y=10, anchor="n")

        self.new_deal_btn = tk.Button(
            center_col, text="New Deal", bg=theme.ACCENT_DIM_BG, fg=theme.FG,
            font=theme.font(13, weight="bold"), relief="flat", padx=30, pady=10, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.ACCENT,
            command=self._new_deal,
        )
        self.new_deal_btn.pack(pady=(0, 6))
        self.change_bets_btn = tk.Button(
            center_col, text="Change Bets", bg=theme.GREY_BTN_BG, fg=theme.FG_DIM,
            font=theme.font(13, weight="bold"), relief="flat", padx=30, pady=10, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.GREY_BTN_BORDER,
            command=self._new_round,
        )
        self.change_bets_btn.pack()

        # Everything -- the Ante/Fortune/Jackpot payout breakdown, Round
        # Net, AND the Your Front/Back/Fortune hand summary -- drawn as one
        # unified "ROUND RESULT" panel on a single canvas, rather than the
        # bet rows living in a bordered box with the hand summary as
        # separately-styled Labels hanging off the bottom of it.
        results_col = tk.Frame(self.round_over_frame, bg=felt_theme["felt"])
        results_col.place(relx=0.0, x=16, y=0, anchor="nw")

        self.payout_canvas = tk.Canvas(results_col, width=ROUND_RESULT_PANEL_W, height=ROUND_RESULT_PANEL_H,
                                        bg=felt_theme["felt"], highlightthickness=0)
        self.payout_canvas.pack()

        self.chip_zone = tk.Frame(game_col, bg=felt_theme["felt"])
        self.chip_zone.pack(pady=(20, 0))

        self.chip_frame = tk.Frame(self.chip_zone, bg=felt_theme["felt"])
        tk.Label(
            self.chip_frame, text="Tap a chip, then tap Ante / Fortune / Progressive.",
            bg=felt_theme["felt"], fg=theme.FG_DIM, font=theme.font(9),
        ).pack(pady=(0, 3))
        self.chip_row = tk.Frame(self.chip_frame, bg=felt_theme["felt"])
        self.chip_row.pack()
        for value, face, rim in CHIP_DENOMINATIONS:
            self._make_chip_button(self.chip_row, value, face, rim)

        self.total_lbl = tk.Label(
            self.chip_frame, text="Total bet: £0", bg=felt_theme["felt"], fg=theme.ACCENT,
            font=theme.font(12, weight="bold"),
        )
        self.total_lbl.pack(pady=(4, 0))

        self.clear_btn = tk.Button(
            self.chip_frame, text="Clear Bets", bg=theme.GREY_BTN_BG, fg=theme.FG_DIM,
            font=theme.font(9), relief="flat", padx=10, pady=4, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.GREY_BTN_BORDER,
            command=self._clear_bets,
        )
        self.clear_btn.pack(pady=(3, 0))

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
        # Panel chrome (border/title/multiplier accent) follows the selected
        # table felt theme, same as the felt/spots themselves -- only plain
        # informational text (labels, dividers) stays the fixed neutral
        # FG/BORDER every screen already uses regardless of table theme.
        felt_theme = self.app.settings.theme()
        accent = felt_theme["accent"]
        theme.recessed_panel(canvas, 0, 0, w, h, title="FORTUNE PAYTABLE", title_font_size=13,
                              fill=felt_theme["felt_dark"], outline=accent)
        y = 44  # a genuine gap below the title, not crowding straight into it
        canvas.create_text(20, y, text="Ante", fill=theme.FG, font=theme.font(9), anchor="w")
        canvas.create_text(w - 20, y, text="1:1", fill=accent,
                            font=theme.font(9, weight="bold"), anchor="e")
        y += 15
        canvas.create_text(20, y, text=self.ANTE_COMMISSION_NOTE, fill=theme.FG_DIM,
                            font=theme.font(7), anchor="w")
        y += 15
        canvas.create_line(20, y, w - 20, y, fill=theme.BORDER)
        y += 14
        # The Fortune rows fill the rest of the panel evenly, down to a
        # matching bottom margin -- rather than a fixed row height that
        # leaves whatever's left over as dead space underneath the last row.
        bottom_margin = 20
        row_h = (h - bottom_margin - y) / (len(FORTUNE_PAYTABLE_ROWS) - 1)
        for label, mult in FORTUNE_PAYTABLE_ROWS:
            canvas.create_text(20, y, text=label, fill=theme.FG, font=theme.font(8), anchor="w")
            canvas.create_text(w - 20, y, text=mult, fill=accent,
                                font=theme.font(8, weight="bold"), anchor="e")
            y += row_h

    # ------------------------------------------------------------------ betting table
    def _draw_table(self):
        self.canvas.delete("all")
        self._draw_spot_rect("ante", STACK_CX, ANTE_BAR_CY, ANTE_BAR_W, ANTE_BAR_H, "ANTE",
                              textured=True, chip_r=ANTE_CHIP_R)
        self._draw_spot_circle("fortune", FORTUNE_CX, TOP_SPOT_CY, FORTUNE_R, "FORTUNE", chip_r=FORTUNE_CHIP_R)
        self._draw_spot_jackpot(JACKPOT_CX, TOP_SPOT_CY, JACKPOT_R, chip_r=JACKPOT_CHIP_R)
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
            self, "♠ Pai Gow Poker -- Rules",
            [
                ("GAMEPLAY", [
                    "**Betting:** Place an Ante (mandatory) plus optional Fortune and Jackpot "
                    "side bets. Every round is played against the dealer.",
                    "**Dealing:** You and the Dealer each get 7 cards from a 53-card deck "
                    "(52 + the Joker). The Joker plays as an Ace, completes a straight or "
                    "flush.",
                    "**Setting your hand:** Arrange your 7 cards into a 2-card Front hand and "
                    "a 5-card Back hand. The Back must rank higher than the Front."
                    "Sort tidies your unplaced cards; "
                    "House Way sets your whole hand automatically, the same way the Dealer always sets "
                    "their own.",
                    "**Settling:** Win both front and back hands to win the Ante"
                    "(1:1, less a 5% commission on the win). Lose both to lose the Ante. Split "
                    "one each way and it's a push. A tied hand is won by the Dealer.",
                ]),
                ("SIDE BETS", [
                    "**Fortune:** the best hand from your own 7 cards, paid on its own "
                    "paytable regardless of the Ante's outcome -- see the panel alongside "
                    "the table.",
                    "**Jackpot:** flat £1, shares the same progressive pool as the other "
                    "tables -- the very best hands pay a share of it directly; see the "
                    "jackpot panel for the rest of the paytable.",
                ]),
            ],
        )

    def _draw_spot_circle(self, key, cx, cy, r, label, chip_r=CHIP_LAYER_MAX_R):
        tag = f"spot_{key}"
        amount = self.bets[key]
        felt_theme = self.app.settings.theme()
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                 fill=felt_theme["felt_dark"], outline=felt_theme["accent"], width=2, tags=(tag,))
        self.canvas.create_text(cx, cy + r + 12, text=label, fill=theme.FG,
                                 font=theme.font(11, weight="bold"), tags=(tag,))
        if amount:
            draw_chip_stack(self.canvas, tag, cx, cy, amount, chip_r)
        else:
            self.canvas.create_text(cx, cy, text="tap to\nbet", fill=theme.FG_DIM,
                                     font=theme.font(9, weight="bold"), justify="center", tags=(tag,))
        self._bind_spot(tag, key)

    def _draw_spot_rect(self, key, cx, cy, width, height, label, textured=False, chip_r=CHIP_LAYER_MAX_R):
        tag = f"spot_{key}"
        amount = self.bets[key]
        felt_theme = self.app.settings.theme()
        x1, y1, x2, y2 = cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2
        theme.rounded_rect(self.canvas, x1, y1, x2, y2, radius=14, fill=felt_theme["felt_dark"],
                            outline=felt_theme["accent"], width=2, tags=(tag,))
        if textured:
            self._draw_felt_texture(x1, y1, x2, y2, felt_theme, tag)
        self.canvas.create_text(cx, y2 + 12, text=label, fill=theme.FG,
                                 font=theme.font(11, weight="bold"), tags=(tag,))
        if amount:
            # draw_chip_stack anchors its base chip at the cy it's given and
            # grows additional denominations upward from there -- so the
            # base chip just sits resting on the spot's own bottom edge,
            # with no layer-count-dependent shift needed.
            stack_cy = y2 - chip_r - 6
            draw_chip_stack(self.canvas, tag, cx, stack_cy, amount, chip_r)
        else:
            stack_cy = y2 - chip_r - 6
            self.canvas.create_text(cx, stack_cy, text="tap to bet", fill=theme.FG_DIM,
                                     font=theme.font(10, weight="bold"), tags=(tag,))
        self._bind_spot(tag, key)

    def _draw_felt_texture(self, x1, y1, x2, y2, felt_theme, tag):
        inset = 9
        step = 9
        color = theme.lerp_color(felt_theme["felt_dark"], felt_theme["felt"], 0.4)
        ix1, iy1, ix2, iy2 = x1 + inset, y1 + inset, x2 - inset, y2 - inset
        c = ix1 - iy2
        c_max = ix2 - iy1
        while c <= c_max:
            xs = max(ix1, iy1 + c)
            xe = min(ix2, iy2 + c)
            if xs < xe:
                self.canvas.create_line(xs, xs - c, xe, xe - c, fill=color, width=1, tags=(tag,))
            c += step

    def _draw_spot_jackpot(self, cx, cy, r, chip_r=JACKPOT_CHIP_R):
        tag = "spot_jackpot"
        felt_theme = self.app.settings.theme()
        placed = bool(self.bets["jackpot"])
        if placed:
            import math
            t = 0.5 + 0.5 * math.sin(self._jackpot_pulse_t)
            outline_color = theme.lerp_color(felt_theme["felt_dark"], felt_theme["accent"], t)
        else:
            outline_color = felt_theme["accent"]
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=felt_theme["felt_dark"],
                                 outline=outline_color, width=3, tags=(tag,))
        self.canvas.create_text(cx, cy + r + 12, text="JACKPOT", fill=theme.FG,
                                 font=theme.font(11, weight="bold"), tags=(tag,))
        if placed:
            from ui.chips import CHIP_COLORS_BY_VALUE
            face, rim = CHIP_COLORS_BY_VALUE[1]
            token_r = chip_r
            self.canvas.create_oval(cx - token_r, cy - token_r, cx + token_r, cy + token_r,
                                     fill=face, outline=rim, width=2, tags=(tag,))
            self.canvas.create_text(cx, cy, text="£1", fill="#ffffff",
                                     font=theme.font(10, weight="bold"), tags=(tag,))
        else:
            self.canvas.create_text(cx, cy, text="tap\n£1", fill=theme.FG_DIM,
                                     font=theme.font(8, weight="bold"), justify="center", tags=(tag,))
        self._bind_spot(tag, "jackpot")

    def _bind_spot(self, tag, key):
        if tag in self._bound_spot_tags:
            return
        self._bound_spot_tags.add(tag)
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
        self.round_over_frame.pack_forget()
        self.result_lbl.pack(pady=BETTING_RESULT_LBL_PADY, before=self.chip_zone)
        for w in self.action_frame.pack_slaves():
            w.pack_forget()
        self.deal_btn.pack(side="left")
        self.action_frame.pack(pady=BETTING_ACTION_FRAME_PADY, before=self.chip_zone)
        self.chip_frame.pack(pady=CHIP_FRAME_PADY)
        self._draw_table()
        self._update_total()

    def _show_no_controls(self):
        self.canvas.configure(height=CANVAS_HEIGHT)
        self.round_over_frame.pack_forget()
        self.result_lbl.pack(pady=PLAY_RESULT_LBL_PADY, before=self.chip_zone)
        self.chip_frame.pack_forget()
        for w in self.action_frame.pack_slaves():
            w.pack_forget()
        self.action_frame.pack(pady=(8, 0), before=self.chip_zone)

    def _show_setting_controls(self):
        self.round_over_frame.pack_forget()
        self.chip_frame.pack_forget()
        for w in self.action_frame.pack_slaves():
            w.pack_forget()
        self.sort_btn.pack(side="left", padx=6)
        self.middle_btn.pack(side="left", padx=6)
        self.confirm_btn.pack(side="left", padx=6)
        self.action_frame.pack(pady=(8, 0), before=self.chip_zone)
        self._refresh_confirm_state()

    def _show_round_over_controls(self):
        self.chip_frame.pack_forget()
        for w in self.action_frame.pack_slaves():
            w.pack_forget()
        self.result_lbl.pack_forget()
        self.action_frame.pack_forget()
        self.round_over_frame.pack(pady=(4, 0), before=self.chip_zone)

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
        if trial_bets["jackpot"] and sum(trial_bets.values()) > self.app.finance.balance + 1e-9:
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
        if sum(trial_bets.values()) > self.app.finance.balance + 1e-9:
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
        if sum(self.bets.values()) > self.app.finance.balance:
            self.bets = {k: 0 for k in BET_KEYS}
            if persist:
                self._persist_state()

    # ------------------------------------------------------------------ dealing
    def _on_deal(self):
        if self.bets["ante"] <= 0:
            dialogs.info(self, "$ deal --require-bet", "You must place an Ante bet to deal.", accent=theme.WARN)
            return
        total = sum(self.bets.values())
        if not self.app.finance.can_afford(total):
            choice = dialogs.choice(
                self, "$ deal --check-funds", "You don't have enough balance to cover these bets.",
                [("Go Home", "home"), ("Cashier", "cashier")],
            )
            if choice == "home":
                self.app.show_frame("menu")
            elif choice == "cashier":
                self.app.show_frame("finances")
            return

        # New Deal re-deals with the same bets without a trip back through
        # the betting screen -- the previous (now settled) round's stake
        # chips are still sitting on the felt at this point, so those need
        # sweeping away before this round's own stakes get placed (see
        # _withdraw_stale_stakes). A plain DEAL from the betting screen has
        # no such leftovers -- betting's own Ante/Fortune/Jackpot spots
        # aren't the play felt's, and nothing's been placed on the felt yet.
        is_new_deal = self.state == "resolved"
        # Captured now, before anything's hidden -- the very button the
        # player just pressed is still on-screen at this point, wherever
        # DEAL/New Deal happens to be laid out, so the new stakes can fly
        # on from *there* (see _place_stakes_then) rather than some
        # unrelated fixed point.
        origin_xy = self._widget_canvas_center(self.new_deal_btn if is_new_deal else self.deal_btn)
        # Hidden immediately, before any withdrawal animation even starts --
        # not just once it's done -- so New Deal/Change Bets can't be
        # double-clicked mid-withdrawal into re-entering this method with
        # the previous round's own stakes only halfway swept away.
        self._show_no_controls()

        def proceed():
            self.round_bets = dict(self.bets)
            self.app.finance.place_wager(total)
            self._refresh_balance()

            self.result = self.game.deal(
                ante_bet=self.bets["ante"], fortune_bet=self.bets["fortune"], jackpot_bet=self.bets["jackpot"],
                jackpot_amount=self.app.jackpot.amount,
            )
            self.state = "dealt"
            self.card_zone = {i: "felt" for i in range(7)}
            self.felt_slot_order = list(range(7))
            self.front_order = []
            self.back_order = []
            self.active_zone = "front"
            self._player_cards_revealed = 0
            self._dealer_dealt_count = 0
            self._dealer_revealed = 0
            self._dealer_separated = False
            self.result_lbl.configure(text="Dealing...", fg=theme.FG)
            self._place_stakes_then(origin_xy, self._animate_deal_in)

        if is_new_deal:
            self._withdraw_stale_stakes(origin_xy, proceed)
        else:
            proceed()

    def _widget_canvas_center(self, widget):
        """A Tk widget's own on-screen centre, converted into self.canvas's
        local coordinate space -- lets an animation start from wherever a
        button the player just pressed actually sits (see origin_xy above),
        even though that button lives in a totally different widget/layout
        hierarchy than the canvas itself."""
        self.canvas.update_idletasks()
        cx = widget.winfo_rootx() + widget.winfo_width() / 2 - self.canvas.winfo_rootx()
        cy = widget.winfo_rooty() + widget.winfo_height() / 2 - self.canvas.winfo_rooty()
        return cx, cy

    def _place_stakes_then(self, origin_xy, on_done):
        """Flies this round's Ante/Fortune/Jackpot stakes onto their felt
        spots from origin_xy (the DEAL/New Deal button just pressed) before
        calling on_done -- the placement half of the same "chips physically
        move" language the payout side already has (_chip_move_away/
        _chip_move_in), which previously just had the finished stack pop in
        with the rest of _redraw_felt's own static drawing.

        Runs to completion (all stakes at once, see _run_parallel) before
        on_done -- normally _animate_deal_in -- ever starts, rather than
        overlapping with it: _animate_deal_in's own repeated _redraw_felt
        calls (one per card as it lands) would otherwise stomp an
        in-progress fly-in with the finished, full-size stack on every one
        of those redraws."""
        assert self.result is not None
        self._side_stakes_animating = True
        self._redraw_felt()  # dealer mat / zones / felt mat + stake shells -- no chips, no cards, yet

        def finish():
            self._side_stakes_animating = False
            on_done()

        fns = []
        for cx, cy, amount, tag in (
            (ANTE_TOKEN_CX, SIDE_STAKE_BOTTOM_CY, self.result.ante_bet, "chip_ante"),
            (FORTUNE_CX_PLAY, SIDE_STAKE_TOP_CY, self.result.fortune_bet, "chip_fortune"),
            (JACKPOT_CX_PLAY, SIDE_STAKE_TOP_CY, self.result.jackpot_bet, "chip_jackpot"),
        ):
            if amount > 0:
                fns.append(lambda cb, cx=cx, cy=cy, amount=amount, tag=tag:
                           self._place_stake_chip(origin_xy, cx, cy, amount, tag, cb))
        self._run_parallel(fns, finish)

    def _place_stake_chip(self, origin_xy, cx, cy, amount, tag, on_done):
        ox, oy = origin_xy
        travel_tag = f"place_{tag}"

        def frame(t):
            x = ox + (cx - ox) * t
            y = oy + (cy - oy) * t
            r = CHIP_R * t
            self.canvas.delete(travel_tag)
            if r > 1:
                draw_chip_stack(self.canvas, travel_tag, x, y, amount, r)

        def done():
            self.canvas.delete(travel_tag)
            on_done()

        self._animate(STAKE_PLACE_MS, frame, on_done=done)

    # ------------------------------------------------------------------ deal-in
    def _animate_deal_in(self):
        assert self.result is not None
        self._redraw_felt()
        # Alternates player/dealer, one card each per beat -- neither side's
        # cards are actually on the table until their own turn in this
        # sequence lands them there (see _draw_felt_cards/_draw_dealer_cards,
        # both gated on how far through this the deal-in actually is).
        order = []
        for i in range(7):
            order.append(("player", i))
            order.append(("dealer", i))
        animated = self.app.settings.get("animations_enabled")
        if animated:
            for slot, (kind, i) in enumerate(order):
                self.after((slot + 1) * DEAL_CARD_STAGGER_MS, self._fly_deal_card, kind, i)
            delay = (len(order) + 1) * DEAL_CARD_STAGGER_MS + DEAL_FLIGHT_MS
        else:
            delay = 30
        self.after(delay, self._on_deal_in_done)

    def _fly_deal_card(self, kind, i):
        assert self.result is not None
        if kind == "player":
            card = self.result.player_cards[i]
            tx = _felt_card_x(i, 7, FELT_MAT_X1, FELT_MAT_X2)
            ty = FELT_Y

            def on_arrive():
                self._player_cards_revealed = i + 1
                self._redraw_felt()

            self._animate_card_flight(f"flycard_p{i}", card, tx, ty, CARD_WIDTH, CARD_HEIGHT, True, on_arrive)
        else:
            card = self.result.dealer_cards[i]
            tx = _dealer_cluster_x(i)
            ty = DEALER_Y

            def on_arrive():
                self._dealer_dealt_count = i + 1
                self._redraw_felt()

            self._animate_card_flight(f"flycard_d{i}", card, tx, ty, CARD_WIDTH, CARD_HEIGHT, False, on_arrive)

    def _animate_card_flight(self, tag, card, tx, ty, tw, th, face_up_at_end, on_arrive):
        sx, sy = DECK_X1, DECK_Y
        accent = self.app.settings.theme()["accent"]

        def frame(t):
            self.canvas.delete(tag)
            x = sx + (tx - sx) * t
            y = sy + (ty - sy) * t
            w = CARD_WIDTH + (tw - CARD_WIDTH) * t
            h = CARD_HEIGHT + (th - CARD_HEIGHT) * t
            if face_up_at_end and t > 0.65:
                flip_t = min(1.0, (t - 0.65) / 0.35)
                squeeze = abs(1 - 2 * flip_t)
                fw = max(4, w * squeeze)
                fx = x + (w - fw) / 2
                if flip_t >= 0.5:
                    draw_card(self.canvas, fx, y, card, width=fw, height=h, tags=(tag,))
                else:
                    draw_card_back(self.canvas, fx, y, self._current_felt, accent, width=fw, height=h, tags=(tag,))
            else:
                draw_card_back(self.canvas, x, y, self._current_felt, accent, width=w, height=h, tags=(tag,))

        def done():
            self.canvas.delete(tag)
            on_arrive()

        self._animate(DEAL_FLIGHT_MS, frame, on_done=done)

    def _on_deal_in_done(self):
        # Authoritative "dealing has actually finished" signal, regardless
        # of which path got here (the staggered fly-ins, or animations
        # being off and skipping straight here) -- guarantees every card's
        # actually showing once play begins.
        self._player_cards_revealed = 7
        self._dealer_dealt_count = 7
        self._redraw_felt()
        self.state = "setting"
        self.result_lbl.configure(text="Set your hand: 2 cards Front, 5 Back.", fg=theme.FG)
        self._show_setting_controls()

    # ------------------------------------------------------------------ felt / zone drawing
    def _draw_dealer_mat(self):
        felt_theme = self.app.settings.theme()
        theme.rounded_rect(self.canvas, DEALER_MAT_X1, DEALER_MAT_TOP, DEALER_MAT_X2, DEALER_MAT_BOTTOM,
                            radius=DEALER_MAT_RADIUS, fill=felt_theme["felt_dark"], outline=felt_theme["accent"],
                            width=2, tags=("dealer_mat",))
        self.canvas.create_text(CANVAS_WIDTH / 2, DEALER_MAT_LABEL_Y, text="DEALER", fill=theme.ACCENT,
                                 font=theme.font(9, weight="bold"), tags=("dealer_mat",))

    def _draw_deck(self):
        """The face-down shoe every dealt card visibly flies out of (see
        _animate_card_flight) -- its own small zone, in-line with Front/
        Back/the side stakes rather than up beside the Dealer."""
        felt_theme = self.app.settings.theme()
        theme.rounded_rect(self.canvas, DECK_ZONE_X1, ZONE_TOP, DECK_ZONE_X2, ZONE_BOTTOM, radius=12,
                            fill=felt_theme["felt_dark"], outline=theme.FG_DIM, width=1, tags=("zone_bg",))
        self.canvas.create_text(DECK_ZONE_CX, ZONE_TOP + ZONE_LABEL_Y_OFFSET, text="DECK", fill=theme.FG_DIM,
                                 font=theme.font(10, weight="bold"), tags=("zone_bg",))
        draw_card_back(self.canvas, DECK_X1, DECK_Y, self._current_felt, felt_theme["accent"], tags=("zone_bg",))

    def _draw_dealer_cards(self):
        assert self.result is not None
        if self._dealer_separated:
            # Once separated, the settled Front/Back groups (not the
            # pre-split cluster below) are the correct thing to draw here --
            # see _draw_dealer_settled. Standard Pai Gow Poker never calls
            # _redraw_felt() again once separated (separation only ever
            # happens after Confirm, by which point play has moved on to the
            # reveal/payout sequence), but Face Up Pai Gow does -- its own
            # dealer reveal happens *before* the player sets their hand, so
            # every card placement's own _redraw_felt() during that setting
            # phase runs with _dealer_separated already true.
            self._draw_dealer_settled()
            return
        for i, card in enumerate(self.result.dealer_cards):
            tag = f"dealer_card_{i}"
            self.canvas.delete(tag)
            if i >= self._dealer_dealt_count:
                continue  # not dealt yet -- see _animate_deal_in
            x = _dealer_cluster_x(i)
            face_up = i < self._dealer_revealed
            if face_up:
                draw_card(self.canvas, x, DEALER_Y, card, tags=(tag,))
            else:
                draw_card_back(self.canvas, x, DEALER_Y, self._current_felt,
                                self.app.settings.theme()["accent"], tags=(tag,))

    def _draw_felt_mat(self):
        felt_theme = self.app.settings.theme()
        theme.rounded_rect(self.canvas, FELT_MAT_X1, FELT_TOP, FELT_MAT_X2, FELT_MAT_BOTTOM,
                            radius=DEALER_MAT_RADIUS, fill=felt_theme["felt_dark"], outline=theme.FG_DIM,
                            width=2, tags=("felt_mat",))
        self.canvas.create_text(CANVAS_WIDTH / 2, FELT_LABEL_Y, text="YOUR CARDS", fill=theme.FG_DIM,
                                 font=theme.font(9, weight="bold"), tags=("felt_mat",))

    def _draw_felt_cards(self):
        assert self.result is not None
        for i, card in enumerate(self.result.player_cards):
            tag = f"feltslot_{i}"
            self.canvas.delete(tag)
            if i >= self._player_cards_revealed:
                continue  # not dealt yet -- see _animate_deal_in
            if self.card_zone.get(i) != "felt":
                continue
            x = _felt_card_x(self.felt_slot_order.index(i) if i in self.felt_slot_order else i, 7,
                              FELT_MAT_X1, FELT_MAT_X2)
            draw_card(self.canvas, x, FELT_Y, card, tags=(tag, "player_card", f"cardidx_{i}"))
            self.canvas.tag_bind(tag, "<Button-1>", lambda e, idx=i: self._on_felt_card_click(idx))
            # xx=x (not just idx=i) -- x is the per-iteration loop variable,
            # so every one of these 7 lambdas needs its own default-arg
            # snapshot of it, or they'd all close over the same variable
            # and read whatever x was left at by the loop's final iteration
            # once actually invoked later on a real <Enter> event.
            self.canvas.tag_bind(
                tag, "<Enter>", lambda e, idx=i, xx=x: self._on_card_hover(idx, xx, FELT_Y, CARD_WIDTH, CARD_HEIGHT)
            )
            self.canvas.tag_bind(tag, "<Leave>", lambda e: self._on_card_unhover())

    def _draw_zones(self):
        felt_theme = self.app.settings.theme()
        self._draw_deck()
        front_active = self.active_zone == "front" and self.state == "setting"
        back_active = self.active_zone == "back" and self.state == "setting"
        theme.rounded_rect(self.canvas, FRONT_ZONE_X1, ZONE_TOP, FRONT_ZONE_X2, ZONE_BOTTOM, radius=12,
                            fill=felt_theme["felt_dark"],
                            outline=theme.ACCENT if front_active else theme.FG_DIM,
                            width=3 if front_active else 1, tags=("zone_bg",))
        theme.rounded_rect(self.canvas, BACK_ZONE_X1, ZONE_TOP, BACK_ZONE_X2, ZONE_BOTTOM, radius=12,
                            fill=felt_theme["felt_dark"],
                            outline=theme.ACCENT if back_active else theme.FG_DIM,
                            width=3 if back_active else 1, tags=("zone_bg",))
        self.canvas.create_text(FRONT_ZONE_CX, ZONE_TOP + ZONE_LABEL_Y_OFFSET, text="FRONT",
                                 fill=theme.ACCENT if front_active else theme.FG_DIM,
                                 font=theme.font(10, weight="bold"), tags=("zone_bg",))
        self.canvas.create_text(BACK_ZONE_CX, ZONE_TOP + ZONE_LABEL_Y_OFFSET, text="BACK",
                                 fill=theme.ACCENT if back_active else theme.FG_DIM,
                                 font=theme.font(10, weight="bold"), tags=("zone_bg",))

    def _draw_placed_cards(self):
        assert self.result is not None
        cards = self.result.player_cards
        # Front: fanned horizontally, same row height and overlap
        # convention as Back -- in line with the rest of the play area
        # (Dealer row, felt row, Back's own fan) rather than stacked
        # vertically on its own.
        row_y = ZONE_TOP + ZONE_LABEL_Y_OFFSET + 24
        n_front = len(self.front_order)
        front_fan_w = (n_front - 1) * FRONT_CARD_OVERLAP_X + CARD_WIDTH if n_front else 0
        front_start_x = FRONT_ZONE_CX - front_fan_w / 2
        for pos, idx in enumerate(self.front_order):
            tag = f"frontcard_{idx}"
            self.canvas.delete(tag)
            x = front_start_x + pos * FRONT_CARD_OVERLAP_X
            draw_card(self.canvas, x, row_y, cards[idx], tags=(tag, "player_card", f"cardidx_{idx}"))
            # A later card overlaps the one before it, covering its right
            # portion -- so only THIS card's own exposed sliver (up to
            # where the next card starts covering it) should actually
            # register as itself. See _bind_placed_card_hit.
            exposed_w = FRONT_CARD_OVERLAP_X if pos < n_front - 1 else CARD_WIDTH
            self._bind_placed_card_hit(idx, x, row_y, exposed_w, CARD_HEIGHT)

        back_y = ZONE_TOP + ZONE_LABEL_Y_OFFSET + 24
        n_back = len(self.back_order)
        fan_w = (n_back - 1) * BACK_CARD_OVERLAP_X + CARD_WIDTH if n_back else 0
        start_x = BACK_ZONE_CX - fan_w / 2
        for pos, idx in enumerate(self.back_order):
            tag = f"backcard_{idx}"
            self.canvas.delete(tag)
            x = start_x + pos * BACK_CARD_OVERLAP_X
            draw_card(self.canvas, x, back_y, cards[idx], tags=(tag, "player_card", f"cardidx_{idx}"))
            exposed_w = BACK_CARD_OVERLAP_X if pos < n_back - 1 else CARD_WIDTH
            self._bind_placed_card_hit(idx, x, back_y, exposed_w, CARD_HEIGHT)

    def _bind_placed_card_hit(self, idx, x, y, exposed_w, exposed_h):
        """An invisible hit-region covering just this card's own exposed
        sliver (see _draw_placed_cards), drawn on top of every visible card
        in that band -- so hover/click always target whichever card you
        can actually see there, not whichever fanned card's full rectangle
        happens to extend furthest over it in z-order. Without this, only
        the last (fully unobscured) card in a fanned/stacked group could
        ever be hovered or clicked as itself."""
        hit_tag = f"hit_{idx}"
        self.canvas.delete(hit_tag)
        self.canvas.create_rectangle(x, y, x + exposed_w, y + exposed_h, fill="", outline="", tags=(hit_tag,))
        self.canvas.tag_bind(hit_tag, "<Button-1>", lambda e, i=idx: self._on_placed_card_click(i))
        self.canvas.tag_bind(
            hit_tag, "<Enter>", lambda e, i=idx, xx=x, yy=y: self._on_card_hover(i, xx, yy, CARD_WIDTH, CARD_HEIGHT)
        )
        self.canvas.tag_bind(hit_tag, "<Leave>", lambda e: self._on_card_unhover())

    def _on_card_hover(self, idx, x, y, w, h):
        if self._hover_tag:
            self.canvas.delete(self._hover_tag)
        tag = "hover_highlight"
        self.canvas.create_rectangle(x - 3, y - 3, x + w + 3, y + h + 3, outline=theme.ACCENT, width=2, tags=(tag,))
        # Lower below this specific card's own tag (every player card --
        # felt or placed -- carries cardidx_{idx}), not the shared
        # "player_card" tag every card carries: lowering below THAT always
        # re-stacks the highlight beneath the very first player card ever
        # drawn, regardless of which card idx is actually being hovered.
        self.canvas.tag_lower(tag, f"cardidx_{idx}")
        self._hover_tag = tag
        self.canvas.configure(cursor="hand2")

    def _on_card_unhover(self):
        if self._hover_tag:
            self.canvas.delete(self._hover_tag)
            self._hover_tag = None
        self.canvas.configure(cursor="")

    def _redraw_felt(self):
        self.canvas.delete("all")
        self._draw_dealer_mat()
        if self.result:
            self._draw_dealer_cards()
        self._draw_zones()
        if self.result:
            self._draw_placed_cards()
            # Your Ante/Fortune/Jackpot stakes -- visible for the whole
            # round, from the moment the cards start dealing, not just
            # once the outcome's determined (see _draw_side_stakes).
            self._draw_side_stakes(draw_chips=not self._side_stakes_animating)
        self._draw_felt_mat()
        if self.result:
            self._draw_felt_cards()

    # ------------------------------------------------------------------ placement
    def _activate_needed_zone(self):
        """Sets active_zone to whichever zone still needs cards -- Front if
        it's short, else Back -- rather than trusting whatever zone the
        last click happened to touch. Call this any time front_order/
        back_order's lengths change (placing, removing, or House Way).

        Deriving this fresh from the actual counts (rather than e.g. just
        setting it to "the zone a card was just removed from") matters
        because the highlighted zone could otherwise end up pointing at one
        that's already full while the other still needs a card -- e.g.
        remove a card from Front, then one from Back too: naively that's
        "back", but if Back then refills to 5 while Front is still short,
        there'd be no click-based way back to Front without first undoing
        an already-placed card."""
        if len(self.front_order) < 2:
            self.active_zone = "front"
        elif len(self.back_order) < 5:
            self.active_zone = "back"
        # else: both full -- nothing left to place, leave active_zone as-is.

    def _on_felt_card_click(self, idx):
        if self.state != "setting":
            return
        zone = self.active_zone
        if zone == "front" and len(self.front_order) >= 2:
            return
        if zone == "back" and len(self.back_order) >= 5:
            return
        self.card_zone[idx] = zone
        (self.front_order if zone == "front" else self.back_order).append(idx)
        self._activate_needed_zone()
        self._on_card_unhover()
        self._redraw_felt()
        self._refresh_confirm_state()

    def _on_placed_card_click(self, idx):
        if self.state != "setting":
            return
        zone = self.card_zone.get(idx)
        if zone == "front":
            self.front_order.remove(idx)
        elif zone == "back":
            self.back_order.remove(idx)
        else:
            return
        self.card_zone[idx] = "felt"
        self._activate_needed_zone()
        self._on_card_unhover()
        self._redraw_felt()
        self._refresh_confirm_state()

    def _current_split_valid(self):
        if len(self.front_order) != 2 or len(self.back_order) != 5:
            return False
        assert self.result is not None
        cards = self.result.player_cards
        front = [cards[i] for i in self.front_order]
        back = [cards[i] for i in self.back_order]
        front_eval = evaluate_two_card_hand(front)
        back_eval = best_five_card_eval_with_joker(back)
        return compare_hands(back_eval, front_eval) > 0

    def _refresh_confirm_state(self):
        front_ready = len(self.front_order) == 2
        back_ready = len(self.back_order) == 5
        if front_ready and back_ready:
            # Fully placed -- CONFIRM, gated by the normal foul check.
            valid = self._current_split_valid()
            self.result_lbl.configure(text="Confirm your hand?", fg=theme.FG)
            self.confirm_btn.configure(
                text="CONFIRM", command=self._on_confirm,
                state="normal" if valid else "disabled",
                bg=theme.ACCENT_DIM_BG if valid else theme.GREY_BTN_BG,
                fg=theme.FG if valid else theme.GREY_BTN_TEXT,
                highlightbackground=theme.ACCENT if valid else theme.GREY_BTN_BORDER,
            )
            if not valid:
                self.result_lbl.configure(
                    text="That's a foul -- the Back hand must outrank the Front. Rearrange it.", fg=theme.WARN)
        else:
            # Still being placed -- SET, a shortcut that drops the rest of
            # the felt straight into Back once Front's own 2 cards are in
            # (see _on_set_shortcut), rather than requiring every Back card
            # to be clicked one at a time.
            self.confirm_btn.configure(
                text="SET", command=self._on_set_shortcut,
                state="normal" if front_ready else "disabled",
                bg=theme.ACCENT_DIM_BG if front_ready else theme.GREY_BTN_BG,
                fg=theme.FG if front_ready else theme.GREY_BTN_TEXT,
                highlightbackground=theme.ACCENT if front_ready else theme.GREY_BTN_BORDER,
            )
            if self.state == "setting":
                if front_ready:
                    self.result_lbl.configure(text="Place the rest?", fg=theme.FG)
                else:
                    self.result_lbl.configure(text="Set your hand: 2 cards Front, 5 Back.", fg=theme.FG)

    def _lock_setting_buttons(self):
        """Disables Sort/middle/Confirm, and sets _setting_locked, for the
        duration of a card-placement animation (Sort, House Way, or the
        SET shortcut) -- without this, a second click mid-animation
        re-enters the same handler while it's still mutating front_order/
        back_order/card_zone, starting a second overlapping place_next
        chain on top of the first's and corrupting that shared state (the
        exact bug a repeated SET click used to hit -- Confirm would end up
        permanently stuck). The disabled buttons alone stop a real second
        click; _setting_locked (checked at each handler's own top) stops a
        re-entrant *call* even if something else dispatches one."""
        self._setting_locked = True
        self.sort_btn.configure(state="disabled")
        self.middle_btn.configure(state="disabled")
        self.confirm_btn.configure(state="disabled")

    def _unlock_setting_buttons(self):
        """Restores Sort/middle to normal (and clears _setting_locked) once
        a placement animation finishes. Confirm's own state/text is
        deliberately left alone here -- _refresh_confirm_state(), always
        called right after this, fully re-derives it from the actual
        front/back completeness anyway."""
        self._setting_locked = False
        self.sort_btn.configure(state="normal")
        self.middle_btn.configure(state="normal")

    def _on_set_shortcut(self):
        """SET's shortcut: once Front has its 2 cards, places every card
        still on the felt into Back one at a time -- the same beat House
        Way's own placement uses -- rather than making you click each of
        the (up to 5) remaining cards individually. Placed in hand-display
        order (see _back_display_key), not raw felt order, so e.g. a pair
        lands together up front and a straight lands in sequence."""
        if self.state != "setting" or len(self.front_order) != 2 or self._setting_locked:
            return
        assert self.result is not None
        cards = self.result.player_cards
        remaining = [i for i in range(7) if self.card_zone.get(i) == "felt"]
        counts = {}
        for i in remaining:
            r = _back_display_rank(cards[i])
            counts[r] = counts.get(r, 0) + 1
        remaining.sort(key=lambda i: _back_display_key(cards[i], counts), reverse=True)
        self._lock_setting_buttons()

        def place_next(rem):
            if not rem:
                self._activate_needed_zone()
                self._redraw_felt()
                self._unlock_setting_buttons()
                self._refresh_confirm_state()
                return
            idx = rem[0]
            self.card_zone[idx] = "back"
            self.back_order.append(idx)
            self._redraw_felt()
            self._after_delay(HOUSE_WAY_FLIGHT_MS, lambda: place_next(rem[1:]))

        self._on_card_unhover()
        self._after_delay(HOUSE_WAY_FLIGHT_MS, lambda: place_next(remaining))

    # ------------------------------------------------------------------ Sort / House Way
    def _on_sort(self):
        if self.state != "setting" or self._setting_locked:
            return
        felt_indices = [i for i in range(7) if self.card_zone.get(i) == "felt"]
        if len(felt_indices) < 2:
            return
        assert self.result is not None
        cards = self.result.player_cards
        occupied_slots = sorted(self.felt_slot_order.index(i) for i in felt_indices)
        sorted_indices = sorted(felt_indices, key=lambda i: _sort_key(cards[i]), reverse=True)
        new_order = list(self.felt_slot_order)
        for slot, idx in zip(occupied_slots, sorted_indices):
            new_order[slot] = idx
        old_order = list(self.felt_slot_order)
        self._lock_setting_buttons()

        def frame(t):
            self.canvas.delete("sortmove")
            for slot in occupied_slots:
                idx = new_order[slot]
                old_slot = old_order.index(idx)
                x0 = _felt_card_x(old_slot, 7, FELT_MAT_X1, FELT_MAT_X2)
                x1 = _felt_card_x(slot, 7, FELT_MAT_X1, FELT_MAT_X2)
                x = x0 + (x1 - x0) * t
                tag = f"feltslot_{idx}"
                self.canvas.delete(tag)
                draw_card(self.canvas, x, FELT_Y, cards[idx], tags=("sortmove",))

        def done():
            self.felt_slot_order = new_order
            self._redraw_felt()
            self._unlock_setting_buttons()
            self._refresh_confirm_state()

        self._animate(SORT_MOVE_MS, frame, on_done=done)

    def _on_house_way(self):
        if self.state != "setting" or self._setting_locked:
            return
        assert self.result is not None
        cards = self.result.player_cards
        front_cards, back_cards = house_way_set(cards)
        front_indices = [cards.index(c) for c in front_cards]
        back_indices = [cards.index(c) for c in back_cards]

        self.front_order = []
        self.back_order = []
        self.card_zone = {i: "felt" for i in range(7)}
        self.felt_slot_order = list(range(7))
        self._redraw_felt()
        self._lock_setting_buttons()

        def place_next(remaining):
            if not remaining:
                self._activate_needed_zone()
                self._redraw_felt()
                self._unlock_setting_buttons()
                self._refresh_confirm_state()
                return
            zone, idx = remaining[0]
            self.card_zone[idx] = zone
            (self.front_order if zone == "front" else self.back_order).append(idx)
            self._redraw_felt()
            self._after_delay(HOUSE_WAY_FLIGHT_MS, lambda: place_next(remaining[1:]))

        plan = [("front", i) for i in front_indices] + [("back", i) for i in back_indices]
        self._after_delay(HOUSE_WAY_FLIGHT_MS, lambda: place_next(plan))

    # ------------------------------------------------------------------ confirm / reveal
    def _on_confirm(self):
        if not self._current_split_valid():
            return
        assert self.result is not None
        cards = self.result.player_cards
        front = [cards[i] for i in self.front_order]
        back = [cards[i] for i in self.back_order]
        self.game.set_player_hand(front, back)
        self.state = "revealing"
        self.result_lbl.configure(text="Dealer's turn.", fg=theme.FG)
        self._show_no_controls()
        self._dealer_revealed = 0
        self._redraw_felt()
        self._reveal_dealer()

    def _reveal_dealer(self):
        assert self.result is not None  # always called right after _on_confirm's own assert
        result = self.result

        def reveal_next(i):
            card = result.dealer_cards[i]
            x = _dealer_cluster_x(i)
            cx_slot = x + CARD_WIDTH / 2
            tag = f"dealer_card_{i}"
            self.canvas.delete(tag)

            def done():
                self._dealer_revealed = i + 1
                self._redraw_felt()

            self._animate_flip(self.canvas, tag, cx_slot, DEALER_Y, card, REVEAL_FLIP_MS, on_done=done)

        self._run_staggered(7, REVEAL_STAGGER_MS, reveal_next)
        animated = self.app.settings.get("animations_enabled")
        delay = 7 * REVEAL_STAGGER_MS + REVEAL_FLIP_MS if animated else 30
        self.after(delay, lambda: self._after_delay(300, self._separate_dealer_hand))

    def _animate_flip(self, canvas, tag, cx_slot, y, card, duration, on_done=None):
        """Flips a face-down card at (cx_slot, y) face up in place by
        narrowing it to a sliver and back out, swapping the face at the
        midpoint -- same beat Blackjack/Three Card Poker use for their own
        dealer reveals."""
        accent = self.app.settings.theme()["accent"]

        def frame(t):
            squeeze = abs(1 - 2 * t)
            w = max(6, CARD_WIDTH * squeeze)
            x = cx_slot - w / 2
            canvas.delete(tag)
            if squeeze > 0.35:
                if t >= 0.5:
                    draw_card(canvas, x, y, card, width=w, tags=(tag,))
                else:
                    draw_card_back(canvas, x, y, self._current_felt, accent, width=w, tags=(tag,))
            else:
                canvas.create_rectangle(x, y, x + w, y + CARD_HEIGHT,
                                         fill="#fdfdf5", outline="#222222", tags=(tag,))

        self._animate(duration, frame, on_done=on_done)

    def _separate_dealer_hand(self):
        """The Dealer's own House Way front-2/back-5 split, animated: every
        card slides from its cluster position (see _dealer_cluster_x) out
        to its own group's spot -- front left, back right, a clear gap
        between them -- then FRONT/BACK labels appear once they've landed,
        before the payout sequence starts."""
        self._dealer_separated = True
        self.result = self.game.settle()
        self._animate_dealer_separation()

    def _dealer_front_back_positions(self):
        assert self.result is not None
        front_cards = sorted(self.result.dealer_front, key=_sort_key, reverse=True)
        back_cards = sorted(self.result.dealer_back, key=_sort_key, reverse=True)
        return front_cards, back_cards

    def _dealer_group_layout(self):
        """The shared geometry for the Dealer's settled Front (2) / Back
        (5) groups -- both fully separated, side by side, no overlap (the
        Dealer mat has plenty of room, unlike the player's own tight Back
        zone, which fans with overlap out of necessity, not style) -- with
        a wide gap between the two groups, not a single continuous row, so
        it reads the same "two hands" way the player's own Front/Back zones
        do. Returns (front_gap, front_w, back_gap, back_w, start_x,
        back_x_start)."""
        front_gap = CARD_WIDTH + 8
        front_w = CARD_WIDTH + front_gap
        back_gap = CARD_WIDTH + 8
        back_w = CARD_WIDTH + 4 * back_gap
        total_w = front_w + DEALER_GROUP_GAP + back_w
        start_x = CANVAS_WIDTH / 2 - total_w / 2
        back_x_start = start_x + front_w + DEALER_GROUP_GAP
        return front_gap, front_w, back_gap, back_w, start_x, back_x_start

    def _dealer_target_x(self):
        """{id(card): target_x} for all 7 Dealer cards, at their settled
        Front/Back group position."""
        front_cards, back_cards = self._dealer_front_back_positions()
        front_gap, front_w, back_gap, back_w, start_x, back_x_start = self._dealer_group_layout()
        targets = {}
        for i, card in enumerate(front_cards):
            targets[id(card)] = start_x + i * front_gap
        for i, card in enumerate(back_cards):
            targets[id(card)] = back_x_start + i * back_gap
        return targets

    def _draw_dealer_settled(self):
        """The Dealer's already-separated Front/Back groups, at rest -- the
        steady-state counterpart to _animate_dealer_separation's own final
        frame, used by _draw_dealer_cards so a later full-canvas
        _redraw_felt() (see its own comment) redraws this instead of
        silently leaving the Dealer's cards blank."""
        assert self.result is not None
        target_x = self._dealer_target_x()
        for card in self.result.dealer_cards:
            draw_card(self.canvas, target_x[id(card)], DEALER_Y, card, tags=("dealer_settled",))
        self._draw_dealer_group_labels()

    def _animate_dealer_separation(self):
        assert self.result is not None
        self.canvas.delete("dealer_card_0", "dealer_card_1", "dealer_card_2", "dealer_card_3",
                            "dealer_card_4", "dealer_card_5", "dealer_card_6")
        cards = self.result.dealer_cards
        start_x = {id(card): _dealer_cluster_x(i) for i, card in enumerate(cards)}
        target_x = self._dealer_target_x()

        def frame(t):
            self.canvas.delete("dealer_settled")
            for card in cards:
                x = start_x[id(card)] + (target_x[id(card)] - start_x[id(card)]) * t
                draw_card(self.canvas, x, DEALER_Y, card, tags=("dealer_settled",))

        def done():
            self._draw_dealer_group_labels()
            self._on_dealer_separated()

        self._animate(SEPARATE_MOVE_MS, frame, on_done=done)

    def _on_dealer_separated(self):
        """Called once the Dealer's settled Front/Back groups have finished
        sliding apart -- standard Pai Gow Poker always reaches this via
        Confirm -> settle() -> reveal -> separate, so the round's already
        fully resolved and there's nothing left to do but pause briefly and
        pay out. Overridden by games/pai_gow_poker_face_up/ui.py, whose own
        reveal happens *before* the player has set a hand at all."""
        self._after_delay(400, self._start_payout_sequence)

    def _draw_dealer_group_labels(self):
        """"FRONT"/"BACK" above the Dealer's own settled groups -- same
        mint-green, bold styling the "DEALER" mat label itself uses."""
        front_gap, front_w, back_gap, back_w, start_x, back_x_start = self._dealer_group_layout()
        front_cx = start_x + front_w / 2
        back_cx = back_x_start + back_w / 2
        label_y = DEALER_MAT_TOP + 10  # clear of both the box's own top border and the cards below
        self.canvas.create_text(front_cx, label_y, text="FRONT", fill=theme.ACCENT,
                                 font=theme.font(9, weight="bold"), tags=("dealer_settled",))
        self.canvas.create_text(back_cx, label_y, text="BACK", fill=theme.ACCENT,
                                 font=theme.font(9, weight="bold"), tags=("dealer_settled",))

    # ------------------------------------------------------------------ payout
    def _payout_items(self):
        assert self.result is not None
        items = []
        items.append(dict(cx=ANTE_TOKEN_CX, cy=SIDE_STAKE_BOTTOM_CY, bet=self.result.ante_bet,
                           ret=self.result.ante_return, max_r=CHIP_R, tag="chip_ante"))
        if self.result.fortune_bet > 0:
            items.append(dict(cx=FORTUNE_CX_PLAY, cy=SIDE_STAKE_TOP_CY, bet=self.result.fortune_bet,
                               ret=self.result.fortune_return, max_r=CHIP_R, tag="chip_fortune"))
        if self.result.jackpot_bet > 0:
            items.append(dict(cx=JACKPOT_CX_PLAY, cy=SIDE_STAKE_TOP_CY, bet=self.result.jackpot_bet,
                               ret=self.result.jackpot_return, max_r=CHIP_R, tag="chip_jackpot"))
        return items

    def _withdraw_stale_stakes(self, dest_xy, on_done):
        """New Deal re-deals without a trip back through the betting
        screen (see _on_deal), so the previous round's settled stakes --
        each one's original bet stack, plus any win-payout overlay
        _chip_move_in left sitting beside it (that one's never cleaned up
        on its own -- see its own docstring) -- are still sitting on the
        felt at this point. Sweeps whatever's actually still there off
        toward dest_xy (the New Deal button the player just pressed -- see
        _on_deal; the player's taking these chips back, not the dealer)
        before this round's own fresh stakes get placed, rather than
        letting them simply vanish under the canvas wipe that starts the
        next deal-in.

        Driven by what's actually on the canvas (find_withtag), not by
        re-deriving win/loss/push from self.result -- a losing stake's own
        chips are already gone by now (_chip_move_away deleted them at
        settlement), so this only ever sweeps a tag that still has
        something to sweep."""
        fns = []
        for item in self._payout_items():
            tag = item["tag"]
            if self.canvas.find_withtag(tag):
                fns.append(lambda cb, item=item: self._sweep_stake_away(item, dest_xy, cb))
            win_tag = f"travelwin_{tag}"
            if self.canvas.find_withtag(win_tag):
                win_item = dict(item, tag=win_tag, bet=item["ret"] - item["bet"],
                                 cx=item["cx"] + PAYOUT_WIN_LANDING_OFFSET_X,
                                 cy=item["cy"] + PAYOUT_WIN_LANDING_OFFSET_Y)
                fns.append(lambda cb, win_item=win_item: self._sweep_stake_away(win_item, dest_xy, cb))
        self._run_parallel(fns, on_done)

    def _sweep_stake_away(self, item, dest_xy, on_done):
        """One stale chip stack's own sweep toward dest_xy -- the same
        shrink-while-travelling motion _chip_move_away uses for a losing
        payout (which always sweeps to the dealer), just reused here with
        an arbitrary destination so a stake can be withdrawn toward the
        player instead (see _withdraw_stale_stakes)."""
        dx, dy = dest_xy
        travel_tag = f"withdraw_{item['tag']}"

        def frame(t):
            cx = item["cx"] + (dx - item["cx"]) * t
            cy = item["cy"] + (dy - item["cy"]) * t
            r = item["max_r"] * (1 - t)
            self.canvas.delete(travel_tag)
            if r > 1:
                draw_chip_stack(self.canvas, travel_tag, cx, cy, item["bet"], r)

        def done():
            self.canvas.delete(travel_tag)
            self.canvas.delete(item["tag"])
            on_done()

        self.canvas.delete(item["tag"])
        self._animate(PAYOUT_CHIP_MOVE_MS, frame, on_done=done)

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
        self._animate(PAYOUT_CHIP_MOVE_MS, frame, on_done=done)

    def _chip_move_in(self, item, on_done):
        win_amount = item["ret"] - item["bet"]
        if win_amount <= 0:
            on_done()
            return
        travel_tag = f"travelwin_{item['tag']}"
        landing_cx = item["cx"] + PAYOUT_WIN_LANDING_OFFSET_X
        landing_cy = item["cy"] + PAYOUT_WIN_LANDING_OFFSET_Y

        def frame(t):
            cx = DEALER_CENTER_X + (landing_cx - DEALER_CENTER_X) * t
            cy = DEALER_CENTER_Y + (landing_cy - DEALER_CENTER_Y) * t
            r = item["max_r"] * t
            self.canvas.delete(travel_tag)
            if r > 1:
                draw_chip_stack(self.canvas, travel_tag, cx, cy, win_amount, r)

        self._animate(PAYOUT_CHIP_MOVE_MS, frame, on_done=on_done)

    def _animate_payouts(self, on_done):
        items = self._payout_items()
        losers = [it for it in items if it["ret"] < it["bet"] - 1e-9]
        winners = [it for it in items if it["ret"] > it["bet"] + 1e-9]
        fns = [(lambda cb, it=it: self._chip_move_away(it, cb)) for it in losers]
        fns += [(lambda cb, it=it: self._chip_move_in(it, cb)) for it in winners]
        if not fns:
            on_done()
            return
        self._run_sequential(fns, on_done)

    def _start_payout_sequence(self):
        # The stake chips are already on canvas -- drawn continuously by
        # _redraw_felt (see _draw_side_stakes) since the moment the round
        # started, not freshly here -- _animate_payouts just picks them up
        # by their existing tags.
        self._animate_payouts(self._on_round_settled)

    def _draw_side_stakes(self, draw_chips=True):
        # Fortune/Jackpot/Ante in a triangle -- Fortune and Jackpot as the
        # top two points, Ante below them -- matching the betting screen's
        # own Fortune/Jackpot-above-Ante convention, in the space between
        # the Back zone and the Dealer mat's right edge.
        #
        # `draw_chips=False` (see _place_stakes_then) draws just the
        # felt+label shells, leaving the chip stacks themselves to an
        # in-progress fly-in animation instead of popping them straight to
        # their finished, full size.
        assert self.result is not None
        felt_theme = self.app.settings.theme()

        def stake(cx, cy, amount, chips_tag, label):
            shell_tag = f"shell_{chips_tag}"
            self.canvas.create_oval(cx - SIDE_STAKE_FELT_R, cy - SIDE_STAKE_FELT_R,
                                     cx + SIDE_STAKE_FELT_R, cy + SIDE_STAKE_FELT_R,
                                     fill=felt_theme["felt_dark"], outline=felt_theme["accent"], width=2,
                                     tags=(shell_tag,))
            if draw_chips:
                draw_chip_stack(self.canvas, chips_tag, cx, cy, amount, CHIP_R)
            self.canvas.create_text(cx, cy + SIDE_STAKE_FELT_R + 10, text=label, fill=theme.FG_DIM,
                                     font=theme.font(8, weight="bold"), tags=(shell_tag,))

        stake(ANTE_TOKEN_CX, SIDE_STAKE_BOTTOM_CY, self.result.ante_bet, "chip_ante", "ANTE")
        if self.result.fortune_bet > 0:
            stake(FORTUNE_CX_PLAY, SIDE_STAKE_TOP_CY, self.result.fortune_bet, "chip_fortune", "FORTUNE")
        if self.result.jackpot_bet > 0:
            stake(JACKPOT_CX_PLAY, SIDE_STAKE_TOP_CY, self.result.jackpot_bet, "chip_jackpot", "JACKPOT")

    # ------------------------------------------------------------------ settle
    def _record_stats(self, summary):
        gs = self.app.game_stats
        gs.record_bet(self.GAME_KEY, "ante", summary.ante_bet, summary.ante_return)
        gs.record_hand(self.GAME_KEY, hand_outcome_label(summary))
        if summary.fortune_bet > 0:
            gs.record_bet(self.GAME_KEY, "fortune", summary.fortune_bet, summary.fortune_return)
        if summary.jackpot_bet > 0:
            gs.record_bet(self.GAME_KEY, "jackpot", summary.jackpot_bet, summary.jackpot_return)

    def _on_round_settled(self):
        assert self.result is not None
        summary = self.result
        self._record_stats(summary)
        self.app.finance.add_return(summary.total_returned)
        self.app.finance.record_round_played(summary.net_result)
        self.app.game_stats.record_round_net(self.GAME_KEY, summary.net_result)
        if summary.jackpot_pool_won:
            self.app.jackpot.win()
        elif summary.jackpot_pool_partial_fraction is not None:
            self.app.jackpot.set_amount(self.app.jackpot.amount * (1 - summary.jackpot_pool_partial_fraction))
        self._refresh_balance()
        self.app.on_balance_changed()
        self.state = "resolved"
        self._show_result(summary)
        self._show_round_over_controls()

    def _show_result(self, summary):
        # No separate "Ante: Win/Lose +£X" line, and no separate "Round Net"
        # label beside the buttons -- both are already fully captured by
        # the ROUND RESULT panel's own Ante row and its own Round Net row.
        rows = [(f"Ante £{summary.ante_bet:.0f}", summary.ante_return - summary.ante_bet)]
        if summary.fortune_bet > 0:
            rows.append((f"Fortune £{summary.fortune_bet:.0f}", summary.fortune_return - summary.fortune_bet))
        if summary.jackpot_bet > 0:
            rows.append((f"Jackpot £{summary.jackpot_bet:.0f}", summary.jackpot_return - summary.jackpot_bet))

        front_name = summary.player_front_eval[1] if summary.player_front_eval else ""
        back_name = summary.player_back_eval[1] if summary.player_back_eval else ""
        front_win = bool(summary.player_front_eval and summary.dealer_front_eval
                          and compare_hands(summary.player_front_eval, summary.dealer_front_eval) > 0)
        back_win = bool(summary.player_back_eval and summary.dealer_back_eval
                         and compare_hands(summary.player_back_eval, summary.dealer_back_eval) > 0)
        fortune_hand_name = TIER_LABELS.get(summary.fortune_tier, "No qualifying hand") \
            if summary.fortune_tier else "No qualifying hand"
        hand_rows = [
            (f"Your Front: {front_name}", "WIN" if front_win else "LOSE", theme.WIN_COLOR if front_win else theme.LOSE_COLOR),
            (f"Your Back: {back_name}", "WIN" if back_win else "LOSE", theme.WIN_COLOR if back_win else theme.LOSE_COLOR),
            (f"Fortune Hand: {fortune_hand_name}", None, None),
        ]
        self._draw_round_result_panel(rows, summary.net_result, hand_rows)

    def _draw_round_result_panel(self, rows, net_result, hand_rows):
        """One unified "ROUND RESULT" panel -- same bordered-panel look and
        row format Three Card Poker's own round-result panel uses -- for
        both halves of the round summary: the Ante/Fortune/Jackpot payout
        breakdown + Round Net, AND (same row styling, just appended below a
        second divider rather than living in their own separately-styled
        block) the Your Front/Back/Fortune hand summary. `hand_rows` is a
        list of (label, right_text_or_None, right_color_or_None) -- the
        Fortune Hand row has no right-hand value, just its own left-aligned
        line."""
        canvas = self.payout_canvas
        canvas.delete("all")
        w, h = ROUND_RESULT_PANEL_W, ROUND_RESULT_PANEL_H
        felt_theme = self.app.settings.theme()
        theme.recessed_panel(canvas, 0, 0, w, h, title="ROUND RESULT",
                              fill=felt_theme["felt_dark"], outline=felt_theme["accent"])

        row_font = theme.font(9)
        row_font_bold = theme.font(9, weight="bold")
        row_h = 17
        y = 40
        for label, net in rows:
            canvas.create_text(22, y, text=label, fill=theme.FG, font=row_font, anchor="w")
            canvas.create_text(w - 22, y, text=_format_signed(net), fill=_net_color(net),
                                font=row_font_bold, anchor="e")
            y += row_h

        y += 5
        canvas.create_line(22, y, w - 22, y, fill=theme.BORDER)
        y += row_h
        canvas.create_text(22, y, text="Round Net", fill=theme.FG, font=theme.font(10, weight="bold"), anchor="w")
        canvas.create_text(w - 22, y, text=_format_signed(net_result), fill=_net_color(net_result),
                            font=theme.font(10, weight="bold"), anchor="e")
        y += row_h

        y += 5
        canvas.create_line(22, y, w - 22, y, fill=theme.BORDER)
        y += row_h
        for label, right_text, right_color in hand_rows:
            canvas.create_text(22, y, text=label, fill=theme.FG, font=row_font, anchor="w")
            if right_text is not None:
                canvas.create_text(w - 22, y, text=right_text, fill=right_color, font=row_font_bold, anchor="e")
            y += row_h

    def _new_deal(self):
        self._on_deal()

    def _new_round(self):
        self.state = "betting"
        self.result_lbl.configure(text="Place your ante to begin.", fg=theme.FG)
        self._sanitize_bets()
        self._show_betting_controls()

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
        "every stake's chips fly/sweep at the same time" (contrast
        _run_sequential, used for payouts settling one at a time)."""
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

    def _run_staggered(self, count, stagger_ms, fn):
        """Calls fn(i) for i in range(count), staggered by `stagger_ms` --
        or immediately back-to-back if animations are off, so a follow-up
        `self.after` delay timed against the animated case's total duration
        never races ahead of these."""
        if self.app.settings.get("animations_enabled"):
            for i in range(count):
                self.after(i * stagger_ms, fn, i)
        else:
            for i in range(count):
                fn(i)

    def _after_delay(self, ms, fn):
        """A plain standalone pause -- collapses to an immediate call when
        animations are off, same convention _animate/_run_staggered follow."""
        if self.app.settings.get("animations_enabled"):
            self.after(ms, fn)
        else:
            fn()

    # ------------------------------------------------------------------ theme / lifecycle
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
        # The paytable/jackpot panels aren't plain-bg widgets this walk can
        # catch -- they're canvas-drawn (or, for JackpotDisplay, built with
        # their own explicit panel_bg/border at construction time), so they
        # need their own refresh whenever the felt theme actually changes.
        # _show_result (not _draw_round_result_panel directly) is what Face
        # Up Pai Gow overrides, so redrawing through it here keeps this one
        # method correct for both games with no extra work.
        self.jackpot_display.retheme(felt_theme["felt_dark"], felt_theme["accent"])
        self._draw_paytable()
        if self.state == "resolved" and self.result is not None:
            self._show_result(self.result)

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
