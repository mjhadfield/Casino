"""
A vertically-scrollable container: a Canvas + Scrollbar pair around an inner
Frame that holds the real content. The inner frame is free to grow taller
than the canvas -- a screen with a long, data-driven layout (e.g. Stats'
per-game breakdown, which grows with every game added to the library) would
otherwise just have its overflow silently clipped, with nothing on screen to
say there's more below. The scrollbar only actually appears once the content
overflows -- see _update_scrollbar_visibility -- so a screen that happens to
fit doesn't grow a redundant, always-disabled-looking scrollbar.

Usage: build a ScrollableFrame(parent, bg) and pack/place it where the old
plain body Frame used to go, then pack the screen's actual content into its
`.inner` attribute instead of into the ScrollableFrame itself.
"""
import tkinter as tk


class ScrollableFrame(tk.Frame):
    def __init__(self, parent, bg):
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        # Scrollbar is deliberately not packed yet -- only shown once the
        # content actually overflows, see _update_scrollbar_visibility.
        self.canvas.pack(side="left", fill="both", expand=True)

        self.inner = tk.Frame(self.canvas, bg=bg)
        self._inner_window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<Enter>", lambda e: self._bind_wheel())
        self.canvas.bind("<Leave>", lambda e: self._unbind_wheel())

    def _on_inner_configure(self, _event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._update_scrollbar_visibility()

    def _on_canvas_configure(self, event):
        # The inner frame always matches the canvas's own width -- only its
        # height is free to grow past it and scroll.
        self.canvas.itemconfigure(self._inner_window, width=event.width)
        self._update_scrollbar_visibility()

    def _update_scrollbar_visibility(self):
        bbox = self.canvas.bbox("all")
        content_height = (bbox[3] - bbox[1]) if bbox else 0
        overflowing = content_height > self.canvas.winfo_height()
        showing = bool(self.scrollbar.winfo_ismapped())
        if overflowing and not showing:
            self.scrollbar.pack(side="right", fill="y")
        elif not overflowing and showing:
            self.scrollbar.pack_forget()

    # Only scrolls while the pointer's actually over this widget, via
    # bind_all -- bound/unbound on Enter/Leave -- so it doesn't steal wheel
    # events aimed at some other widget once the pointer moves away.
    def _bind_wheel(self):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)      # Windows/macOS
        self.canvas.bind_all("<Button-4>", self._on_mousewheel_linux)  # Linux/X11 scroll up
        self.canvas.bind_all("<Button-5>", self._on_mousewheel_linux)  # Linux/X11 scroll down

    def _unbind_wheel(self):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event):
        if self.scrollbar.winfo_ismapped():
            self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def _on_mousewheel_linux(self, event):
        if self.scrollbar.winfo_ismapped():
            self.canvas.yview_scroll(-1 if event.num == 4 else 1, "units")
