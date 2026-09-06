import tkinter as tk
from tkinter import messagebox

from core.cards import Card, Suit
from core.settings import STANDARD_CARD_STYLES
from core.themes import THEMES, PREMIUM_THEMES
from core.themes import resolve as resolve_theme
from core.unlocks import PREMIUM_CARD_STYLES, PREMIUM_FEATURES
from games.three_card_poker import logic as tcp_logic
from games.pai_gow_poker import logic as pgp_logic
from games.pai_gow_poker_face_up import logic as pgpfu_logic
from games.mississippi_stud import logic as ms_logic
from games.ultimate_texas_holdem import logic as uth_logic
from games.let_it_ride import logic as lir_logic
from games.high_card_flush import logic as hcf_logic
from games.baccarat import logic as bacc_logic
from ui import card_widgets, dialogs, main_menu, theme
from ui.collapsible import make_collapsible
from ui.scrollable import ScrollableFrame

# (PREMIUM_FEATURES key, display label, settings.py key) -- one entry per
# feature that gets a Settings toggle once owned. Only ever iterated
# through _draw_features()'s own ownership check, so a future second
# feature is just one more tuple here.
FEATURE_TOGGLES = [
    ("strategy_guide", "Strategy Guide", "strategy_guide_enabled"),
    ("four_colour_deck", "Four Colour Deck", "four_colour_deck_enabled"),
]


class SettingsFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.BG)
        self.app = app
        self._toggle_redraws = []
        self._feature_toggle_redraws = []  # rebuilt fresh by _draw_features() every call, not appended-to
        self._collapsers = []       # every gated section's collapse() -- on_show resets them all
        self.feature_vars = {}      # settings_key -> BooleanVar, populated by _draw_features()

        self.sound_var = tk.BooleanVar(value=app.settings.get("sound_enabled"))
        self.anim_var = tk.BooleanVar(value=app.settings.get("animations_enabled"))
        self.theme_var = tk.StringVar(value=app.settings.get("theme"))
        self.card_style_var = tk.StringVar(value=app.settings.get("card_style"))
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

        tk.Frame(inner, bg=theme.BORDER, height=1).pack(fill="x", pady=16)

        self._make_card_style_row(inner)

        self._make_features_row(inner)

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
        # This is an admin override sitting alongside the real unlock
        # routes now (achievements and the Crowns Store, see core/unlocks.py
        # and core/achievements.py) -- a manual escape hatch, not the only
        # way a game gets unlocked any more.
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
            "This permanently deletes Blackjack's bet, hand and payout breakdown "
            "on the Stats screen -- Standard, Counting and 6:5 share one breakdown, "
            "so this clears all three.",
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
    def _make_toggle_row(self, parent, label, var, redraw_list=None):
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
        # Static rows (Sound Effects/Animations) live for the frame's whole
        # lifetime, so their own redraw closure is appended once and stays
        # valid forever -- self._toggle_redraws is the default target.
        # Features rows are rebuilt from scratch every time _draw_features()
        # runs (their own OWNED set can change mid-session), so THEIR
        # closures go into a caller-supplied list instead, one that gets
        # reset (not appended-to) on every rebuild -- appending them here
        # too would leak a growing pile of closures pointing at canvases
        # that no longer exist.
        (redraw_list if redraw_list is not None else self._toggle_redraws).append(redraw)

    # ------------------------------------------------------------------ theme swatches
    def _make_theme_row(self, parent):
        row = tk.Frame(parent, bg=theme.BG_ELEVATED)
        row.pack(fill="x", pady=(6, 0))
        tk.Label(row, text="Theme", bg=theme.BG_ELEVATED, fg=theme.FG,
                 font=theme.font(12)).pack(anchor="w", pady=(0, 6))

        desc = tk.Frame(row, bg=theme.BG_ELEVATED)
        desc.pack(anchor="w", pady=(0, 10))
        tk.Label(desc, text="Buy additional themes with ", bg=theme.BG_ELEVATED, fg=theme.FG_DIM,
                 font=theme.font(9)).pack(side="left")
        crowns_link = tk.Label(desc, text="crowns", bg=theme.BG_ELEVATED, fg=theme.SECONDARY,
                                font=theme.font(9, weight="bold"), cursor="hand2")
        crowns_link.pack(side="left")
        crowns_link.bind("<Button-1>", lambda e: self.app.show_frame("store"))

        self.swatch_row = tk.Frame(row, bg=theme.BG_ELEVATED)
        self.swatch_row.pack(anchor="w")
        self._draw_theme_swatches()

    def _owns_theme(self, name):
        return name in THEMES or self.app.achievements.owns_theme(name)

    def _draw_theme_swatches(self):
        # Rebuilt from scratch on every call (initial build, on_show, and
        # after picking one) rather than a fixed set of widgets toggled in
        # place -- a theme bought in the Crowns Store mid-session needs to
        # newly APPEAR here on the very next on_show(), not just change
        # colour, since a still-locked one is hidden entirely now (a theme
        # is purely cosmetic with nothing worth previewing locked, unlike a
        # game tile, which stays visible with a padlock).
        for child in self.swatch_row.winfo_children():
            child.destroy()
        all_themes = {**THEMES, **PREMIUM_THEMES}
        for name, colors in all_themes.items():
            if not self._owns_theme(name):
                continue
            cell = tk.Frame(self.swatch_row, bg=theme.BG_ELEVATED)
            cell.pack(side="left", padx=(0, 18))
            canvas = tk.Canvas(cell, width=44, height=44, bg=theme.BG_ELEVATED, highlightthickness=0,
                                cursor="hand2")
            canvas.pack()
            canvas.bind("<Button-1>", lambda e, n=name: self._select_theme(n))
            tk.Label(cell, text=name, bg=theme.BG_ELEVATED, fg=theme.FG_DIM,
                     font=theme.font(9)).pack(pady=(4, 0))
            if name == self.theme_var.get():
                canvas.create_oval(1, 1, 43, 43, outline=theme.ACCENT, width=3)
            canvas.create_oval(8, 8, 36, 36, fill=colors["felt"], outline=colors["accent"], width=2)

    def _select_theme(self, name):
        self.theme_var.set(name)
        # Live preview -- the whole app reskins immediately (not just this
        # swatch row), per the user's own choice; _on_cancel() is what
        # reverts this if they leave without saving. Card style previews
        # read a felt/accent too, so they need to track the theme being
        # PREVIEWED, not the last-saved one -- see _draw_card_style_swatches.
        self.app.apply_global_theme(preview_name=name)
        self._draw_theme_swatches()
        self._draw_card_style_swatches()

    # ------------------------------------------------------------------ card style swatches
    _CARD_STYLE_PREVIEW = Card("K", Suit.SPADES)  # same rank/suit for every
    # swatch and every style -- the point is comparing how ONE card looks
    # across styles, not showing off different ranks.
    _SWATCH_CARD_W, _SWATCH_CARD_H = 30, 42

    def _make_card_style_row(self, parent):
        row = tk.Frame(parent, bg=theme.BG_ELEVATED)
        row.pack(fill="x")
        tk.Label(row, text="Card Style", bg=theme.BG_ELEVATED, fg=theme.FG,
                 font=theme.font(12)).pack(anchor="w", pady=(0, 6))

        desc = tk.Frame(row, bg=theme.BG_ELEVATED)
        desc.pack(anchor="w", pady=(0, 10))
        tk.Label(desc, text="Buy additional styles with ", bg=theme.BG_ELEVATED, fg=theme.FG_DIM,
                 font=theme.font(9)).pack(side="left")
        crowns_link = tk.Label(desc, text="crowns", bg=theme.BG_ELEVATED, fg=theme.SECONDARY,
                                font=theme.font(9, weight="bold"), cursor="hand2")
        crowns_link.pack(side="left")
        crowns_link.bind("<Button-1>", lambda e: self.app.show_frame("store"))

        self.card_style_row = tk.Frame(row, bg=theme.BG_ELEVATED)
        self.card_style_row.pack(anchor="w")
        self._draw_card_style_swatches()

    def _owns_card_style(self, name):
        return name in STANDARD_CARD_STYLES or self.app.achievements.owns_card_style(name)

    def _draw_card_style_swatches(self):
        # Same "rebuilt from scratch, locked ones hidden entirely" approach
        # as _draw_theme_swatches -- see its own comment for why.
        for child in self.card_style_row.winfo_children():
            child.destroy()
        all_styles = {**STANDARD_CARD_STYLES, **PREMIUM_CARD_STYLES}
        w, h = self._SWATCH_CARD_W, self._SWATCH_CARD_H
        pad = 6
        canvas_w, canvas_h = w * 2 + pad * 3, h + pad * 2
        for name, style in all_styles.items():
            if not self._owns_card_style(name):
                continue
            cell = tk.Frame(self.card_style_row, bg=theme.BG_ELEVATED)
            cell.pack(side="left", padx=(0, 18))
            canvas = tk.Canvas(cell, width=canvas_w, height=canvas_h, bg=theme.BG_ELEVATED,
                                highlightthickness=0, cursor="hand2")
            canvas.pack()
            canvas.bind("<Button-1>", lambda e, n=name: self._select_card_style(n))
            # resolve_theme(self.theme_var.get()) rather than
            # self.app.settings.theme() -- this needs to track whatever
            # theme is currently being PREVIEWED (see _select_theme), which
            # can differ from the last-saved one until Save is clicked.
            previewed = resolve_theme(self.theme_var.get())
            card_widgets.draw_card(canvas, pad, pad, self._CARD_STYLE_PREVIEW, width=w, height=h, style=style)
            card_widgets.draw_card_back(canvas, pad * 2 + w, pad, previewed["felt"],
                                         previewed["accent"], width=w, height=h, style=style)
            if name == self.card_style_var.get():
                canvas.create_rectangle(1, 1, canvas_w - 1, canvas_h - 1, outline=theme.ACCENT, width=2)
            tk.Label(cell, text=name, bg=theme.BG_ELEVATED, fg=theme.FG_DIM,
                     font=theme.font(9)).pack(pady=(4, 0))

    def _select_card_style(self, name):
        self.card_style_var.set(name)
        self._draw_card_style_swatches()

    # ------------------------------------------------------------------ features
    def _make_features_row(self, parent):
        # A container of its own (rather than building straight into
        # `parent`) so _draw_features() can wipe and rebuild ONLY this
        # section's own children -- including its own heading/divider,
        # which only appear at all once something is actually owned (see
        # _draw_features).
        self.features_container = tk.Frame(parent, bg=theme.BG_ELEVATED)
        self.features_container.pack(fill="x")
        self._draw_features()

    def _draw_features(self):
        for child in self.features_container.winfo_children():
            child.destroy()
        self.feature_vars = {}
        self._feature_toggle_redraws = []
        owned = [(key, label, setting_key) for key, label, setting_key in FEATURE_TOGGLES
                 if self.app.achievements.owns_feature(key)]
        if not owned:
            # Nothing bought yet -- no heading, no divider, no trace of the
            # category at all (same "hide entirely rather than show
            # locked" reasoning ui/store_screen.py's own catalogs follow).
            return
        tk.Frame(self.features_container, bg=theme.BORDER, height=1).pack(fill="x", pady=16)
        tk.Label(self.features_container, text="Features", bg=theme.BG_ELEVATED, fg=theme.FG,
                 font=theme.font(12)).pack(anchor="w", pady=(0, 10))
        for _key, label, setting_key in owned:
            var = tk.BooleanVar(value=self.app.settings.get(setting_key))
            self.feature_vars[setting_key] = var
            self._make_toggle_row(self.features_container, label, var,
                                   redraw_list=self._feature_toggle_redraws)

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
            "theme": self.theme_var.get(),
            "card_style": self.card_style_var.get(),
            "jackpot_rate_per_second": self.jackpot_rate_var.get(),
            # feature_vars is dynamic (rebuilt by _draw_features() from
            # whatever's currently owned) -- iterating it generically here
            # rather than hardcoding "strategy_guide_enabled" by name means
            # a second future feature needs no changes to this method at all.
            **{setting_key: var.get() for setting_key, var in self.feature_vars.items()},
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
        self.app.settings.set("theme", self.theme_var.get())
        self.app.settings.set("card_style", self.card_style_var.get())
        for setting_key, var in self.feature_vars.items():
            self.app.settings.set(setting_key, var.get())
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
        # Leaving without saving -- the theme swatches may have live-
        # previewed a different theme (see _select_theme); revert the whole
        # app back to whatever's actually persisted. A no-op (empty color
        # map) if the theme was never touched this visit.
        self.app.apply_global_theme()
        self.app.show_frame("menu")

    # ------------------------------------------------------------------ lifecycle
    def on_show(self):
        self.sound_var.set(self.app.settings.get("sound_enabled"))
        self.anim_var.set(self.app.settings.get("animations_enabled"))
        self.theme_var.set(self.app.settings.get("theme"))
        self.card_style_var.set(self.app.settings.get("card_style"))
        self.jackpot_rate_var.set(f"{self.app.settings.get('jackpot_rate_per_second'):.2f}")
        self.jackpot_debug_var.set(f"{self.app.jackpot.amount:.2f}")
        for var, game_key in self._unlock_vars:
            var.set(self.app.unlocks.is_unlocked(game_key))
        for redraw in self._toggle_redraws:
            redraw()
        self._draw_theme_swatches()
        self._draw_card_style_swatches()
        self._draw_features()
        # Gated sections always start collapsed on a fresh visit -- but
        # app.admin_unlocked is deliberately NOT reset here, so re-opening
        # one after having already entered the password once this session
        # (even on a different screen) doesn't prompt again.
        for collapse in self._collapsers:
            collapse()
        self._original = self._snapshot()
