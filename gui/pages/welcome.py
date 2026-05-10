from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk

if TYPE_CHECKING:
    from gui.wizard import Wizard

_BG = "#16213e"
_ACCENT = "#c0392b"


class WelcomePage(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame, wizard: "Wizard") -> None:
        super().__init__(parent, fg_color=_BG, corner_radius=0)
        self._wizard = wizard
        self._build()

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=2)
        self.grid_rowconfigure(2, weight=1)

        title = ctk.CTkLabel(
            self, text="Welcome",
            font=ctk.CTkFont(size=30, weight="bold"),
            text_color="#ffffff",
        )
        title.grid(row=0, column=0, pady=(48, 4), padx=40, sticky="sw")

        body_text = (
            "This tool will compress the asset archives of your Ren'Py game by\n"
            "converting all images (PNG, WebP, JPG) to lossless AVIF — achieving\n"
            "significantly smaller file sizes with zero quality loss.\n\n"
            "What will happen:\n"
            "  •  Images inside .rpa archives are re-encoded as lossless AVIF.\n"
            "  •  Script files (.rpy) are updated to reference the new format.\n"
            "  •  Compiled bytecode (.rpyc) is removed so the game recompiles\n"
            "     its scripts automatically on the next launch.\n\n"
            "Optionally, you can keep a backup of the original .rpa files.\n\n"
            "Press Next to select your game folder."
        )
        body = ctk.CTkLabel(
            self, text=body_text,
            font=ctk.CTkFont(size=13),
            text_color="#c8d6e5",
            justify="left",
            anchor="nw",
            wraplength=520,
        )
        body.grid(row=1, column=0, pady=0, padx=40, sticky="nw")

        sep = ctk.CTkFrame(self, height=2, fg_color=_ACCENT)
        sep.grid(row=2, column=0, sticky="sew", padx=40, pady=(0, 24))

    def on_show(self) -> None:
        pass

    def on_next(self) -> None:
        self._wizard.navigate_to("folder_select")
