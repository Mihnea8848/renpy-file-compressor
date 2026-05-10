from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk

if TYPE_CHECKING:
    from gui.wizard import Wizard

_BG = "#16213e"
_ACCENT = "#c0392b"
_ROW_ODD = "#1e2d45"
_ROW_EVEN = "#172338"


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
    return f"{pct:.1f}% saved"


class DonePage(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame, wizard: "Wizard") -> None:
        super().__init__(parent, fg_color=_BG, corner_radius=0)
        self._wizard = wizard
        self._build()

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            self, text="Done!",
            font=ctk.CTkFont(size=30, weight="bold"),
            text_color="#2ecc71",
        ).grid(row=0, column=0, pady=(44, 4), padx=40, sticky="w")

        self._summary_label = ctk.CTkLabel(
            self, text="",
            font=ctk.CTkFont(size=13),
            text_color="#c8d6e5",
        )
        self._summary_label.grid(row=1, column=0, pady=(0, 16), padx=40, sticky="w")

        self._table_frame = ctk.CTkScrollableFrame(
            self, fg_color=_ROW_EVEN, corner_radius=6,
        )
        self._table_frame.grid(row=2, column=0, sticky="nsew", padx=40, pady=(0, 16))
        self._table_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self._note = ctk.CTkLabel(
            self,
            text="Launch the game once to let Ren'Py recompile updated scripts.",
            font=ctk.CTkFont(size=11),
            text_color="#7f8c8d",
        )
        self._note.grid(row=3, column=0, padx=40, pady=(0, 8), sticky="w")

    def on_show(self) -> None:
        for w in self._table_frame.winfo_children():
            w.destroy()

        results = self._wizard.app_state.get("compress_results", [])
        if not results:
            self._summary_label.configure(text="No results available.")
            return

        total_old = sum(r["size"] for r in results)
        total_new = sum(r.get("new_size", r["size"]) for r in results)
        saved = total_old - total_new

        self._summary_label.configure(
            text=f"Compression complete — "
                 f"{_fmt_size(total_old)} → {_fmt_size(total_new)}  "
                 f"({_pct(total_old, total_new)})"
        )

        headers = ["Archive", "Original", "Compressed", "Savings"]
        for col, h in enumerate(headers):
            ctk.CTkLabel(
                self._table_frame, text=h,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=_ACCENT,
            ).grid(row=0, column=col, padx=10, pady=6, sticky="w")

        for i, r in enumerate(results):
            new = r.get("new_size", r["size"])
            row_vals = [
                r["name"],
                _fmt_size(r["size"]),
                _fmt_size(new),
                _pct(r["size"], new),
            ]
            for col, val in enumerate(row_vals):
                ctk.CTkLabel(
                    self._table_frame, text=val,
                    font=ctk.CTkFont(size=12),
                    text_color="#dde3ea",
                ).grid(row=i + 1, column=col, padx=10, pady=4, sticky="w")

    def on_next(self) -> None:
        self._wizard.destroy()
