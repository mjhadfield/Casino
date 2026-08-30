import math
import os
import tkinter as tk
from typing import Optional

from core.hand_evaluator import HAND_NAMES
from core.persistence import load_json, save_json
from games.three_card_poker.logic import (
    ANTE_BONUS_MULTIPLIERS,
    GAME_KEY,
    hand_outcome_label,
    JACKPOT_BET_AMOUNT,
    JACKPOT_ROYAL_NON_SPADES_PAYOUT,
    JACKPOT_STRAIGHT_FLUSH_PAYOUT,
    JACKPOT_STRAIGHT_PAYOUT,
    JACKPOT_THREE_OF_A_KIND_PAYOUT,
    PAIR_PLUS_MULTIPLIERS,
    PRIME_SAME_COLOUR_3_MULTIPLIER,
    PRIME_SAME_COLOUR_6_MULTIPLIER,
    RoundResult,
    should_play,
    ThreeCardPokerGame,
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

STATE_FILENAME = "three_card_poker_state.json"
DEFAULT_STATE = {"bets": {"ante": 0, "pair_plus": 0, "prime": 0, "jackpot": 0}, "selected_chip": 5}

# --- Layout constants ------------------------------------------------------
# The whole game area (table canvas + paytable) is built at these fixed pixel
# sizes and centred as one block in the window, rather than stretching to
# fill it -- see `_build_ui`. That also means a future "UI scale" setting can
# be added later just by multiplying this block of constants by a factor
# before building/drawing, without restructuring the layout itself.
#
# CHIP_DENOMINATIONS/CHIP_COLORS_BY_VALUE/CHIP_SIZE/CHIP_LAYER_MAX_R and the
# chip-drawing routines themselves now live in ui/chips.py -- shared with any
# other game (e.g. Blackjack) so chip colours/rendering can never drift
# between them. Re-imported above under their original names so nothing
# below has to change.
CANVAS_WIDTH = 760
# 366 (where the Ante circle ends -- see ANTE_STRIP_BOTTOM below) + 18px
# margin below it -- half the original 36px, so the result text/buttons
# right below the canvas sit closer to it.
CANVAS_HEIGHT = 384

PAYTABLE_WIDTH = 240
PAYTABLE_HEIGHT = 340
PAYOUT_PANEL_WIDTH = 380
PAYOUT_PANEL_HEIGHT = 220  # tall enough for the extra Jackpot row on top of the usual bets

# The jackpot side bet spot: a small circular token to the right of the Ante
# box, sized noticeably smaller than Ante/Pair Plus/Prime since it's always
# exactly £1 -- a flag to toggle, not a stack of chips to build up.
JACKPOT_SPOT_R = 32

# Fixed gap between the top bar and the table -- half of what plain vertical
# centring in the window used to leave there.
CONTENT_TOP_MARGIN = 35

# --- Betting-view-only spacing ----------------------------------------------
# Every value below is read only while the betting screen is showing (Deal
# button, chip tray) -- never touched during the dealt/resolved screens the
# same widgets are reused for, so none of this affects that screen's own
# layout. Derived empirically (measured widget positions on a real render)
# rather than from a formula, since the label/canvas geometry they're
# balancing around isn't itself expressed as simple constants.
#
# "Place your Ante bet to begin." sits in a fixed ~44px gap below the Ante
# box already (canvas's own bottom margin below where the Ante box happens
# to be drawn) -- action_frame's usual (8, 0) top pady is bumped closer to
# that on the Deal button's side too, so the label roughly centres between
# the Ante box and Deal rather than hugging the box with Deal close behind
# it. Pulled back in by ~15px from the exact balance point to bring Deal
# itself back up a little.
BETTING_ACTION_FRAME_PADY = (23, 0)

# The chip tray (chip_frame) floats centred inside its reserved chip_zone by
# default; this pady overrides that centring so the chip row itself (not the
# tray's outer box, which also includes the "tap a chip..." caption above it
# and the Total/Clear Bets below) sits at the midpoint between Deal and
# Clear Bets.
CHIP_FRAME_PADY = (16, 45)

# --- Rules button ------------------------------------------------------
# Sits to the left of the table, vertically centred on the Ante box and
# horizontally halfway between the Ante box's left edge and the canvas's
# own left edge -- see _draw_rules_button, called from _draw_table (betting
# only, so it never appears once a hand's been dealt).
RULES_BUTTON_WIDTH = 106   # 92 * 1.15
RULES_BUTTON_HEIGHT = 54   # taller than a first pass at this -- more air
                            # around the ♠ icon and the "RULES" text below it
RULES_BUTTON_RADIUS = RULES_BUTTON_HEIGHT // 2  # a full stadium/pill shape --
                                                 # evenly rounded all the way
                                                 # round, not just at the corners

# --- Card-view (post-Deal) geometry ----------------------------------------
# Top to bottom: the dealer's cards, then a compact strip of bet indicators
# -- Play stacked above Ante (Play gets top billing: it's the bet the player
# is actively choosing to make, sized generously so the played hand stays
# legible under its chips), with Pair Plus/Prime/Jackpot off to the sides --
# both live on the main `canvas`. The result text, Play/Fold buttons, and
# *then* the player's fanned hand follow below it as separate widgets (the
# hand sits in its own small `fan_canvas`, shown only while there's an
# actual fan to show -- see _on_deal/_on_round_settled) -- so the cards the
# player is actually deciding about sit right under the buttons that decide
# their fate, not above them. Choosing Play or folding onto Prime/Pair Plus
# then visibly moves the hand *up* onto the strip -- a single continuous
# slide isn't possible between the two separate canvases, so it's actually
# two animations (shrink away, then grow back in) timed to read as one --
# see _animate_to_rest.
CARD_ROW_GAP = CARD_WIDTH + 15
CARD_ROW_WIDTH = 2 * CARD_ROW_GAP + CARD_WIDTH
CARD_ROW_START_X = CANVAS_WIDTH / 2 - CARD_ROW_WIDTH / 2

# Dealer mat: a rounded-rectangle felt behind the dealer's row, the same
# "printed felt" language the bet strip below uses -- drawn first so the
# card spots/cards themselves sit on top of it. Margins are kept well clear
# of the corner radius so a card is never clipped by the rounding.
DEALER_MAT_RADIUS = 14
DEALER_MAT_TOP = 10
DEALER_MAT_LABEL_Y = DEALER_MAT_TOP + 9
DEALER_Y = DEALER_MAT_TOP + 24                   # dealer cards' top-left y
DEALER_MAT_BOTTOM = DEALER_Y + CARD_HEIGHT + 20
DEALER_MAT_SIDE_MARGIN = 40
DEALER_MAT_X1 = CARD_ROW_START_X - DEALER_MAT_SIDE_MARGIN
DEALER_MAT_X2 = CARD_ROW_START_X + CARD_ROW_WIDTH + DEALER_MAT_SIDE_MARGIN

# Bet indicator strip -- a deliberately larger gap below the dealer mat than
# any other gap in this view, so the dealer's area and the player's clearly
# read as two separate zones. Play sits on top (bigger, sized for the played
# hand's cards); Ante is a circle directly below it, on the shared
# centreline, the same size as Pair Plus/Prime/Jackpot rather than a
# separate small box -- so its chip stack isn't stuck at a noticeably
# smaller scale than the side bets sitting right next to it.
GAP_DEALER_TO_STRIP = 34
STRIP_TOP = DEALER_MAT_BOTTOM + GAP_DEALER_TO_STRIP
STACK_CX = CANVAS_WIDTH / 2

PLAY_BOX_W = 182   # 140 * 1.3
PLAY_BOX_H = 94    # 72 * 1.3
# Big enough that Ante's label (drawn above its circle, like Pair Plus/
# Prime/Jackpot) clears the Play box's bottom edge with a bit of daylight,
# not just clears it -- a plain gap wouldn't need to be this wide, but the
# label eats into it from below.
STACK_GAP = 24

PLAY_BOX_TOP = STRIP_TOP
PLAY_BOX_BOTTOM = PLAY_BOX_TOP + PLAY_BOX_H
PLAY_BOX_CY = (PLAY_BOX_TOP + PLAY_BOX_BOTTOM) / 2

ANTE_STRIP_R = 30  # matches PAIR_PLUS_STRIP_R/PRIME_STRIP_R below
ANTE_STRIP_CY = PLAY_BOX_BOTTOM + STACK_GAP + ANTE_STRIP_R
ANTE_STRIP_BOTTOM = ANTE_STRIP_CY + ANTE_STRIP_R

PAIR_PLUS_STRIP_CX = 233
PAIR_PLUS_STRIP_R = 30
PRIME_STRIP_CX = 527
PRIME_STRIP_R = 30
JACKPOT_STRIP_CX = 603
JACKPOT_STRIP_R = 22

# Payout animation (see _animate_payouts): after the dealer's cards are
# revealed, a lost bet's chips slide to the dealer's centre and a won bet's
# extra chips slide out from it -- "the dealer's centre" is simply the
# midpoint of their own card row.
DEALER_CENTER_X = CANVAS_WIDTH / 2
DEALER_CENTER_Y = DEALER_Y + CARD_HEIGHT / 2

# A winning bet's payout lands a little above its spot's existing stake
# stack rather than directly on it, so it visibly reads as an addition to
# what's already there instead of just replacing it.
PAYOUT_WIN_LANDING_OFFSET_X = 20
PAYOUT_WIN_LANDING_OFFSET_Y = 20

# fan_canvas: the player's own small canvas, below the Play/Fold buttons --
# overlapping, with the outer two cards riding slightly lower than the
# middle one, like a hand of cards held with a gentle arc.
FAN_Y = 14   # top margin within fan_canvas, not the shared canvas above
FAN_GAP = 46
FAN_ARC_OFFSET = 8
FAN_CANVAS_HEIGHT = FAN_Y + CARD_HEIGHT + FAN_ARC_OFFSET + 14

# The player's own felt mat, behind the fanned hand in fan_canvas -- same
# rounded-rectangle language as the dealer's mat (and the same width, so
# the two line up), but a distinct, neutral border colour rather than the
# felt's own accent, so the dealer's and the player's areas read as clearly
# different zones despite sharing the same felt/rounded-rect styling.
FAN_MAT_X1 = DEALER_MAT_X1
FAN_MAT_X2 = DEALER_MAT_X2
FAN_MAT_TOP = 4
FAN_MAT_BOTTOM = FAN_CANVAS_HEIGHT - 4
FAN_MAT_RADIUS = 12
FAN_MAT_BORDER = theme.FG_DIM

# Cards that come to rest on a bet-indicator spot -- the played hand landing
# on Play, or a folded hand resting on Prime/Pair Plus to show there's still
# something to collect -- are drawn at this reduced scale: big enough to
# read, small enough to fit on the same spot the chips already sit on.
REST_CARD_SCALE = 0.55
REST_CARD_WIDTH = CARD_WIDTH * REST_CARD_SCALE
REST_CARD_HEIGHT = CARD_HEIGHT * REST_CARD_SCALE
REST_CARD_FAN_OFFSET = 30  # horizontal spread of the 3 resting cards -- wide
                            # enough that the middle card's own index isn't
                            # fully swallowed by the outer two plus the chips

# The played hand gets its own, bigger scale -- the Play box has plenty of
# room to spare (see PLAY_BOX_W/H above), so its cards fill more of it
# instead of sitting at the same modest size the smaller Prime/Pair Plus
# fold spots need.
PLAY_REST_CARD_SCALE = 0.75
PLAY_REST_CARD_WIDTH = CARD_WIDTH * PLAY_REST_CARD_SCALE
PLAY_REST_CARD_HEIGHT = CARD_HEIGHT * PLAY_REST_CARD_SCALE
PLAY_REST_CARD_FAN_OFFSET = 34

# Play's own pacing for _settle_played_hand -- half a second slower overall
# than _animate_to_rest's Fold-preserving defaults (150ms/200ms, split
# evenly: +250ms to each of the vanish-from-the-fan and grow-in-at-Play
# phases that together read as one continuous "card to the Play box" slide),
# plus its own half-second pause once the cards have landed before the Play
# bet's chips are placed on top of them.
PLAY_SETTLE_VANISH_MS = 400
PLAY_SETTLE_GROW_MS = 450
PLAY_CHIP_DELAY_MS = 500

# Dealer reveal: a pause once the Play chips have landed before the first
# card flips face up, then the same half-second beat between each of the 3
# cards (_run_staggered's own stagger, not each flip's own -- brisker --
# 200ms flip duration). Payout starts the instant the last card lands, no
# extra pause of its own.
DEALER_REVEAL_START_DELAY_MS = 500
DEALER_REVEAL_STAGGER_MS = 500

# Each payout chip's own travel animation (_chip_move_away/_chip_move_in) --
# half of the previous (already-slowed) 560ms, to speed the payout back up.
PAYOUT_CHIP_MOVE_MS = 280


def _ease_out_cubic(t):
    return 1 - (1 - t) ** 3




# Used to animate the jackpot glow/sheen by brightness rather than by
# resizing shapes -- see ui/theme.py for the implementation, the natural
# home for a color-math primitive shared with theme.py's own dim-tint blends.
_lerp_color = theme.lerp_color


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

# Rows for the jackpot meter's own mini paytable -- read from the same
# constants logic.py actually pays out, so it can't drift out of sync.
JACKPOT_PAYTABLE_ROWS = [
    ("Straight", f"£{JACKPOT_STRAIGHT_PAYOUT:.0f}"),
    ("Three of a Kind", f"£{JACKPOT_THREE_OF_A_KIND_PAYOUT:.0f}"),
    ("Straight Flush", f"£{JACKPOT_STRAIGHT_FLUSH_PAYOUT:.0f}"),
    ("Royal Flush (non-♠)", f"£{JACKPOT_ROYAL_NON_SPADES_PAYOUT:.0f}"),
    ("Royal Flush (♠)", "100% JACKPOT"),
]
JACKPOT_PAYTABLE_HIGHLIGHT_ROW = len(JACKPOT_PAYTABLE_ROWS) - 1  # the spades Royal Flush


def _max_round_cost(bets):
    """Worst-case total the player could end up committing this round: the
    upfront wager plus a Play bet equal to the Ante if they choose to play
    (the Play bet always matches the Ante -- see ThreeCardPokerGame.resolve).
    A real casino would never let you place an Ante you couldn't back up with
    a matching Play bet, so bet placement is checked against this, not just
    the upfront total. The jackpot side bet is flat, like Pair Plus/Prime --
    never doubled by a Play bet."""
    return bets["ante"] * 2 + bets["pair_plus"] + bets["prime"] + bets["jackpot"]


def _format_signed(amount):
    """£6 as +£6, -£6, or £0. Every ordinary bet/payout here is a whole
    number, but a jackpot win pays out the meter's exact pence value, so this
    also handles fractional, comma-grouped amounts (e.g. +£17,432.87)."""
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


class ThreeCardPokerFrame(tk.Frame):
    def __init__(self, parent, app):
        # Overwritten a few lines later by _build_ui's self.configure(bg=
        # theme["felt"]) once self.app is set -- theme.BG here is just a
        # harmless placeholder for the instant before that happens.
        super().__init__(parent, bg=theme.BG)
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
            "jackpot": int(saved_bets.get("jackpot", 0)),
        }
        self.selected_chip = int(saved.get("selected_chip", DEFAULT_STATE["selected_chip"]))
        self._sanitize_bets(persist=False)

        self.chip_canvases = {}  # value -> (canvas, face colour, rim colour)
        self._jackpot_pulse_t = 0.0  # phase for the jackpot spot's breathing glow, once a bet's placed
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

        # Top bar is NOT felt-scoped -- it's this app's global chrome, so it
        # always uses the one fixed terminal accent regardless of which
        # table felt is selected (see ui/theme.py's module docstring).
        top_bar = tk.Frame(self, bg=theme.BG_ELEVATED)
        top_bar.pack(fill="x")
        tk.Button(
            top_bar, text="← Menu", bg=theme.BG_ELEVATED, fg=theme.FG_DIM, relief="flat",
            font=theme.font(11), padx=12, pady=6, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.BORDER, highlightcolor=theme.ACCENT,
            command=lambda: self.app.show_frame("menu"),
        ).pack(side="left", padx=(20, 10), pady=10)
        tk.Label(top_bar, text="Three Card Poker", bg=theme.BG_ELEVATED, fg=theme.ACCENT,
                 font=theme.font(16, weight="bold")).pack(side="left", padx=10)
        self.balance_lbl = tk.Label(top_bar, text="£0.00", bg=theme.BG_ELEVATED, fg=theme.WIN_COLOR,
                                     font=theme.font(12, weight="bold"))
        self.balance_lbl.pack(side="right", padx=20)
        theme.breadcrumb(top_bar, "three_card_poker", bg=theme.BG_ELEVATED,
                          player=self.app.current_player["name"]).pack(side="right", padx=(6, 6))

        # `body` is the full-window stage; `content` is the actual UI at its
        # fixed base size, centred horizontally within it as one block rather
        # than stretching -- so resizing the window never changes the table's
        # own proportions or shifts the table and paytable apart. Anchored to
        # a fixed offset from the top (not vertically centred) so any extra
        # window height becomes slack at the bottom instead of pushing the
        # whole table down and leaving a big gap under the top bar.
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
        self.canvas.pack(padx=12, pady=(10, 4))

        self.result_lbl = tk.Label(
            game_col, text="Place your Ante bet to begin.", bg=felt_theme["felt"], fg=theme.FG,
            font=theme.font(13, weight="bold"), wraplength=900, justify="center",
        )
        self.result_lbl.pack(pady=(0, 6))

        # --- action buttons (contents swapped by state) -- sits right under the
        # instructions text, with only a small, constant gap: Deal, Play+Fold and
        # New Deal+Change Bets are all single-row layouts of the same height, so
        # this needs no space reservation of its own to stay put between states.
        self.action_frame = tk.Frame(game_col, bg=felt_theme["felt"])
        self.action_frame.pack(pady=(8, 0))

        self.deal_btn = tk.Button(
            self.action_frame, text="DEAL", bg=theme.ACCENT_DIM_BG, fg=theme.FG,
            font=theme.font(13, weight="bold"), relief="flat", padx=30, pady=10, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.ACCENT,
            command=self._on_deal,
        )
        self.play_btn = tk.Button(
            self.action_frame, text="PLAY", bg=theme.ACCENT_DIM_BG, fg=theme.FG,
            font=theme.font(13, weight="bold"), relief="flat", padx=30, pady=10, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.ACCENT,
            command=lambda: self._finish_round(folded=False),
        )
        self.fold_btn = tk.Button(
            self.action_frame, text="FOLD", bg=theme.LOSE_DIM_BG, fg=theme.FG,
            font=theme.font(13, weight="bold"), relief="flat", padx=30, pady=10, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.LOSE_COLOR,
            command=lambda: self._finish_round(folded=True),
        )
        # Round-over controls: a quick rebet (same bets, dealt immediately)
        # is the common case, so it gets the primary accent styling; Change
        # Bets -- back to the betting screen -- is the secondary option.
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

        # The player's fanned hand -- its own small canvas below the
        # Play/Fold buttons (see the module docstring above), rather than
        # part of the main canvas above them. Only packed while there's an
        # actual fan to show -- shown in _on_deal, hidden again in
        # _on_round_settled -- so it takes up no space (and leaves no gap)
        # once the hand's moved onto the strip and this is empty again.
        self.fan_canvas = tk.Canvas(game_col, bg=felt_theme["felt"], highlightthickness=0,
                                     width=CANVAS_WIDTH, height=FAN_CANVAS_HEIGHT)

        # --- below that: chip tray (betting) or the round result (resolved)
        # -- never both, so they share one reserved zone. `chip_zone` stays
        # packed (and its footprint reserved) in every state even though its
        # contents are state-specific -- so switching between them never
        # changes `content`'s overall size. `content` is centred as a block, so
        # an actual size change there would re-centre (and shift) everything,
        # undoing the Deal <-> Play/Fold alignment -- but because the reserved
        # space sits below the buttons rather than between them and the
        # instructions, there's no visible gap where it matters.
        self.chip_zone = tk.Frame(game_col, bg=felt_theme["felt"])
        self.chip_zone.pack(pady=(10, 0))

        # Chip tray: pick a denomination, then tap a betting spot on the table.
        # Total bet and Clear Bets are grouped into it too.
        self.chip_frame = tk.Frame(self.chip_zone, bg=felt_theme["felt"])
        tk.Label(
            self.chip_frame, text="Tap a chip, then tap Ante / Pair Plus / Prime to place it",
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

        # Round result: shown once a round resolves, in place of the chip tray.
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
        # No expand=True: paytable_col fills the game column's full height
        # (which varies by state -- e.g. fan_canvas showing/hiding), and
        # expand=True would centre the paytable in whatever slack that
        # leaves, drifting it up and down between states. Packed plainly, it
        # just sits at its natural size right below the jackpot display,
        # unaffected by how tall the game column happens to be.
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
        for label, multiplier in rows:
            canvas.create_text(20, y, text=label, fill=theme.FG, font=theme.font(9), anchor="w")
            canvas.create_text(w - 20, y, text=f"{multiplier}:1", fill=accent,
                                font=theme.font(9, weight="bold"), anchor="e")
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
        self._draw_spot_rect("ante", ante_cx, ante_cy, ante_w, ante_h, "ANTE", textured=True)

        jp_cx = ante_cx + ante_w / 2 + 55 + JACKPOT_SPOT_R
        self._draw_spot_jackpot(jp_cx, ante_cy, JACKPOT_SPOT_R)

        # Halfway between the Ante box's left edge and the canvas's own left
        # edge, vertically centred on the Ante box.
        ante_left = ante_cx - ante_w / 2
        self._draw_rules_button(ante_left / 2, ante_cy)

    def _draw_rules_button(self, cx, cy):
        tag = "rules_button"
        felt_theme = self.app.settings.theme()
        x1, y1 = cx - RULES_BUTTON_WIDTH / 2, cy - RULES_BUTTON_HEIGHT / 2
        x2, y2 = cx + RULES_BUTTON_WIDTH / 2, cy + RULES_BUTTON_HEIGHT / 2
        self._draw_rounded_rect(self.canvas, x1, y1, x2, y2, radius=RULES_BUTTON_RADIUS,
                                 fill=felt_theme["felt_dark"], outline=felt_theme["accent"],
                                 width=2, tags=(tag,))
        self.canvas.create_text(cx, cy - 12, text="♠", fill=felt_theme["accent"],
                                 font=theme.font(15, weight="bold"), tags=(tag,))
        self.canvas.create_text(cx, cy + 10, text="RULES", fill=theme.FG,
                                 font=theme.font(9, weight="bold"), tags=(tag,))
        self.canvas.tag_bind(tag, "<Button-1>", lambda _e: self._show_rules())
        self.canvas.tag_bind(tag, "<Enter>", lambda _e: self.canvas.configure(cursor="hand2"))
        self.canvas.tag_bind(tag, "<Leave>", lambda _e: self.canvas.configure(cursor=""))

    def _show_rules(self):
        dialogs.document(
            self, "♠ Three Card Poker -- Rules",
            [
                ("GAMEPLAY", [
                    "**Betting:** Players place an Ante (mandatory) plus Pair Plus, Prime, "
                    "and Jackpot side bets (optional).",
                    "**Dealing:** The dealer deals three cards face-down to the player and to themselves.",
                    "**Decision:** Players must choose to Fold (forfeiting the Ante) or Play "
                    "(placing a Play bet equal to the Ante).",
                    "**Resolution:** If the dealer does not qualify (has less than Queen-high), "
                    "the Ante bet pays 1:1 and the Play bet pushes.",
                    "**Resolution:** If the dealer qualifies, hands are compared. A winning player "
                    "hand pays 1:1 on both Ante and Play bets; a losing hand loses both. "
                    "Ties result in a push.",
                ]),
                ("HAND RANKINGS", [
                    ("High Card", [("Q", "h"), ("6", "s"), ("4", "d")]),
                    ("Pair", [("8", "h"), ("8", "d"), ("3", "c")]),
                    ("Flush", [("2", "c"), ("7", "c"), ("J", "c")]),
                    ("Straight", [("5", "h"), ("6", "d"), ("7", "s")]),
                    ("Three of a Kind", [("9", "h"), ("9", "d"), ("9", "c")]),
                    ("Straight Flush", [("7", "d"), ("8", "d"), ("9", "d")]),
                ]),
                ("OPTIMAL PLAY",
                 "Play with **Q-6-4** or better, fold all other hands. The Prime bonus is "
                 "claimed when folded."),
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
            self._draw_chip_stack(tag, cx, cy, amount, max_r=CHIP_LAYER_MAX_R)
        else:
            self.canvas.create_text(cx, cy, text="tap to bet", fill=theme.FG_DIM,
                                     font=theme.font(9, weight="bold"), tags=(tag,))
        self._bind_spot(tag, key)

    def _draw_spot_rect(self, key, cx, cy, width, height, label, textured=False):
        tag = f"spot_{key}"
        amount = self.bets[key]
        felt_theme = self.app.settings.theme()
        x1, y1, x2, y2 = cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2
        # Rounded, matching the dealer mat / fan mat / post-deal Play spot --
        # was a plain right-angled rectangle, the one square shape left on
        # the betting screen.
        self._draw_rounded_rect(self.canvas, x1, y1, x2, y2, radius=10, fill=felt_theme["felt_dark"],
                                 outline=felt_theme["accent"], width=2, tags=(tag,))
        if textured:
            self._draw_felt_texture(x1, y1, x2, y2, felt_theme, tag)
        self.canvas.create_text(cx, y1 + 18, text=label, fill=theme.FG,
                                 font=theme.font(11, weight="bold"), tags=(tag,))
        stack_cy = cy + 16
        if amount:
            self._draw_chip_stack(tag, cx, stack_cy, amount, max_r=CHIP_LAYER_MAX_R)
        else:
            self.canvas.create_text(cx, stack_cy, text="tap to bet", fill=theme.FG_DIM,
                                     font=theme.font(10, weight="bold"), tags=(tag,))
        self._bind_spot(tag, key)

    def _draw_felt_texture(self, x1, y1, x2, y2, felt_theme, tag):
        """A faint diagonal hatch drawn over a spot's flat fill -- just the
        Ante box for now (see textured= in _draw_spot_rect), so it doesn't
        read as a completely flat cutout the way the plain betting circles
        do. Lines are inset from the edges since a Canvas has no true
        clipping to keep them off the rounded corners drawn under them."""
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
        """The £1 jackpot side bet: an on/off spot rather than a chip stack
        (it's always exactly £1, never stacked higher). Placed, its ring
        breathes -- a smooth, continuous fade in brightness between the
        felt's own accent and its dimmer felt_dark, driven by
        _pulse_jackpot -- rather than the old neon-glow halo (too gaudy)
        or a hard on/off blink (tried it, too abrupt). The chip itself
        stays the same blue as every other £1 chip in the tray."""
        tag = "spot_jackpot"
        felt_theme = self.app.settings.theme()
        placed = bool(self.bets["jackpot"])
        if placed:
            t = 0.5 + 0.5 * math.sin(self._jackpot_pulse_t)  # 0 -> 1 -> 0, one slow breath
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

    def _draw_chip_stack(self, tag, cx, cy, amount, max_r):
        """Thin delegate to ui/chips.py's shared draw_chip_stack, bound to
        this screen's own canvas -- kept as a same-named method so every
        call site elsewhere in this file (there are several) doesn't need
        to change."""
        draw_chip_stack(self.canvas, tag, cx, cy, amount, max_r)

    def _bind_spot(self, tag, key):
        if tag in self._bound_spot_tags:
            return
        self._bound_spot_tags.add(tag)
        self.canvas.tag_bind(tag, "<Button-1>", lambda e, k=key: self._on_place_chip(k))
        self.canvas.tag_bind(tag, "<Enter>", lambda e: self.canvas.configure(cursor="hand2"))
        self.canvas.tag_bind(tag, "<Leave>", lambda e: self.canvas.configure(cursor=""))

    # ------------------------------------------------------------------ jackpot meter / glow
    def _on_jackpot_changed(self, raw_amount):
        """Registered on the shared JackpotManager -- fires on every tick (and
        on any manual change), so the meter stays live no matter which screen
        is showing when the jackpot grows."""
        self.jackpot_display.set_value(raw_amount)

    def _pulse_jackpot(self):
        """Keeps the jackpot spot's ring smoothly breathing (brightness
        fading in and out between the felt's accent and its dimmer
        felt_dark) while a bet's placed on it. Self-perpetuating for the
        frame's whole lifetime (like JackpotManager's own tick loop) --
        cheap enough that it's not worth starting/stopping around
        visibility, and redrawing the whole table is safe here since
        nothing else animates during betting. Runs at ~30fps (the same
        cadence as _animate) so the breathing reads as smooth rather than a
        visible step between frames -- more redraw overhead than the
        earlier hard blink, but reads far better."""
        if self.state == "betting" and self.bets.get("jackpot"):
            self._jackpot_pulse_t += 0.06
            self._draw_table()
        self.after(33, self._pulse_jackpot)

    # ------------------------------------------------------------------ state transitions
    def _show_betting_controls(self):
        for w in self.action_frame.pack_slaves():
            w.pack_forget()
        self.deal_btn.pack()
        # Betting-screen-only spacing (see BETTING_ACTION_FRAME_PADY) -- every
        # other state restores the ordinary (8, 0) below, so this never
        # touches the dealt/resolved screens' own Play/Fold or New Deal
        # spacing.
        self.action_frame.pack(pady=BETTING_ACTION_FRAME_PADY)
        self.payout_canvas.pack_forget()
        self.chip_frame.pack(pady=CHIP_FRAME_PADY)
        self._draw_table()
        self._update_total()

    def _show_decision_controls(self):
        self.chip_frame.pack_forget()
        self.payout_canvas.pack_forget()
        for w in self.action_frame.pack_slaves():
            w.pack_forget()
        self.action_frame.pack(pady=(8, 0))
        self.play_btn.pack(side="left", padx=8)
        self.fold_btn.pack(side="left", padx=8)

    def _show_round_over_controls(self):
        self.chip_frame.pack_forget()
        for w in self.action_frame.pack_slaves():
            w.pack_forget()
        self.action_frame.pack(pady=(8, 0))
        self.new_deal_btn.pack(side="left", padx=8)
        self.change_bets_btn.pack(side="left", padx=8)

    def _show_no_controls(self):
        """No action buttons visible -- used during the brief pause/animation
        between Deal and the cards actually landing, and between Play/Fold
        and the dealer's reveal, so nothing can be clicked mid-animation."""
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
        """The jackpot spot is on/off, not a stack -- tapping it places or
        removes exactly the one £1 bet, regardless of the selected chip."""
        trial_bets = dict(self.bets)
        trial_bets["jackpot"] = 0 if self.bets["jackpot"] else int(JACKPOT_BET_AMOUNT)
        if trial_bets["jackpot"] and _max_round_cost(trial_bets) > self.app.finance.balance + 1e-9:
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
        if _max_round_cost(trial_bets) > balance + 1e-9:
            upfront = trial_bets["ante"] + trial_bets["pair_plus"] + trial_bets["prime"] + trial_bets["jackpot"]
            if upfront <= balance + 1e-9:
                # They could afford to place it, just not to also match it with
                # a Play bet later -- a casino wouldn't let you place an Ante
                # you can't back up.
                dialogs.info(
                    self, "$ ante --check-funds",
                    "You wouldn't have enough left to match this Ante with a Play bet "
                    "if you choose to play. Reduce your bet or add funds.",
                    accent=theme.WARN,
                )
            else:
                dialogs.info(
                    self, "$ bet --check-funds", "You don't have enough balance to place that chip.",
                    accent=theme.WARN,
                )
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
            self.bets = {"ante": 0, "pair_plus": 0, "prime": 0, "jackpot": 0}
            if persist:
                self._persist_state()

    # ------------------------------------------------------------------ round flow
    def _on_deal(self):
        ante, pair_plus, prime, jackpot = (
            self.bets["ante"], self.bets["pair_plus"], self.bets["prime"], self.bets["jackpot"],
        )
        if ante <= 0:
            dialogs.info(self, "$ deal --require-ante", "You must place an Ante bet to deal.", accent=theme.WARN)
            return

        # Checked against the worst case (this wager plus a matching Play bet),
        # not just the upfront total -- _adjust_bet already enforces this on
        # every chip placement, so this is a defensive re-check, not the
        # primary guard (see _adjust_bet and _sanitize_bets).
        if not self.app.finance.can_afford(_max_round_cost(self.bets)):
            choice = dialogs.choice(
                self, "$ deal --check-funds",
                "You don't have enough balance to cover these bets plus a matching Play bet.",
                [("Go Home", "home"), ("Cashier", "cashier")],
            )
            if choice == "home":
                self.app.show_frame("menu")
            elif choice == "cashier":
                self.app.show_frame("finances")
            return

        total_upfront = ante + pair_plus + prime + jackpot
        self.app.finance.place_wager(total_upfront)
        self._refresh_balance()

        self.result = self.game.play_round(ante, pair_plus, prime, jackpot)
        self.state = "dealt"

        self.result_lbl.configure(text="Dealing...", fg=theme.FG)
        self._show_no_controls()

        # Shown fresh for this round -- hidden again once resolved (see
        # _on_round_settled), so it only ever takes up space (right below
        # the Play/Fold buttons) while there's an actual hand in it.
        self.fan_canvas.delete("all")
        self.fan_canvas.pack(pady=(14, 0), before=self.chip_zone)
        self._draw_fan_mat()

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
                dialogs.info(
                    self, "$ play --check-funds",
                    "You don't have enough balance to match the Play bet. Folding instead.",
                    accent=theme.WARN,
                )
                folded = True
            else:
                self.app.finance.place_wager(play_bet)

        result = self.game.resolve(folded, jackpot_amount=self.app.jackpot.amount)
        # resolve() always populates player_eval before returning (see its
        # own assert in logic.py) -- re-asserted here since that narrowing
        # doesn't carry across the function boundary.
        assert result.player_eval is not None
        if result.total_returned > 0:
            self.app.finance.add_return(result.total_returned)
        self.app.finance.record_round_played(result.net_result)
        self.app.game_stats.record_round_net(GAME_KEY, result.net_result)
        for key, bet, ret in self._resolved_bet_totals(result):
            self.app.game_stats.record_bet(GAME_KEY, key, bet, ret)
        self.app.game_stats.record_hand(GAME_KEY, hand_outcome_label(result.player_eval, result.folded))
        # Statistically correct Play/Fold decision: play Q-6-4 or better,
        # fold anything worse (see should_play) -- correct iff that verdict
        # matches whether the player actually played or folded.
        decision_correct = should_play(result.player_eval) != result.folded
        self.app.game_stats.record_strategy_decision(GAME_KEY, result.folded, decision_correct)
        if result.jackpot_won:
            self.app.jackpot.win()  # resets it to its floor -- see JackpotManager.win
        # The balance itself is credited right here (above) so it's correct
        # immediately no matter what happens next -- but the *display* of it
        # (both this screen's own top-bar figure and the Cashier's) is
        # deliberately held back until _on_round_settled, once the payout
        # chip animation has actually finished and the ROUND RESULT panel is
        # showing, rather than jumping to the new total while the chips are
        # still visibly sliding around.

        self._show_no_controls()
        on_settled = lambda: self._reveal_dealer(result)
        if folded:
            self._settle_folded_hand(on_settled)
        else:
            self._settle_played_hand(on_settled)

    def _new_deal(self):
        """New Deal: skips the betting screen entirely and deals again
        straight away with the same bets as last round -- _on_deal() reads
        straight from self.bets, which round-over never clears, and does
        its own affordability check. The last round's chips have been
        sitting in place on the strip since payout (see _animate_payouts) --
        swept away here, right as the new hand is about to be dealt, rather
        than the moment the previous round resolved."""
        assert self.result is not None, "_new_deal called before a round was ever dealt"
        if not self.app.finance.can_afford(_max_round_cost(self.bets)):
            # Mirrors _on_deal's own affordability check -- checked here too,
            # before touching the controls, so a balance too low to rebet
            # just shows the warning and leaves New Deal/Change Bets exactly
            # as they were rather than hiding them for a sweep that's about
            # to be aborted anyway (_on_deal would hit this same check and
            # bail, but only after the controls were already hidden).
            self._on_deal()
            return
        self._show_no_controls()
        self._sweep_remaining_chips(self._payout_chip_items(self.result), self._on_deal)

    def _new_round(self):
        """Change Bets: back to the betting screen to adjust before dealing
        again. Bets carry over so it's a starting point, not a blank slate --
        Clear Bets is there if they want £0 instead."""
        self.state = "betting"
        self.result_lbl.configure(text="Place your Ante bet to begin.", fg=theme.FG)
        self._sanitize_bets()
        self._show_betting_controls()

    # ------------------------------------------------------------------ card-view rendering
    def _draw_card_zones(self):
        """Draws the static post-Deal background for one round: a rounded-
        rectangle felt mat behind the dealer's row (drawn first, so the
        dealer's card spots/cards sit on top of it) and the bet-indicator
        strip below it (see _draw_bet_strip) -- Ante, Play, and whichever of
        Pair Plus/Prime/Jackpot are actually in play, so the active bonus
        bets stay visible for the whole hand instead of vanishing the
        moment betting ends. Individual cards are separate, tagged canvas
        items drawn/animated on top of this background."""
        self.canvas.delete("all")
        felt_theme = self.app.settings.theme()
        self._draw_rounded_rect(
            self.canvas, DEALER_MAT_X1, DEALER_MAT_TOP, DEALER_MAT_X2, DEALER_MAT_BOTTOM, radius=DEALER_MAT_RADIUS,
            fill=felt_theme["felt_dark"], outline=felt_theme["accent"], width=2, tags=("zone_bg",),
        )
        self.canvas.create_text(CANVAS_WIDTH / 2, DEALER_MAT_LABEL_Y, text="DEALER", fill=theme.ACCENT,
                                 font=theme.font(9, weight="bold"), tags=("zone_bg",))
        self._draw_bet_strip()

    def _draw_bet_strip(self):
        """The bet-indicator strip between the dealer's mat and the
        player's fan: Play on top (Play starts empty -- an outline printed
        on the felt, like a real table's permanent Play spot, until Play is
        chosen), Ante directly below it as a circle the same size as Pair
        Plus/Prime/Jackpot (which flank the pair, only if actually
        wagered). Drawn once, right after dealing -- cards+chips are added
        to individual spots afterwards (see _settle_played_hand/
        _settle_folded_hand) rather than redrawing the whole strip, so
        those additions can layer on top in the right order."""
        self._draw_strip_rect("play", PLAY_BOX_TOP, PLAY_BOX_W, PLAY_BOX_H, "PLAY")
        self._draw_strip_circle("ante", STACK_CX, ANTE_STRIP_CY, ANTE_STRIP_R, "ANTE")
        if self.bets["pair_plus"]:
            self._draw_strip_circle("pair_plus", PAIR_PLUS_STRIP_CX, PLAY_BOX_CY, PAIR_PLUS_STRIP_R, "PAIR PLUS")
        if self.bets["prime"]:
            self._draw_strip_circle("prime", PRIME_STRIP_CX, PLAY_BOX_CY, PRIME_STRIP_R, "PRIME")
        if self.bets["jackpot"]:
            self._draw_strip_circle("jackpot", JACKPOT_STRIP_CX, PLAY_BOX_CY, JACKPOT_STRIP_R, "JACKPOT")

    def _draw_strip_rect(self, key, top, w, h, label):
        """The Play spot, centred on STACK_CX -- "play" isn't a real bet
        key, so its chip stack is always 0 here, drawn as an empty outline
        until the played hand's chips are added separately once Play is
        chosen. Its label sits dead centre, the same point the played
        hand's cards land on and the chips on top of them -- it's meant to
        end up covered, the way a printed felt spot does once something's
        placed on it."""
        tag = f"strip_{key}"
        self.canvas.delete(tag)
        felt_theme = self.app.settings.theme()
        amount = self.bets.get(key, 0)
        x1, y1, x2, y2 = STACK_CX - w / 2, top, STACK_CX + w / 2, top + h
        self._draw_rounded_rect(self.canvas, x1, y1, x2, y2, radius=10, fill=felt_theme["felt_dark"],
                                 outline=felt_theme["accent"], width=2, tags=(tag,))
        cy = (y1 + y2) / 2
        self.canvas.create_text(STACK_CX, cy, text=label, fill=theme.FG,
                                 font=theme.font(9, weight="bold"), tags=(tag,))
        if amount:
            self._draw_chip_stack(tag, STACK_CX, cy, amount, max_r=20)

    def _draw_strip_circle(self, key, cx, cy, r, label):
        """One circular strip spot -- Ante (always) or Pair Plus/Prime/
        Jackpot (only when actually wagered, see _draw_bet_strip) -- all
        the same size, so none of their chip stacks reads as smaller than
        the others."""
        tag = f"strip_{key}"
        self.canvas.delete(tag)
        felt_theme = self.app.settings.theme()
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=felt_theme["felt_dark"],
                                 outline=felt_theme["accent"], width=2, tags=(tag,))
        self.canvas.create_text(cx, cy - r - 10, text=label, fill=theme.FG,
                                 font=theme.font(9, weight="bold"), tags=(tag,))
        # Chips get their own extra tag alongside the shared one, so the
        # payout animation can delete/redraw just the chips later without
        # touching this spot's own circle+label -- see _draw_chip_stack.
        self._draw_chip_stack((tag, f"{tag}_chips"), cx, cy, self.bets.get(key, 0), max_r=20)

    # See ui/theme.py for the canonical implementation -- shared with
    # ui/settings_screen.py's toggle switches, which drew the exact same
    # polygon math independently before this was factored out.
    _draw_rounded_rect = staticmethod(theme.rounded_rect)

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
            draw_card_back(self.canvas, x, DEALER_Y, self._current_felt,
                            self.app.settings.theme()["accent"], tags=(tag,))

    def _draw_player_card_at(self, i, card, x, y, face_up=True):
        """Draws into fan_canvas -- every caller of this is drawing the
        player's fanned hand (deal-in, or the muck slide-off), never the
        strip on the main canvas."""
        tag = f"player_card_{i}"
        self.fan_canvas.delete(tag)
        if face_up:
            draw_card(self.fan_canvas, x, y, card, tags=(tag,))
        else:
            draw_card_back(self.fan_canvas, x, y, self._current_felt,
                            self.app.settings.theme()["accent"], tags=(tag,))

    def _fan_slots(self):
        """Top-left (x, y) for each of the player's 3 cards, in dealt order,
        overlapping in a gentle arc -- the resting spot while Play/Fold is
        being decided."""
        cx = CANVAS_WIDTH / 2
        centers_x = [cx - FAN_GAP, cx, cx + FAN_GAP]
        ys = [FAN_Y + FAN_ARC_OFFSET, FAN_Y, FAN_Y + FAN_ARC_OFFSET]
        return [(x - CARD_WIDTH / 2, y) for x, y in zip(centers_x, ys)]

    def _draw_fan_mat(self):
        """The player's own felt mat in fan_canvas, behind the fanned hand
        -- drawn once per round, right after fan_canvas is cleared, so it
        persists underneath as individual cards are animated in/out on top
        of it. Same rounded-rectangle language as the dealer's mat, but a
        distinct neutral border (FAN_MAT_BORDER) so the two read as clearly
        different zones rather than identical twins."""
        felt_theme = self.app.settings.theme()
        self._draw_rounded_rect(
            self.fan_canvas, FAN_MAT_X1, FAN_MAT_TOP, FAN_MAT_X2, FAN_MAT_BOTTOM, radius=FAN_MAT_RADIUS,
            fill=felt_theme["felt_dark"], outline=FAN_MAT_BORDER, width=2, tags=("fan_mat_bg",),
        )

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

    def _run_sequential(self, fns, on_done=None):
        """Calls each fn(cb) in turn, only starting the next once the
        current one calls its own cb -- unlike _run_staggered's fixed-delay
        overlap, this is for steps that must strictly follow one another
        (the payout animation's stages -- see _animate_payouts). Each fn is
        expected to internally use _animate, which already collapses to an
        instant call when animations are off, so a whole chain built from
        this still resolves synchronously in that case."""
        def step(i):
            if i >= len(fns):
                if on_done:
                    on_done()
                return
            fns[i](lambda: step(i + 1))
        step(0)

    def _after_delay(self, ms, fn):
        """Runs fn() after a plain `ms` pause -- e.g. a beat between one
        animation settling and the next one starting -- collapsing to an
        immediate call when animations are off, same convention _animate/
        _run_staggered already follow for anything driven frame-by-frame."""
        if self.app.settings.get("animations_enabled"):
            self.after(ms, fn)
        else:
            fn()

    def _animate_flip(self, canvas, tag, cx_slot, y, card, reveal, duration, on_done=None):
        """Flips a card in place by narrowing it to a sliver and back out,
        swapping the face at the midpoint. `reveal=True` turns a face-down
        card face up (the dealer's reveal, on the main canvas); `reveal=
        False` turns a face-up card face down (folding, on fan_canvas,
        before it's tucked under a spot or mucked away)."""
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
        self.result_lbl.configure(text="Your cards are dealt. Play or Fold?", fg=theme.FG)
        self._show_decision_controls()

    def _animate_to_rest(self, cards, target_cx, target_cy, group_tag, spot_tag=None,
                          face_up=True, sort=False, on_done=None,
                          rest_width=REST_CARD_WIDTH, rest_height=REST_CARD_HEIGHT,
                          fan_offset=REST_CARD_FAN_OFFSET,
                          vanish_ms=150, grow_ms=200):
        """Moves the player's 3 cards from the fan (in fan_canvas, below the
        Play/Fold buttons) to a resting spot on the strip (in self.canvas,
        above them) -- Play (win/push/lose) or Prime/Pair Plus (folding with
        one of those still active), at `rest_width`/`rest_height` (Play's
        own, bigger PLAY_REST_CARD_* by default via _settle_played_hand; the
        smaller module-level REST_CARD_* otherwise).

        A single continuous slide isn't possible between two separate
        canvas widgets, so this is actually two animations timed to read as
        one: the fan shrinks away to a point in fan_canvas, then the cards
        grow back in at their target in self.canvas.

        `spot_tag`, if given, is an existing spot already on self.canvas
        that these cards should end up BEHIND, so its chip stack stays on
        top and the cards just peek out from underneath -- the "folded onto
        Prime/Pair Plus" look. `sort` orders them highest-to-lowest, left to
        right, matching how the hand reads once settled; folded cards stay
        in dealt order since they land face-down anyway.

        `vanish_ms`/`grow_ms` are this pair's own durations -- default to
        the Fold tuck-under-a-spot timing (Prime/Pair Plus), untouched;
        _settle_played_hand passes its own slower pair for the Play spot."""
        assert self.result is not None
        fan_slots = self._fan_slots()
        order = sorted(range(3), key=lambda i: -cards[i].value) if sort else list(range(3))
        offsets = [-fan_offset, 0, fan_offset]
        vanish_cx, vanish_cy = CANVAS_WIDTH / 2, 0  # towards the top of fan_canvas, i.e. towards the strip above it

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
                    if face_up:
                        draw_card(self.fan_canvas, cx - w / 2, cy - h / 2, cards[i], width=w, height=h, tags=(tag,))
                    else:
                        draw_card_back(self.fan_canvas, cx - w / 2, cy - h / 2, self._current_felt,
                                        self.app.settings.theme()["accent"], width=w, height=h, tags=(tag,))

        def grow_frame(t):
            for new_pos, orig_i in enumerate(order):
                tcx, tcy = target_cx + offsets[new_pos], target_cy
                w = rest_width * t
                h = rest_height * t
                tag = f"player_card_{orig_i}"
                self.canvas.delete(tag)
                draw_tags = (tag, group_tag)
                if w > 3 and h > 3:
                    if face_up:
                        draw_card(self.canvas, tcx - w / 2, tcy - h / 2, cards[orig_i], width=w, height=h,
                                  tags=draw_tags)
                    else:
                        draw_card_back(self.canvas, tcx - w / 2, tcy - h / 2, self._current_felt,
                                        self.app.settings.theme()["accent"], width=w, height=h, tags=draw_tags)
                    if spot_tag:
                        self.canvas.tag_lower(tag, spot_tag)

        def start_grow():
            self._animate(grow_ms, grow_frame, on_done=on_done)

        self._animate(vanish_ms, vanish_frame, on_done=start_grow)

    def _settle_played_hand(self, on_done):
        """Play: the hand comes to rest centred on the Play spot -- now
        above the fan, so this moves the cards *up* -- sorted highest to
        lowest, then, after a beat, the Play bet's chips are placed on top
        of the cards, the traditional casino way of signalling "I'm playing
        this hand". The "PLAY" label sits at this same centre point and
        ends up covered, same as a printed felt spot would.

        Slower than Fold's own use of _animate_to_rest (PLAY_SETTLE_VANISH_
        MS/PLAY_SETTLE_GROW_MS vs. that method's own Fold-preserving
        defaults) and with its own pause (PLAY_CHIP_DELAY_MS) before the
        chips actually land, rather than the instant of the cards -- this is
        the moment the player commits real money, so it's given its own
        unhurried beat rather than reusing Fold's brisker pacing."""
        assert self.result is not None
        result = self.result  # captured locally so the closure below doesn't dereference self.result directly
        play_cy = PLAY_BOX_CY

        def show_play_chips():
            # Smaller than the usual strip chip stack -- these sit on top of
            # the played cards, not an empty spot, so a smaller stack leaves
            # the middle card's own index actually readable.
            self._draw_chip_stack(("strip_play", "strip_play_chips"), STACK_CX, play_cy, result.play_bet,
                                   max_r=18)
            if on_done:
                on_done()

        def cards_settled():
            self._after_delay(PLAY_CHIP_DELAY_MS, show_play_chips)

        self._animate_to_rest(result.player_cards, STACK_CX, play_cy, "played_hand",
                               sort=True, on_done=cards_settled,
                               rest_width=PLAY_REST_CARD_WIDTH, rest_height=PLAY_REST_CARD_HEIGHT,
                               fan_offset=PLAY_REST_CARD_FAN_OFFSET,
                               vanish_ms=PLAY_SETTLE_VANISH_MS, grow_ms=PLAY_SETTLE_GROW_MS)

    def _settle_folded_hand(self, on_done):
        """Fold: if Prime or Pair Plus actually *won* (both pay regardless
        of the Ante/Play decision, but a bet placed on one that lost has
        nothing to show for itself), the folded hand is flipped face down
        and tucked underneath that spot -- cards peeking out from under the
        chips -- exactly the physical tell a real table gives that there's
        still something to collect even though the hand isn't being played.
        Otherwise it's just mucked away as before."""
        assert self.result is not None
        result = self.result  # captured locally so the closure below doesn't dereference self.result directly
        if result.prime_return > 0:
            rest_cx, spot_tag = PRIME_STRIP_CX, "strip_prime"
        elif result.pair_plus_return > 0:
            rest_cx, spot_tag = PAIR_PLUS_STRIP_CX, "strip_pair_plus"
        else:
            self._muck_player_cards(on_done)
            return

        rest_cy = PLAY_BOX_CY  # matches where the Prime/Pair Plus circles themselves are drawn

        def after_flip():
            self._animate_to_rest(result.player_cards, rest_cx, rest_cy, "folded_hand",
                                   spot_tag=spot_tag, face_up=False, on_done=on_done)

        self._flip_fan_face_down(after_flip)

    def _flip_fan_face_down(self, on_done):
        """Flips each fanned card face down in place, staggered -- the first
        step of folding, shared by both _settle_folded_hand (which then
        tucks the hand under Prime/Pair Plus) and _muck_player_cards (which
        then slides it away)."""
        assert self.result is not None
        cards = self.result.player_cards
        fan_slots = self._fan_slots()

        def flip_one(i):
            sx, sy = fan_slots[i]
            cx_slot = sx + CARD_WIDTH / 2
            self._animate_flip(
                self.fan_canvas, f"player_card_{i}", cx_slot, sy, cards[i], reveal=False, duration=180,
                on_done=(on_done if i == 2 else None),
            )

        self._run_staggered(3, 70, flip_one)

    def _muck_player_cards(self, on_done):
        """No active Pair Plus/Prime to show off on a fold -- flip face down
        and slide the hand off-canvas, same as a real muck."""
        assert self.result is not None
        fan_slots = self._fan_slots()

        def slide_one(i):
            sx, sy = fan_slots[i]

            def slide(t, sx=sx, sy=sy):
                tx, ty = CANVAS_WIDTH + 90, sy - 40  # forwards (up) and off to the side
                self._draw_player_card_at(i, None, sx + (tx - sx) * t, sy + (ty - sy) * t, face_up=False)

            self._animate(220, slide, on_done=(on_done if i == 2 else None))

        self._flip_fan_face_down(lambda: self._run_staggered(3, 70, slide_one))

    def _reveal_dealer(self, result):
        # Called right as the Play chips land (see _settle_played_hand) --
        # a pause (DEALER_REVEAL_START_DELAY_MS) before the first card flips
        # face up, same beat (DEALER_REVEAL_STAGGER_MS) between each of the
        # 3. Once all of them are up, the payout chip animation runs
        # immediately (see _animate_payouts), and only once *that's*
        # finished does the round actually settle -- see _on_round_settled.
        after_reveal = lambda: self._animate_payouts(result, lambda: self._on_round_settled(result))

        def flip_one(i):
            cx_slot = self._dealer_slot_x(i) + CARD_WIDTH / 2
            self._animate_flip(
                self.canvas, f"dealer_card_{i}", cx_slot, DEALER_Y, result.dealer_cards[i], reveal=True, duration=200,
                on_done=after_reveal if i == 2 else None,
            )

        self._after_delay(DEALER_REVEAL_START_DELAY_MS, lambda: self._run_staggered(3, DEALER_REVEAL_STAGGER_MS, flip_one))

    # ------------------------------------------------------------------ payout chip animation
    def _resolved_bet_totals(self, result):
        """(key, bet, ret) for every bet actually placed this round, in the
        canonical Play/Ante/Pair Plus/Prime/Jackpot order (see logic.py's
        BET_TYPES). `ret` combines a bet's main return with any return that
        doesn't have its own separate stake -- the Ante Bonus rides on the
        Ante, since it's paid alongside it rather than as its own wager --
        so this reflects the net change in value at each bet, not each
        payout line item in the result panel.

        Shared by the payout chip animation, which adds on-table layout
        info on top (see _payout_chip_items below), and by the lifetime
        stats recorded once a round settles (see _finish_round)."""
        totals = []
        if not result.folded and result.play_bet:
            totals.append(("play", result.play_bet, result.play_return))
        if result.ante_bet:
            totals.append(("ante", result.ante_bet, result.ante_return + result.ante_bonus_return))
        if result.pair_plus_bet:
            totals.append(("pair_plus", result.pair_plus_bet, result.pair_plus_return))
        if result.prime_bet:
            totals.append(("prime", result.prime_bet, result.prime_return))
        if result.jackpot_bet:
            totals.append(("jackpot", result.jackpot_bet, result.jackpot_return))
        return totals

    def _payout_chip_items(self, result):
        """_resolved_bet_totals, with each bet's on-table spot (where its
        chips actually sit -- position, tag, sizing) attached, for the
        payout chip animation."""
        layout = {
            "play": (STACK_CX, PLAY_BOX_CY, "strip_play", 18),
            "ante": (STACK_CX, ANTE_STRIP_CY, "strip_ante", 20),
            "pair_plus": (PAIR_PLUS_STRIP_CX, PLAY_BOX_CY, "strip_pair_plus", 20),
            "prime": (PRIME_STRIP_CX, PLAY_BOX_CY, "strip_prime", 20),
            "jackpot": (JACKPOT_STRIP_CX, PLAY_BOX_CY, "strip_jackpot", 20),
        }
        items = []
        for key, bet, ret in self._resolved_bet_totals(result):
            cx, cy, spot_tag, max_r = layout[key]
            items.append(dict(key=key, bet=bet, ret=ret, cx=cx, cy=cy, spot_tag=spot_tag,
                               max_r=max_r))
        return items

    def _chip_move_away(self, item, on_done):
        """Stage 1 -- one call per losing bet, chained by _animate_payouts:
        the spot's existing stake chips slide from the spot towards the
        dealer's centre, shrinking away to nothing as they travel so they
        sink out of view before ever reaching the dealer's cards -- never
        passing on top of them -- rather than arriving at full size and
        having to be tucked behind them."""
        chips_tag = f"{item['spot_tag']}_chips"
        self.canvas.delete(chips_tag)
        travel_tag = f"chip_travel_{item['key']}"
        from_cx, from_cy = item["cx"], item["cy"]

        def frame(t):
            cx = from_cx + (DEALER_CENTER_X - from_cx) * t
            cy = from_cy + (DEALER_CENTER_Y - from_cy) * t
            self.canvas.delete(travel_tag)
            r = item["max_r"] * (1 - t)
            if r > 2:
                self._draw_chip_stack(travel_tag, cx, cy, item["bet"], r)

        def arrived():
            self.canvas.delete(travel_tag)
            if on_done:
                on_done()

        self._animate(PAYOUT_CHIP_MOVE_MS, frame, on_done=arrived)

    def _chip_move_in(self, item, on_done):
        """Stage 2 -- one call per winning bet, chained by _animate_payouts:
        a new stack for just the win portion (return minus stake -- the
        stake itself never left the spot) appears at the dealer's centre
        and slides out to land just above the spot's existing stack,
        growing in size as it travels so it reads as being dealt out rather
        than sliding in already full-size."""
        win_amount = item["ret"] - item["bet"]
        travel_tag = f"chip_travel_{item['key']}"
        to_cy = item["cy"] + PAYOUT_WIN_LANDING_OFFSET_Y
        to_cx = item["cx"] + PAYOUT_WIN_LANDING_OFFSET_X

        def frame(t):
            cx = DEALER_CENTER_X + (to_cx - DEALER_CENTER_X) * t
            cy = DEALER_CENTER_Y + (to_cy - DEALER_CENTER_Y) * t
            self.canvas.delete(travel_tag)
            if item["max_r"] * t > 2:
                self._draw_chip_stack(travel_tag, cx, cy, win_amount, item["max_r"] * t)

        self._animate(PAYOUT_CHIP_MOVE_MS, frame, on_done=on_done)

    def _sweep_remaining_chips(self, items, on_done):
        """Called from _new_deal, right as the player deals the next hand --
        not part of _animate_payouts' own chain (see its docstring): every
        spot that still holds chips (pushes, untouched since Stage 1/2;
        wins, with their Stage 2 addition sitting alongside the original
        stake) slides away together towards the round result panel below
        the canvas. A literal slide into that separate widget isn't
        possible (see the fan_canvas/self.canvas split in the module
        docstring above), so this just shrinks everything to a point
        heading that way -- the same trick _animate_to_rest's vanish phase
        uses."""
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
                    self._draw_chip_stack(base_tag, ncx, ncy, it["bet"], r)

                win_amount = it["ret"] - it["bet"]
                if win_amount > 0:
                    travel_tag = f"chip_travel_{it['key']}"
                    wcy = it["cy"] + PAYOUT_WIN_LANDING_OFFSET_Y
                    wcx = it["cx"] + PAYOUT_WIN_LANDING_OFFSET_X
                    nwcx, nwcy = wcx + (target_x - wcx) * t, wcy + (target_y - wcy) * t
                    self.canvas.delete(travel_tag)
                    if r > 2:
                        self._draw_chip_stack(travel_tag, nwcx, nwcy, win_amount, r)

        def finish():
            for it in remaining:
                self.canvas.delete(f"{it['spot_tag']}_chips")
                self.canvas.delete(f"chip_travel_{it['key']}")
            if on_done:
                on_done()

        self._animate(280, frame, on_done=finish)

    def _animate_payouts(self, result, on_done):
        """The payout choreography once the dealer's cards are revealed:
        losing bets swept to the dealer one at a time, then winning bets
        paid out from the dealer one at a time -- see _chip_move_away/
        _chip_move_in. Whatever's left (pushes, and wins with their payout
        now sitting alongside the original stake) just stays in place on
        the table after that, through the round result panel and all, until
        the player deals again -- see _new_deal, which sweeps it away then.
        Respects the animations toggle the same way the rest of the app
        does: each stage is built on _animate, which already collapses to
        an instant final frame when animations are off, so this whole
        chain just resolves synchronously in that case."""
        items = self._payout_chip_items(result)
        losing = [it for it in items if it["ret"] == 0]
        winning = [it for it in items if it["ret"] > it["bet"]]

        stages = (
            [lambda cb, it=it: self._chip_move_away(it, cb) for it in losing]
            + [lambda cb, it=it: self._chip_move_in(it, cb) for it in winning]
        )
        self._run_sequential(stages, on_done)

    def _on_round_settled(self, result):
        # The hand's already moved onto the strip (or been mucked) by this
        # point -- fan_canvas is empty, so hiding it lets the payout panel
        # sit right after the Play/Fold row instead of leaving a gap where
        # the fan used to be.
        self.fan_canvas.pack_forget()
        # The balance was actually credited back in _finish_round, but its
        # *display* -- this screen's own top-bar figure, and the Cashier/
        # Menu's -- only updates now, once the payout chip animation has
        # actually finished and the ROUND RESULT panel is about to appear,
        # rather than jumping to the new total while chips are still
        # visibly sliding around.
        self._refresh_balance()
        self.app.on_balance_changed()
        self._show_result(result)
        self._show_round_over_controls()
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
            "fold": theme.FG_DIM,
            "dealer_no_qualify": theme.WIN_COLOR,
            "win": theme.WIN_COLOR,
            "lose": theme.LOSE_COLOR,
            "push": theme.PUSH_COLOR,
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
        y = 46
        for label, net in rows:
            canvas.create_text(24, y, text=label, fill=theme.FG, font=theme.font(10), anchor="w")
            canvas.create_text(w - 24, y, text=_format_signed(net), fill=_net_color(net),
                                font=theme.font(10, weight="bold"), anchor="e")
            y += 20

        y += 6
        canvas.create_line(24, y, w - 24, y, fill=theme.BORDER)
        y += 20
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
        """Re-applies the felt colour everywhere it was set from the theme at
        build time. Settings can change `table_theme` after this frame was
        already built (frames are built once and reused), so a plain one-off
        `self.configure(bg=...)` at build time never actually took effect
        anywhere but this outer frame -- which every visible widget sits on
        top of, so the change was invisible until a full app restart rebuilt
        everything from scratch."""
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
        self.jackpot_display.retheme(felt_theme["felt_dark"], felt_theme["accent"])
        self._draw_paytable()
        if self.state == "resolved" and self.result is not None:
            self._draw_payout_panel(self.result)

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