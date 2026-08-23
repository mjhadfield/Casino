import tkinter as tk
from tkinter import messagebox

from core.settings import TABLE_THEMES
from ui.scrollable import ScrollableFrame

BG = "#0b0b0b"
PANEL_BG = "#0e2a1a"    # matches the game's paytable/payout plaques
PANEL_BORDER = "#d4af37"
GOLD = "#d4af37"


class SettingsFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self._toggle_redraws = []
        self.theme_canvases = {}

        self.sound_var = tk.BooleanVar(value=app.settings.get("sound_enabled"))
        self.anim_var = tk.BooleanVar(value=app.settings.get("animations_enabled"))
        self.theme_var = tk.StringVar(value=app.settings.get("table_theme"))
        self.jackpot_rate_var = tk.StringVar(value=f"{app.settings.get('jackpot_rate_per_second'):.2f}")
        self._original = self._snapshot()

        top_bar = tk.Frame(self, bg="#111111")
        top_bar.pack(fill="x")
        tk.Button(
            top_bar, text="← Back", bg="#1c1c1c", fg="#cccccc", relief="flat",
            font=("Helvetica", 11), padx=12, pady=6, cursor="hand2",
            command=lambda: self._on_cancel(),
        ).pack(side="left", padx=20, pady=12)
        tk.Label(top_bar, text="Settings", bg="#111111", fg=GOLD,
                 font=("Georgia", 18, "bold")).pack(side="left", padx=10)

        # Scrollable -- the Preferences/Jackpot/Danger Zone panels plus the
        # Save/Cancel row can add up to more height than the window
        # comfortably fits (they used to just get cut off, Save included,
        # with no indication there was more below); see ui/scrollable.py.
        scroll = ScrollableFrame(self, bg=BG)
        scroll.pack(fill="both", expand=True)
        body = tk.Frame(scroll.inner, bg=BG)
        body.pack(fill="both", expand=True, padx=40, pady=30)

        panel = tk.Frame(body, bg=PANEL_BG, highlightbackground=PANEL_BORDER, highlightthickness=2)
        panel.pack(fill="x")
        inner = tk.Frame(panel, bg=PANEL_BG)
        inner.pack(fill="x", padx=26, pady=22)

        tk.Label(inner, text="PREFERENCES", bg=PANEL_BG, fg=GOLD,
                 font=("Georgia", 13, "bold")).pack(anchor="w", pady=(0, 14))

        self._make_toggle_row(inner, "Sound Effects", self.sound_var)
        self._make_toggle_row(inner, "Animations", self.anim_var)

        tk.Frame(inner, bg="#3a6b4c", height=1).pack(fill="x", pady=16)

        self._make_theme_row(inner)

        jackpot_panel = tk.Frame(body, bg=PANEL_BG, highlightbackground=PANEL_BORDER, highlightthickness=2)
        jackpot_panel.pack(fill="x", pady=(24, 0))
        jackpot_inner = tk.Frame(jackpot_panel, bg=PANEL_BG)
        jackpot_inner.pack(fill="x", padx=26, pady=22)
        tk.Label(jackpot_inner, text="PROGRESSIVE JACKPOT", bg=PANEL_BG, fg=GOLD,
                 font=("Georgia", 13, "bold")).pack(anchor="w", pady=(0, 14))
        self._make_jackpot_rate_row(jackpot_inner)
        tk.Frame(jackpot_inner, bg="#3a6b4c", height=1).pack(fill="x", pady=16)
        self._make_jackpot_debug_row(jackpot_inner)

        danger_panel = tk.Frame(body, bg="#1a0d0d", highlightbackground="#5a1c1c", highlightthickness=2)
        danger_panel.pack(fill="x", pady=(24, 0))
        danger_inner = tk.Frame(danger_panel, bg="#1a0d0d")
        danger_inner.pack(fill="x", padx=26, pady=18)
        tk.Label(danger_inner, text="DANGER ZONE", bg="#1a0d0d", fg="#e05555",
                 font=("Georgia", 12, "bold")).pack(anchor="w")
        tk.Label(
            danger_inner, text="Reset lifetime statistics. Your balance is not affected.",
            bg="#1a0d0d", fg="#cc9999", font=("Helvetica", 9),
        ).pack(anchor="w", pady=(6, 10))
        tk.Button(
            danger_inner, text="Reset Statistics", bg="#5a1c1c", fg="#ffffff", relief="flat",
            font=("Helvetica", 10, "bold"), padx=14, pady=6, cursor="hand2",
            command=self._reset_stats,
        ).pack(anchor="w")

        action_row = tk.Frame(body, bg=BG)
        action_row.pack(pady=(28, 0))
        tk.Button(
            action_row, text="SAVE", bg=GOLD, fg="#111111", relief="flat",
            font=("Helvetica", 13, "bold"), padx=30, pady=10, cursor="hand2",
            command=self._on_save,
        ).pack(side="left", padx=8)
        tk.Button(
            action_row, text="Cancel", bg="#333333", fg="#f0f0f0", relief="flat",
            font=("Helvetica", 11), padx=20, pady=10, cursor="hand2",
            command=self._on_cancel,
        ).pack(side="left", padx=8)

    # ------------------------------------------------------------------ toggle switches
    def _make_toggle_row(self, parent, label, var):
        row = tk.Frame(parent, bg=PANEL_BG)
        row.pack(fill="x", pady=8)
        tk.Label(row, text=label, bg=PANEL_BG, fg="#f0f0f0", font=("Helvetica", 12)).pack(side="left")

        canvas = tk.Canvas(row, width=46, height=24, bg=PANEL_BG, highlightthickness=0, cursor="hand2")
        canvas.pack(side="right")

        def redraw():
            canvas.delete("all")
            on = var.get()
            track_fill = "#1f8a4c" if on else "#3a3a3a"
            track_outline = GOLD if on else "#666666"
            self._draw_rounded_rect(canvas, 2, 2, 44, 22, radius=11,
                                     fill=track_fill, outline=track_outline, width=1.5)
            knob_cx = 34 if on else 12
            canvas.create_oval(knob_cx - 8, 4, knob_cx + 8, 20, fill="#ffffff", outline="")

        def on_click(event=None):
            var.set(not var.get())
            redraw()

        canvas.bind("<Button-1>", on_click)
        redraw()
        self._toggle_redraws.append(redraw)

    def _draw_rounded_rect(self, canvas, x1, y1, x2, y2, radius, **kwargs):
        points = [
            x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
            x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
        ]
        return canvas.create_polygon(points, smooth=True, **kwargs)

    # ------------------------------------------------------------------ theme swatches
    def _make_theme_row(self, parent):
        row = tk.Frame(parent, bg=PANEL_BG)
        row.pack(fill="x", pady=(6, 0))
        tk.Label(row, text="Table Felt Theme", bg=PANEL_BG, fg="#f0f0f0",
                 font=("Helvetica", 12)).pack(anchor="w", pady=(0, 10))

        swatch_row = tk.Frame(row, bg=PANEL_BG)
        swatch_row.pack(anchor="w")
        for name, colors in TABLE_THEMES.items():
            cell = tk.Frame(swatch_row, bg=PANEL_BG)
            cell.pack(side="left", padx=(0, 18))
            canvas = tk.Canvas(cell, width=44, height=44, bg=PANEL_BG, highlightthickness=0, cursor="hand2")
            canvas.pack()
            canvas.bind("<Button-1>", lambda e, n=name: self._select_theme(n))
            tk.Label(cell, text=name, bg=PANEL_BG, fg="#cccccc", font=("Helvetica", 9)).pack(pady=(4, 0))
            self.theme_canvases[name] = canvas
        self._draw_theme_swatches()

    def _draw_theme_swatches(self):
        for name, canvas in self.theme_canvases.items():
            canvas.delete("all")
            colors = TABLE_THEMES[name]
            if name == self.theme_var.get():
                canvas.create_oval(1, 1, 43, 43, outline=GOLD, width=3)
            canvas.create_oval(8, 8, 36, 36, fill=colors["felt"], outline=colors["accent"], width=2)

    def _select_theme(self, name):
        self.theme_var.set(name)
        self._draw_theme_swatches()

    # ------------------------------------------------------------------ jackpot
    def _make_jackpot_rate_row(self, parent):
        row = tk.Frame(parent, bg=PANEL_BG)
        row.pack(fill="x", pady=4)
        tk.Label(row, text="Growth Rate", bg=PANEL_BG, fg="#f0f0f0", font=("Helvetica", 12)).pack(side="left")
        tk.Label(row, text="£ / second", bg=PANEL_BG, fg="#999999", font=("Helvetica", 9)).pack(side="right")
        tk.Entry(
            row, textvariable=self.jackpot_rate_var, width=8, bg="#1c1c1c", fg="#f0f0f0",
            insertbackground="#f0f0f0", relief="flat", justify="right",
        ).pack(side="right", padx=8)

    def _make_jackpot_debug_row(self, parent):
        tk.Label(
            parent, text="Manually set the jackpot amount -- for debugging, applies immediately.",
            bg=PANEL_BG, fg="#999999", font=("Helvetica", 9),
        ).pack(anchor="w", pady=(0, 8))
        row = tk.Frame(parent, bg=PANEL_BG)
        row.pack(fill="x")
        tk.Label(row, text="Set Jackpot", bg=PANEL_BG, fg="#f0f0f0", font=("Helvetica", 12)).pack(side="left")
        self.jackpot_debug_var = tk.StringVar(value=f"{self.app.jackpot.amount:.2f}")
        tk.Button(
            row, text="Set", bg="#333333", fg="#cccccc", relief="flat",
            font=("Helvetica", 9, "bold"), padx=12, pady=4, cursor="hand2",
            command=self._apply_jackpot_debug_value,
        ).pack(side="right")
        tk.Entry(
            row, textvariable=self.jackpot_debug_var, width=10, bg="#1c1c1c", fg="#f0f0f0",
            insertbackground="#f0f0f0", relief="flat", justify="right",
        ).pack(side="right", padx=8)
        tk.Label(row, text="£", bg=PANEL_BG, fg="#999999", font=("Helvetica", 9)).pack(side="right")

    def _apply_jackpot_debug_value(self):
        try:
            amount = float(self.jackpot_debug_var.get().strip().replace("£", "").replace(",", ""))
        except ValueError:
            messagebox.showwarning("Invalid Amount", "Enter a valid £ amount for the jackpot.")
            return
        self.app.jackpot.set_amount(amount)
        self.jackpot_debug_var.set(f"{self.app.jackpot.amount:.2f}")
        messagebox.showinfo("Jackpot Updated", f"Jackpot set to £{self.app.jackpot.amount:,.2f}.")

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
            if not messagebox.askyesno("Unsaved Changes", "Unsaved changes, quit without saving?"):
                return
        self.app.show_frame("menu")

    def _reset_stats(self):
        if messagebox.askyesno(
            "Reset Statistics",
            "This will reset lifetime statistics, including the per-game breakdown on the "
            "Stats screen. Your balance will not change. Continue?",
        ):
            self.app.finance.reset_stats_only()
            self.app.game_stats.reset()
            self.app.on_balance_changed()
            messagebox.showinfo("Done", "Lifetime statistics have been reset.")

    # ------------------------------------------------------------------ lifecycle
    def on_show(self):
        self.sound_var.set(self.app.settings.get("sound_enabled"))
        self.anim_var.set(self.app.settings.get("animations_enabled"))
        self.theme_var.set(self.app.settings.get("table_theme"))
        self.jackpot_rate_var.set(f"{self.app.settings.get('jackpot_rate_per_second'):.2f}")
        self.jackpot_debug_var.set(f"{self.app.jackpot.amount:.2f}")
        for redraw in self._toggle_redraws:
            redraw()
        self._draw_theme_swatches()
        self._original = self._snapshot()
