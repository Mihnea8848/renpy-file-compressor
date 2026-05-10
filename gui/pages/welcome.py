from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk

from gui.wizard import C_ACCENT, C_TEXT, C_TEXT_SUB, C_WHITE

if TYPE_CHECKING:
    from gui.wizard import Wizard


class WelcomePage(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame, wizard: "Wizard") -> None:
        super().__init__(parent, fg_color=C_WHITE, corner_radius=0)
        self._wizard = wizard
        self._build()

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # Blue header strip
        header = ctk.CTkFrame(self, fg_color="#003087", corner_radius=0, height=80)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)

        ctk.CTkLabel(
            header,
            text="Welcome to the HHG File Compressor",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#ffffff",
            anchor="w",
        ).place(x=28, y=14)

        ctk.CTkLabel(
            header,
            text="Reduce the disk footprint of your Ren'Py game using modern codecs.",
            font=ctk.CTkFont(size=12),
            text_color="#c8d6e5",
            anchor="w",
        ).place(x=28, y=44)

        # Thin separator below header
        ctk.CTkFrame(self, height=1, fg_color="#d0d0d0", corner_radius=0).grid(
            row=1, column=0, sticky="ew"
        )

        # Body
        body = ctk.CTkFrame(self, fg_color=C_WHITE, corner_radius=0)
        body.grid(row=2, column=0, sticky="nsew", padx=32, pady=20)
        body.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            body,
            text="This wizard will:",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=C_TEXT,
            anchor="w",
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        steps = [
            ("Images",  "Convert PNG / WebP / JPG images to lossless AVIF — typically 20–70% smaller."),
            ("Movies",  "Re-encode video files to AV1, achieving 40–60% smaller files."),
            ("Scripts", "Update .rpy script files to reference the new file formats."),
            ("Safety",  "All changes are staged before any original file is touched.\n"
                        "If anything fails or you cancel, your game files are left intact."),
        ]
        for i, (label, desc) in enumerate(steps):
            row_frame = ctk.CTkFrame(body, fg_color="#f7f9fc", corner_radius=4,
                                     border_width=1, border_color="#dde3ea")
            row_frame.grid(row=i + 1, column=0, sticky="ew", pady=4)
            row_frame.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                row_frame,
                text=label,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=C_ACCENT,
                width=72,
                anchor="e",
            ).grid(row=0, column=0, padx=(12, 10), pady=8, sticky="ne")

            ctk.CTkLabel(
                row_frame,
                text=desc,
                font=ctk.CTkFont(size=12),
                text_color=C_TEXT_SUB,
                anchor="w",
                justify="left",
                wraplength=400,
            ).grid(row=0, column=1, padx=(0, 12), pady=8, sticky="w")

        ctk.CTkLabel(
            body,
            text="Click Next to select your game folder.",
            font=ctk.CTkFont(size=12),
            text_color=C_TEXT_SUB,
            anchor="w",
        ).grid(row=len(steps) + 1, column=0, sticky="w", pady=(16, 0))

    def on_show(self) -> None:
        pass

    def on_next(self) -> None:
        self._wizard.navigate_to("folder_select")
