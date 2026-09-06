"""
A transient, non-blocking "Achievement Unlocked" banner shown over whichever
screen (a game, or Cashier) is currently active. place()'d directly on that
screen's own Frame -- never a tk.Toplevel (see ui/dialogs.py's
_TerminalDialog, reserved for modal/blocking popups; the player is still
mid-game here, this must never grab focus or block input). Styled with
theme.recessed_panel (the same double-bordered look every game's own ROUND
RESULT/PAYTABLE panel already uses) and theme.pill (the "+N Crowns" badge).

Multiple achievements earned at once (e.g. one round crossing both a hands
milestone and a streak threshold) are queued and shown one at a time, each
getting its own clear moment, rather than stacking or combining them.
"""
import tkinter as tk

from ui import theme

WIDTH, HEIGHT = 420, 110
HOLD_MS = 3200

_state = {}  # id(frame) -> {"pending": [Achievement, ...], "widget": Canvas | None}


def queue(frame, app, achievements):
    """Enqueue one or more newly-earned Achievements to show over `frame`.
    Safe to call repeatedly, or with an empty/falsy `achievements` (a no-op
    then) -- every settle-hook call site passes whatever its own check
    calls returned, without needing its own truthiness guard first."""
    if not achievements:
        return
    entry = _state.setdefault(id(frame), {"pending": [], "widget": None})
    entry["pending"].extend(achievements)
    if entry["widget"] is None:
        _show_next(frame, app, entry)


def _show_next(frame, app, entry):
    if not entry["pending"]:
        _state.pop(id(frame), None)
        return
    achievement = entry["pending"].pop(0)
    entry["widget"] = _build(frame, achievement)

    def dismiss():
        entry["widget"].destroy()
        entry["widget"] = None
        _show_next(frame, app, entry)

    # Same "respect the animations setting" idiom as every game's own
    # _after_delay -- collapses to an instant walk through the whole queue
    # when animations are off, rather than a real multi-second hold.
    if app.settings.get("animations_enabled"):
        frame.after(HOLD_MS, dismiss)
    else:
        dismiss()


def _build(frame, achievement):
    canvas = tk.Canvas(frame, width=WIDTH, height=HEIGHT, bg=theme.BG_ELEVATED, highlightthickness=0)
    canvas.place(relx=0.5, rely=0.09, anchor="n")
    # Canvas overrides both .lift() and .tkraise() to mean the canvas-ITEM
    # op (an alias for tag_raise, which needs a tag/id argument) -- Misc's
    # widget-stacking tkraise has to be reached explicitly, unbound, to
    # raise the banner itself above its siblings.
    tk.Misc.tkraise(canvas)
    theme.recessed_panel(canvas, 0, 0, WIDTH, HEIGHT, title="ACHIEVEMENT UNLOCKED", outline=theme.SECONDARY)
    canvas.create_text(20, 50, text=achievement.name, fill=theme.FG,
                        font=theme.font(13, weight="bold"), anchor="w")
    canvas.create_text(20, 74, text=achievement.description, fill=theme.FG_DIM,
                        font=theme.font(9), anchor="w", width=WIDTH - 140, justify="left")
    theme.pill(canvas, WIDTH - 55, 28, f"+{achievement.crowns} Crowns",
               fill=theme.SECONDARY_DIM_BG_ELEVATED, outline=theme.SECONDARY, text_fg=theme.SECONDARY)
    return canvas
