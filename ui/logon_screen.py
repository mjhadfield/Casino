"""
Character select -- both the very first screen shown on launch, before any
per-player manager or game/menu frame exists, *and* a permanent, persistent
screen reachable at any later point via Settings' "Player Screen" button
(see CasinoApp.frames["logon"] in main.py. 

Also the intended home for later, currently-unbuilt features scoped to a
player rather than a session -- character creation beyond a plain name,
bonus stores, prizes -- once those exist, they belong on this screen too.

On the very first visit (before any session has ever started),
self.app.current_player is still None and self.app.finance/.settings/
.jackpot/.game_stats/.unlocks are still None -- this frame only ever reads
self.app.players and self.app.current_player (guarded against None), never
any of those five, so it stays valid on both that first visit and every
later one.

"""
import tkinter as tk

from core.players import legacy_migration_needed, migrate_legacy_data
from ui import theme, dialogs

ROW_WIDTH = 420
PANEL_WIDTH = 460
NAME_MAX_LENGTH = 24
DELETE_CONTINUE_PHRASE = "continue"
DELETE_FINAL_PHRASE = "sudo rm -rf"


class LogonFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.MENU_BG)
        self.app = app
        self._delete_step = None       # None | "warning" | "picker" | "final"
        self._delete_selected = set()  # slugs currently toggled in the picker step

        # --- top bar --- same look as ui/main_menu.py's, minus the
        # Cashier/Stats/Settings buttons -- nothing to navigate to yet.
        top_bar = tk.Frame(self, bg=theme.MENU_BG)
        top_bar.pack(fill="x", side="top")

        self._make_spade(top_bar).pack(side="left", padx=(20, 8), pady=14)
        tk.Label(
            top_bar, text="HADFIELD CASINO", bg=theme.MENU_BG, fg=theme.SECONDARY,
            font=theme.font(18, weight="bold"),
        ).pack(side="left")
        self._make_spade(top_bar).pack(side="left", padx=(8, 0), pady=14)

        # Packed before the breadcrumb (side="right" stacks inward from the
        # edge -- see ui/main_menu.py's own matching comment), so this ends
        # up at the outer-right corner and the breadcrumb sits just left of
        # it, same as every other action button on that screen's top bar.
        self._make_trash_icon(top_bar).pack(side="right", padx=(6, 20), pady=14)
        theme.breadcrumb(top_bar, "login", bg=theme.MENU_BG).pack(side="right", padx=(6, 6), pady=14)

        tk.Frame(self, bg=theme.MENU_DIVIDER, height=1).pack(fill="x")

        self.body = tk.Frame(self, bg=theme.MENU_BG)
        self.body.pack(fill="both", expand=True)
        self._render_body()

    def on_show(self):
        """Rebuilds the whole body fresh every time this screen is
        navigated to -- a mid-session switch, a new player created, or an
        account deleted can all mean the roster's changed since this was
        last shown. Also drops back out of any in-progress delete flow --
        arriving at this screen fresh should never leave a half-finished
        deletion pending from a previous visit."""
        self._delete_step = None
        self._delete_selected = set()
        self._render_body()

    def _render_body(self):
        for child in self.body.winfo_children():
            child.destroy()

        if legacy_migration_needed(self.app.data_dir, self.app.players.save_path):
            self._build_welcome_form(self.body)
        elif self._delete_step == "warning":
            self._build_delete_warning(self.body)
        elif self._delete_step == "picker":
            self._build_delete_picker(self.body)
        elif self._delete_step == "final":
            self._build_delete_final(self.body)
        else:
            self._build_player_select(self.body)

    def _make_panel(self, parent, border_color, top_pad=70):
        """Shared shell for every flat "form" this screen shows (the
        welcome form, and each delete-flow step below) -- a bordered
        BG_ELEVATED card centred in the body. Returns the inner frame to
        build the actual content into."""
        panel = tk.Frame(
            parent, bg=theme.BG_ELEVATED, width=PANEL_WIDTH,
            highlightbackground=border_color, highlightthickness=1,
        )
        panel.pack(pady=(top_pad, 0))
        inner = tk.Frame(panel, bg=theme.BG_ELEVATED)
        inner.pack(padx=30, pady=26, fill="x")
        return inner

    # ------------------------------------------------------------ player select
    def _build_player_select(self, parent):
        tk.Label(
            parent, text="Select a player", bg=theme.MENU_BG, fg=theme.FG,
            font=theme.font(16, weight="bold"),
        ).pack(pady=(40, 4))
        tk.Label(
            parent, text="Good luck at the tables.",
            bg=theme.MENU_BG, fg=theme.FG_DIM, font=theme.font(10),
        ).pack(pady=(0, 24))

        roster_col = tk.Frame(parent, bg=theme.MENU_BG)
        roster_col.pack()

        players = self.app.players.list_players()
        if not players:
            tk.Label(
                roster_col, text="Welcome, you don't have a membership? No worries, show me some ID and I'll get you set up.",
                bg=theme.MENU_BG, fg=theme.FG_DIM, font=theme.font(10),
            ).pack(pady=(0, 16))
        else:
            for player in players:
                self._make_player_row(roster_col, player).pack(pady=6)

        self._make_new_player_row(roster_col).pack(pady=(16, 0))

    def _make_player_row(self, parent, player):
        is_current = (
            self.app.current_player is not None
            and player["slug"] == self.app.current_player["slug"]
        )
        row = tk.Frame(
            parent, bg=theme.ACCENT_DIM_BG if is_current else theme.BG, width=ROW_WIDTH, height=65,
            highlightbackground=theme.ACCENT, highlightthickness=2 if is_current else 1,
        )
        row.pack_propagate(False)
        row_bg = theme.ACCENT_DIM_BG if is_current else theme.BG

        last_played = player.get("last_played_at")
        if is_current:
            subtitle = "currently playing"
        elif not last_played:
            subtitle = "never played"
        else:
            subtitle = f"last played {last_played[:10]}"

        text_col = tk.Frame(row, bg=row_bg)
        text_col.pack(side="left", fill="both", expand=True, padx=18)
        name_lbl = tk.Label(
            text_col, text=player["name"], bg=row_bg, fg=theme.FG,
            font=theme.font(13, weight="bold"), anchor="w",
        )
        name_lbl.pack(fill="x", pady=(10, 0))
        subtitle_lbl = tk.Label(
            text_col, text=subtitle, bg=row_bg, fg=theme.ACCENT if is_current else theme.FG_DIM,
            font=theme.font(9), anchor="w",
        )
        subtitle_lbl.pack(fill="x", pady=(0, 10))

        arrow = tk.Label(row, text="→", bg=row_bg, fg=theme.ACCENT, font=theme.font(16))
        arrow.pack(side="right", padx=18)

        def pick(_e=None, slug=player["slug"]):
            self.app.start_session(slug)
        for widget in (row, text_col, name_lbl, subtitle_lbl, arrow):
            widget.configure(cursor="hand2")
            widget.bind("<Button-1>", pick)

        return row

    def _make_new_player_row(self, parent):
        row = tk.Frame(
            parent, bg=theme.ACCENT_DIM_BG, width=ROW_WIDTH, height=48,
            highlightbackground=theme.ACCENT, highlightthickness=1, cursor="hand2",
        )
        row.pack_propagate(False)
        label = tk.Label(
            row, text="+ New Player", bg=theme.ACCENT_DIM_BG, fg=theme.ACCENT,
            font=theme.font(12, weight="bold"), cursor="hand2",
        )
        label.pack(expand=True)

        for widget in (row, label):
            widget.bind("<Button-1>", self._on_new_player)
        return row

    def _on_new_player(self, _event=None):
        name = dialogs.prompt_text(
            self, "$ useradd", "Choose a name for the new player.",
        )
        if not name:
            return  # cancelled
        slug = self.app.players.create_player(name)
        self.app.start_session(slug)

    # ------------------------------------------------------------ legacy migration
    def _build_welcome_form(self, parent):
        inner = self._make_panel(parent, theme.ACCENT)

        tk.Label(
            inner, text="$ sudo install player rewards", bg=theme.BG_ELEVATED, fg=theme.ACCENT,
            font=theme.font(13, weight="bold"), anchor="w",
        ).pack(fill="x", pady=(0, 12))
        tk.Label(
            inner,
            text="Welcome back, we've changed the player rewards system since your last visit.\n\n"
                 "We'll keep your previous play history \n\n"
                 "Please sign your name on the back.",
            bg=theme.BG_ELEVATED, fg=theme.FG_DIM, font=theme.font(10),
            wraplength=PANEL_WIDTH - 60, justify="left", anchor="w",
        ).pack(fill="x", pady=(0, 16))

        name_var = tk.StringVar()
        entry = tk.Entry(
            inner, textvariable=name_var, font=theme.font(12),
            bg=theme.BG, fg=theme.FG, insertbackground=theme.FG, relief="flat",
            highlightthickness=1, highlightbackground=theme.BORDER, highlightcolor=theme.ACCENT,
        )
        entry.pack(fill="x", ipady=6)
        entry.focus_set()

        error_lbl = tk.Label(
            inner, text="", bg=theme.BG_ELEVATED, fg=theme.LOSE_COLOR, font=theme.font(9), anchor="w",
        )
        error_lbl.pack(fill="x", pady=(6, 0))

        def submit(_event=None):
            name = name_var.get().strip()
            if not name:
                error_lbl.configure(text="Enter a name to continue.")
                return
            if len(name) > NAME_MAX_LENGTH:
                error_lbl.configure(text=f"Keep it to {NAME_MAX_LENGTH} characters or fewer.")
                return
            slug = migrate_legacy_data(self.app.data_dir, self.app.players.save_path, name)
            self.app.start_session(slug)

        entry.bind("<Return>", submit)

        tk.Button(
            inner, text="Accept", bg=theme.ACCENT_DIM_BG, fg=theme.ACCENT, relief="flat",
            font=theme.font(11, weight="bold"), padx=16, pady=8, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.ACCENT,
            command=submit,
        ).pack(pady=(14, 0))

    def _make_spade(self, parent):
        """Matches ui/main_menu.py's own _make_spade -- kept as a separate
        copy rather than a shared import since it's four lines and this
        screen has no other reason to depend on main_menu.py."""
        size = 28
        canvas = tk.Canvas(parent, width=size, height=size, bg=theme.MENU_BG, highlightthickness=0)
        theme.outlined_glyph(canvas, size / 2, size / 2, "♠", size=22, fill="#000000", outline=theme.ACCENT)
        return canvas

    # ------------------------------------------------------------ delete accounts
    def _make_trash_icon(self, parent):
        """A small red trash-can button opening the delete-accounts flow
        (see _on_delete_accounts). Canvas-drawn rather than a Unicode
        glyph, so it renders identically regardless of the system's emoji
        font support -- the same reasoning ui/theme.py's outlined_glyph
        docstring gives for drawing the spade accents the same way."""
        size = 26
        canvas = tk.Canvas(parent, width=size, height=size, bg=theme.MENU_BG, highlightthickness=0, cursor="hand2")
        color = theme.LOSE_COLOR
        canvas.create_rectangle(9, 3, size - 9, 6, outline=color, width=2)  # lid handle
        canvas.create_line(4, 7, size - 4, 7, fill=color, width=2)         # lid
        canvas.create_polygon(  # bin body, narrower at the base
            6, 9, size - 6, 9, size - 8, size - 3, 8, size - 3,
            outline=color, fill="", width=2, joinstyle="round",
        )
        for x in (size * 0.35, size * 0.5, size * 0.65):
            canvas.create_line(x, 11, x, size - 6, fill=color, width=1.5)  # ridges
        canvas.bind("<Button-1>", self._on_delete_accounts)
        return canvas

    def _on_delete_accounts(self, _event=None):
        self._delete_step = "warning"
        self._render_body()

    def _cancel_delete_flow(self):
        self._delete_step = None
        self._delete_selected = set()
        self._render_body()

    def _build_delete_warning(self, parent):
        """Step 1: a typed-phrase pre-warning -- the only way through is
        typing "Continue" exactly; Cancel drops straight back to the
        ordinary player-select roster with nothing changed."""
        inner = self._make_panel(parent, theme.LOSE_COLOR)

        tk.Label(
            inner, text="$ rm -account", bg=theme.BG_ELEVATED, fg=theme.LOSE_COLOR,
            font=theme.font(13, weight="bold"), anchor="w",
        ).pack(fill="x", pady=(0, 12))
        tk.Label(
            inner, text="PRE-WARNING -- account deletions are irreversible.",
            bg=theme.BG_ELEVATED, fg=theme.LOSE_COLOR, font=theme.font(10, weight="bold"),
            wraplength=PANEL_WIDTH - 60, justify="left", anchor="w",
        ).pack(fill="x", pady=(0, 8))
        tk.Label(
            inner, text=f'To continue, please type "{DELETE_CONTINUE_PHRASE}".',
            bg=theme.BG_ELEVATED, fg=theme.FG_DIM, font=theme.font(10),
            wraplength=PANEL_WIDTH - 60, justify="left", anchor="w",
        ).pack(fill="x", pady=(0, 16))

        phrase_var = tk.StringVar()
        entry = tk.Entry(
            inner, textvariable=phrase_var, font=theme.font(12),
            bg=theme.BG, fg=theme.FG, insertbackground=theme.FG, relief="flat",
            highlightthickness=1, highlightbackground=theme.BORDER, highlightcolor=theme.LOSE_COLOR,
        )
        entry.pack(fill="x", ipady=6)
        entry.focus_set()

        error_lbl = tk.Label(
            inner, text="", bg=theme.BG_ELEVATED, fg=theme.LOSE_COLOR, font=theme.font(9), anchor="w",
        )
        error_lbl.pack(fill="x", pady=(6, 0))

        def confirm(_event=None):
            if phrase_var.get() != DELETE_CONTINUE_PHRASE:
                error_lbl.configure(text=f'Type "{DELETE_CONTINUE_PHRASE}" exactly to continue.')
                return
            self._delete_step = "picker"
            self._render_body()

        entry.bind("<Return>", confirm)

        btn_row = tk.Frame(inner, bg=theme.BG_ELEVATED)
        btn_row.pack(pady=(14, 0))
        tk.Button(
            btn_row, text="Cancel", bg=theme.GREY_BTN_BG, fg=theme.FG_DIM, relief="flat",
            font=theme.font(11), padx=16, pady=8, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.GREY_BTN_BORDER,
            command=self._cancel_delete_flow,
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            btn_row, text="Confirm", bg=theme.LOSE_DIM_BG_ELEVATED, fg=theme.LOSE_COLOR, relief="flat",
            font=theme.font(11, weight="bold"), padx=16, pady=8, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.LOSE_COLOR,
            command=confirm,
        ).pack(side="left")

    def _build_delete_picker(self, parent):
        """Step 2: a multi-select list of every account -- click a row to
        toggle it (highlighted red once selected); the currently active
        player, if any, is shown but not clickable, since the account
        you're playing as can't be deleted out from under itself."""
        inner = self._make_panel(parent, theme.LOSE_COLOR)

        tk.Label(
            inner, text="$ rm -account --select", bg=theme.BG_ELEVATED, fg=theme.LOSE_COLOR,
            font=theme.font(13, weight="bold"), anchor="w",
        ).pack(fill="x", pady=(0, 10))
        tk.Label(
            inner, text="Select the account(s) to delete.", bg=theme.BG_ELEVATED, fg=theme.FG_DIM,
            font=theme.font(10), anchor="w",
        ).pack(fill="x", pady=(0, 14))

        current_slug = self.app.current_player["slug"] if self.app.current_player else None
        players = self.app.players.list_players()
        selected = self._delete_selected

        rows_col = tk.Frame(inner, bg=theme.BG_ELEVATED)
        rows_col.pack(fill="x")
        row_widgets = {}

        def refresh_row(slug):
            row, lbl = row_widgets[slug]
            is_sel = slug in selected
            bg = theme.LOSE_DIM_BG_ELEVATED if is_sel else theme.BG
            row.configure(bg=bg, highlightbackground=theme.LOSE_COLOR if is_sel else theme.BORDER)
            lbl.configure(bg=bg, fg=theme.LOSE_COLOR if is_sel else theme.FG)

        def toggle(slug):
            selected.symmetric_difference_update({slug})
            refresh_row(slug)

        for player in players:
            slug = player["slug"]
            is_current = slug == current_slug
            is_sel = slug in selected
            if is_current:
                row_bg, border = theme.GREY_BTN_BG, theme.GREY_BTN_BORDER
            elif is_sel:
                row_bg, border = theme.LOSE_DIM_BG_ELEVATED, theme.LOSE_COLOR
            else:
                row_bg, border = theme.BG, theme.BORDER

            row = tk.Frame(
                rows_col, bg=row_bg, height=40,
                highlightbackground=border, highlightthickness=1,
            )
            row.pack_propagate(False)
            row.pack(fill="x", pady=3)
            label_text = player["name"] + ("  (currently playing)" if is_current else "")
            fg = theme.GREY_BTN_TEXT if is_current else (theme.LOSE_COLOR if is_sel else theme.FG)
            lbl = tk.Label(row, text=label_text, bg=row_bg, fg=fg, font=theme.font(11), anchor="w")
            lbl.pack(fill="both", expand=True, padx=12)
            row_widgets[slug] = (row, lbl)

            if not is_current:
                def click(_e=None, s=slug):
                    toggle(s)
                row.configure(cursor="hand2")
                lbl.configure(cursor="hand2")
                row.bind("<Button-1>", click)
                lbl.bind("<Button-1>", click)

        status_lbl = tk.Label(inner, text="", bg=theme.BG_ELEVATED, fg=theme.LOSE_COLOR, font=theme.font(9), anchor="w")
        status_lbl.pack(fill="x", pady=(8, 0))

        def do_delete():
            if not selected:
                status_lbl.configure(text="Select at least one account to delete.")
                return
            self._delete_step = "final"
            self._render_body()

        btn_row = tk.Frame(inner, bg=theme.BG_ELEVATED)
        btn_row.pack(pady=(14, 0))
        tk.Button(
            btn_row, text="Cancel", bg=theme.GREY_BTN_BG, fg=theme.FG_DIM, relief="flat",
            font=theme.font(11), padx=16, pady=8, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.GREY_BTN_BORDER,
            command=self._cancel_delete_flow,
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            btn_row, text="DELETE", bg=theme.LOSE_DIM_BG_ELEVATED, fg=theme.LOSE_COLOR, relief="flat",
            font=theme.font(11, weight="bold"), padx=16, pady=8, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.LOSE_COLOR,
            command=do_delete,
        ).pack(side="left")

    def _build_delete_final(self, parent):
        """Step 3: names exactly who's about to be deleted and requires
        typing the final "sudo rm -rf" phrase -- only past this point does
        anything actually touch disk (see the confirm() closure below)."""
        inner = self._make_panel(parent, theme.LOSE_COLOR)

        names = [
            p["name"] for p in self.app.players.list_players()
            if p["slug"] in self._delete_selected
        ]

        tk.Label(
            inner, text="$ rm -rf --confirm", bg=theme.BG_ELEVATED, fg=theme.LOSE_COLOR,
            font=theme.font(13, weight="bold"), anchor="w",
        ).pack(fill="x", pady=(0, 12))
        tk.Label(
            inner, text=f"This will permanently delete: {', '.join(names)}",
            bg=theme.BG_ELEVATED, fg=theme.LOSE_COLOR, font=theme.font(10, weight="bold"),
            wraplength=PANEL_WIDTH - 60, justify="left", anchor="w",
        ).pack(fill="x", pady=(0, 8))
        tk.Label(
            inner, text=f"To delete the selected accounts, type: {DELETE_FINAL_PHRASE}",
            bg=theme.BG_ELEVATED, fg=theme.FG_DIM, font=theme.font(10),
            wraplength=PANEL_WIDTH - 60, justify="left", anchor="w",
        ).pack(fill="x", pady=(0, 16))

        phrase_var = tk.StringVar()
        entry = tk.Entry(
            inner, textvariable=phrase_var, font=theme.font(12),
            bg=theme.BG, fg=theme.FG, insertbackground=theme.FG, relief="flat",
            highlightthickness=1, highlightbackground=theme.BORDER, highlightcolor=theme.LOSE_COLOR,
        )
        entry.pack(fill="x", ipady=6)
        entry.focus_set()

        error_lbl = tk.Label(
            inner, text="", bg=theme.BG_ELEVATED, fg=theme.LOSE_COLOR, font=theme.font(9), anchor="w",
        )
        error_lbl.pack(fill="x", pady=(6, 0))

        def confirm(_event=None):
            if phrase_var.get() != DELETE_FINAL_PHRASE:
                error_lbl.configure(text=f'Type "{DELETE_FINAL_PHRASE}" exactly to continue.')
                return
            deleted_slugs = self._delete_selected
            for slug in deleted_slugs:
                self.app.players.delete_player(slug, self.app.data_dir)
                self.app.sessions.pop(slug, None)
            deleted_count = len(deleted_slugs)
            self._delete_step = None
            self._delete_selected = set()
            self._render_body()
            dialogs.info(self, "$ rm -account", f"Deleted {deleted_count} account(s).")

        entry.bind("<Return>", confirm)

        btn_row = tk.Frame(inner, bg=theme.BG_ELEVATED)
        btn_row.pack(pady=(14, 0))
        tk.Button(
            btn_row, text="Cancel", bg=theme.GREY_BTN_BG, fg=theme.FG_DIM, relief="flat",
            font=theme.font(11), padx=16, pady=8, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.GREY_BTN_BORDER,
            command=self._cancel_delete_flow,
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            btn_row, text="Confirm", bg=theme.LOSE_DIM_BG_ELEVATED, fg=theme.LOSE_COLOR, relief="flat",
            font=theme.font(11, weight="bold"), padx=16, pady=8, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.LOSE_COLOR,
            command=confirm,
        ).pack(side="left")
