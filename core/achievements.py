"""
Per-player Crowns/achievement progression -- follows the same load_json/
save_json convention every other manager uses (core/persistence.py), except
it also holds a live `app` reference, the one existing precedent for that
being core/jackpot.py's JackpotManager(path, app) -- needed here so award()
can apply an achievement's own unlocks_game_keys via app.unlocks directly, and so
check_deposit()/check_round() can read app.finance/app.unlocks without every
caller having to plumb that data through by hand. Never touches tkinter --
showing the actual banner is the caller's job (see ui/achievement_banner.py),
kept out of core/ the same way every other UI concern is.

The cross-game HANDS_LADDER (hands_10/100/500/...) always means "play N
ROUNDS" -- it's sourced from FinanceManager's own hands_played, incremented
once per round for every game uniformly, tied to that same round's overall
net_result (see FinanceManager.record_round_played's own biggest_win
tracking), so it can't mean anything else.

Per-game milestones (PER_GAME_HANDS_MILESTONES) mean "play N hands", full
stop -- i.e. whatever the Stats screen itself would call "Total Hands" for
that game (core/game_stats.py's record_hand -- one call per round for every
game except Blackjack, which calls it once per actual Hand, correctly
over-counting a split box or a second box in play). check_round's own
`hand_count` parameter (default 1, correct as-is for every game that's
always exactly one hand per round) is how a game whose hands-per-round can
exceed 1 reports that -- see games/blackjack/ui.py's own call site. This
used to be a uniform round-based tally instead (deliberately NOT reusing
GameStatsManager's hand-count, to dodge this exact inconsistency) --
flipped the other way after a live player reasonably expected "Play 20
Hands (Blackjack)" to match the "Total Hands: 20" they could already see on
the Stats screen for that same game, and found it didn't.
"""
from core.achievements_data import (
    ACHIEVEMENT_GAME_KEY_ALIASES,
    ACHIEVEMENTS,
    CARD_STYLE_UNLOCK_PRICE_CROWNS,
    DEPOSIT_LADDER,
    FEATURE_UNLOCK_PRICE_CROWNS,
    HANDS_LADDER,
    PER_GAME_HANDS_MILESTONES,
    STORE_UNLOCK_PRICE_CROWNS,
    THEME_UNLOCK_PRICE_CROWNS,
    WITHDRAW_LADDER,
)
from core.persistence import load_json, save_json
from core.settings import STANDARD_CARD_STYLES, TABLE_THEMES
from core.unlocks import PREMIUM_CARD_STYLES, PREMIUM_FEATURES, PREMIUM_TABLE_THEMES

DEFAULT_ACHIEVEMENTS_DATA = {
    "earned": [],              # achievement keys already earned, in earn order
    "crowns": 0,               # current spendable Crowns balance
    "game_rounds_played": {},  # game_key -> int, HANDS played in that game (see check_round's hand_count)
    "streaks": {},             # game_key -> {"length": int, "direction": "win"|"lose"|None}
    # No more "themes_owned" list -- a premium theme's ownership lives in
    # app.unlocks now, the same is_unlocked/set_unlocked mechanism a game's
    # own lock state already uses (see core/unlocks.py's own docstring and
    # _reconcile_unlocks' migration below, for a save that still has one).
}


class AchievementsManager:
    def __init__(self, save_path, app, sandbox=False):
        self.save_path = save_path
        self.app = app
        # Sandbox Mode disables the whole achievement/Crowns layer -- every
        # check_* below returns [] immediately without even incrementing
        # its own counters, and owns_theme() reports every theme as owned
        # (see main.py's start_session, which derives this from the
        # player's own account_type). Never persisted here: it's re-derived
        # fresh from the roster every session, not stored in this file's
        # own data.
        self.sandbox = sandbox
        # Fixed field names (unlike unlocks.py's dynamically-growing game-key
        # set) -- load_json's own shallow dict.update over
        # DEFAULT_ACHIEVEMENTS_DATA already backfills any top-level key
        # missing from an older save, same convention as
        # FinanceManager/SettingsManager; no extra migration needed.
        self.data = load_json(save_path, DEFAULT_ACHIEVEMENTS_DATA)
        # NOT calling self._reconcile_unlocks() here -- self.app.unlocks
        # doesn't exist yet at this point in main.py's start_session (every
        # manager is built as a local variable first; the live self.app.X
        # pointers are only swapped in afterwards, all at once, since every
        # frame reads them during its own construction). The caller runs it
        # explicitly once that swap has actually happened -- see
        # main.py's start_session, right after self.achievements is set.

    def _reconcile_unlocks(self):
        """Catch-up passes for progress that predates a rule change -- call
        once per session, after self.app.unlocks is actually live (see
        __init__'s own note above); cheap (a handful of dict lookups per
        pass) and safe to always run, whether or not any of them actually
        finds anything to do. Every pass only ever RAISES a stored number
        (or turns a lock ON), never the reverse -- reconciling can catch a
        player up, never set them back.

        Pass T: a premium theme this file used to own directly, back when
        theme ownership was its own themes_owned list here rather than
        living in app.unlocks like every other unlockable -- fold any such
        list into app.unlocks once, then drop it; nothing reads
        themes_owned any more once this has run.

        Pass 0: a raw game_key that's since become an
        ACHIEVEMENT_GAME_KEY_ALIASES entry (e.g. Pai Gow Poker's Face Up
        table used to record its rounds under its own
        "pai_gow_poker_face_up" bucket, before achievement-counting was
        merged across both Pai Gow tables) -- fold any such legacy bucket
        into its canonical one, one time, so an existing player's
        already-played hands count immediately rather than only newly
        played ones. check_round itself only ever writes to the canonical
        key from here on, so this legacy key stops growing the moment this
        has run once; safe to leave in permanently as a no-op after that.

        Pass 1: game_rounds_played can UNDER-count a game whose hands-per-
        round can exceed 1 (currently just Blackjack -- see check_round's
        own hand_count parameter), if some of a player's progress predates
        that parameter existing (it used to increment by a flat 1 always,
        matching every OTHER game's own always-1-hand-per-round shape, but
        not Blackjack's). GameStatsManager's own per-game hand tally
        (core/game_stats.py's record_hand, one call per ACTUAL hand
        already, including a split or a second box) is ground truth for
        "how many hands has this player really played" -- raise
        game_rounds_played to match it wherever it's currently behind,
        folding in the same ACHIEVEMENT_GAME_KEY_ALIASES merge as Pass 0
        (summing every raw key's own Stats hand-count for a merged
        canonical bucket like "pai_gow_poker"). Deliberately a max(), not
        an overwrite: a player who used Settings' own per-game stats reset
        clears GameStatsManager's tally without touching this one, and
        that must never claw back real achievement progress.

        Pass 2: an achievement that gained (or was repointed at different)
        unlocks_game_keys AFTER a player had already earned it -- award()
        only ever applies unlocks_game_keys at the exact moment an
        achievement is newly earned, so one that was already in `earned`
        before some of those effects existed on it (e.g. tcp_hands_100 used
        to be a plain no-effect completionist achievement before the
        progression chain gave it one) would otherwise never apply the
        missing effect(s) -- no amount of further play re-triggers award()
        for an already-earned key.

        Pass 3: a per-game milestone whose THRESHOLD moved (e.g. "unlock
        the next game" moving from 100 hands to 20) or a new one being
        added below an existing player's already-recorded game_rounds_played
        total -- PER_GAME_HANDS_MILESTONES is normally only ever consulted
        from inside check_round, so a player who already has, say, 100
        Blackjack hands recorded wouldn't see the now-earned 20-hand
        achievement (and whatever it unlocks) until they happened to play
        one more Blackjack round -- this re-checks every threshold against
        already-recorded progress right away instead of waiting for that.
        Run after Passes 0-1, so it sees each bucket's true, merged total."""
        if self.sandbox:
            return  # unlocks are already bypassed entirely for Sandbox
        owned_themes = self.data.pop("themes_owned", None)
        if owned_themes:
            for theme_name in owned_themes:
                if not self.app.unlocks.is_unlocked(theme_name):
                    self.app.unlocks.set_unlocked(theme_name, True)
            self._save()  # drop the now-empty legacy key from disk right away

        rounds = self.data["game_rounds_played"]
        changed = False
        for raw_key, canonical_key in ACHIEVEMENT_GAME_KEY_ALIASES.items():
            if raw_key in rounds:
                rounds[canonical_key] = rounds.get(canonical_key, 0) + rounds.pop(raw_key)
                changed = True

        for canonical_key in PER_GAME_HANDS_MILESTONES:
            raw_keys = [canonical_key] + [
                raw for raw, canon in ACHIEVEMENT_GAME_KEY_ALIASES.items() if canon == canonical_key
            ]
            true_hands = sum(sum(self.app.game_stats.game_hand_counts(rk).values()) for rk in raw_keys)
            if true_hands > rounds.get(canonical_key, 0):
                rounds[canonical_key] = true_hands
                changed = True
        if changed:
            self._save()  # persist Passes 0-1 immediately, not just whenever award() next happens to save

        for key in self.data["earned"]:
            achievement = ACHIEVEMENTS.get(key)  # None for a since-deleted key (e.g. the old tcp_hands_50) -- skip
            if achievement:
                for unlock_key in achievement.unlocks_game_keys:
                    if not self.app.unlocks.is_unlocked(unlock_key):
                        self.app.unlocks.set_unlocked(unlock_key, True)

        for game_key, milestones in PER_GAME_HANDS_MILESTONES.items():
            played = rounds.get(game_key, 0)
            for threshold, key in milestones:
                if played >= threshold:
                    self.award(key)

    # ------------------------------------------------------------ queries
    def is_earned(self, key):
        return key in self.data["earned"]

    def earned_keys(self):
        return list(self.data["earned"])

    @property
    def crowns(self):
        return self.data["crowns"]

    def game_streak(self, game_key):
        """{"length": int, "direction": "win"|"lose"|None} -- this game's
        current consecutive win/lose streak. Exposed publicly (not just an
        internal implementation detail of the two Global streak
        achievements below) so a future GAME-specific streak achievement
        (e.g. "win 10 in a row" scoped to one particular game) can read the
        exact same counters rather than tracking its own."""
        return self.data.get("streaks", {}).get(game_key, {"length": 0, "direction": None})

    def owns_theme(self, theme_name):
        # TABLE_THEMES are always free, no unlock state needed at all; a
        # premium one's ownership is just app.unlocks.is_unlocked, exactly
        # like a game's own lock state -- which already reports True
        # unconditionally for a Sandbox player (see UnlocksManager's own
        # always_unlocked), so there's no separate self.sandbox check to
        # make here any more.
        return theme_name in TABLE_THEMES or self.app.unlocks.is_unlocked(theme_name)

    def owns_card_style(self, style_name):
        # Exactly owns_theme's own reasoning, one catalog over: STANDARD_
        # CARD_STYLES are always free, a premium one's ownership is
        # app.unlocks.is_unlocked -- same Sandbox bypass included for free.
        return style_name in STANDARD_CARD_STYLES or self.app.unlocks.is_unlocked(style_name)

    def owns_feature(self, feature_key):
        # No always-free counterpart catalog here (unlike themes/card
        # styles) -- every feature starts locked, so this is just the
        # unlock check directly, Sandbox bypass included for free.
        return self.app.unlocks.is_unlocked(feature_key)

    # ------------------------------------------------------------ awarding
    def award(self, key):
        """No-op (returns None) if `key` is unknown or already earned;
        otherwise marks it earned, credits its Crowns, applies every one of
        its unlocks_game_keys (if any) via app.unlocks, and returns the
        Achievement so the caller can hand it to the banner queue."""
        if key in self.data["earned"]:
            return None
        achievement = ACHIEVEMENTS.get(key)
        if achievement is None:
            return None
        self.data["earned"].append(key)
        self.data["crowns"] += achievement.crowns
        for unlock_key in achievement.unlocks_game_keys:
            self.app.unlocks.set_unlocked(unlock_key, True)
        self._save()
        return achievement

    def check_deposit(self):
        """The lifetime cumulative deposit ladder (£200/1,000/5,000/10,000),
        read straight off FinanceManager's own running total -- every
        threshold at or below it is (re-)checked, same "back-fill on first
        ship" idempotency as check_round's own HANDS_LADDER loop. Call
        after a successful app.finance.deposit(...)."""
        if self.sandbox:
            return []
        newly = []
        lifetime_deposited = self.app.finance.data["lifetime_deposited"]
        for threshold, key in DEPOSIT_LADDER:
            if lifetime_deposited >= threshold:
                got = self.award(key)
                if got:
                    newly.append(got)
        return newly

    def check_withdraw(self, amount):
        """The single-transaction withdrawal ladder (£200/1,000/5,000/
        10,000) -- deliberately checked against THIS ONE withdrawal's own
        `amount`, not a lifetime running total (contrast check_deposit
        above), so it only fires for a withdrawal that's itself big enough,
        not a lifetime's worth of small ones adding up. A single big enough
        withdrawal still clears every threshold under it at once. Call
        after a successful app.finance.withdraw(amount)."""
        if self.sandbox:
            return []
        newly = []
        for threshold, key in WITHDRAW_LADDER:
            if amount >= threshold:
                got = self.award(key)
                if got:
                    newly.append(got)
        return newly

    def check_round(self, game_key: str, net_result, hand_count=1):
        """The generic per-round hook, called at every game's own settle
        point -- covers the cross-game hands-ladder, this one game's own
        hands-played milestone (if it has one), and this one game's own
        win/lose streak. Returns every newly-awarded Achievement, in fire
        order.

        `game_key` is whatever raw GAME_KEY the calling table's own UI
        passes in -- normalized once, right here, via
        ACHIEVEMENT_GAME_KEY_ALIASES, so a family of tables that should
        count as "the same game" for achievement purposes (Pai Gow Poker's
        Standard + Face Up) accumulates into one shared bucket, exactly
        like Blackjack's own 3 tables already do for free by simply sharing
        one literal GAME_KEY end to end. Every counter below (rounds
        played, milestones, streak) is keyed off the NORMALIZED key, not
        the raw one.

        `hand_count` is how many actual hands this one round settled -- 1
        for every game except Blackjack, where a second box or a split can
        make a single round worth 2, 3 or 4 (see games/blackjack/ui.py's
        own call site, which counts exactly what it's about to hand
        GameStatsManager.record_hand). Only the per-game milestone ladder
        below scales by it; the cross-game HANDS_LADDER above and the
        win/lose streak below are deliberately still one-per-ROUND (see
        this module's own docstring)."""
        if self.sandbox:
            return []
        newly = []
        game_key = ACHIEVEMENT_GAME_KEY_ALIASES.get(game_key, game_key)

        total_hands = self.app.finance.data["hands_played"]
        for threshold, key in HANDS_LADDER:
            if total_hands >= threshold:
                got = self.award(key)
                if got:
                    newly.append(got)

        rounds = self.data["game_rounds_played"]
        rounds[game_key] = rounds.get(game_key, 0) + hand_count
        for threshold, key in PER_GAME_HANDS_MILESTONES.get(game_key, []):
            if rounds[game_key] >= threshold:
                got = self.award(key)
                if got:
                    newly.append(got)

        streak = self._update_streak(game_key, net_result)
        if streak["length"] >= 5:
            key = "streak_win_5" if streak["direction"] == "win" else "streak_lose_5"
            got = self.award(key)
            if got:
                newly.append(got)

        self._save()
        return newly

    def check_three_card_poker(self, result):
        """result: games/three_card_poker/logic.py's RoundResult."""
        if self.sandbox:
            return []
        newly = []
        if (result.outcome == "win" and result.pair_plus_bet > 0
                and result.pair_plus_return > result.pair_plus_bet
                and result.prime_bet > 0 and result.prime_return > result.prime_bet):
            got = self.award("tcp_triple_bonus")
            if got:
                newly.append(got)
        if result.folded and result.prime_bet > 0 and result.prime_return > result.prime_bet:
            got = self.award("tcp_fold_prime")
            if got:
                newly.append(got)
        return newly

    def check_blackjack(self, summary):
        """summary: games/blackjack/logic.py's RoundSummary."""
        if self.sandbox:
            return []
        newly = []
        if len(summary.boxes) == 2:
            if all(b.main_returned > b.main_wagered for b in summary.boxes):
                got = self.award("bj_both_boxes_main")
                if got:
                    newly.append(got)
            if all(any(ret > getattr(b, f"{k}_bet") for k, ret in b.side_bet_results.items())
                   for b in summary.boxes):
                got = self.award("bj_both_boxes_side")
                if got:
                    newly.append(got)
        return newly

    # ------------------------------------------------------------ Crowns Store
    def purchase_unlock(self, game_key):
        if self.app.unlocks.is_unlocked(game_key) or self.data["crowns"] < STORE_UNLOCK_PRICE_CROWNS:
            return False
        self.data["crowns"] -= STORE_UNLOCK_PRICE_CROWNS
        self.app.unlocks.set_unlocked(game_key, True)
        self._save()
        return True

    def purchase_theme(self, theme_name):
        if (theme_name not in PREMIUM_TABLE_THEMES or self.owns_theme(theme_name)
                or self.data["crowns"] < THEME_UNLOCK_PRICE_CROWNS):
            return False
        self.data["crowns"] -= THEME_UNLOCK_PRICE_CROWNS
        self.app.unlocks.set_unlocked(theme_name, True)
        self._save()
        return True

    def purchase_card_style(self, style_name):
        if (style_name not in PREMIUM_CARD_STYLES or self.owns_card_style(style_name)
                or self.data["crowns"] < CARD_STYLE_UNLOCK_PRICE_CROWNS):
            return False
        self.data["crowns"] -= CARD_STYLE_UNLOCK_PRICE_CROWNS
        self.app.unlocks.set_unlocked(style_name, True)
        self._save()
        return True

    def purchase_feature(self, feature_key):
        if (feature_key not in PREMIUM_FEATURES or self.owns_feature(feature_key)
                or self.data["crowns"] < FEATURE_UNLOCK_PRICE_CROWNS):
            return False
        self.data["crowns"] -= FEATURE_UNLOCK_PRICE_CROWNS
        self.app.unlocks.set_unlocked(feature_key, True)
        self._save()
        return True

    # ------------------------------------------------------------ internal
    def _update_streak(self, game_key, net_result):
        streaks = self.data.setdefault("streaks", {})
        cur = streaks.get(game_key, {"length": 0, "direction": None})
        if net_result > 1e-9:
            direction = "win"
        elif net_result < -1e-9:
            direction = "lose"
        else:
            return cur  # a push neither extends nor breaks a streak
        cur = ({"length": cur["length"] + 1, "direction": direction} if cur.get("direction") == direction
               else {"length": 1, "direction": direction})
        streaks[game_key] = cur
        return cur

    def _save(self):
        save_json(self.save_path, self.data)
