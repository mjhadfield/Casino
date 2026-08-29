"""
Custom modal dialogs styled to match the terminal aesthetic (ui/theme.py) --
used in place of tkinter.messagebox, whose native OS dialogs don't take any
of that styling and can't host a password field anyway.

Both entry points block (via wait_window) until the dialog closes and return
a plain bool, the same calling convention as messagebox.askyesno -- callers
don't need to know these are hand-built Toplevels rather than native ones.
"""
import tkinter as tk
import tkinter.font as tkfont
from typing import Any, Callable, cast

from ui import theme
from ui.scrollable import ScrollableFrame

# Gates any "admin" section anywhere in the app (Settings' Jackpot Config /
# Danger Zone, Cashier's override panel, ...) -- a placeholder password
# rather than a real auth system, per explicit request ("just be 'admin' for
# now"). See ensure_admin_unlocked below for how it's actually checked.
ADMIN_PASSWORD = "admin"


class _TerminalDialog(tk.Toplevel):
    """Shared chrome for both dialogs below: a bordered, dark, monospace
    popup centred on its parent, closable via Escape or the window manager's
    own close button (treated as Cancel either way)."""

    def __init__(self, parent, title, message, danger=False, accent=None):
        super().__init__(parent.winfo_toplevel())
        # Off-screen until run() has actually centred it -- a Toplevel maps
        # itself (at the WM's default placement, typically the screen's top
        # left) as soon as it has content, which otherwise flashes there for
        # a frame before the explicit geometry() below ever takes effect.
        # withdraw() would hide it just as well, but leaves it unmapped --
        # some widgets (a Text widget's wrapped line count, see document()
        # below) can't be measured correctly until they're actually
        # realized, so this stays mapped, just off the visible screen.
        _place_off_screen(self)
        # Really bool (confirm()/info()) or Optional[str] (choice()'s
        # returned option key) depending on which entry point built this --
        # Any rather than a narrower union so both call patterns can freely
        # assign to it without fighting the checker.
        self.result: Any = False
        border = accent or (theme.LOSE_COLOR if danger else theme.ACCENT)
        self.configure(bg=theme.BG_ELEVATED, highlightbackground=border, highlightthickness=2)
        self.overrideredirect(True)  # no OS title bar -- this is a small, self-contained popup
        self.resizable(False, False)

        body = tk.Frame(self, bg=theme.BG_ELEVATED)
        body.pack(padx=1, pady=1)

        tk.Label(
            body, text=title, bg=theme.BG_ELEVATED, fg=border,
            font=theme.font(12, weight="bold"), anchor="w",
        ).pack(fill="x", padx=20, pady=(18, 8))
        tk.Label(
            body, text=message, bg=theme.BG_ELEVATED, fg=theme.FG_DIM,
            font=theme.font(10), wraplength=320, justify="left", anchor="w",
        ).pack(fill="x", padx=20, pady=(0, 6))

        self.error_lbl = tk.Label(
            body, text="", bg=theme.BG_ELEVATED, fg=theme.LOSE_COLOR, font=theme.font(9),
        )
        self.error_lbl.pack(fill="x", padx=20)

        self.extra = tk.Frame(body, bg=theme.BG_ELEVATED)
        self.extra.pack(fill="x", padx=20, pady=(0, 4))

        button_row = tk.Frame(body, bg=theme.BG_ELEVATED)
        button_row.pack(fill="x", padx=20, pady=(10, 18))
        tk.Button(
            button_row, text="Cancel", bg=theme.GREY_BTN_BG, fg=theme.FG_DIM, relief="flat",
            font=theme.font(10), padx=14, pady=6, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.GREY_BTN_BORDER,
            command=self._cancel,
        ).pack(side="right")
        confirm_bg = theme.LOSE_DIM_BG_ELEVATED if danger else theme.ACCENT_DIM_BG_ELEVATED
        confirm_fg = theme.LOSE_COLOR if danger else theme.ACCENT
        self.confirm_btn = tk.Button(
            button_row, text="Confirm", bg=confirm_bg, fg=confirm_fg, relief="flat",
            font=theme.font(10, weight="bold"), padx=14, pady=6, cursor="hand2",
            highlightthickness=1, highlightbackground=confirm_fg,
            command=self._confirm,
        )
        self.confirm_btn.pack(side="right", padx=(0, 8))

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda _e: self._cancel())
        self.bind("<Return>", lambda _e: self._confirm())

    def _confirm(self):
        """Overridden by the password variant to validate before closing."""
        self.result = True
        self.destroy()

    def _cancel(self):
        self.result = False
        self.destroy()

    def run(self):
        _center_over_parent(self)
        # self.master is really the Tk/Toplevel passed to super().__init__
        # above, but Misc (its static type) is broader than what
        # wm_transient's stub accepts -- cast rather than widen the actual
        # runtime type.
        self.transient(cast(tk.Wm, self.master))
        self.grab_set()
        self.wait_window()
        return self.result


def _place_off_screen(win):
    """Maps `win` (a Toplevel) somewhere well outside the visible desktop
    instead of at whatever spot the WM would first put it -- used in place
    of withdraw() specifically because it keeps the window mapped/realized,
    which withdraw() doesn't: a withdrawn window can't correctly measure a
    Text widget's wrapped line count (document() below relies on this --
    Tk reports a wildly wrong number until the widget's actually been
    realized), even though plain Label sizing is unaffected either way."""
    win.geometry("+-4000+-4000")


def _center_over_parent(win):
    """Positions `win` (a Toplevel) centred over whichever window it was
    built on top of -- shared by every dialog here, including document()'s
    below, which isn't an instance of _TerminalDialog. Moves it on-screen
    (see the matching _place_off_screen when each of those was created)
    only now that it's actually in the right place, rather than wherever it
    was first mapped."""
    win.update_idletasks()
    parent = win.master
    x = parent.winfo_rootx() + (parent.winfo_width() - win.winfo_reqwidth()) // 2
    y = parent.winfo_rooty() + (parent.winfo_height() - win.winfo_reqheight()) // 2
    win.geometry(f"+{max(0, x)}+{max(0, y)}")


def confirm(parent, title, message, danger=False, confirm_text="Confirm"):
    """A styled yes/no dialog -- `title` is shown terminal-prompt style
    (e.g. "$ rm --stats --lifetime"), `message` is the plain-English
    explanation underneath. Returns True iff Confirm was clicked."""
    dialog = _TerminalDialog(parent, title, message, danger=danger)
    dialog.confirm_btn.configure(text=confirm_text)
    return dialog.run()


def info(parent, title, message, accent=None):
    """A single-button acknowledgement dialog -- the styled equivalent of
    messagebox.showinfo/showwarning, for after an action confirm() already
    gated, or for a plain "this isn't allowed" notice with nothing to
    confirm. `accent` defaults to the ordinary mint accent; pass
    theme.WARN for a warning-toned one (e.g. a rejected bet)."""
    dialog = _TerminalDialog(parent, title, message, accent=accent or theme.ACCENT)
    dialog.confirm_btn.configure(text="OK")
    for child in list(dialog.confirm_btn.master.winfo_children()):
        if child is not dialog.confirm_btn:
            child.destroy()  # drop the Cancel button -- nothing to cancel
    dialog.confirm_btn.pack(side="right")
    dialog.run()


def confirm_with_password(parent, title, message, password,
                           wrong_message="Access denied -- incorrect password."):
    """Same as confirm(), plus a masked password field -- Confirm only
    actually closes the dialog (returning True) once the entered text
    matches `password`; a wrong guess shows `wrong_message` inline and lets
    the user try again rather than closing. Used to gate a whole section
    (see ui/settings_screen.py) rather than one single action."""
    dialog = _TerminalDialog(parent, title, message, danger=False)
    dialog.confirm_btn.configure(text="Unlock")

    tk.Label(
        dialog.extra, text="Password:", bg=theme.BG_ELEVATED, fg=theme.FG, font=theme.font(9),
    ).pack(anchor="w", pady=(4, 4))
    password_var = tk.StringVar()
    entry = tk.Entry(
        dialog.extra, textvariable=password_var, show="•", font=theme.font(11),
        bg=theme.BG, fg=theme.FG, insertbackground=theme.FG, relief="flat",
        highlightthickness=1, highlightbackground=theme.BORDER, highlightcolor=theme.ACCENT,
    )
    entry.pack(fill="x")
    entry.focus_set()

    def try_confirm():
        if password_var.get() == password:
            dialog.result = True
            dialog.destroy()
        else:
            dialog.error_lbl.configure(text=wrong_message)
            password_var.set("")
            entry.focus_set()

    # Not also bound on `entry` itself -- <Return> already bubbles up to this
    # binding on the Toplevel regardless of which child widget has focus, and
    # binding it twice would run try_confirm() (and, on success, destroy())
    # a second time on an already-closed window.
    dialog._confirm = try_confirm
    dialog.confirm_btn.configure(command=try_confirm)

    return dialog.run()


def prompt_text(parent, title, message, max_length=24, confirm_text="Create"):
    """Same shape as confirm_with_password, but for a single unmasked line
    of free text rather than a password check -- used by the logon
    screen's "+ New Player" flow. Confirm only actually closes the dialog
    (returning the trimmed text) once it's non-empty and no longer than
    `max_length`; an invalid entry shows an inline error and lets the user
    try again, the same way a wrong password does. Returns None if the
    dialog was cancelled instead.

    Deliberately not used for the logon screen's legacy-migration prompt
    (see ui/logon_screen.py) -- a popup Toplevel right after the main
    window's very first deiconify is a real problem: the window manager
    hasn't settled focus onto the new window yet, so an override-redirect
    dialog shown at exactly that moment can come up uncentred and never
    actually receive keyboard input. That one's built as flat widgets
    directly on the frame instead, which doesn't have this failure mode."""
    dialog = _TerminalDialog(parent, title, message, danger=False)
    dialog.confirm_btn.configure(text=confirm_text)

    text_var = tk.StringVar()
    entry = tk.Entry(
        dialog.extra, textvariable=text_var, font=theme.font(11),
        bg=theme.BG, fg=theme.FG, insertbackground=theme.FG, relief="flat",
        highlightthickness=1, highlightbackground=theme.BORDER, highlightcolor=theme.ACCENT,
    )
    entry.pack(fill="x", pady=(4, 4))
    entry.focus_set()

    def try_confirm():
        name = text_var.get().strip()
        if not name:
            dialog.error_lbl.configure(text="Enter a name to continue.")
        elif len(name) > max_length:
            dialog.error_lbl.configure(text=f"Keep it to {max_length} characters or fewer.")
        else:
            dialog.result = name
            dialog.destroy()

    # See confirm_with_password's matching comment -- not also bound on
    # `entry` itself, <Return> already bubbles up to this Toplevel binding.
    dialog._confirm = try_confirm
    dialog.confirm_btn.configure(command=try_confirm)

    result = dialog.run()
    return result or None  # dialog.result defaults to False on cancel, not ""/None


def ensure_admin_unlocked(app, parent, slug):
    """The shared gate behind every "admin" section anywhere in the app --
    Settings' Jackpot Config and Danger Zone, Cashier's override panel, and
    anywhere else that needs it later. The first time *anything* asks for
    it, this prompts for ADMIN_PASSWORD via confirm_with_password; once
    entered correctly it sets app.admin_unlocked, so every later call here
    -- even from a completely different screen -- returns True immediately
    without prompting again for the rest of this app session."""
    if getattr(app, "admin_unlocked", False):
        return True
    unlocked = confirm_with_password(
        parent, f"$ sudo access --section {slug}",
        "Administrator privileges are required to view this section. "
        "Enter the admin password to continue.",
        password=ADMIN_PASSWORD,
    )
    if unlocked:
        app.admin_unlocked = True
    return unlocked


def choice(parent, title, message, options, accent=None):
    """A warning-styled dialog offering custom named actions instead of the
    usual Confirm/Cancel -- e.g. Three Card Poker's insufficient-balance
    warning, which offers "Go Home" and "Cashier" rather than a single OK.

    `options` is an ordered list of (label, key) pairs -- the *last* one is
    the primary/accent-styled action, and ends up leftmost, the same
    position Confirm sits in every other dialog here (Cancel-equivalents
    conventionally end up rightmost); everything before it is styled as a
    plain secondary button. Returns the key of whichever was clicked, or
    None if the dialog was dismissed instead (Escape / closed) -- "leave
    things as they are and try something else" always stays an option,
    even when it's not one of the named buttons."""
    dialog = _TerminalDialog(parent, title, message, accent=accent or theme.WARN)
    dialog.result = None
    button_row = dialog.confirm_btn.master
    for child in list(button_row.winfo_children()):
        child.destroy()  # drop the default Cancel/Confirm pair

    # options is never actually empty in practice (every call site names at
    # least one action), but statically that's not guaranteed -- start with
    # a real no-op rather than None so the type stays a plain callable all
    # the way through to the dialog._confirm assignment below.
    primary_pick: Callable[[], None] = lambda: None
    for i, (label, key) in enumerate(options):
        primary = i == len(options) - 1
        bg = theme.ACCENT_DIM_BG_ELEVATED if primary else theme.GREY_BTN_BG
        fg = theme.ACCENT if primary else theme.FG_DIM
        border = theme.ACCENT if primary else theme.GREY_BTN_BORDER

        def pick(_k=key):
            dialog.result = _k
            dialog.destroy()

        if primary:
            primary_pick = pick
        tk.Button(
            button_row, text=label, bg=bg, fg=fg, relief="flat",
            font=theme.font(10, weight="bold" if primary else "normal"), padx=14, pady=6, cursor="hand2",
            highlightthickness=1, highlightbackground=border,
            command=pick,
        ).pack(side="right", padx=(8, 0))

    dialog._confirm = primary_pick  # <Return> triggers the primary action, same as every other dialog
    return dialog.run()


def _render_rich_text(parent, text, width, prefix="", fg=None, pady=0):
    """Renders one paragraph or bulleted list line for document() below,
    honouring **bold** markdown-lite spans -- e.g. Optimal Play's
    "Q-6-4", or a bulleted GAMEPLAY sub-heading like "**Betting:**".
    `prefix` (e.g. "• ") is prepended as plain text, not itself scanned for
    "**". Plain text (no "**" anywhere) stays a simple Label; a bold span
    needs a read-only Text widget instead, since a Label can only ever
    have one font for its whole text. Text has no wraplength option the
    way Label does, so its width is set in characters, measured from the
    actual resolved font so it still lines up with `width` in pixels; its
    height (in lines) isn't known until after the wrapped text is actually
    laid out, so that's set in a second pass once Tk's reported it."""
    fg = fg or theme.FG_DIM
    if "**" not in text:
        tk.Label(
            parent, text=prefix + text, bg=theme.BG_ELEVATED, fg=fg,
            font=theme.font(10), anchor="w", justify="left", wraplength=width,
        ).pack(fill="x", pady=pady)
        return

    base_font = theme.font(10)
    bold_font = theme.font(10, weight="bold")
    char_w = tkfont.Font(font=base_font).measure("0") or 7
    text_widget = tk.Text(
        parent, bg=theme.BG_ELEVATED, fg=fg, font=base_font,
        wrap="word", relief="flat", bd=0, highlightthickness=0, cursor="arrow",
        padx=0, pady=0, height=1, width=max(20, width // char_w),
    )
    text_widget.tag_configure("bold", font=bold_font, foreground=theme.FG)
    if prefix:
        text_widget.insert("end", prefix)
    for i, part in enumerate(text.split("**")):
        if part:
            text_widget.insert("end", part, "bold" if i % 2 else "")
    text_widget.configure(state="disabled")
    text_widget.pack(fill="x", pady=pady)

    text_widget.update_idletasks()
    lines = text_widget.count("1.0", "end", "displaylines")
    if isinstance(lines, tuple):
        lines = lines[0] if lines else 1
    text_widget.configure(height=max(1, lines or 1))


_SUIT_GLYPHS = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}
# Traditional red/black rather than a single uniform accent treatment --
# tried the mint-outline look (matching the Main Menu's spade accents)
# first, but at this small size it read as soft/fuzzy and hearts/diamonds
# were hard to tell apart from each other without colour doing some of the
# work the way it does on a real card. True black (#000) would vanish
# against the dialog's own near-black background, so GREY_BTN_TEXT stands
# in as the darkest tone that still actually reads on it.
_SUIT_COLORS = {"s": theme.GREY_BTN_TEXT, "c": theme.GREY_BTN_TEXT, "h": theme.LOSE_COLOR, "d": theme.LOSE_COLOR}


def _draw_hand_notation(parent, cards, bg):
    """A compact "Q♠ 6♥ 4♦"-style strip for one hand-ranking example --
    `cards` is a list of (rank, suit_letter) pairs, suits coloured per
    _SUIT_COLORS. A Label can only ever have one font/colour for its whole
    text, so this needs its own small Canvas rather than being part of the
    surrounding Label the way the rest of the line is."""
    rank_font = tkfont.Font(font=theme.font(11, weight="bold"))
    suit_font = theme.font(13, weight="bold")
    suit_size = 13
    gap_after_rank = 2
    gap_between_cards = 10
    pad = 3

    x = pad
    rank_widths = []
    for rank, _suit in cards:
        rw = rank_font.measure(rank)
        rank_widths.append(rw)
        x += rw + gap_after_rank + suit_size + gap_between_cards
    total_w = x - gap_between_cards + pad
    canvas = tk.Canvas(parent, width=total_w, height=22, bg=bg, highlightthickness=0)

    x = pad
    cy = 11
    for (rank, suit), rw in zip(cards, rank_widths):
        canvas.create_text(x, cy, text=rank, fill=theme.FG, font=theme.font(11, weight="bold"), anchor="w")
        x += rw + gap_after_rank
        canvas.create_text(x + suit_size / 2, cy, text=_SUIT_GLYPHS[suit],
                            fill=_SUIT_COLORS[suit], font=suit_font)
        x += suit_size + gap_between_cards
    return canvas


# The Rules popup's own scrollable content area (title-to-Close-button) is
# capped at this height and scrolls past it -- without a cap, a game with a
# long GAMEPLAY list + all 9 HAND RANKINGS rows + a STRATEGY paragraph
# (worst case today: Let It Ride) can produce a popup taller than the main
# window's own fixed 820px height (main.py's own geometry("1200x820")),
# pushing its bottom off-window -- _center_over_parent only clamps the
# popup's top-left corner, never its size. 480px leaves room under the
# title (~46px) and above the Close button (~70px) that this is never the
# binding constraint for any rules screen that already fits today.
_DOCUMENT_MAX_CONTENT_HEIGHT = 480


def document(parent, title, sections, width=460, max_content_height=_DOCUMENT_MAX_CONTENT_HEIGHT):
    """A larger read-only popup for a block of reference text (e.g. Three
    Card Poker's Rules button) -- too much content for confirm()/info()'s
    one-line message, so this isn't built on _TerminalDialog. `sections` is
    an ordered list of (heading, body) pairs: `body` is either a paragraph
    string (wrapped, dim) or a list of short strings rendered one per line
    with a leading bullet (e.g. a hand-ranking order). Single "Close"
    button/Escape/window-close -- purely informational, nothing to return."""
    win = tk.Toplevel(parent.winfo_toplevel())
    _place_off_screen(win)  # avoids a top-left flash before it's positioned -- see its own docstring
    win.configure(bg=theme.BG_ELEVATED, highlightbackground=theme.ACCENT, highlightthickness=2)
    win.overrideredirect(True)
    win.resizable(False, False)

    body = tk.Frame(win, bg=theme.BG_ELEVATED)
    body.pack(padx=1, pady=1)

    tk.Label(
        body, text=title, bg=theme.BG_ELEVATED, fg=theme.ACCENT,
        font=theme.font(14, weight="bold"), anchor="w",
    ).pack(fill="x", padx=24, pady=(20, 4))

    scroll = ScrollableFrame(body, bg=theme.BG_ELEVATED)
    scroll.canvas.configure(width=width)
    scroll.pack(fill="both", padx=24)
    content = scroll.inner  # already the right bg -- no extra nesting needed

    for heading, section_body in sections:
        tk.Label(
            content, text=heading, bg=theme.BG_ELEVATED, fg=theme.ACCENT,
            font=theme.font(11, weight="bold"), anchor="w",
        ).pack(fill="x", pady=(14, 4))
        if isinstance(section_body, (list, tuple)):
            for line in section_body:
                if isinstance(line, tuple):
                    # (label, cards) -- label plus a small rank/suit-icon
                    # strip, e.g. "High Card (" + "Q♠ 6♥ 4♦" + ")" -- see
                    # _draw_hand_notation.
                    label, cards = line
                    row = tk.Frame(content, bg=theme.BG_ELEVATED)
                    row.pack(fill="x", pady=1, anchor="w")
                    tk.Label(
                        row, text=f"• {label} (", bg=theme.BG_ELEVATED, fg=theme.FG, font=theme.font(10),
                    ).pack(side="left")
                    _draw_hand_notation(row, cards, theme.BG_ELEVATED).pack(side="left")
                    tk.Label(row, text=")", bg=theme.BG_ELEVATED, fg=theme.FG, font=theme.font(10)).pack(side="left")
                else:
                    _render_rich_text(content, line, width - 20, prefix="• ", fg=theme.FG, pady=1)
        else:
            _render_rich_text(content, section_body, width)

    # Only knowable once every section actually exists; must happen before
    # _center_over_parent (which needs the final, possibly-capped size).
    win.update_idletasks()
    natural_height = content.winfo_reqheight()
    scroll.canvas.configure(height=min(natural_height, max_content_height))

    tk.Button(
        body, text="Close", bg=theme.ACCENT_DIM_BG_ELEVATED, fg=theme.ACCENT, relief="flat",
        font=theme.font(10, weight="bold"), padx=18, pady=6, cursor="hand2",
        highlightthickness=1, highlightbackground=theme.ACCENT,
        command=win.destroy,
    ).pack(pady=(18, 20))

    win.protocol("WM_DELETE_WINDOW", win.destroy)
    win.bind("<Escape>", lambda _e: win.destroy())

    _center_over_parent(win)
    win.transient(cast(tk.Wm, win.master))
    win.grab_set()
    win.wait_window()
