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

from ui import theme


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


def _draw_mahjong_dragon_tile(canvas, cx, cy, size, color, glyph):
    """A mahjong tile face -- a portrait rounded-rect outline with a
    slightly inset bevel line (the raised-edge look a real mahjong tile
    has) and one Chinese character centred inside. Shared by the two
    dragon tiles Pai Gow Poker and its Face Up variant are each named
    after -- see draw_pai_gow_icon (Red Dragon, 中) and
    draw_pai_gow_face_up_icon (Green Dragon, 發)."""
    tile_w, tile_h = size * 0.62, size * 0.88
    x1, y1 = cx - tile_w / 2, cy - tile_h / 2
    x2, y2 = cx + tile_w / 2, cy + tile_h / 2
    theme.rounded_rect(canvas, x1, y1, x2, y2, radius=size * 0.1, outline=color, fill="", width=2)
    inset = size * 0.08
    theme.rounded_rect(canvas, x1 + inset, y1 + inset, x2 - inset, y2 - inset,
                        radius=size * 0.06, outline=color, fill="", width=1)
    canvas.create_text(cx, cy, text=glyph, fill=color, font=("Helvetica", round(size * 0.38), "bold"))


def draw_pai_gow_icon(canvas, cx, cy, size, color):
    """The Red Dragon mahjong tile (中, "centre") -- Pai Gow's own
    traditional Chinese-tile origins, and the "Fortune" variant's own
    icon here (see draw_pai_gow_face_up_icon's paired Green Dragon)."""
    _draw_mahjong_dragon_tile(canvas, cx, cy, size, color, "中")


def draw_pai_gow_face_up_icon(canvas, cx, cy, size, color):
    """The Green Dragon mahjong tile (發, "fortune") -- Face Up Pai Gow's
    own icon, paired with (but visually distinct from) standard Pai Gow
    Poker's Red Dragon tile above."""
    _draw_mahjong_dragon_tile(canvas, cx, cy, size, color, "發")


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


def draw_ultimate_texas_holdem_icon(canvas, cx, cy, size, color):
    """A cowboy hat -- Ultimate Texas Hold'em's namesake state, simple and
    unmistakable as line art even at icon size."""
    brim_w, brim_h = size * 0.95, size * 0.16
    brim_y = cy + size * 0.18
    canvas.create_oval(cx - brim_w / 2, brim_y - brim_h / 2, cx + brim_w / 2, brim_y + brim_h / 2,
                        outline=color, width=2)
    crown_w, crown_h = size * 0.5, size * 0.42
    crown_top = brim_y - crown_h
    canvas.create_polygon(
        cx - crown_w / 2, brim_y,
        cx - crown_w / 2 + size * 0.06, crown_top + size * 0.05,
        cx - crown_w * 0.15, crown_top,
        cx + crown_w * 0.15, crown_top,
        cx + crown_w / 2 - size * 0.06, crown_top + size * 0.05,
        cx + crown_w / 2, brim_y,
        outline=color, fill="", width=2, smooth=True, joinstyle="round",
    )
    canvas.create_line(cx - crown_w / 2 + size * 0.03, brim_y - size * 0.07,
                        cx + crown_w / 2 - size * 0.03, brim_y - size * 0.07,
                        fill=color, width=2)  # hat band


def draw_high_card_flush_icon(canvas, cx, cy, size, color):
    """Three fanned cards sharing one suit pip -- a Flush is a shared-suit
    hand, and the larger pip on the centred, tallest card nods to the
    "High Card" half of the name (same fanned-card layout the Three Card
    Poker tile motif uses, just suited)."""
    w, h = size * 0.5, size * 0.78
    for i, dx in enumerate((-size * 0.22, 0, size * 0.22)):
        canvas.create_rectangle(cx + dx - w / 2, cy - h / 2, cx + dx + w / 2, cy + h / 2,
                                 outline=color, width=2)
        pip_size = 11 if i == 1 else 8
        canvas.create_text(cx + dx, cy, text="♠", fill=color, font=("Helvetica", pip_size, "bold"))


def draw_padlock(canvas, cx, cy, size, color, locked=True):
    """A padlock badge -- the game tiles' lock-status indicator (see
    ui/main_menu.py, core/unlocks.py): a rounded body with a keyhole, and a
    thin-lined shackle looping over the top -- closed when locked, swung
    open to one side (pivoting on its still-seated left leg) when unlocked.
    Modelled on a classic flat padlock glyph (thin strokes, rounded
    corners) rather than a solid-filled silhouette. `cy` is the body's own
    centre -- callers need to leave roughly 1.3x `size` of clear room
    *above* it too, for the shackle's loop."""
    stroke = max(0.6, size * 0.035)

    body_w, body_h = size * 0.66, size * 0.5
    body_r = size * 0.09
    body_top = cy - body_h * 0.35
    body_bottom = body_top + body_h
    x1, x2 = cx - body_w / 2, cx + body_w / 2
    theme.rounded_rect(canvas, x1, body_top, x2, body_bottom, radius=body_r,
                        outline=color, fill="", width=stroke)

    # Keyhole -- a small circle over a downward-tapering wedge, the one
    # detail that reads as "padlock" rather than just "rounded box".
    keyhole_r = size * 0.06
    keyhole_cy = body_top + body_h * 0.4
    canvas.create_oval(cx - keyhole_r, keyhole_cy - keyhole_r, cx + keyhole_r, keyhole_cy + keyhole_r,
                        outline=color, width=stroke * 0.85)
    wedge_top_w, wedge_bottom_w, wedge_h = keyhole_r * 0.85, keyhole_r * 0.3, size * 0.12
    wedge_top_y = keyhole_cy + keyhole_r * 0.6
    canvas.create_polygon(
        cx - wedge_top_w, wedge_top_y, cx + wedge_top_w, wedge_top_y,
        cx + wedge_bottom_w, wedge_top_y + wedge_h, cx - wedge_bottom_w, wedge_top_y + wedge_h,
        outline=color, fill="", width=stroke * 0.85, joinstyle="round",
    )

    # Shackle -- a rounded loop (arc + two straight legs) seated into the
    # body's top edge.
    shackle_r = body_w * 0.32
    leg_h = size * 0.24
    leg_bottom = body_top + size * 0.05
    if locked:
        arc_top = body_top - leg_h - shackle_r
        canvas.create_arc(cx - shackle_r, arc_top, cx + shackle_r, arc_top + shackle_r * 2,
                           start=0, extent=180, style="arc", outline=color, width=stroke)
        canvas.create_line(cx - shackle_r, arc_top + shackle_r, cx - shackle_r, leg_bottom,
                            fill=color, width=stroke)
        canvas.create_line(cx + shackle_r, arc_top + shackle_r, cx + shackle_r, leg_bottom,
                            fill=color, width=stroke)
    else:
        # Swung open, pivoting on the left leg -- the loop lifts and tilts
        # clear to the right, the universal "unlocked" tell. Currently
        # unused (see ui/main_menu.py -- only a locked tile gets a badge at
        # all), kept for whenever an unlocked badge is wanted again.
        shift, lift = shackle_r * 0.55, size * 0.1
        arc_top = body_top - leg_h - shackle_r - lift
        arc_cx = cx - shift
        canvas.create_arc(arc_cx - shackle_r, arc_top, arc_cx + shackle_r, arc_top + shackle_r * 2,
                           start=0, extent=165, style="arc", outline=color, width=stroke)
        canvas.create_line(arc_cx - shackle_r * math.cos(math.radians(15)),
                            arc_top + shackle_r - shackle_r * math.sin(math.radians(15)),
                            cx - shackle_r * 0.78, leg_bottom, fill=color, width=stroke)


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
