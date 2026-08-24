"""
A collapsible bordered panel: a "$ ..." header with a ▸/▾ chevron that
toggles a body Frame between shown and hidden. Shared by ui/settings_screen.py
(each section gated behind an admin password the first time it's opened) and
ui/stats_screen.py (no gating, just plain expand/collapse, and Lifetime Stats
starts already open) -- both wanted the identical bordered-panel/chevron/
header look, just with different rules for whether a click is allowed to
actually expand the section.
"""
import tkinter as tk

from ui import theme


def make_collapsible(parent, title_text, pady=(24, 0), bg=None, border=None, fg=None,
                      before_expand=None, start_expanded=False, reset_list=None):
    """Builds the panel and returns the body Frame -- pack the section's real
    content into that, nothing about expanding/collapsing it is the caller's
    job from there.

    `before_expand`, if given, is called (no args) right before the body
    would be shown; if it returns falsy the section stays collapsed instead
    (Settings' password gate). Left as None, a click always expands.

    `start_expanded=True` builds the panel already open (Stats' Lifetime
    panel) rather than the usual collapsed-until-clicked default.

    `reset_list`, if given, has this section's "reset to its default
    open/closed state" function appended -- a caller managing several
    sections can then just call each one (e.g. every time its screen is
    shown) to put them all back where a fresh visit should find them,
    without needing to know which ones default open vs. closed.
    """
    bg = bg or theme.BG_ELEVATED
    border = border or theme.BORDER
    fg = fg or theme.ACCENT

    panel = tk.Frame(parent, bg=bg, highlightbackground=border, highlightthickness=1)
    panel.pack(fill="x", pady=pady)

    header = tk.Frame(panel, bg=bg, cursor="hand2")
    header.pack(fill="x", padx=26, pady=16)
    chevron = tk.Label(header, text="▾" if start_expanded else "▸", bg=bg, fg=fg,
                        font=theme.font(11, weight="bold"), cursor="hand2")
    chevron.pack(side="left", padx=(0, 10))
    title_lbl = tk.Label(header, text=title_text, bg=bg, fg=fg,
                          font=theme.font(13, weight="bold"), cursor="hand2")
    title_lbl.pack(side="left")

    body = tk.Frame(panel, bg=bg)
    body_pack_opts = dict(fill="x", padx=26, pady=(0, 22))
    if start_expanded:
        body.pack(**body_pack_opts)

    def collapse():
        body.pack_forget()
        chevron.configure(text="▸")

    def expand():
        body.pack(**body_pack_opts)
        chevron.configure(text="▾")

    def toggle(_event=None):
        if body.winfo_ismapped():
            collapse()
        elif before_expand is None or before_expand():
            expand()

    for widget in (header, chevron, title_lbl):
        widget.bind("<Button-1>", toggle)

    if reset_list is not None:
        reset_list.append(expand if start_expanded else collapse)
    return body
