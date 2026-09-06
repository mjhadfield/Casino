"""
A small floating hover tooltip -- shown centred directly on top of the
hovered group of widgets (both axes), destroyed once the mouse leaves all
of them. Built as a plain undecorated, non-modal Toplevel, the standard
Tkinter idiom for this -- a deliberately different case from
ui/achievement_banner.py's own "never a Toplevel" precedent: that one is
about avoiding Toplevel for in-flow content that belongs on the current
frame. A tooltip is the opposite kind of thing -- it must be able to float
outside its own widget's bounds (e.g. over a tile near the very edge of the
window, where a place()'d sibling widget couldn't reach) and it never
grabs focus or blocks input, which is exactly what a bare Toplevel is for.
"""
import tkinter as tk

from ui import theme

_active = {}  # id(anchor) -> Toplevel, so a group only ever has one tooltip open
_group_state = {}  # id(anchor) -> {"hovered": set(id(widget)), "hide_job": after-id|None}

# How long a <Leave> waits before actually hiding -- long enough for the
# matching <Enter> on a sibling widget in the same group to arrive first
# (crossing from one child of a tile to another fires Leave-then-Enter,
# both within the same event-processing pass), short enough that actually
# leaving the whole group still reads as instant.
HIDE_DELAY_MS = 60


def attach(widgets, text_fn):
    """Treats every widget in `widgets` (a single widget, or a list of
    them -- e.g. ui/game_tile.py's own status_widgets, a tile's outer Frame
    plus every child drawn on top of it) as ONE hoverable region: shown
    once when the mouse enters any of them, positioned centred on top of
    the group's overall bounding box (the first widget given -- for a game
    tile that's always the outer Frame, which already spans the tile's
    full size) on both axes, rather than following the cursor, and hidden
    only once the mouse has left all of them (debounced by HIDE_DELAY_MS
    so moving between two sibling widgets in the same group never flickers
    it closed and immediately reopens it elsewhere).

    `text_fn` is either a plain string, or a zero-arg callable returning
    one (or a falsy value, to show nothing that hover) -- called fresh on
    every single hover rather than once at attach time, since a locked
    tile's own required achievement can change without the tile itself
    being rebuilt (e.g. right after a different achievement fires).

    Since the tooltip is centred directly on top of the group (both axes),
    it visually covers part of it -- the moment the real cursor drifts onto
    the tooltip window itself, the widget underneath sees a <Leave>, same
    as leaving to anywhere else. Without special handling that would hide
    the tooltip, which re-exposes the widget, which re-fires <Enter>, which
    shows it again right back under the cursor -- an endless flicker. The
    fix: once shown, the tooltip's own window is added to this SAME group
    (bound with the same on_enter/on_leave below), so hovering onto it is
    just hovering another member of the group, not leaving it."""
    if isinstance(widgets, (list, tuple)):
        group = list(widgets)
    else:
        group = [widgets]
    anchor = group[0]
    state = _group_state.setdefault(id(anchor), {"hovered": set(), "hide_job": None})

    def on_enter(widget):
        def handler(_event):
            if state["hide_job"] is not None:
                # A pending hide from a moment ago (crossing from one
                # member of this same group to another -- another widget,
                # or the tooltip's own window) never actually fired --
                # cancel it and, crucially, don't re-show either: the
                # tooltip already on screen was never hidden, so showing
                # "again" here would destroy-and-recreate it (see _show's
                # own _hide-first line), which is exactly the flicker this
                # debounce exists to prevent.
                anchor.after_cancel(state["hide_job"])
                state["hide_job"] = None
            state["hovered"].add(id(widget))
            if id(anchor) not in _active:
                text = text_fn() if callable(text_fn) else text_fn
                if text:
                    tip = _show(anchor, text)
                    # The tooltip itself joins the group it's showing for --
                    # see this function's own docstring above.
                    tip.bind("<Enter>", on_enter(tip), add="+")
                    tip.bind("<Leave>", on_leave(tip), add="+")
        return handler

    def on_leave(widget):
        def handler(_event):
            state["hovered"].discard(id(widget))

            def maybe_hide():
                state["hide_job"] = None
                if not state["hovered"]:
                    _hide(anchor)

            if state["hide_job"] is not None:
                anchor.after_cancel(state["hide_job"])
            state["hide_job"] = anchor.after(HIDE_DELAY_MS, maybe_hide)
        return handler

    def on_destroy(widget):
        def handler(_event):
            state["hovered"].discard(id(widget))
            # Unconditional the moment the anchor itself goes (a tile grid
            # rebuild destroys it outright) -- not just "if nothing's
            # hovered any more": the tooltip's own window could still be
            # sitting in `hovered` (the cursor resting on it, never having
            # left), which would otherwise block this hide forever, since
            # nothing can generate a <Leave> for an anchor that no longer
            # exists to receive one.
            if widget is anchor or not state["hovered"]:
                _hide(anchor)
        return handler

    for w in group:
        w.bind("<Enter>", on_enter(w), add="+")
        w.bind("<Leave>", on_leave(w), add="+")
        # A hovered widget can be destroyed (e.g. a tile grid rebuild)
        # without ever getting its own <Leave> -- without this, that
        # tooltip would be left floating on screen forever with nothing
        # left to dismiss it. Not bound on the tooltip's own window itself
        # (see on_enter above) -- that one's only ever destroyed by our own
        # _hide(), never externally, so it needs no such safety net.
        w.bind("<Destroy>", on_destroy(w), add="+")


def _show(anchor, text):
    _hide(anchor)  # never more than one open for this group at a time
    tip = tk.Toplevel(anchor)
    tip.overrideredirect(True)
    tip.attributes("-topmost", True)
    tip.configure(bg=theme.SECONDARY)
    tk.Label(
        tip, text=text, bg=theme.BG_ELEVATED, fg=theme.FG, font=theme.font(9),
        wraplength=260, justify="left", padx=10, pady=6,
    ).pack(padx=1, pady=1)  # the SECONDARY bg behind shows through as a 1px border

    # Centred on the anchor (the group's own outer widget, e.g. a tile's
    # full-size Frame) on BOTH axes -- fixed to the group itself, not the
    # cursor, deliberately overlapping its content rather than sitting
    # below it.
    anchor.update_idletasks()
    tip.update_idletasks()
    anchor_cx = anchor.winfo_rootx() + anchor.winfo_width() // 2
    anchor_cy = anchor.winfo_rooty() + anchor.winfo_height() // 2
    x = anchor_cx - tip.winfo_width() // 2
    y = anchor_cy - tip.winfo_height() // 2
    tip.geometry(f"+{max(0, x)}+{max(0, y)}")
    _active[id(anchor)] = tip
    return tip


def _hide(anchor):
    tip = _active.pop(id(anchor), None)
    if tip is not None:
        tip.destroy()
