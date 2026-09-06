"""
The Achievements screen -- reachable from the Main Menu's own top bar (the
"Crowns: N" button, see ui/main_menu.py), and from here on into the Crowns
Store (ui/store_screen.py). Lists every core.achievements_data.Achievement,
filterable by category tab (All/Money/Global/Game -- an achievement can
appear under more than one, see Achievement.categories), each showing its
own Crowns reward and (once earned) a clear "earned" look. A card's own
flavour text isn't shown inline any more -- hover the card for it (see
ui/tooltip.py) -- so a card is just its title, Crowns badge, and game tag.

All/Money/Global/Game default to showing only INCOMPLETE achievements --
the "Show completed" checkbox (see show_completed_var) puts earned ones
back into whichever category tab is active, alongside the incomplete ones,
for anyone who'd rather browse one list than switch tabs. The dedicated
Completed tab is unaffected by that checkbox either way -- it always shows
every earned achievement regardless of category, and is where the
checkbox's own "off" state sends you to see them separately. An empty
result reads differently depending which kind of tab it's on (see
_rebuild_cards): nothing left incomplete in a category is a "you're done"
message, nothing earned yet on the Completed tab is the opposite.
"""
import tkinter as tk
import tkinter.font as tkfont

from core import achievements_data
from ui import main_menu, theme, tooltip
from ui.scrollable import ScrollableFrame

# game_key -> display name, built from the one canonical game list
# (ui/main_menu.py's GAMES) so a card's own "which game"/"unlocks which
# game" tag never drifts out of sync with it. A key that only ever appears
# as an achievement's own game_key/unlocks_game_key -- never as a
# main-menu row's own gating key -- isn't covered by that list, so it
# needs an explicit label here too: "blackjack" is the shared stats bucket
# behind all 3 Blackjack tables, but the main-menu row itself is gated on
# "blackjack_6_5" (the actual first-available table) instead, so plain
# "blackjack" would otherwise have no label at all.
_TABLE_LABELS = {
    "blackjack": "Blackjack",
    "blackjack_count": "Blackjack (Counting)",
    "blackjack_6_5": "Blackjack (6:5)",
    "pai_gow_poker": "Pai Gow Poker",
    "pai_gow_poker_face_up": "Pai Gow Poker (Face Up!)",
}
GAME_LABELS = {game_key: name for _icon, name, _subtitle, game_key, _frame_name in main_menu.GAMES}
for _key, _label in _TABLE_LABELS.items():
    GAME_LABELS.setdefault(_key, _label)

# The distinct game_key values actually used by CATEGORY_GAME achievements,
# in first-declared order (core/achievements_data.py's own ACHIEVEMENTS
# dict preserves insertion order) -- which happens to already be the
# progression chain's own order, since that's the order they're declared
# in. This is the Game tab's own sub-filter row (see _build_game_filter_row)
# -- computed from the data itself rather than hardcoded, so a new game's
# own achievement automatically gets a sub-filter button for free.
GAME_FILTER_KEYS = []
for _a in achievements_data.ACHIEVEMENTS.values():
    if achievements_data.CATEGORY_GAME in _a.categories and _a.game_key and _a.game_key not in GAME_FILTER_KEYS:
        GAME_FILTER_KEYS.append(_a.game_key)

# Sentinel for "every game" on the sub-filter row -- not a real game_key,
# same "screen-only sentinel" convention CATEGORY_ALL/CATEGORY_COMPLETED
# already use above.
GAME_FILTER_ALL = "all"

# The sub-filter row's own buttons read 15% smaller than the main category
# tabs (theme.font(11)/padx16/pady8) -- one deliberate, consistent scale-
# down applied to every size metric, not just the font.
_GAME_FILTER_FONT_SIZE = round(11 * 0.85)
_GAME_FILTER_PADX = round(16 * 0.85)
_GAME_FILTER_PADY = round(8 * 0.85)

# Not a real Achievement.categories tag (nothing is ever stamped with
# this) -- same "screen-only sentinel tab" convention CATEGORY_ALL already
# uses, just for the opposite filter: every OTHER tab excludes earned
# achievements, this one shows nothing BUT them, regardless of category.
CATEGORY_COMPLETED = "completed"

_TABS = (
    (achievements_data.CATEGORY_ALL, "All"),
    (achievements_data.CATEGORY_MONEY, "Money"),
    (achievements_data.CATEGORY_GLOBAL, "Global"),
    (achievements_data.CATEGORY_GAME, "Game"),
    (CATEGORY_COMPLETED, "Completed"),
)


class AchievementsFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.BG)
        self.app = app
        self.category_var = tk.StringVar(value=achievements_data.CATEGORY_ALL)
        # Off by default -- All/Money/Global/Game hide earned achievements
        # unless this is ticked, at which point they show up alongside the
        # incomplete ones on whichever of those tabs is active. Meaningless
        # on the Completed tab itself (already earned-only regardless), so
        # the checkbox is disabled there -- see _select_category.
        self.show_completed_var = tk.BooleanVar(value=False)
        # Only meaningful while category_var is CATEGORY_GAME -- see
        # _build_game_filter_row/_rebuild_cards. Persists across switching
        # away and back, same as show_completed_var above, rather than
        # resetting to "all games" every time Game is reselected.
        self.game_filter_var = tk.StringVar(value=GAME_FILTER_ALL)
        self._tab_buttons = {}
        self._game_filter_buttons = {}

        top_bar = tk.Frame(self, bg=theme.BG_ELEVATED)
        top_bar.pack(fill="x")
        tk.Button(
            top_bar, text="← Back", bg=theme.BG_ELEVATED, fg=theme.FG_DIM, relief="flat",
            font=theme.font(11), padx=12, pady=6, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.BORDER, highlightcolor=theme.ACCENT,
            command=lambda: app.show_frame("menu"),
        ).pack(side="left", padx=(20, 10), pady=12)
        tk.Label(top_bar, text="Achievements", bg=theme.BG_ELEVATED, fg=theme.ACCENT,
                 font=theme.font(18, weight="bold")).pack(side="left", padx=10)
        theme.breadcrumb(top_bar, "achievements", bg=theme.BG_ELEVATED,
                          player=app.current_player["name"]).pack(side="right", padx=20, pady=12)
        self.crowns_lbl = tk.Label(
            top_bar, text="\U0001F451 Crowns: 0", bg=theme.BG_ELEVATED, fg=theme.SECONDARY,
            font=theme.font(12, weight="bold"),
        )
        self.crowns_lbl.pack(side="right", padx=10, pady=12)
        tk.Button(
            top_bar, text="\U0001F6D2 Crowns Store", bg=theme.BG_ELEVATED, fg=theme.SECONDARY,
            activebackground=theme.SECONDARY_DIM_BG_ELEVATED, activeforeground=theme.SECONDARY,
            font=theme.font(11), relief="flat", padx=14, pady=8, cursor="hand2",
            highlightthickness=1, highlightbackground=theme.SECONDARY, highlightcolor=theme.SECONDARY,
            command=lambda: app.show_frame("store"),
        ).pack(side="right", padx=10, pady=12)

        tabs_row = tk.Frame(self, bg=theme.BG)
        tabs_row.pack(fill="x", padx=40, pady=(20, 0))
        for key, label in _TABS:
            btn = tk.Button(
                tabs_row, text=label, relief="flat", font=theme.font(11, weight="bold"),
                padx=16, pady=8, cursor="hand2", highlightthickness=1,
                command=lambda k=key: self._select_category(k),
            )
            btn.pack(side="left", padx=(0, 10))
            self._tab_buttons[key] = btn
        self._refresh_tab_styles()

        # Game's own sub-filter row -- one button per game with a Game-
        # category achievement, plus "All", further narrowing the Game tab
        # by which game a card belongs to. Built once here (like tabs_row
        # above), packed into the layout immediately below the main tabs,
        # then hidden right away (see _select_category) since the initial
        # category is CATEGORY_ALL, not Game -- self.game_filter_row itself
        # is kept so it can be re-packed in the right spot (before
        # options_row) whenever the Game tab is actually selected. All 9
        # buttons (All + 8 games) don't fit on one line at this width (the
        # main window is a fixed, never-resizable 1200x820 -- see main.py --
        # so this wrap is a one-time, safe-to-hardcode layout decision, not
        # something that needs to react to an actual resize): wrapped onto
        # as many rows as needed, measuring each label's real rendered
        # width up front (tkfont.Font.measure) rather than creating a
        # button, checking its size, and discarding it -- a Button's own
        # master can't be changed after construction, so the row it
        # belongs in has to be decided before it's built, not after.
        self.game_filter_row = tk.Frame(self, bg=theme.BG)
        self.game_filter_row.pack(fill="x", padx=40, pady=(10, 0))
        filter_items = [(GAME_FILTER_ALL, "All")] + [(gk, GAME_LABELS.get(gk, gk)) for gk in GAME_FILTER_KEYS]
        measure_font = tkfont.Font(font=theme.font(_GAME_FILTER_FONT_SIZE, weight="bold"))
        # A button's own rendered width beyond its bare text: padx on both
        # sides, plus a fixed fudge factor for its border/highlightthickness
        # (a couple of pixels, not worth measuring exactly), plus the
        # padx=(0, 8) gap this loop always leaves after it.
        BUTTON_CHROME = 2 * _GAME_FILTER_PADX + 10 + 8
        MAX_ROW_WIDTH = 1100  # content area is ~1120px (1200 window - 2x40 outer padx); a small safety margin
        row = None
        row_width = 0
        for key, label in filter_items:
            btn_width = measure_font.measure(label) + BUTTON_CHROME
            if row is None or row_width + btn_width > MAX_ROW_WIDTH:
                row = tk.Frame(self.game_filter_row, bg=theme.BG)
                row.pack(fill="x", anchor="w", pady=(0, 6))
                row_width = 0
            btn = tk.Button(
                row, text=label, relief="flat", font=theme.font(_GAME_FILTER_FONT_SIZE, weight="bold"),
                padx=_GAME_FILTER_PADX, pady=_GAME_FILTER_PADY, cursor="hand2", highlightthickness=1,
                command=lambda k=key: self._select_game_filter(k),
            )
            btn.pack(side="left", padx=(0, 8))
            self._game_filter_buttons[key] = btn
            row_width += btn_width
        self._refresh_game_filter_styles()
        self.game_filter_row.pack_forget()

        self.options_row = tk.Frame(self, bg=theme.BG)
        self.options_row.pack(fill="x", padx=40, pady=(10, 0))
        self.show_completed_check = tk.Checkbutton(
            self.options_row, text="Show completed", variable=self.show_completed_var,
            command=self._rebuild_cards, bg=theme.BG, fg=theme.FG_DIM, font=theme.font(10),
            activebackground=theme.BG, activeforeground=theme.FG_DIM, selectcolor=theme.BG_ELEVATED,
            highlightthickness=0, bd=0, cursor="hand2", anchor="w",
        )
        self.show_completed_check.pack(side="left")

        scroll = ScrollableFrame(self, bg=theme.BG)
        scroll.pack(fill="both", expand=True)
        self.cards_body = tk.Frame(scroll.inner, bg=theme.BG)
        self.cards_body.pack(fill="both", expand=True, padx=40, pady=20)
        self._rebuild_cards()

    def on_show(self):
        self.crowns_lbl.configure(text=f"\U0001F451 Crowns: {self.app.achievements.crowns}")
        self._rebuild_cards()

    # ------------------------------------------------------------------ category tabs
    def _select_category(self, key):
        self.category_var.set(key)
        self._refresh_tab_styles()
        # "Show completed" only ever affects All/Money/Global/Game -- the
        # Completed tab already shows nothing but earned achievements
        # regardless of it, so disable it there rather than leave a control
        # visible that can't actually change what's on screen.
        self.show_completed_check.configure(state="disabled" if key == CATEGORY_COMPLETED else "normal")
        # The game sub-filter row only ever makes sense on the Game tab --
        # shown/hidden here rather than always visible-but-disabled, since
        # "which game" is meaningless everywhere else. before=self.options_row
        # keeps it in the right spot in the packing order every time it's
        # re-shown, not appended after whatever else is already packed.
        if key == achievements_data.CATEGORY_GAME:
            self.game_filter_row.pack(fill="x", padx=40, pady=(10, 0), before=self.options_row)
        else:
            self.game_filter_row.pack_forget()
        self._rebuild_cards()

    def _refresh_tab_styles(self):
        active_key = self.category_var.get()
        for key, btn in self._tab_buttons.items():
            active = key == active_key
            btn.configure(
                bg=theme.ACCENT_DIM_BG if active else theme.GREY_BTN_BG,
                fg=theme.ACCENT if active else theme.FG_DIM,
                activebackground=theme.ACCENT_DIM_BG if active else theme.GREY_BTN_BG,
                activeforeground=theme.ACCENT if active else theme.FG_DIM,
                highlightbackground=theme.ACCENT if active else theme.GREY_BTN_BORDER,
            )

    # ------------------------------------------------------------------ game sub-filter
    def _select_game_filter(self, key):
        self.game_filter_var.set(key)
        self._refresh_game_filter_styles()
        self._rebuild_cards()

    def _refresh_game_filter_styles(self):
        active_key = self.game_filter_var.get()
        for key, btn in self._game_filter_buttons.items():
            active = key == active_key
            btn.configure(
                bg=theme.ACCENT_DIM_BG if active else theme.GREY_BTN_BG,
                fg=theme.ACCENT if active else theme.FG_DIM,
                activebackground=theme.ACCENT_DIM_BG if active else theme.GREY_BTN_BG,
                activeforeground=theme.ACCENT if active else theme.FG_DIM,
                highlightbackground=theme.ACCENT if active else theme.GREY_BTN_BORDER,
            )

    # ------------------------------------------------------------------ cards
    def _rebuild_cards(self):
        for child in self.cards_body.winfo_children():
            child.destroy()
        category = self.category_var.get()
        is_earned = self.app.achievements.is_earned
        if category == CATEGORY_COMPLETED:
            matches = [a for a in achievements_data.ACHIEVEMENTS.values() if is_earned(a.key)]
            empty_text = "No achievements completed yet."
        else:
            show_completed = self.show_completed_var.get()
            # Only meaningful on the Game tab itself (the row's hidden
            # everywhere else, see _select_category) -- "all" games is a
            # no-op filter, same sentinel-checking shape show_completed's
            # own "show everything" state already uses above.
            game_filter = self.game_filter_var.get() if category == achievements_data.CATEGORY_GAME \
                else GAME_FILTER_ALL
            matches = [
                a for a in achievements_data.ACHIEVEMENTS.values()
                if (category == achievements_data.CATEGORY_ALL or category in a.categories)
                and (game_filter == GAME_FILTER_ALL or a.game_key == game_filter)
                and (show_completed or not is_earned(a.key))
            ]
            empty_text = "All achievements complete!"

        if not matches:
            tk.Label(
                self.cards_body, text=empty_text, bg=theme.BG, fg=theme.FG_DIM,
                font=theme.font(12, weight="bold"),
            ).pack(pady=40)
            return
        for achievement in matches:
            self._build_card(achievement)

    def _build_card(self, achievement):
        earned = self.app.achievements.is_earned(achievement.key)
        card = tk.Frame(
            self.cards_body, bg=theme.BG_ELEVATED,
            highlightbackground=theme.ACCENT if earned else theme.BORDER, highlightthickness=1,
        )
        card.pack(fill="x", pady=6)
        inner = tk.Frame(card, bg=theme.BG_ELEVATED)
        inner.pack(fill="x", padx=16, pady=12)

        header = tk.Frame(inner, bg=theme.BG_ELEVATED)
        header.pack(fill="x")
        name_text = ("✓ " if earned else "") + achievement.name
        name_lbl = tk.Label(header, text=name_text, bg=theme.BG_ELEVATED, fg=theme.ACCENT if earned else theme.FG,
                             font=theme.font(12, weight="bold"))
        name_lbl.pack(side="left")
        badge = tk.Canvas(header, width=110, height=24, bg=theme.BG_ELEVATED, highlightthickness=0)
        badge.pack(side="right")
        theme.pill(badge, 55, 12, f"+{achievement.crowns} Crowns", fill=theme.SECONDARY_DIM_BG_ELEVATED,
                   outline=theme.SECONDARY, text_fg=theme.SECONDARY)

        # Every widget on the card, so hovering any part of it (background,
        # title, badge, tag line) shows the same one tooltip -- see
        # ui/tooltip.py's own attach(), the same grouped/fixed-position
        # approach ui/game_tile.py's locked tiles already use.
        hover_widgets = [card, inner, header, name_lbl, badge]

        tags = []
        if achievement.game_key:
            tags.append(GAME_LABELS.get(achievement.game_key, achievement.game_key))
        if achievement.unlocks_game_keys:
            # Joined into one tag, not one per key -- an achievement that
            # unlocks more than one thing at once (see bj_hands_100/
            # pgp_hands_100) still reads as a single "Unlocks: X and Y"
            # line, not two separate bullet-separated "Unlocks:" tags.
            unlock_names = [GAME_LABELS.get(k, k) for k in achievement.unlocks_game_keys]
            tags.append(f"Unlocks: {' and '.join(unlock_names)}")
        if tags:
            tags_lbl = tk.Label(inner, text="  •  ".join(tags), bg=theme.BG_ELEVATED, fg=theme.FG_DIM,
                                 font=theme.font(8, weight="bold"))
            tags_lbl.pack(anchor="w", pady=(6, 0))
            hover_widgets.append(tags_lbl)

        tooltip.attach(hover_widgets, achievement.description)
