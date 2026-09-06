"""
The Blackjack picker screen -- shown between the main menu and an actual
Blackjack table now that there are three tables (Standard, Counting, 6:5).
See ui/table_menu.py's own docstring for the shared screen this subclasses.
"""
from ui import game_icons
from ui.table_menu import TableMenuFrame

# (icon, name, subtitle, game_key, frame_name) -- same 5-tuple shape as
# ui/main_menu.py's own GAMES rows, just laid out as one row instead of a
# whole grid. Every tile reuses Blackjack's existing icon unchanged (no
# variant-specific icon was asked for -- an easy swap later if wanted).
TILES = [
    (game_icons.draw_blackjack_icon, "6:5", "6:5 is a scam, in real life you should walk away",
     "blackjack_6_5", "blackjack_6_5"),
    (game_icons.draw_blackjack_icon, "Standard", "Blackjack pays 3:2, as it should.",
     "blackjack", "blackjack"),
    (game_icons.draw_blackjack_icon, "Counting", "8 deck shoe with visible count",
     "blackjack_count", "blackjack_count"),
]


class BlackjackMenuFrame(TableMenuFrame):
    GAME_TITLE = "Blackjack"
    BREADCRUMB = "blackjack_menu"
    TILES = TILES
