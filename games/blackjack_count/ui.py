"""
Blackjack (Counting) table screen. Subclasses games.blackjack.ui.BlackjackFrame
-- every betting/animation/payout/paytable/rules mechanism is reused
unchanged. Only what's different is overridden here: the game engine
(BlackjackCountGame instead of BlackjackGame, via _make_game), a distinct
save file / top-bar title+breadcrumb (GAME_KEY is deliberately NOT
overridden -- see below), a live "Count: N" label in the top bar that grows
card by card in step with the reveal animations (_on_card_revealed), and the
deck's fill-level + red penetration-line visual (_draw_deck).
"""
import tkinter as tk

from games.blackjack.ui import BlackjackFrame, CARD_HEIGHT, CARD_WIDTH, DECK_LABEL_Y, DECK_X1, DECK_Y
from games.blackjack_count.logic import BlackjackCountGame, RESHUFFLE_PENETRATION
from ui import theme
from ui.card_widgets import draw_card_back

STATE_FILENAME = "blackjack_count_state.json"

# Standard Hi-Lo running count: low cards (2-6) tilt the remaining shoe rich
# in high cards (+1), high cards (10/face/Ace) do the opposite (-1), 7-9 are
# neutral (0). See BlackjackCountFrame._on_card_revealed.
HI_LO_VALUES = {
    "2": 1, "3": 1, "4": 1, "5": 1, "6": 1,
    "7": 0, "8": 0, "9": 0,
    "10": -1, "J": -1, "Q": -1, "K": -1, "A": -1,
}


class BlackjackCountFrame(BlackjackFrame):
    STATE_FILENAME = STATE_FILENAME
    # GAME_KEY is inherited from BlackjackFrame ("blackjack") rather than
    # overridden -- Standard and Counting are different tables but the same
    # game as far as GameStatsManager/the Stats screen are concerned, so
    # bets/hands/net-results from both feed one shared "blackjack" bucket
    # instead of splitting the Stats screen's own breakdown across two
    # near-identical sections.
    GAME_TITLE = "Blackjack (Counting)"
    BREADCRUMB = "blackjack_count"

    def __init__(self, parent, app):
        super().__init__(parent, app)
        # The displayed running count -- grown one card at a time by
        # _on_card_revealed as each one actually lands face-up on screen,
        # not by reading self.game's own state (the engine has no count of
        # its own -- see games/blackjack_count/logic.py's docstring). Safe
        # to set after super().__init__() -- nothing during construction
        # (the betting screen, no round in progress yet) ever calls
        # _on_card_revealed.
        self.displayed_count = 0

    def _make_game(self):
        return BlackjackCountGame()

    # ------------------------------------------------------------------ top bar
    def _build_extra_top_bar_widgets(self, top_bar):
        self.count_lbl = tk.Label(
            top_bar, text="Count: 0", bg=theme.BG_ELEVATED, fg=theme.SECONDARY,
            font=theme.font(12, weight="bold"),
        )
        self.count_lbl.pack(side="right", padx=(0, 10))

    def _on_card_revealed(self, card):
        """Grows the displayed count by this one card's own Hi-Lo value --
        called by the base class the instant a card actually finishes
        landing/flipping face-up (see BlackjackFrame's own docstring on
        this hook), so the count ticks up in step with what's visible
        rather than jumping ahead to whatever self.game has already dealt
        into play before its own reveal animation has run. Resets to 0
        first if the shoe was just reshuffled -- see
        BlackjackCountGame.just_reshuffled."""
        if self.game.just_reshuffled:
            self.displayed_count = 0
            self.game.just_reshuffled = False
        self.displayed_count += HI_LO_VALUES[card.rank]
        count = self.displayed_count
        self.count_lbl.configure(text=f"Count: {count:+d}" if count else "Count: 0")

    # ------------------------------------------------------------------ deck visual
    def _draw_deck(self):
        """Same "DECK" label + card-back glyph BlackjackFrame's own
        _draw_deck draws, plus two things standard Blackjack has no need
        for: a solid fill rising from the bottom of the box as the shoe is
        dealt down (self.game.shoe.cards_remaining() -- see
        Deck.cards_remaining, unused anywhere else in the app until now),
        and a fixed red line marking RESHUFFLE_PENETRATION -- where the fill
        will reach right when the shoe reshuffles. Unlike the count, this
        tracks the shoe's own true, instant state rather than lagging to
        match the reveal animations -- the physical shoe empties in real
        time as cards are dealt, whether or not the player's actually seen
        each one yet."""
        tag = "deck"
        felt_theme = self.app.settings.theme()
        self.canvas.create_text(DECK_X1 + CARD_WIDTH / 2, DECK_LABEL_Y, text="DECK", fill=theme.FG_DIM,
                                 font=theme.font(9, weight="bold"), tags=(tag,))
        draw_card_back(self.canvas, DECK_X1, DECK_Y, self._current_felt, felt_theme["accent"], tags=(tag,))

        total = self.game.shoe.num_decks * 52
        dealt = total - self.game.shoe.cards_remaining()
        fill_h = CARD_HEIGHT * min(1.0, dealt / total)
        if fill_h > 0:
            # Fills bottom-up, drawn on top of the card back (no alpha
            # blending on a Tk canvas -- this is what makes the box read as
            # "filling up" rather than just tinting it).
            self.canvas.create_rectangle(
                DECK_X1, DECK_Y + CARD_HEIGHT - fill_h, DECK_X1 + CARD_WIDTH, DECK_Y + CARD_HEIGHT,
                fill=felt_theme["accent"], outline="", tags=(tag,),
            )
            # Redraw the border crisp on top of the fill block.
            self.canvas.create_rectangle(
                DECK_X1, DECK_Y, DECK_X1 + CARD_WIDTH, DECK_Y + CARD_HEIGHT,
                outline=felt_theme["accent"], width=2, tags=(tag,),
            )
        # Fixed at the (1 - RESHUFFLE_PENETRATION) mark from the top -- where
        # the rising fill will sit once the shoe is due to reshuffle -- drawn
        # last so it's always visible above the fill.
        line_y = DECK_Y + CARD_HEIGHT * (1 - RESHUFFLE_PENETRATION)
        self.canvas.create_line(
            DECK_X1, line_y, DECK_X1 + CARD_WIDTH, line_y, fill=theme.LOSE_COLOR, width=2, tags=(tag,),
        )
