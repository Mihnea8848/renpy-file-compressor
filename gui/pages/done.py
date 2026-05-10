from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk

from gui.wizard import C_ACCENT, C_TEXT, C_TEXT_SUB, C_WHITE

if TYPE_CHECKING:
    from gui.wizard import Wizard


def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _pct(old: int, new: int) -> str:
    if old == 0:
        return "—"
    pct = (old - new) / old * 100
    return f"−{pct:.1f}%" if pct >= 0 else f"+{abs(pct):.1f}%"


class DonePage(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame, wizard: "Wizard") -> None:
        super().__init__(parent, fg_color=C_WHITE, corner_radius=0)
        self._wizard = wizard
        self._build()

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # Green header strip
        header = ctk.CTkFrame(self, fg_color="#1a6b3a", corner_radius=0, height=80)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        ctk.CTkLabel(
            header, text="Compression Complete",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#ffffff", anchor="w",
        ).place(x=28, y=14)
        self._header_sub = ctk.CTkLabel(
            header, text="",
            font=ctk.CTkFont(size=12), text_color="#a8e6c0", anchor="w")
        self._header_sub.place(x=28, y=44)

        ctk.CTkFrame(self, height=1, fg_color="#d0d0d0", corner_radius=0).grid(
            row=1, column=0, sticky="ew")

        # Summary label
        self._summary = ctk.CTkLabel(
            self, text="",
            font=ctk.CTkFont(size=12),
            text_color=C_TEXT_SUB,
            anchor="w",
        )
        self._summary.grid(row=2, column=0, padx=32, pady=(14, 4), sticky="w")

        # Results table in a scrollable frame
        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color=C_WHITE, corner_radius=0,
            scrollbar_fg_color="#f0f0f0", scrollbar_button_color="#c0c0c0",
        )
        self._scroll.grid(row=3, column=0, sticky="nsew", padx=32, pady=(0, 8))
        self._scroll.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self._note = ctk.CTkLabel(
            self,
            text="Launch the game once to let Ren'Py recompile updated scripts from .rpy source.",
            font=ctk.CTkFont(size=11),
            text_color=C_TEXT_SUB,
            anchor="w",
        )
        self._note.grid(row=4, column=0, padx=32, pady=(0, 8), sticky="w")

    def on_show(self) -> None:
        for w in self._scroll.winfo_children():
            w.destroy()

        results = self._wizard.app_state.get("compress_results", [])
        if not results:
            self._summary.configure(text="No results available.")
            return

        total_old = sum(r["size"] for r in results)
        total_new = sum(r.get("new_size", r["size"]) for r in results)
        saved = total_old - total_new

        self._header_sub.configure(
            text=f"Saved {_fmt_size(saved)} ({_pct(total_old, total_new)})"
        )
        self._summary.configure(
            text=f"Total: {_fmt_size(total_old)} → {_fmt_size(total_new)}"
        )

        # Table header
        headers = ["Archive", "Original", "Compressed", "Savings"]
        for col, h in enumerate(headers):
            ctk.CTkLabel(
                self._scroll, text=h,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=C_TEXT_SUB,
            ).grid(row=0, column=col, padx=(10, 4), pady=(4, 6), sticky="w")

        ctk.CTkFrame(
            self._scroll, height=1, fg_color="#d0d0d0", corner_radius=0
        ).grid(row=1, column=0, columnspan=4, sticky="ew", padx=10, pady=(0, 4))

        for i, r in enumerate(results):
            new = r.get("new_size", r["size"])
            row_vals = [
                r["name"],
                _fmt_size(r["size"]),
                _fmt_size(new),
                _pct(r["size"], new),
            ]
            for col, val in enumerate(row_vals):
                color = "#27ae60" if col == 3 and r["size"] > new else C_TEXT_SUB
                ctk.CTkLabel(
                    self._scroll, text=val,
                    font=ctk.CTkFont(size=11),
                    text_color=C_TEXT if col == 0 else color,
                    fg_color="#f7f9fc" if i % 2 == 0 else C_WHITE,
                ).grid(row=i + 2, column=col, padx=(10, 4), pady=3, sticky="w")

    def on_next(self) -> None:
        self._wizard.destroy()
