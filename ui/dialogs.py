"""
Custom modal dialogs styled to match the terminal aesthetic (ui/theme.py) --
used in place of tkinter.messagebox, whose native OS dialogs don't take any
of that styling and can't host a password field anyway.

Both entry points block (via wait_window) until the dialog closes and return
a plain bool, the same calling convention as messagebox.askyesno -- callers
don't need to know these are hand-built Toplevels rather than native ones.
"""
import tkinter as tk

from ui import theme


class _TerminalDialog(tk.Toplevel):
    """Shared chrome for both dialogs below: a bordered, dark, monospace
    popup centred on its parent, closable via Escape or the window manager's
    own close button (treated as Cancel either way)."""

    def __init__(self, parent, title, message, danger=False, accent=None):
        super().__init__(parent.winfo_toplevel())
        self.result = False
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
        self.update_idletasks()
        parent = self.master
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_reqwidth()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_reqheight()) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        self.transient(parent)
        self.grab_set()
        self.wait_window()
        return self.result


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


def choice(parent, title, message, options, accent=None):
    """A warning-styled dialog offering custom named actions instead of the
    usual Confirm/Cancel -- e.g. Three Card Poker's insufficient-balance
    warning, which offers "Go Home" and "Cashier" rather than a single OK.

    `options` is an ordered list of (label, key) pairs, rendered right-to-
    left with the *last* one as the primary/accent-styled action (matching
    where Confirm sits in every other dialog here) and the rest styled as
    plain secondary buttons. Returns the key of whichever was clicked, or
    None if the dialog was dismissed instead (Escape / closed) -- "leave
    things as they are and try something else" always stays an option,
    even when it's not one of the named buttons."""
    dialog = _TerminalDialog(parent, title, message, accent=accent or theme.WARN)
    dialog.result = None
    button_row = dialog.confirm_btn.master
    for child in list(button_row.winfo_children()):
        child.destroy()  # drop the default Cancel/Confirm pair

    primary_pick = None
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
