"""
The Crowns Store -- reached from the Achievements screen. Sells four
things, all really the same underlying mechanism (core/unlocks.py's own
is_unlocked/set_unlocked) with a different catalog: early unlocks of a
still-locked game, a small set of premium themes (see core/themes.py's
PREMIUM_THEMES -- these now reskin the whole app, not just a table's felt)
and premium card styles (core/unlocks.py's PREMIUM_CARD_STYLES) that then
show up, once owned, in the Settings screen's own theme/card-style pickers,
and premium FEATURES (its PREMIUM_FEATURES) -- functional additions to a
game's own screen, toggled on/off in Settings' own "Features" category
once owned.
"""
import tkinter as tk

from core import achievements_data
from core.cards import Card, Suit
from core.themes import PREMIUM_THEMES
from core.unlocks import PREMIUM_CARD_STYLES, PREMIUM_FEATURES
from ui import card_widgets, dialogs, main_menu, theme
from ui.scrollable import ScrollableFrame


class StoreFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.BG)
        self.app = app

        top_bar = tk.Frame(self, bg=theme.BG_ELEVATED)
        top_bar.pack(fill="x")
        tk.Button(
            top_bar, text="← Back", bg=theme.BG_ELEVATED, fg=theme.FG_DIM, relief="flat",
            font=theme.font(11), padx=12, pady=6, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.BORDER, highlightcolor=theme.ACCENT,
            command=lambda: app.show_frame("achievements"),
        ).pack(side="left", padx=(20, 10), pady=12)
        tk.Label(top_bar, text="Crowns Store", bg=theme.BG_ELEVATED, fg=theme.ACCENT,
                 font=theme.font(18, weight="bold")).pack(side="left", padx=10)
        theme.breadcrumb(top_bar, "store", bg=theme.BG_ELEVATED,
                          player=app.current_player["name"]).pack(side="right", padx=20, pady=12)
        self.crowns_lbl = tk.Label(
            top_bar, text="\U0001F451 Crowns: 0", bg=theme.BG_ELEVATED, fg=theme.SECONDARY,
            font=theme.font(12, weight="bold"),
        )
        self.crowns_lbl.pack(side="right", padx=10, pady=12)
        # A second, explicit way back to Achievements alongside "← Back"
        # above -- this screen is now also reachable directly from the
        # Main Menu's own Crowns Store tile (bypassing Achievements
        # entirely), so "← Back" alone (always Achievements, regardless of
        # how this screen was reached) may not read as obviously as a
        # dedicated, clearly-labelled button does.
        tk.Button(
            top_bar, text="\U0001F3C6 See Achievements", bg=theme.BG_ELEVATED, fg=theme.SECONDARY,
            activebackground=theme.SECONDARY_DIM_BG_ELEVATED, activeforeground=theme.SECONDARY,
            font=theme.font(11), relief="flat", padx=12, pady=6, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.SECONDARY, highlightcolor=theme.SECONDARY,
            command=lambda: app.show_frame("achievements"),
        ).pack(side="right", padx=(6, 10), pady=12)

        scroll = ScrollableFrame(self, bg=theme.BG)
        scroll.pack(fill="both", expand=True)
        self.body = tk.Frame(scroll.inner, bg=theme.BG)
        self.body.pack(fill="both", expand=True, padx=40, pady=20)

        tk.Label(self.body, text="GAME UNLOCKS", bg=theme.BG, fg=theme.ACCENT,
                 font=theme.font(11, weight="bold")).pack(anchor="w", pady=(0, 10))
        self.unlocks_body = tk.Frame(self.body, bg=theme.BG)
        self.unlocks_body.pack(fill="x")

        tk.Label(self.body, text="PREMIUM THEMES", bg=theme.BG, fg=theme.ACCENT,
                 font=theme.font(11, weight="bold")).pack(anchor="w", pady=(24, 10))
        self.themes_body = tk.Frame(self.body, bg=theme.BG)
        self.themes_body.pack(fill="x")

        tk.Label(self.body, text="PREMIUM CARD STYLES", bg=theme.BG, fg=theme.ACCENT,
                 font=theme.font(11, weight="bold")).pack(anchor="w", pady=(24, 10))
        self.card_styles_body = tk.Frame(self.body, bg=theme.BG)
        self.card_styles_body.pack(fill="x")

        tk.Label(self.body, text="FEATURES", bg=theme.BG, fg=theme.ACCENT,
                 font=theme.font(11, weight="bold")).pack(anchor="w", pady=(24, 10))
        self.features_body = tk.Frame(self.body, bg=theme.BG)
        self.features_body.pack(fill="x")

        self._rebuild()

    def on_show(self):
        self.crowns_lbl.configure(text=f"\U0001F451 Crowns: {self.app.achievements.crowns}")
        self._rebuild()

    def _rebuild(self):
        self._rebuild_unlocks()
        self._rebuild_themes()
        self._rebuild_card_styles()
        self._rebuild_features()

    # ------------------------------------------------------------------ game unlocks
    def _rebuild_unlocks(self):
        for child in self.unlocks_body.winfo_children():
            child.destroy()
        price = achievements_data.STORE_UNLOCK_PRICE_CROWNS
        locked_games = [
            (game_key, name) for _icon, name, _subtitle, game_key, _frame_name in main_menu.GAMES
            if not self.app.unlocks.is_unlocked(game_key)
        ]
        if not locked_games:
            tk.Label(self.unlocks_body, text="Every game is already unlocked!", bg=theme.BG,
                     fg=theme.FG_DIM, font=(theme.mono_family(), 10, "italic")).pack(anchor="w")
            return
        for game_key, name in locked_games:
            self._build_purchase_row(
                self.unlocks_body, name, f"Buy for {price} Crowns",
                command=lambda gk=game_key, n=name: self._buy_unlock(gk, n),
            )

    def _buy_unlock(self, game_key, name):
        price = achievements_data.STORE_UNLOCK_PRICE_CROWNS
        if not dialogs.confirm(
            self, "$ store --unlock", f"Unlock {name} now for {price} Crowns?",
        ):
            return
        if self.app.achievements.purchase_unlock(game_key):
            self.app.on_crowns_changed()
            dialogs.info(self, "$ store --unlock", f"{name} is now unlocked!")
            self._rebuild()
        else:
            dialogs.info(self, "$ store --unlock", "You don't have enough Crowns for that.",
                         accent=theme.WARN)

    # ------------------------------------------------------------------ premium themes
    def _rebuild_themes(self):
        for child in self.themes_body.winfo_children():
            child.destroy()
        for name, colors in PREMIUM_THEMES.items():
            owned = self.app.achievements.owns_theme(name)
            row = tk.Frame(self.themes_body, bg=theme.BG_ELEVATED, highlightbackground=theme.BORDER,
                            highlightthickness=1)
            row.pack(fill="x", pady=4)
            inner = tk.Frame(row, bg=theme.BG_ELEVATED)
            inner.pack(fill="x", padx=16, pady=10)
            swatch = tk.Canvas(inner, width=32, height=32, bg=theme.BG_ELEVATED, highlightthickness=0)
            swatch.pack(side="left", padx=(0, 12))
            swatch.create_oval(2, 2, 30, 30, fill=colors["felt"], outline=colors["accent"], width=2)
            tk.Label(inner, text=name, bg=theme.BG_ELEVATED, fg=theme.FG,
                     font=theme.font(11, weight="bold")).pack(side="left")
            price = achievements_data.THEME_UNLOCK_PRICE_CROWNS
            if owned:
                tk.Label(inner, text="Owned", bg=theme.BG_ELEVATED, fg=theme.ACCENT,
                         font=theme.font(10, weight="bold")).pack(side="right")
            else:
                tk.Button(
                    inner, text=f"Buy for {price} Crowns", bg=theme.SECONDARY_DIM_BG_ELEVATED,
                    fg=theme.SECONDARY, activebackground=theme.SECONDARY_DIM_BG_ELEVATED,
                    activeforeground=theme.SECONDARY, relief="flat", padx=12, pady=6, cursor="hand2",
                    highlightthickness=1, highlightbackground=theme.SECONDARY,
                    command=lambda n=name: self._buy_theme(n),
                ).pack(side="right")

    def _buy_theme(self, name):
        price = achievements_data.THEME_UNLOCK_PRICE_CROWNS
        if not dialogs.confirm(
            self, "$ store --theme", f"Buy the {name} theme for {price} Crowns?",
        ):
            return
        if self.app.achievements.purchase_theme(name):
            self.app.on_crowns_changed()
            dialogs.info(self, "$ store --theme", f"{name} is now available in Settings.")
            self._rebuild()
        else:
            dialogs.info(self, "$ store --theme", "You don't have enough Crowns for that.",
                         accent=theme.WARN)

    # ------------------------------------------------------------------ premium card styles
    _PREVIEW_CARD = Card("K", Suit.SPADES)

    def _rebuild_card_styles(self):
        for child in self.card_styles_body.winfo_children():
            child.destroy()
        for name, style in PREMIUM_CARD_STYLES.items():
            owned = self.app.achievements.owns_card_style(name)
            row = tk.Frame(self.card_styles_body, bg=theme.BG_ELEVATED, highlightbackground=theme.BORDER,
                            highlightthickness=1)
            row.pack(fill="x", pady=4)
            inner = tk.Frame(row, bg=theme.BG_ELEVATED)
            inner.pack(fill="x", padx=16, pady=10)
            swatch = tk.Canvas(inner, width=32, height=44, bg=theme.BG_ELEVATED, highlightthickness=0)
            swatch.pack(side="left", padx=(0, 12))
            card_widgets.draw_card(swatch, 1, 1, self._PREVIEW_CARD, width=30, height=42, style=style)
            tk.Label(inner, text=name, bg=theme.BG_ELEVATED, fg=theme.FG,
                     font=theme.font(11, weight="bold")).pack(side="left")
            price = achievements_data.CARD_STYLE_UNLOCK_PRICE_CROWNS
            if owned:
                tk.Label(inner, text="Owned", bg=theme.BG_ELEVATED, fg=theme.ACCENT,
                         font=theme.font(10, weight="bold")).pack(side="right")
            else:
                tk.Button(
                    inner, text=f"Buy for {price} Crowns", bg=theme.SECONDARY_DIM_BG_ELEVATED,
                    fg=theme.SECONDARY, activebackground=theme.SECONDARY_DIM_BG_ELEVATED,
                    activeforeground=theme.SECONDARY, relief="flat", padx=12, pady=6, cursor="hand2",
                    highlightthickness=1, highlightbackground=theme.SECONDARY,
                    command=lambda n=name: self._buy_card_style(n),
                ).pack(side="right")

    def _buy_card_style(self, name):
        price = achievements_data.CARD_STYLE_UNLOCK_PRICE_CROWNS
        if not dialogs.confirm(
            self, "$ store --card-style", f"Buy the {name} card style for {price} Crowns?",
        ):
            return
        if self.app.achievements.purchase_card_style(name):
            self.app.on_crowns_changed()
            dialogs.info(self, "$ store --card-style", f"{name} is now available in Settings.")
            self._rebuild()
        else:
            dialogs.info(self, "$ store --card-style", "You don't have enough Crowns for that.",
                         accent=theme.WARN)

    # ------------------------------------------------------------------ premium features
    def _rebuild_features(self):
        for child in self.features_body.winfo_children():
            child.destroy()
        for key, info in PREMIUM_FEATURES.items():
            owned = self.app.achievements.owns_feature(key)
            row = tk.Frame(self.features_body, bg=theme.BG_ELEVATED, highlightbackground=theme.BORDER,
                            highlightthickness=1)
            row.pack(fill="x", pady=4)
            inner = tk.Frame(row, bg=theme.BG_ELEVATED)
            inner.pack(fill="x", padx=16, pady=10)
            text_col = tk.Frame(inner, bg=theme.BG_ELEVATED)
            text_col.pack(side="left", fill="x", expand=True)
            tk.Label(text_col, text=info["name"], bg=theme.BG_ELEVATED, fg=theme.FG,
                     font=theme.font(11, weight="bold")).pack(anchor="w")
            tk.Label(text_col, text=info["description"], bg=theme.BG_ELEVATED, fg=theme.FG_DIM,
                     font=theme.font(9)).pack(anchor="w", pady=(2, 0))
            price = info["price"]  # per-entry, not a flat catalog-wide price -- see PREMIUM_FEATURES' own docstring
            if owned:
                tk.Label(inner, text="Owned", bg=theme.BG_ELEVATED, fg=theme.ACCENT,
                         font=theme.font(10, weight="bold")).pack(side="right")
            else:
                tk.Button(
                    inner, text=f"Buy for {price} Crowns", bg=theme.SECONDARY_DIM_BG_ELEVATED,
                    fg=theme.SECONDARY, activebackground=theme.SECONDARY_DIM_BG_ELEVATED,
                    activeforeground=theme.SECONDARY, relief="flat", padx=12, pady=6, cursor="hand2",
                    highlightthickness=1, highlightbackground=theme.SECONDARY,
                    command=lambda k=key, n=info["name"], p=price: self._buy_feature(k, n, p),
                ).pack(side="right")

    def _buy_feature(self, key, name, price):
        if not dialogs.confirm(
            self, "$ store --feature", f"Buy {name} for {price} Crowns?",
        ):
            return
        if self.app.achievements.purchase_feature(key):
            self.app.on_crowns_changed()
            dialogs.info(self, "$ store --feature", f"{name} is now available in Settings.")
            self._rebuild()
        else:
            dialogs.info(self, "$ store --feature", "You don't have enough Crowns for that.",
                         accent=theme.WARN)

    # ------------------------------------------------------------------ shared row builder
    def _build_purchase_row(self, parent, name, button_text, command):
        row = tk.Frame(parent, bg=theme.BG_ELEVATED, highlightbackground=theme.BORDER, highlightthickness=1)
        row.pack(fill="x", pady=4)
        inner = tk.Frame(row, bg=theme.BG_ELEVATED)
        inner.pack(fill="x", padx=16, pady=10)
        tk.Label(inner, text=name, bg=theme.BG_ELEVATED, fg=theme.FG,
                 font=theme.font(11, weight="bold")).pack(side="left")
        tk.Button(
            inner, text=button_text, bg=theme.SECONDARY_DIM_BG_ELEVATED, fg=theme.SECONDARY,
            activebackground=theme.SECONDARY_DIM_BG_ELEVATED, activeforeground=theme.SECONDARY,
            relief="flat", padx=12, pady=6, cursor="hand2", highlightthickness=1,
            highlightbackground=theme.SECONDARY, command=command,
        ).pack(side="right")
