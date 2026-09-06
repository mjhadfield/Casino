"""
The single catalog of whole-app themes -- what used to be just a poker
table's own felt colour (core/settings.py's old TABLE_THEMES) plus the
Crowns-gated premium felts (core/unlocks.py's old PREMIUM_TABLE_THEMES) has
grown into the one thing that skins the ENTIRE app: menus, Settings, Store,
every screen, not just a table's own felt. Both catalogs now live here,
in core/ (not ui/) so this stays framework-agnostic the same way every
other core/ module is -- ui/theme.py (which knows about tkinter) reads
FROM here, never the other way around.

Each entry carries 8 keys:
  - felt / felt_dark / accent -- unchanged from the old table-felt system;
    every game table still reads these three directly (draw_card_back,
    the paytable/round-result panel chrome, etc.) via
    core.settings.SettingsManager.theme(). ~145 call sites across every
    game depend on exactly this shape -- don't rename or drop these.
  - bg / bg_elevated / menu_bg / border / border_soft -- the app-wide
    "chrome" tokens ui/theme.py used to hardcode as one fixed palette.
    ui/theme.py's own FG/FG_DIM/WARN/SECONDARY/lock-red palette stay
    theme-INVARIANT (defined once, never per-theme) -- those are neutral
    ink/signal colours, not brand colours, and hold up against every
    background below without needing their own 7 hand-tuned variants.

"Terminal" is the default, and its 5 new chrome keys are today's exact
ui/theme.py values (BG/BG_ELEVATED/MENU_BG/BORDER/BORDER_SOFT) -- a
byte-for-byte no-op for every existing player, since Terminal is the only
theme that's ever actually been applied app-wide so far. The other 7 are
hand-authored extensions of each theme's own existing felt/felt_dark/accent
colourway, following the same relationship Terminal itself has: menu_bg
equals felt exactly, bg sits darker than felt_dark, bg_elevated sits
between the two, and border/border_soft are felt tinted a little towards
the theme's own accent.

Adding a new theme is exactly this: one more 8-key entry in THEMES (free)
or PREMIUM_THEMES (Crowns Store / achievement-gated, via
core.unlocks.is_unlocked/set_unlocked same as everything else there) --
nothing else needs to know a new one exists.
"""

# Always-free themes -- no unlock state needed at all (see core/unlocks.py's
# own docstring for why that distinction matters: PREMIUM_THEMES below is
# the one place membership implies "needs an is_unlocked() check").
THEMES = {
    "Terminal": {
        "felt": "#141917", "felt_dark": "#0b0e0d", "accent": "#35e0a0",
        "bg": "#06080a", "bg_elevated": "#0c1210", "menu_bg": "#141917",
        "border": "#1c2622", "border_soft": "#141b18",
    },
    "Classic Green": {
        "felt": "#0a2e14", "felt_dark": "#051a0b", "accent": "#39ff88",
        "bg": "#040f07", "bg_elevated": "#081c0d", "menu_bg": "#0a2e14",
        "border": "#173a22", "border_soft": "#0f2717",
    },
    "Amber CRT": {
        "felt": "#3a2308", "felt_dark": "#1f1204", "accent": "#ffb347",
        "bg": "#170d02", "bg_elevated": "#2a1706", "menu_bg": "#3a2308",
        "border": "#4a2f0d", "border_soft": "#301f08",
    },
    "Muted Grey": {
        "felt": "#2a2a2a", "felt_dark": "#151515", "accent": "#cfd6d1",
        "bg": "#0d0d0d", "bg_elevated": "#1c1c1c", "menu_bg": "#2a2a2a",
        "border": "#3a3a3a", "border_soft": "#242424",
    },
}

# Premium, Crowns-gated themes -- purchased in the Crowns Store
# (core/achievements.py's AchievementsManager.purchase_theme, priced via
# core/achievements_data.py's THEME_UNLOCK_PRICE_CROWNS, one flat price for
# all of them) or unlocked by a future achievement the same way any game is.
# Same exact 8-key shape as THEMES -- chip colours (ui/chips.py's
# CHIP_DENOMINATIONS) are a fixed, never-themed casino convention and are
# explicitly NOT part of either catalog.
PREMIUM_THEMES = {
    "Crimson Velvet": {
        "felt": "#3a0d14", "felt_dark": "#1f0509", "accent": "#ff4d6d",
        "bg": "#140306", "bg_elevated": "#26080d", "menu_bg": "#3a0d14",
        "border": "#4a1420", "border_soft": "#2e0a12",
    },
    "Royal Gold": {
        "felt": "#1a1506", "felt_dark": "#0d0a02", "accent": "#ffd700",
        "bg": "#0a0803", "bg_elevated": "#14100a", "menu_bg": "#1a1506",
        "border": "#2e2610", "border_soft": "#1c170a",
    },
    "Neon Void": {
        "felt": "#0a0018", "felt_dark": "#05000c", "accent": "#b026ff",
        "bg": "#030008", "bg_elevated": "#08000f", "menu_bg": "#0a0018",
        "border": "#22103a", "border_soft": "#160a26",
    },
    "Blue Ice": {
        "felt": "#0d2a45", "felt_dark": "#071a2c", "accent": "#5fd4ff",
        "bg": "#040d17", "bg_elevated": "#08182a", "menu_bg": "#0d2a45",
        "border": "#1a3a5a", "border_soft": "#102640",
    },
}


def resolve(name):
    """Every theme name a player could have saved resolves through here --
    a free THEMES entry, an owned PREMIUM_THEMES one, or (an unknown/
    missing name -- a save predating a theme, or a premium one no longer
    owned) the Terminal default. Callers stay ownership-agnostic on
    purpose, same caveat core/settings.py's old theme() docstring always
    carried: something else is solely responsible for only ever letting a
    player SELECT a theme they actually own."""
    return THEMES.get(name) or PREMIUM_THEMES.get(name) or THEMES["Terminal"]
