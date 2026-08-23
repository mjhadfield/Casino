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
    two opposite corners and one decent-sized suit icon in the centre."""
    tags = _card_tags(tags)
    text_color = "#c0392b" if card.color == "red" else "#1a1a1a"
    canvas.create_rectangle(
        x, y, x + width, y + height,
        fill="#fdfdf5", outline="#222222", width=2, tags=tags,
    )
    canvas.create_text(
        x + 6, y + 5, text=card.rank, font=("Helvetica", 13, "bold"),
        fill=text_color, anchor="nw", tags=tags,
    )
    canvas.create_text(
        x + width - 6, y + height - 5, text=card.rank,
        font=("Helvetica", 13, "bold"), fill=text_color, anchor="se", tags=tags,
    )
    canvas.create_text(
        x + width / 2, y + height / 2, text=card.symbol,
        font=("Helvetica", 55), fill=text_color, tags=tags,
    )


def draw_card_back(canvas, x, y, accent="#d4af37", width=CARD_WIDTH, height=CARD_HEIGHT, tags=()):
    """Draws a face-down card back at (x, y)."""
    tags = _card_tags(tags)
    canvas.create_rectangle(
        x, y, x + width, y + height,
        fill="#0b3d24", outline=accent, width=2, tags=tags,
    )
    canvas.create_rectangle(
        x + 6, y + 6, x + width - 6, y + height - 6,
        outline=accent, width=1, tags=tags,
    )
    canvas.create_text(
        x + width / 2, y + height / 2, text="♠",
        font=("Helvetica", 20), fill=accent, tags=tags,
    )
