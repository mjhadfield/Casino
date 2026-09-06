"""
Canvas-drawing helpers for playing cards. Pure tkinter (no image assets),
so any game in the library can render a hand with a couple of function
calls instead of re-implementing card art.

A card's STYLE -- its front colours/outline effect, and its own back look
-- is always passed in explicitly by the caller as a resolved `style` dict
(core/settings.py's SettingsManager.card_style()), the exact same
convention this module's own `felt`/`accent` params already follow for a
table's own felt colours -- kept that way rather than a module-level
global so this module stays exactly as decoupled from app/session state as
it's always been (every game's own ui.py caches the current style
alongside its own `_current_felt`, refreshed at the same points). `style=
None` (the default) falls back to DEFAULT_CARD_STYLE below, so a call site
that hasn't been threaded through yet still renders something reasonable
rather than raising.

Every style dict shares one shape:
  front_bg/front_border -- the card face's own background/border colour.
  text_black/text_red    -- rank+suit colour for a black-suited/red-suited
                             card respectively (never card.color itself --
                             that only ever says "red" or "black").
  text_blue/text_green    -- diamonds'/clubs' own colour when the Four
                             Colour Deck feature (core/unlocks.py's
                             PREMIUM_FEATURES) is active for this card --
                             see the `four_colour` key below. Present on
                             every style precisely so a style can still be
                             picked as `style=None`/DEFAULT_CARD_STYLE
                             without draw_card ever needing a fallback for
                             a missing key; unused, like text_black/
                             text_red, unless a card's own suit calls for it.
  four_colour              -- not part of a style's own identity (never set
                             by STANDARD_CARD_STYLES/PREMIUM_CARD_STYLES
                             themselves) -- folded in as an extra key by
                             AchievementsManager.resolve_card_style() when
                             the player owns AND has enabled the feature.
                             Kept on the style dict rather than threaded as
                             its own draw_card() parameter so none of this
                             module's ~150 existing call sites (every game's
                             own ui.py) need to change to support it.
  outline                 -- None for a plain front (Light's own look), or
                             a colour for a front-highlight treatment: just
                             an inner accent border a little inside the
                             card's own edge (see draw_card). Every rank/
                             suit glyph is still drawn exactly once, in its
                             own plain fill colour -- deliberately NOT
                             touched by `outline` at all. Two earlier
                             attempts here both got walked back: outlining
                             the glyphs themselves (repeated offset copies
                             behind each one) read as blur rather than a
                             crisp highlight, and a decorative emblem
                             behind the centre suit symbol just clashed
                             with it rather than complementing it.
  back                    -- {"kind": "felt"} to reuse the caller's own
                             live felt/accent exactly as before (every
                             standard style); {"kind": "fancy", "bg",
                             "trim", "emblem"} for a premium style's own
                             self-contained, felt-INDEPENDENT back design
                             (see _draw_fancy_back) -- a premium back is a
                             cosmetic identity that should look the same
                             regardless of which table felt happens to be
                             active, unlike a standard style's own back.
"""
import math

from core.cards import Suit

CARD_WIDTH = 70
CARD_HEIGHT = 100

DEFAULT_CARD_STYLE = {
    "front_bg": "#fdfdf5",
    "front_border": "#222222",
    "text_black": "#1a1a1a",
    "text_red": "#ad291b",
    "text_blue": "#1f5fa8",
    "text_green": "#1f7a3d",
    "outline": None,
    "back": {"kind": "felt"},
}

# suit -> the style key its rank/suit text uses when four_colour is active
# (see draw_card's own _suit_text_color). Spades/hearts are left out --
# they fall through to the same text_black/text_red every style already
# had, four_colour or not.
_FOUR_COLOUR_KEYS = {Suit.DIAMONDS: "text_blue", Suit.CLUBS: "text_green"}


def _suit_text_color(style, card):
    if style.get("four_colour"):
        key = _FOUR_COLOUR_KEYS.get(card.suit)
        if key and key in style:
            return style[key]
    return style["text_red"] if card.color == "red" else style["text_black"]


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


def draw_card(canvas, x, y, card, width=CARD_WIDTH, height=CARD_HEIGHT, tags=(), style=None):
    """Draws a face-up card at (x, y) on the given tkinter Canvas: the rank in
    two opposite corners and one decent-sized suit icon in the centre.

    Text size and corner margins scale with `height`/`width` relative to the
    default CARD_WIDTH/CARD_HEIGHT (identical output at the defaults -- the
    scaling is a no-op there), so a smaller card -- e.g. Three Card Poker's
    bet-indicator "resting" cards -- still reads cleanly instead of full-size
    rank/suit text overflowing a shrunken rectangle.

    A Joker (Pai Gow Poker's 53rd card -- see core.cards) has no rank/suit to
    print, so it gets its own distinct face here rather than falling through
    to the rank/suit-pip rendering below, which would crash on its None
    suit -- no other game's cards can ever hit this branch. Deliberately
    NOT style-aware: gold-on-purple is already its own fixed, always-
    distinct identity regardless of which card style is active (the one
    card in the deck that must never be mistaken for a real rank/suit)."""
    if getattr(card, "is_joker", False):
        _draw_joker_face(canvas, x, y, width, height, tags)
        return
    style = style or DEFAULT_CARD_STYLE
    tags = _card_tags(tags)
    text_color = _suit_text_color(style, card)
    outline = style.get("outline")
    corner_font = max(8, round(13 * height / CARD_HEIGHT))
    symbol_font = max(10, round(55 * height / CARD_HEIGHT))
    # An outlined style draws its own inner accent border a little inside
    # the card's edge (see below) -- the corner rank needs the bigger 10/9
    # margin to clear it and not sit flush against it. A plain style (no
    # border to clear) keeps the original 6/5 -- unconditionally widening
    # this would just push the corner in further than it needs to go on
    # every style that was already fine as it was.
    margin_x = (10 if outline else 6) * width / CARD_WIDTH
    margin_y = (9 if outline else 5) * height / CARD_HEIGHT
    canvas.create_rectangle(
        x, y, x + width, y + height,
        fill=style["front_bg"], outline=style["front_border"], width=2, tags=tags,
    )
    if outline:
        # The highlight itself: just an inner accent border a little inside
        # the card's own edge. An earlier version also put an emblem shape
        # behind the centre suit symbol (reusing the style's own "fancy"
        # back emblem) -- dropped, since sitting directly behind the suit
        # icon it was drawn on top of, it just clashed with it rather than
        # reading as a highlight.
        inset = 6 * min(width / CARD_WIDTH, height / CARD_HEIGHT)
        canvas.create_rectangle(x + inset, y + inset, x + width - inset, y + height - inset,
                                 outline=outline, width=1, tags=tags)
    canvas.create_text(x + margin_x, y + margin_y, text=card.rank, font=("Helvetica", corner_font, "bold"),
                        fill=text_color, anchor="nw", tags=tags)
    canvas.create_text(x + width - margin_x, y + height - margin_y, text=card.rank,
                        font=("Helvetica", corner_font, "bold"), fill=text_color, anchor="se", tags=tags)
    canvas.create_text(x + width / 2, y + height / 2, text=card.symbol, font=("Helvetica", symbol_font),
                        fill=text_color, tags=tags)


def _draw_joker_face(canvas, x, y, width, height, tags):
    """The Joker's own face -- gold on deep purple, clearly distinct from
    every real rank/suit (no suit pip, no red/black rank text) so it reads
    at a glance as the one card in the deck that isn't a normal playing
    card. Scales the same way draw_card's own rank/suit text does."""
    tags = _card_tags(tags)
    gold = "#e0b040"
    corner_font = max(7, round(11 * height / CARD_HEIGHT))
    star_font = max(10, round(50 * height / CARD_HEIGHT))
    margin_x = 6 * width / CARD_WIDTH
    margin_y = 5 * height / CARD_HEIGHT
    canvas.create_rectangle(
        x, y, x + width, y + height,
        fill="#2a1240", outline=gold, width=2, tags=tags,
    )
    for cx, cy, anchor in ((x + margin_x, y + margin_y, "nw"), (x + width - margin_x, y + height - margin_y, "se")):
        canvas.create_text(cx, cy, text="JKR", font=("Helvetica", corner_font, "bold"),
                            fill=gold, anchor=anchor, tags=tags)
    canvas.create_text(
        x + width / 2, y + height / 2, text="★",  # ★
        font=("Helvetica", star_font), fill=gold, tags=tags,
    )


def draw_card_back(canvas, x, y, felt, accent="#35e0a0", width=CARD_WIDTH, height=CARD_HEIGHT, tags=(), style=None):
    """Draws a face-down card back at (x, y). Scales the same way draw_card
    does -- see its docstring.

    `felt`/`accent` are the caller's *current* table-felt theme colours
    (games/three_card_poker/ui.py tracks `self._current_felt` and reads
    `self.app.settings.theme()["accent"]` for exactly this) -- required
    rather than defaulted, so a card back always matches whichever felt
    theme is actually active instead of a stale hardcoded green/gold,
    UNLESS `style["back"]` says otherwise: {"kind": "felt"} (every standard
    style) uses them exactly as always; {"kind": "fancy", ...} (a premium
    style) ignores them entirely in favour of its own fixed, felt-
    independent design -- see _draw_fancy_back."""
    style = style or DEFAULT_CARD_STYLE
    back = style.get("back") or {"kind": "felt"}
    tags = _card_tags(tags)
    if back.get("kind") == "fancy":
        _draw_fancy_back(canvas, x, y, width, height, back, tags)
        return
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


def _draw_fancy_back(canvas, x, y, width, height, back, tags):
    """A premium card back's own self-contained design: a double border in
    `back["bg"]`/`back["trim"]` plus one centre emblem (see EMBLEM_DRAWERS)
    -- the same structure across every premium style, so adding a new one
    (core/unlocks.py's PREMIUM_CARD_STYLES) is just new colours and an
    emblem pick, never a bespoke drawing routine."""
    bg, trim = back["bg"], back["trim"]
    scale = min(width / CARD_WIDTH, height / CARD_HEIGHT)
    inset = 6 * scale
    inset2 = inset + 5 * scale
    canvas.create_rectangle(x, y, x + width, y + height, fill=bg, outline=trim, width=2, tags=tags)
    canvas.create_rectangle(x + inset, y + inset, x + width - inset, y + height - inset,
                             outline=trim, width=1, tags=tags)
    canvas.create_rectangle(x + inset2, y + inset2, x + width - inset2, y + height - inset2,
                             outline=trim, width=1, tags=tags)
    cx, cy = x + width / 2, y + height / 2
    size = min(width, height) * 0.2
    EMBLEM_DRAWERS.get(back.get("emblem"), _emblem_diamond)(canvas, cx, cy, size, trim, tags)


def _emblem_diamond(canvas, cx, cy, size, color, tags):
    canvas.create_polygon(cx, cy - size, cx + size, cy, cx, cy + size, cx - size, cy,
                           outline=color, fill="", width=2, tags=tags)


def _emblem_star(canvas, cx, cy, size, color, tags):
    points = []
    for i in range(10):
        r = size if i % 2 == 0 else size * 0.42
        angle = math.pi / 2 + i * math.pi / 5
        points.extend([cx + r * math.cos(angle), cy - r * math.sin(angle)])
    canvas.create_polygon(*points, outline=color, fill="", width=2, tags=tags)


def _emblem_hex(canvas, cx, cy, size, color, tags):
    points = []
    for i in range(6):
        angle = math.pi / 6 + i * math.pi / 3
        points.extend([cx + size * math.cos(angle), cy - size * math.sin(angle)])
    canvas.create_polygon(*points, outline=color, fill="", width=2, tags=tags)


def _emblem_ring(canvas, cx, cy, size, color, tags):
    """The fallback emblem for a style with no "fancy" back of its own to
    match (e.g. Dark, whose back stays felt-themed) -- a plain circle, the
    simplest shape that doesn't imply any particular back design."""
    canvas.create_oval(cx - size, cy - size, cx + size, cy + size, outline=color, width=2, tags=tags)


EMBLEM_DRAWERS = {"diamond": _emblem_diamond, "star": _emblem_star, "hex": _emblem_hex, "ring": _emblem_ring}
