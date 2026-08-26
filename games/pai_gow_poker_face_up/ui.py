"""
Face Up Pai Gow Poker table screen.

Subclasses games.pai_gow_poker.ui.PaiGowPokerFrame -- the betting screen,
felt/zone drawing, hand-setting (Sort/Confirm's own foul check), chip tray,
paytable panel, and payout animation are all reused completely unchanged.
Only what's genuinely different (see games/pai_gow_poker_face_up/logic.py's
own module docstring for the rule differences) is overridden here:

  - The dealer's hand is revealed (flipped, then separated into Front/Back)
    immediately once dealing finishes, *before* the player sets their own
    hand -- rather than staying hidden until Confirm.
  - An automatic Ante push, no player hand-setting at all, whenever the
    dealer's revealed hand is an Ace-high Pai Gow.
  - The base game's "HOUSE WAY" button is replaced with a red "FOLD"
    button -- forfeit the Ante immediately (cards flip face down together,
    then fly off screen to the top right, one at a time) rather than set a
    hand you can already tell won't beat the Dealer's revealed one.
  - Confirm settles and pays out directly (the dealer's already revealed
    and separated by then), rather than triggering its own reveal.
  - The rules dialog and the paytable panel's own commission note reflect
    this game's own rules instead of the standard game's.
"""
import tkinter as tk

from games.pai_gow_poker.logic import compare_hands
from games.pai_gow_poker.ui import (
    BACK_CARD_OVERLAP_X,
    BACK_ZONE_CX,
    CANVAS_WIDTH,
    FELT_MAT_X1,
    FELT_MAT_X2,
    FELT_Y,
    FRONT_CARD_OVERLAP_X,
    FRONT_ZONE_CX,
    TIER_LABELS,
    ZONE_LABEL_Y_OFFSET,
    ZONE_TOP,
    PaiGowPokerFrame,
    _felt_card_x,
)
from games.pai_gow_poker_face_up.logic import GAME_KEY, GAME_LABEL, PaiGowFaceUpGame
from ui import dialogs, theme
from ui.card_widgets import CARD_WIDTH, draw_card, draw_card_back

STATE_FILENAME = "pai_gow_poker_face_up_state.json"

# Fold animation timing -- two stages (see _animate_fold_out): every card
# flips face down together, then each flies off screen toward the top
# right one at a time. Deliberately quick -- folding is meant to read as
# "get out fast", not a full deal-in-style reveal.
FOLD_FLIP_MS = 140
FOLD_FLY_MS = 160
FOLD_FLY_STAGGER_MS = 55
# Well beyond the canvas's own top-right corner -- off the visible play
# area entirely, not just resting near its edge.
FOLD_FLY_TARGET = (CANVAS_WIDTH + 140, -160)


class PaiGowPokerFaceUpFrame(PaiGowPokerFrame):
    STATE_FILENAME = STATE_FILENAME
    GAME_KEY = GAME_KEY
    GAME_TITLE = GAME_LABEL
    BREADCRUMB = "pai_gow_poker_face_up"
    ANTE_COMMISSION_NOTE = "(no commission)"

    def _make_game(self):
        return PaiGowFaceUpGame()

    def _make_middle_btn(self):
        # Red, not the base game's gold "HOUSE WAY" -- seeing the Dealer's
        # hand before setting your own means House Way is much less useful
        # here, so this slot becomes "FOLD" instead: give up immediately,
        # rather than bother setting a hand you can already tell can't win.
        return tk.Button(
            self.action_frame, text="FOLD", bg=theme.LOSE_DIM_BG, fg=theme.FG,
            font=theme.font(12, weight="bold"), relief="flat", padx=18, pady=9, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.LOSE_COLOR,
            command=self._on_fold,
        )

    # ------------------------------------------------------------------ dealer revealed up front
    def _on_deal_in_done(self):
        # Same "deal-in has actually finished" bookkeeping as the base
        # game's own _on_deal_in_done -- what differs is what happens
        # next: the Dealer's hand is revealed right away here, rather than
        # moving straight to "setting" and leaving it face down until
        # Confirm.
        self._player_cards_revealed = 7
        self._dealer_dealt_count = 7
        self._redraw_felt()
        self.state = "dealer_revealing"
        self.result_lbl.configure(text="Dealer's hand (Face Up):", fg=theme.FG)
        self._show_no_controls()
        self._dealer_revealed = 0
        self._reveal_dealer()

    def _separate_dealer_hand(self):
        # No settle() here, unlike the base game's own version of this
        # method -- the player hasn't set a hand yet at this point in Face
        # Up (that's the whole point: the Dealer's already-set hand is
        # revealed *before* the player acts). settle() happens in
        # _on_confirm below, once they have.
        self._dealer_separated = True
        self._animate_dealer_separation()

    def _on_dealer_separated(self):
        """Reached once the Dealer's revealed hand has finished sliding
        into its settled Front/Back groups -- overrides the base game's own
        version, which goes straight to payout here (there, this is only
        ever reached *after* the player has already set a hand and it's
        been settled). Here it's the opposite: either the round already
        ended automatically (an Ace-high Pai Gow), or the player is only
        now about to set their own hand."""
        assert self.result is not None
        if getattr(self.result, "dealer_ace_high_push", False):
            self.result_lbl.configure(
                text="Dealer has an Ace-high Pai Gow -- Ante pushes automatically.", fg=theme.PUSH_COLOR)
            self._after_delay(500, self._start_payout_sequence)
            return
        self.state = "setting"
        self._show_setting_controls()

    def _on_confirm(self):
        # The base game's own _on_confirm hands off to _reveal_dealer() --
        # here the Dealer's already revealed and separated (see above), so
        # this settles and pays out directly instead.
        if not self._current_split_valid():
            return
        assert self.result is not None
        cards = self.result.player_cards
        front = [cards[i] for i in self.front_order]
        back = [cards[i] for i in self.back_order]
        self.game.set_player_hand(front, back)
        self.result = self.game.settle()
        self.state = "revealing"
        self.result_lbl.configure(text="Settling...", fg=theme.FG)
        self._show_no_controls()
        self._after_delay(400, self._start_payout_sequence)

    # ------------------------------------------------------------------ fold
    def _on_fold(self):
        if self.state != "setting":
            return
        assert self.result is not None
        self.state = "folding"
        self._on_card_unhover()
        self._show_no_controls()
        self.result_lbl.configure(text="Folding...", fg=theme.LOSE_COLOR)
        self._animate_fold_out()

    def _current_card_position(self, idx):
        """Where card `idx` is actually sitting right now, wherever the
        player's left it -- the felt, Front, or Back -- so the fold
        animation can start from the right spot for each card. Mirrors the
        same layout math _draw_felt_cards/_draw_placed_cards (the base
        game's own) already use to draw these zones, just solved for one
        card's position instead of drawing the whole row."""
        zone = self.card_zone.get(idx)
        if zone == "felt":
            pos = self.felt_slot_order.index(idx) if idx in self.felt_slot_order else idx
            return _felt_card_x(pos, 7, FELT_MAT_X1, FELT_MAT_X2), FELT_Y
        row_y = ZONE_TOP + ZONE_LABEL_Y_OFFSET + 24
        if zone == "front":
            n = len(self.front_order)
            fan_w = (n - 1) * FRONT_CARD_OVERLAP_X + CARD_WIDTH if n else 0
            start_x = FRONT_ZONE_CX - fan_w / 2
            return start_x + self.front_order.index(idx) * FRONT_CARD_OVERLAP_X, row_y
        if zone == "back":
            n = len(self.back_order)
            fan_w = (n - 1) * BACK_CARD_OVERLAP_X + CARD_WIDTH if n else 0
            start_x = BACK_ZONE_CX - fan_w / 2
            return start_x + self.back_order.index(idx) * BACK_CARD_OVERLAP_X, row_y
        raise ValueError(f"card {idx} has no current on-felt position (zone={zone!r})")

    def _animate_fold_out(self):
        """Two stages: every one of the player's 7 cards -- wherever each
        currently sits, felt or already placed -- flips face down
        *together*, in place; then, once that's done, each flies off
        screen toward the top right corner one at a time. Quick throughout
        -- folding is a "get out fast" action, not a deal-in-style reveal."""
        assert self.result is not None
        positions = {idx: self._current_card_position(idx) for idx in range(7)}
        # Whichever one of these tags each card actually carries (only one
        # ever applies), clear it so it doesn't linger under this
        # animation's own drawing of it from here on.
        for idx in range(7):
            self.canvas.delete(f"feltslot_{idx}", f"frontcard_{idx}", f"backcard_{idx}", f"hit_{idx}")

        if not self.app.settings.get("animations_enabled"):
            self._finish_fold()
            return
        self._animate_fold_flip(positions, lambda: self._animate_fold_fly(positions))

    def _animate_fold_flip(self, positions, on_done):
        """Stage 1 -- every card flips face down at once, in place (not
        one at a time), unlike every other flip animation in this game."""
        assert self.result is not None
        cards = self.result.player_cards
        accent = self.app.settings.theme()["accent"]

        def frame(t):
            squeeze = abs(1 - 2 * t)
            w = max(4, CARD_WIDTH * squeeze)
            for idx, (x, y) in positions.items():
                tag = f"foldcard_{idx}"
                self.canvas.delete(tag)
                fx = x + (CARD_WIDTH - w) / 2
                if t < 0.5:
                    draw_card(self.canvas, fx, y, cards[idx], width=w, tags=(tag,))
                else:
                    draw_card_back(self.canvas, fx, y, self._current_felt, accent, width=w, tags=(tag,))

        self._animate(FOLD_FLIP_MS, frame, on_done=on_done)

    def _animate_fold_fly(self, positions):
        """Stage 2 -- each card (already face down) flies off screen to
        the top right corner, one at a time."""
        for slot, idx in enumerate(range(7)):
            self.after(slot * FOLD_FLY_STAGGER_MS, self._fly_one_fold_card, idx, positions[idx])
        self.after(7 * FOLD_FLY_STAGGER_MS + FOLD_FLY_MS, self._finish_fold)

    def _fly_one_fold_card(self, idx, start):
        assert self.result is not None
        card = self.result.player_cards[idx]
        sx, sy = start
        tx, ty = FOLD_FLY_TARGET
        tag = f"foldcard_{idx}"
        accent = self.app.settings.theme()["accent"]

        def frame(t):
            self.canvas.delete(tag)
            x = sx + (tx - sx) * t
            y = sy + (ty - sy) * t
            draw_card_back(self.canvas, x, y, self._current_felt, accent, tags=(tag,))

        def done():
            self.canvas.delete(tag)

        self._animate(FOLD_FLY_MS, frame, on_done=done)

    def _finish_fold(self):
        self.result = self.game.fold()
        self.state = "revealing"
        self._start_payout_sequence()

    # ------------------------------------------------------------------ result panel
    def _show_result(self, summary):
        # Same shape as the base game's own _show_result, except the hand
        # rows -- an Ace-high-Pai-Gow push never had a player hand to
        # report on at all.
        rows = [(f"Ante £{summary.ante_bet:.0f}", summary.ante_return - summary.ante_bet)]
        if summary.fortune_bet > 0:
            rows.append((f"Fortune £{summary.fortune_bet:.0f}", summary.fortune_return - summary.fortune_bet))
        if summary.jackpot_bet > 0:
            rows.append((f"Jackpot £{summary.jackpot_bet:.0f}", summary.jackpot_return - summary.jackpot_bet))

        fortune_hand_name = TIER_LABELS.get(summary.fortune_tier, "No qualifying hand") \
            if summary.fortune_tier else "No qualifying hand"

        if getattr(summary, "dealer_ace_high_push", False):
            hand_rows = [
                ("Dealer: Ace-high Pai Gow", "PUSH", theme.PUSH_COLOR),
                (f"Fortune Hand: {fortune_hand_name}", None, None),
            ]
        elif getattr(summary, "folded", False):
            hand_rows = [
                ("You folded", "LOSE", theme.LOSE_COLOR),
                (f"Fortune Hand: {fortune_hand_name}", None, None),
            ]
        else:
            front_name = summary.player_front_eval[1] if summary.player_front_eval else ""
            back_name = summary.player_back_eval[1] if summary.player_back_eval else ""
            front_win = bool(summary.player_front_eval and summary.dealer_front_eval
                              and compare_hands(summary.player_front_eval, summary.dealer_front_eval) > 0)
            back_win = bool(summary.player_back_eval and summary.dealer_back_eval
                             and compare_hands(summary.player_back_eval, summary.dealer_back_eval) > 0)
            hand_rows = [
                (f"Your Front: {front_name}", "WIN" if front_win else "LOSE",
                 theme.WIN_COLOR if front_win else theme.LOSE_COLOR),
                (f"Your Back: {back_name}", "WIN" if back_win else "LOSE",
                 theme.WIN_COLOR if back_win else theme.LOSE_COLOR),
                (f"Fortune Hand: {fortune_hand_name}", None, None),
            ]
        self._draw_round_result_panel(rows, summary.net_result, hand_rows)

    # ------------------------------------------------------------------ rules
    def _show_rules(self):
        dialogs.document(
            self, "♠ Pai Gow Poker (Face Up!) -- Rules",
            [
                ("GAMEPLAY", [
                    "**Betting:** Place an Ante (mandatory) plus optional Fortune and Jackpot "
                    "side bets. Every round is played against the dealer.",
                    "**Dealing:** You and the Dealer each get 7 cards from a 53-card deck "
                    "(52 + the Joker). The Joker plays as an Ace, or completes a straight or "
                    "flush.",
                    "**Dealer plays first:** the Dealer's hand is set by House Way and "
                    "revealed *before* you set your own -- you get to see it while arranging "
                    "your 7 cards.",
                    "**Ace-high Pai Gow:** if the Dealer's revealed hand has no pair, "
                    "straight, or flush anywhere -- the lowest possible hand -- the round "
                    "ends immediately: the Ante pushes automatically (stake returned), side "
                    "bets still pay as normal, and you don't set a hand that round.",
                    "**Setting your hand:** Arrange your 7 cards into a 2-card Front hand and "
                    "a 5-card Back hand. The Back must rank higher than the Front. Sort "
                    "tidies your unplaced cards; House Way sets your whole hand automatically, "
                    "the same way the Dealer's own is set.",
                    "**Fold:** since you can already see the Dealer's hand, Fold forfeits the "
                    "Ante immediately -- your cards flip face down and fly off screen "
                    "-- rather than bothering to set a hand you can tell won't win. Fortune "
                    "and Jackpot still pay as normal either way.",
                    "**Settling:** Win both front and back hands to win the Ante -- "
                    "**1:1, no commission.** Lose both to lose the Ante. Split one each way "
                    "and it's a push. A tied hand is won by the Dealer.",
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
