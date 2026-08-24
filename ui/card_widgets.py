"""
Canvas-drawing helpers for playing cards. Pure tkinter (no image assets),
so any game in the library can render a hand with a couple of function
calls instead of re-implementing card art.
"""

CARD_WIDTH = 70
CARD_HEIGHT = 100


def _card_tags(tags):
    """Every card item always carries the shared "cards" tag (so a caller can
    still do canvas.delete("cards") to clear every card at once); `tags`
    optionally adds more on top -- e.g. a per-card tag so a single card can
    be selectively deleted/redrawn for an animation frame."""
    if not tags:
        return ("cards",)
    if isinstance(tags, str):
        tags = (tags,)
    return ("cards", *tags)


def draw_card(canvas, x, y, card, width=CARD_WIDTH, height=CARD_HEIGHT, tags=()):
    """Draws a face-up card at (x, y) on the given tkinter Canvas: the rank in
    two opposite corners and one decent-sized suit icon in the centre.

    Text size and corner margins scale with `height`/`width` relative to the
    default CARD_WIDTH/CARD_HEIGHT (identical output at the defaults -- the
    scaling is a no-op there), so a smaller card -- e.g. Three Card Poker's
    bet-indicator "resting" cards -- still reads cleanly instead of full-size
    rank/suit text overflowing a shrunken rectangle."""
    tags = _card_tags(tags)
    text_color = "#c0392b" if card.color == "red" else "#1a1a1a"
    corner_font = max(8, round(13 * height / CARD_HEIGHT))
    symbol_font = max(10, round(55 * height / CARD_HEIGHT))
    margin_x = 6 * width / CARD_WIDTH
    margin_y = 5 * height / CARD_HEIGHT
    canvas.create_rectangle(
        x, y, x + width, y + height,
        fill="#fdfdf5", outline="#222222", width=2, tags=tags,
    )
    canvas.create_text(
        x + margin_x, y + margin_y, text=card.rank, font=("Helvetica", corner_font, "bold"),
        fill=text_color, anchor="nw", tags=tags,
    )
    canvas.create_text(
        x + width - margin_x, y + height - margin_y, text=card.rank,
        font=("Helvetica", corner_font, "bold"), fill=text_color, anchor="se", tags=tags,
    )
    canvas.create_text(
        x + width / 2, y + height / 2, text=card.symbol,
        font=("Helvetica", symbol_font), fill=text_color, tags=tags,
    )


def draw_card_back(canvas, x, y, felt, accent="#35e0a0", width=CARD_WIDTH, height=CARD_HEIGHT, tags=()):
    """Draws a face-down card back at (x, y). Scales the same way draw_card
    does -- see its docstring.

    `felt`/`accent` are the caller's *current* table-felt theme colours
    (games/three_card_poker/ui.py tracks `self._current_felt` and reads
    `self.app.settings.theme()["accent"]` for exactly this) -- required
    rather than defaulted, so a card back always matches whichever felt
    theme is actually active instead of a stale hardcoded green/gold."""
    tags = _card_tags(tags)
    inset = 6 * min(width / CARD_WIDTH, height / CARD_HEIGHT)
    symbol_font = max(8, round(20 * height / CARD_HEIGHT))
    canvas.create_rectangle(
        x, y, x + width, y + height,
        fill=felt, outline=accent, width=2, tags=tags,
    )
    canvas.create_rectangle(
        x + inset, y + inset, x + width - inset, y + height - inset,
        outline=accent, width=1, tags=tags,
    )
    canvas.create_text(
        x + width / 2, y + height / 2, text="♠",
        font=("Helvetica", symbol_font), fill=accent, tags=tags,
    )
