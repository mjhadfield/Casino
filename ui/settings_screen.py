import tkinter as tk
from tkinter import messagebox

from core.settings import TABLE_THEMES
from games.three_card_poker import logic as tcp_logic
from games.pai_gow_poker import logic as pgp_logic
from games.pai_gow_poker_face_up import logic as pgpfu_logic
from games.mississippi_stud import logic as ms_logic
from games.ultimate_texas_holdem import logic as uth_logic
from games.let_it_ride import logic as lir_logic
from games.high_card_flush import logic as hcf_logic
from games.baccarat import logic as bacc_logic
from ui import dialogs, main_menu, theme
from ui.collapsible import make_collapsible
from ui.scrollable import ScrollableFrame


class SettingsFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.BG)
        self.app = app
        self._toggle_redraws = []
        self.theme_canvases = {}
        self._collapsers = []       # every gated section's collapse() -- on_show resets them all

        self.sound_var = tk.BooleanVar(value=app.settings.get("sound_enabled"))
        self.anim_var = tk.BooleanVar(value=app.settings.get("animations_enabled"))
        self.theme_var = tk.StringVar(value=app.settings.get("table_theme"))
        self.jackpot_rate_var = tk.StringVar(value=f"{app.settings.get('jackpot_rate_per_second'):.2f}")
        self._original = self._snapshot()

        top_bar = tk.Frame(self, bg=theme.BG_ELEVATED)
        top_bar.pack(fill="x")
        tk.Button(
            top_bar, text="← Back", bg=theme.BG_ELEVATED, fg=theme.FG_DIM, relief="flat",
            font=theme.font(11), padx=12, pady=6, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.BORDER, highlightcolor=theme.ACCENT,
            command=lambda: self._on_cancel(),
        ).pack(side="left", padx=(20, 10), pady=12)
        tk.Label(top_bar, text="Settings", bg=theme.BG_ELEVATED, fg=theme.ACCENT,
                 font=theme.font(18, weight="bold")).pack(side="left", padx=10)
        theme.breadcrumb(top_bar, "settings", bg=theme.BG_ELEVATED,
                          player=app.current_player["name"]).pack(side="right", padx=20, pady=12)

        # Centred regardless of how wide the left ("← Back"/"Settings") or
        # right (breadcrumb) groups end up -- place() positions relative to
        # top_bar's own current size independently of what's pack()ed on
        # either side of it, rather than needing a pack "expand" spacer on
        # both sides to balance. Switches back to the player-select screen
        # (see ui/logon_screen.py) without closing the app -- also the
        # planned home for character creation/bonus stores later.
        tk.Button(
            top_bar, text="Player Screen", bg=theme.BG_ELEVATED, fg=theme.ACCENT, relief="flat",
            font=theme.font(11, weight="bold"), padx=14, pady=6, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.ACCENT,
            command=lambda: app.show_frame("logon"),
        ).place(relx=0.5, rely=0.5, anchor="center")

        # Scrollable -- the Preferences/Jackpot/Danger Zone panels plus the
        # Save/Cancel row can add up to more height than the window
        # comfortably fits (they used to just get cut off, Save included,
        # with no indication there was more below); see ui/scrollable.py.
        scroll = ScrollableFrame(self, bg=theme.BG)
        scroll.pack(fill="both", expand=True)
        body = tk.Frame(scroll.inner, bg=theme.BG)
        body.pack(fill="both", expand=True, padx=40, pady=30)

        # --- Preferences -- always visible/expanded, no gating, no chevron.
        panel = tk.Frame(body, bg=theme.BG_ELEVATED, highlightbackground=theme.BORDER, highlightthickness=1)
        panel.pack(fill="x")
        inner = tk.Frame(panel, bg=theme.BG_ELEVATED)
        inner.pack(fill="x", padx=26, pady=22)

        tk.Label(inner, text="$ preferences", bg=theme.BG_ELEVATED, fg=theme.ACCENT,
                 font=theme.font(13, weight="bold")).pack(anchor="w", pady=(0, 14))

        self._make_toggle_row(inner, "Sound Effects", self.sound_var)
        self._make_toggle_row(inner, "Animations", self.anim_var)

        tk.Frame(inner, bg=theme.BORDER, height=1).pack(fill="x", pady=16)

        self._make_theme_row(inner)

        # --- Jackpot Config -- collapsed by default, admin-gated to expand.
        jackpot_inner = make_collapsible(
            body, "$ jackpot --config",
            before_expand=lambda: dialogs.ensure_admin_unlocked(self.app, self, "jackpot"),
            reset_list=self._collapsers,
        )
        self._make_jackpot_rate_row(jackpot_inner)
        tk.Frame(jackpot_inner, bg=theme.BORDER, height=1).pack(fill="x", pady=16)
        self._make_jackpot_debug_row(jackpot_inner)

        # --- Game Unlocks -- same gating; each checkbox applies immediately
        # (no Save needed), the same immediate-apply convention the Jackpot
        # debug "Set" button and Danger Zone's own actions already use.
        # Foundation for a future achievements/unlock-progression system
        # (see core/unlocks.py) -- today an admin toggling this panel is the
        # only way a game ever gets unlocked.
        unlock_inner = make_collapsible(
            body, "$ game --unlock",
            before_expand=lambda: dialogs.ensure_admin_unlocked(self.app, self, "unlock"),
            reset_list=self._collapsers,
        )
        tk.Label(
            unlock_inner, text="Toggle which games are unlocked on the Main Menu. Applies immediately.",
            bg=theme.BG_ELEVATED, fg=theme.FG_DIM, font=theme.font(9),
        ).pack(anchor="w", pady=(0, 14))
        self._unlock_vars = []
        for _icon, name, _subtitle, game_key, _frame_name in main_menu.GAMES:
            self._make_unlock_row(unlock_inner, name, game_key)

        # --- Danger Zone -- same gating, red-tinted throughout.
        danger_inner = make_collapsible(
            body, "$ danger --zone",
            bg=theme.LOSE_DIM_BG, border=theme.LOSE_COLOR, fg=theme.LOSE_COLOR,
            before_expand=lambda: dialogs.ensure_admin_unlocked(self.app, self, "danger"),
            reset_list=self._collapsers,
        )
        tk.Label(
            danger_inner, text="Reset Statistics -- your balance will not be affected.",
            bg=theme.LOSE_DIM_BG, fg=theme.FG, font=theme.font(10, weight="bold"),
        ).pack(anchor="w", pady=(0, 14))
        self._make_reset_row(
            danger_inner, "$ rm --stats --lifetime",
            "This permanently deletes your lifetime deposit, withdrawal and wagering totals "
            "on the Stats screen. Your current balance is not affected.",
            "Lifetime statistics have been reset.",
            self._reset_lifetime,
        )
        self._make_reset_row(
            danger_inner, "$ rm --stats --game three_card_poker",
            "This permanently deletes Three Card Poker's bet, hand and strategy breakdown "
            "on the Stats screen.",
            "Three Card Poker's statistics have been reset.",
            lambda: self.app.game_stats.reset_game(tcp_logic.GAME_KEY),
        )
        self._make_reset_row(
            danger_inner, "$ rm --stats --game blackjack",
            "This permanently deletes Blackjack's statistics breakdown. Blackjack isn't "
            "implemented yet, so this currently has nothing to remove.",
            "Blackjack's statistics have been reset.",
            lambda: self.app.game_stats.reset_game("blackjack"),
        )
        self._make_reset_row(
            danger_inner, "$ rm --stats --game pai_gow_poker",
            "This permanently deletes Pai Gow Poker's bet, hand and payout breakdown "
            "on the Stats screen.",
            "Pai Gow Poker's statistics have been reset.",
            lambda: self.app.game_stats.reset_game(pgp_logic.GAME_KEY),
        )
        self._make_reset_row(
            danger_inner, "$ rm --stats --game pai_gow_poker_face_up",
            "This permanently deletes Pai Gow Poker (Face Up!)'s bet, hand and payout "
            "breakdown on the Stats screen.",
            "Pai Gow Poker (Face Up!)'s statistics have been reset.",
            lambda: self.app.game_stats.reset_game(pgpfu_logic.GAME_KEY),
        )
        self._make_reset_row(
            danger_inner, "$ rm --stats --game mississippi_stud",
            "This permanently deletes Mississippi Stud's bet, hand and payout breakdown "
            "on the Stats screen.",
            "Mississippi Stud's statistics have been reset.",
            lambda: self.app.game_stats.reset_game(ms_logic.GAME_KEY),
        )
        self._make_reset_row(
            danger_inner, "$ rm --stats --game ultimate_texas_holdem",
            "This permanently deletes Ultimate Texas Hold'em's bet, hand and payout "
            "breakdown on the Stats screen.",
            "Ultimate Texas Hold'em's statistics have been reset.",
            lambda: self.app.game_stats.reset_game(uth_logic.GAME_KEY),
        )
        self._make_reset_row(
            danger_inner, "$ rm --stats --game let_it_ride",
            "This permanently deletes Let It Ride's bet, hand and payout breakdown on the "
            "Stats screen.",
            "Let It Ride's statistics have been reset.",
            lambda: self.app.game_stats.reset_game(lir_logic.GAME_KEY),
        )
        self._make_reset_row(
            danger_inner, "$ rm --stats --game high_card_flush",
            "This permanently deletes High Card Flush's bet, hand and payout breakdown on the "
            "Stats screen.",
            "High Card Flush's statistics have been reset.",
            lambda: self.app.game_stats.reset_game(hcf_logic.GAME_KEY),
        )
        self._make_reset_row(
            danger_inner, "$ rm --stats --game baccarat",
            "This permanently deletes Baccarat's bet, hand and payout breakdown on the "
            "Stats screen.",
            "Baccarat's statistics have been reset.",
            lambda: self.app.game_stats.reset_game(bacc_logic.GAME_KEY),
        )

        tk.Frame(danger_inner, bg=theme.LOSE_COLOR, height=1).pack(fill="x", pady=(4, 12))
        self._make_reset_row(
            danger_inner, "$ rm --stats --all",
            "This permanently deletes every statistic in the app -- lifetime deposit, "
            "withdrawal and wagering totals, plus every game's bet, hand and payout "
            "breakdown on the Stats screen.",
            "All statistics have been reset.",
            self._reset_all_stats,
            pady=(0, 0),
        )

        action_row = tk.Frame(body, bg=theme.BG)
        action_row.pack(pady=(28, 0))
        tk.Button(
            action_row, text="SAVE", bg=theme.ACCENT_DIM_BG, fg=theme.ACCENT, relief="flat",
            font=theme.font(13, weight="bold"), padx=30, pady=10, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.ACCENT,
            command=self._on_save,
        ).pack(side="left", padx=8)
        tk.Button(
            action_row, text="Cancel", bg=theme.GREY_BTN_BG, fg=theme.FG_DIM, relief="flat",
            font=theme.font(11), padx=20, pady=10, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.GREY_BTN_BORDER,
            command=self._on_cancel,
        ).pack(side="left", padx=8)

    # ------------------------------------------------------------------ toggle switches
    def _make_toggle_row(self, parent, label, var):
        row = tk.Frame(parent, bg=theme.BG_ELEVATED)
        row.pack(fill="x", pady=8)
        tk.Label(row, text=label, bg=theme.BG_ELEVATED, fg=theme.FG, font=theme.font(12)).pack(side="left")

        canvas = tk.Canvas(row, width=46, height=24, bg=theme.BG_ELEVATED, highlightthickness=0, cursor="hand2")
        canvas.pack(side="right")

        def redraw():
            canvas.delete("all")
            on = var.get()
            track_fill = theme.ACCENT_DIM_BG_ELEVATED if on else theme.GREY_BTN_BG
            track_outline = theme.ACCENT if on else theme.GREY_BTN_BORDER
            theme.rounded_rect(canvas, 2, 2, 44, 22, radius=11,
                                fill=track_fill, outline=track_outline, width=1.5)
            knob_cx = 34 if on else 12
            canvas.create_oval(knob_cx - 8, 4, knob_cx + 8, 20, fill="#ffffff", outline="")

        def on_click(event=None):
            var.set(not var.get())
            redraw()

        canvas.bind("<Button-1>", on_click)
        redraw()
        self._toggle_redraws.append(redraw)

    # ------------------------------------------------------------------ theme swatches
    def _make_theme_row(self, parent):
        row = tk.Frame(parent, bg=theme.BG_ELEVATED)
        row.pack(fill="x", pady=(6, 0))
        tk.Label(row, text="Table Felt Theme", bg=theme.BG_ELEVATED, fg=theme.FG,
                 font=theme.font(12)).pack(anchor="w", pady=(0, 10))

        swatch_row = tk.Frame(row, bg=theme.BG_ELEVATED)
        swatch_row.pack(anchor="w")
        for name, colors in TABLE_THEMES.items():
            cell = tk.Frame(swatch_row, bg=theme.BG_ELEVATED)
            cell.pack(side="left", padx=(0, 18))
            canvas = tk.Canvas(cell, width=44, height=44, bg=theme.BG_ELEVATED, highlightthickness=0, cursor="hand2")
            canvas.pack()
            canvas.bind("<Button-1>", lambda e, n=name: self._select_theme(n))
            tk.Label(cell, text=name, bg=theme.BG_ELEVATED, fg=theme.FG_DIM, font=theme.font(9)).pack(pady=(4, 0))
            self.theme_canvases[name] = canvas
        self._draw_theme_swatches()

    def _draw_theme_swatches(self):
        for name, canvas in self.theme_canvases.items():
            canvas.delete("all")
            colors = TABLE_THEMES[name]
            if name == self.theme_var.get():
                canvas.create_oval(1, 1, 43, 43, outline=theme.ACCENT, width=3)
            canvas.create_oval(8, 8, 36, 36, fill=colors["felt"], outline=colors["accent"], width=2)

    def _select_theme(self, name):
        self.theme_var.set(name)
        self._draw_theme_swatches()

    # ------------------------------------------------------------------ jackpot
    def _make_jackpot_rate_row(self, parent):
        row = tk.Frame(parent, bg=theme.BG_ELEVATED)
        row.pack(fill="x", pady=4)
        tk.Label(row, text="Growth Rate", bg=theme.BG_ELEVATED, fg=theme.FG, font=theme.font(12)).pack(side="left")
        tk.Label(row, text="£ / second", bg=theme.BG_ELEVATED, fg=theme.FG_DIM, font=theme.font(9)).pack(side="right")
        tk.Entry(
            row, textvariable=self.jackpot_rate_var, width=8, bg=theme.BG, fg=theme.FG,
            insertbackground=theme.FG, relief="flat", justify="right",
            highlightthickness=1, highlightbackground=theme.BORDER, highlightcolor=theme.ACCENT,
        ).pack(side="right", padx=8)

    def _make_jackpot_debug_row(self, parent):
        tk.Label(
            parent, text="Manually set the jackpot amount -- for debugging, applies immediately.",
            bg=theme.BG_ELEVATED, fg=theme.FG_DIM, font=theme.font(9),
        ).pack(anchor="w", pady=(0, 8))
        row = tk.Frame(parent, bg=theme.BG_ELEVATED)
        row.pack(fill="x")
        tk.Label(row, text="Set Jackpot", bg=theme.BG_ELEVATED, fg=theme.FG, font=theme.font(12)).pack(side="left")
        self.jackpot_debug_var = tk.StringVar(value=f"{self.app.jackpot.amount:.2f}")
        tk.Button(
            row, text="Set", bg=theme.GREY_BTN_BG, fg=theme.FG_DIM, relief="flat",
            font=theme.font(9, weight="bold"), padx=12, pady=4, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.GREY_BTN_BORDER,
            command=self._apply_jackpot_debug_value,
        ).pack(side="right")
        tk.Entry(
            row, textvariable=self.jackpot_debug_var, width=10, bg=theme.BG, fg=theme.FG,
            insertbackground=theme.FG, relief="flat", justify="right",
            highlightthickness=1, highlightbackground=theme.BORDER, highlightcolor=theme.ACCENT,
        ).pack(side="right", padx=8)
        tk.Label(row, text="£", bg=theme.BG_ELEVATED, fg=theme.FG_DIM, font=theme.font(9)).pack(side="right")

    def _apply_jackpot_debug_value(self):
        try:
            amount = float(self.jackpot_debug_var.get().strip().replace("£", "").replace(",", ""))
        except ValueError:
            messagebox.showwarning("Invalid Amount", "Enter a valid £ amount for the jackpot.")
            return
        self.app.jackpot.set_amount(amount)
        self.jackpot_debug_var.set(f"{self.app.jackpot.amount:.2f}")
        messagebox.showinfo("Jackpot Updated", f"Jackpot set to £{self.app.jackpot.amount:,.2f}.")

    # ------------------------------------------------------------------ game unlocks
    def _make_unlock_row(self, parent, name, game_key):
        row = tk.Frame(parent, bg=theme.BG_ELEVATED)
        row.pack(fill="x", pady=4)
        var = tk.BooleanVar(value=self.app.unlocks.is_unlocked(game_key))

        def on_toggle():
            self.app.unlocks.set_unlocked(game_key, var.get())

        tk.Checkbutton(
            row, text=name, variable=var, command=on_toggle,
            bg=theme.BG_ELEVATED, fg=theme.FG, font=theme.font(11),
            activebackground=theme.BG_ELEVATED, activeforeground=theme.FG,
            selectcolor=theme.BG, highlightthickness=0, bd=0, cursor="hand2", anchor="w",
        ).pack(side="left", fill="x")
        self._unlock_vars.append((var, game_key))

    # ------------------------------------------------------------------ danger zone
    def _make_reset_row(self, parent, command_text, warn_message, done_message, action, pady=(0, 12)):
        """One "$ rm ..." reset command: a button styled like the terminal
        command it names, which -- since the section it's in was already
        admin-gated to even see -- only needs a plain are-you-sure (no
        password again) before actually running `action`."""
        tk.Button(
            parent, text=command_text, bg=theme.LOSE_DIM_BG, fg=theme.LOSE_COLOR, relief="flat",
            font=theme.font(10, weight="bold"), padx=14, pady=6, cursor="hand2", anchor="w",
            highlightthickness=1, highlightbackground=theme.LOSE_COLOR,
            command=lambda: self._confirm_and_run(command_text, warn_message, done_message, action),
        ).pack(anchor="w", pady=pady)

    def _confirm_and_run(self, command_text, warn_message, done_message, action):
        if dialogs.confirm(
            self, command_text, f"{warn_message} This cannot be undone. Continue?", danger=True,
        ):
            action()
            dialogs.info(self, command_text, done_message)

    def _reset_lifetime(self):
        self.app.finance.reset_stats_only()
        self.app.on_balance_changed()

    def _reset_all_stats(self):
        """Everything the individual reset rows above do, combined -- the
        lifetime finance totals plus every game's own bet/hand/payout
        breakdown in one shot -- plus every game's own currently-placed
        (not yet dealt) bets, reset back to zero. Balance itself is
        untouched, same as every other reset row here."""
        self._reset_lifetime()
        self.app.game_stats.reset()
        self._reset_all_game_bets()

    def _reset_all_game_bets(self):
        """Every game frame (all of them are built once at startup and
        live for the app's whole session -- see main.py -- whether or not
        they're the one currently on screen) follows the same duck-typed
        convention: a `bets` dict plus a `_persist_state()` that writes it
        to that game's own `<name>_state.json`. Zeroing it here and
        re-persisting is all that's needed -- the actual on-screen chip
        stacks refresh themselves the next time that game is opened,
        since every game's own on_show() already redraws them from
        `self.bets` whenever state == "betting" (a mid-round game is left
        alone entirely; its pending stake is real money already wagered,
        not a bet still waiting to be placed)."""
        for frame in self.app.frames.values():
            bets = getattr(frame, "bets", None)
            persist = getattr(frame, "_persist_state", None)
            if not isinstance(bets, dict) or persist is None or getattr(frame, "state", None) != "betting":
                continue
            for key in bets:
                bets[key] = 0
            persist()

    # ------------------------------------------------------------------ save / cancel
    def _snapshot(self):
        return {
            "sound_enabled": self.sound_var.get(),
            "animations_enabled": self.anim_var.get(),
            "table_theme": self.theme_var.get(),
            "jackpot_rate_per_second": self.jackpot_rate_var.get(),
        }

    def _is_dirty(self):
        return self._snapshot() != self._original

    def _on_save(self):
        try:
            rate = float(self.jackpot_rate_var.get())
            if rate < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Invalid Rate", "Enter a valid, non-negative £/second growth rate.")
            return
        self.app.settings.set("sound_enabled", self.sound_var.get())
        self.app.settings.set("animations_enabled", self.anim_var.get())
        self.app.settings.set("table_theme", self.theme_var.get())
        self.app.settings.set("jackpot_rate_per_second", rate)
        self._original = self._snapshot()
        self.app.show_frame("menu")

    def _on_cancel(self):
        if self._is_dirty():
            choice = dialogs.choice(
                self, "$ settings --exit", "You have unsaved changes.",
                [("Cancel", "cancel"), ("Discard Changes", "discard"), ("Save Changes", "save")],
            )
            if choice == "save":
                self._on_save()
                return
            if choice != "discard":
                return  # Cancel, or dismissed (Escape / closed) -- stay put either way
        self.app.show_frame("menu")

    # ------------------------------------------------------------------ lifecycle
    def on_show(self):
        self.sound_var.set(self.app.settings.get("sound_enabled"))
        self.anim_var.set(self.app.settings.get("animations_enabled"))
        self.theme_var.set(self.app.settings.get("table_theme"))
        self.jackpot_rate_var.set(f"{self.app.settings.get('jackpot_rate_per_second'):.2f}")
        self.jackpot_debug_var.set(f"{self.app.jackpot.amount:.2f}")
        for var, game_key in self._unlock_vars:
            var.set(self.app.unlocks.is_unlocked(game_key))
        for redraw in self._toggle_redraws:
            redraw()
        self._draw_theme_swatches()
        # Gated sections always start collapsed on a fresh visit -- but
        # app.admin_unlocked is deliberately NOT reset here, so re-opening
        # one after having already entered the password once this session
        # (even on a different screen) doesn't prompt again.
        for collapse in self._collapsers:
            collapse()
        self._original = self._snapshot()
