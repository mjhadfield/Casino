"""
Small vector icons for the main menu's game tiles.

Pure tkinter canvas drawing (no image assets) -- the same approach as
ui/card_widgets.py -- rather than system emoji glyphs. Text-emoji glyphs
render at wildly inconsistent sizes across platforms/fonts (a card emoji and
a dice emoji at the same point size can differ by a factor of two), which is
what made the old menu's tile icons look mismatched. Drawing every icon
ourselves, centred in the same fixed-size box, guarantees they all read as
the same size regardless of what's installed on the machine running the app.

Each draw_* function takes a Canvas, a centre point, a size (its bounding
box is roughly `size` x `size`) and a colour, and draws centred there --
nothing else about the canvas is assumed, so main_menu.py just needs to pick
a spot and a size. To add a new game's tile, add one draw_* function here
and reference it from main_menu.py's GAMES list.
"""
import math


def draw_three_card_poker_icon(canvas, cx, cy, size, color):
    """Two fanned playing cards -- a plain card motif for the one game
    that isn't a themed vector icon elsewhere (kept for completeness/tiles
    that want a generic "cards" icon; the main menu itself keeps Three Card
    Poker's original glyph icon rather than using this)."""
    w, h = size * 0.55, size * 0.85
    for angle, dx in ((-1, -size * 0.12), (1, size * 0.12)):
        canvas.create_rectangle(cx + dx - w / 2, cy - h / 2, cx + dx + w / 2, cy + h / 2,
                                 outline=color, width=2)


def draw_blackjack_icon(canvas, cx, cy, size, color):
    """A card with '21' -- blackjack's namesake number."""
    w, h = size * 0.72, size
    canvas.create_rectangle(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2,
                             outline=color, width=2)
    canvas.create_text(cx, cy, text="21", fill=color, font=("Helvetica", round(size * 0.42), "bold"))


def draw_pai_gow_icon(canvas, cx, cy, size, color):
    """Two overlapping Chinese domino tiles with pips -- "Pai Gow" is named
    for the tile game; the poker variant keeps the tiles as its visual
    shorthand."""
    tw, th = size * 0.42, size * 0.78
    for ox, oy in ((-size * 0.16, size * 0.10), (size * 0.16, -size * 0.10)):
        x1, y1 = cx - tw / 2 + ox, cy - th / 2 + oy
        x2, y2 = cx + tw / 2 + ox, cy + th / 2 + oy
        canvas.create_rectangle(x1, y1, x2, y2, outline=color, width=2)
        canvas.create_line(x1, cy + oy, x2, cy + oy, fill=color, width=1)  # tile's halfway divider
        pip_r = size * 0.045
        for px, py in ((-0.09, -0.16), (0.09, -0.16), (-0.09, 0.16), (0.09, 0.16)):
            pcx, pcy = cx + ox + px * size, cy + oy + py * size
            canvas.create_oval(pcx - pip_r, pcy - pip_r, pcx + pip_r, pcy + pip_r, fill=color, outline="")


def draw_mississippi_stud_icon(canvas, cx, cy, size, color):
    """A paddle-wheel riverboat -- the "Mississippi" in Mississippi Stud,
    and distinct enough from the card-shaped icons not to blend in with
    the rest of the row."""
    hull_w, hull_h = size * 0.9, size * 0.28
    hull_top = cy + size * 0.06
    canvas.create_polygon(
        cx - hull_w / 2, hull_top,
        cx + hull_w / 2, hull_top,
        cx + hull_w * 0.38, hull_top + hull_h,
        cx - hull_w * 0.38, hull_top + hull_h,
        outline=color, fill="", width=2,
    )
    cab_w, cab_h = size * 0.4, size * 0.2
    canvas.create_rectangle(cx - cab_w / 2, hull_top - cab_h, cx + cab_w / 2, hull_top, outline=color, width=2)
    canvas.create_line(cx, hull_top - cab_h, cx, hull_top - cab_h - size * 0.18, fill=color, width=2)  # smokestack

    wheel_cx, wheel_cy, wheel_r = cx + hull_w / 2 + size * 0.06, hull_top + hull_h * 0.4, size * 0.22
    canvas.create_oval(wheel_cx - wheel_r, wheel_cy - wheel_r, wheel_cx + wheel_r, wheel_cy + wheel_r,
                        outline=color, width=2)
    for angle in range(0, 360, 45):
        rad = math.radians(angle)
        canvas.create_line(wheel_cx, wheel_cy,
                            wheel_cx + wheel_r * math.cos(rad), wheel_cy + wheel_r * math.sin(rad),
                            fill=color, width=1)

    canvas.create_line(cx - size * 0.5, hull_top + hull_h + size * 0.1,
                        cx + size * 0.5, hull_top + hull_h + size * 0.1, fill=color, width=1)  # waterline


def draw_baccarat_icon(canvas, cx, cy, size, color):
    """A diamond emblem with '9' -- baccarat hands are scored to a maximum
    of 9, and the diamond reads as a touch more upmarket, matching the
    game's reputation at the high-stakes end of the floor."""
    r = size * 0.52
    canvas.create_polygon(cx, cy - r, cx + r * 0.72, cy, cx, cy + r, cx - r * 0.72, cy,
                           outline=color, fill="", width=2)
    canvas.create_text(cx, cy, text="9", fill=color, font=("Helvetica", round(size * 0.42), "bold"))


def draw_let_it_ride_icon(canvas, cx, cy, size, color):
    """Three chips in a row under a forward arrow -- Let It Ride's three
    equal starter bets, which the player either pulls back or "rides"
    onward as more cards are revealed."""
    chip_r = size * 0.14
    chip_y = cy + size * 0.2
    for dx in (-size * 0.28, 0, size * 0.28):
        canvas.create_oval(cx + dx - chip_r, chip_y - chip_r, cx + dx + chip_r, chip_y + chip_r,
                            outline=color, width=2)
    ax1, ax2, ay = cx - size * 0.32, cx + size * 0.22, cy - size * 0.22
    canvas.create_line(ax1, ay, ax2, ay, fill=color, width=2)
    canvas.create_line(ax2, ay, ax2 - size * 0.12, ay - size * 0.1, fill=color, width=2)
    canvas.create_line(ax2, ay, ax2 - size * 0.12, ay + size * 0.1, fill=color, width=2)
