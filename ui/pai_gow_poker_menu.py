"""
The Pai Gow Poker picker screen -- shown between the main menu and an
actual Pai Gow Poker table now that there are two tables (Standard, Face
Up), replacing what used to be two separate main-menu tiles. See
ui/table_menu.py's own docstring for the shared screen this subclasses.
"""
from ui import game_icons
from ui.table_menu import TableMenuFrame

# (icon, name, subtitle, game_key, frame_name) -- same 5-tuple shape as
# ui/main_menu.py's own GAMES rows, just laid out as one row instead of a
# whole grid.
TILES = [
    (game_icons.draw_pai_gow_face_up_icon, "Face Up!", "Dealer plays face up, with no commission.",
     "pai_gow_poker_face_up", "pai_gow_poker_face_up"),
    (game_icons.draw_pai_gow_icon, "Standard", "'Fortune' variant, with face down dealer hand.",
     "pai_gow_poker", "pai_gow_poker"),
]


class PaiGowPokerMenuFrame(TableMenuFrame):
    GAME_TITLE = "Pai Gow Poker"
    BREADCRUMB = "pai_gow_poker_menu"
    TILES = TILES
