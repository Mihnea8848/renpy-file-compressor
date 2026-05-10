from __future__ import annotations

from pathlib import Path
from tkinter import filedialog
from typing import TYPE_CHECKING

import customtkinter as ctk

from gui.wizard import C_ACCENT, C_BTN_SEC, C_BTN_SEC_H, C_FOOTER_SEP, C_TEXT, C_TEXT_SUB, C_WHITE

if TYPE_CHECKING:
    from gui.wizard import Wizard


class FolderSelectPage(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame, wizard: "Wizard") -> None:
        super().__init__(parent, fg_color=C_WHITE, corner_radius=0)
        self._wizard = wizard
        self._build()

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)

        # Blue header strip
        header = ctk.CTkFrame(self, fg_color="#003087", corner_radius=0, height=80)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        ctk.CTkLabel(
            header, text="Select Game Folder",
            font=ctk.CTkFont(size=16, weight="bold"), text_color="#ffffff", anchor="w",
        ).place(x=28, y=14)
        ctk.CTkLabel(
            header, text="Choose the root directory of your Ren'Py game.",
            font=ctk.CTkFont(size=12), text_color="#c8d6e5", anchor="w",
        ).place(x=28, y=44)

        ctk.CTkFrame(self, height=1, fg_color="#d0d0d0", corner_radius=0).grid(
            row=1, column=0, sticky="ew"
        )

        # Body
        body = ctk.CTkFrame(self, fg_color=C_WHITE, corner_radius=0)
        body.grid(row=2, column=0, sticky="nsew", padx=32, pady=24)
        body.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            body,
            text="Game folder:",
            font=ctk.CTkFont(size=12),
            text_color=C_TEXT,
            anchor="w",
        ).grid(row=0, column=0, sticky="w", pady=(0, 4))

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.grid(row=1, column=0, sticky="ew")
        row.grid_columnconfigure(0, weight=1)

        self._path_var = ctk.StringVar()
        ctk.CTkEntry(
            row,
            textvariable=self._path_var,
            fg_color="#f9f9f9",
            border_color=C_FOOTER_SEP,
            border_width=1,
            text_color=C_TEXT,
            height=32,
            font=ctk.CTkFont(size=12),
            corner_radius=2,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            row, text="Browse…", width=90, height=32,
            fg_color=C_BTN_SEC, hover_color=C_BTN_SEC_H,
            text_color=C_TEXT, font=ctk.CTkFont(size=12),
            border_width=1, border_color=C_FOOTER_SEP,
            corner_radius=2, command=self._browse,
        ).grid(row=0, column=1)

        self._status = ctk.CTkLabel(
            body, text="", font=ctk.CTkFont(size=11),
            text_color="#c0392b", anchor="w",
        )
        self._status.grid(row=2, column=0, sticky="w", pady=(6, 0))

        # Separator
        ctk.CTkFrame(body, height=1, fg_color="#e8e8e8", corner_radius=0).grid(
            row=3, column=0, sticky="ew", pady=20
        )

        # Backup option
        ctk.CTkLabel(
            body,
            text="Backup options:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=C_TEXT,
            anchor="w",
        ).grid(row=4, column=0, sticky="w", pady=(0, 8))

        self._backup_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            body,
            text="Create backup copies of original .rpa files",
            variable=self._backup_var,
            font=ctk.CTkFont(size=12),
            text_color=C_TEXT,
            fg_color=C_ACCENT,
            hover_color=C_ACCENT,
            checkmark_color="#ffffff",
            border_color="#aaaaaa",
            corner_radius=2,
        ).grid(row=5, column=0, sticky="w")

        ctk.CTkLabel(
            body,
            text="Backups are saved as <archive>.rpa.bak alongside the originals.\n"
                 "Without backups, original files are permanently replaced.",
            font=ctk.CTkFont(size=11),
            text_color=C_TEXT_SUB,
            anchor="w",
            justify="left",
        ).grid(row=6, column=0, sticky="w", padx=(24, 0), pady=(4, 0))

    def _browse(self) -> None:
        folder = filedialog.askdirectory(title="Select Ren'Py game folder")
        if folder:
            self._path_var.set(folder)
            self._status.configure(text="")

    def on_show(self) -> None:
        existing = self._wizard.app_state.get("game_folder", "")
        if existing:
            self._path_var.set(existing)

    def on_next(self) -> None:
        folder = self._path_var.get().strip()
        if not folder:
            self._status.configure(text="Please select a folder.")
            return

        path = Path(folder)
        if not path.is_dir():
            self._status.configure(text="Folder does not exist.")
            return

        self._wizard.app_state["game_folder"] = folder
        self._wizard.app_state["backup"] = self._backup_var.get()
        self._wizard.navigate_to("validate")
