from __future__ import annotations

import os
from pathlib import Path
from tkinter import filedialog
from typing import TYPE_CHECKING

import customtkinter as ctk

if TYPE_CHECKING:
    from gui.wizard import Wizard

_BG = "#16213e"
_ACCENT = "#c0392b"
_ENTRY_BG = "#1e2d45"


class FolderSelectPage(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame, wizard: "Wizard") -> None:
        super().__init__(parent, fg_color=_BG, corner_radius=0)
        self._wizard = wizard
        self._build()

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self, text="Select Game Folder",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color="#ffffff",
        ).grid(row=0, column=0, pady=(48, 6), padx=40, sticky="w")

        ctk.CTkLabel(
            self,
            text="Select the root folder of your Ren'Py game — the one that\n"
                 "contains the /game/ and /renpy/ sub-folders.",
            font=ctk.CTkFont(size=13),
            text_color="#c8d6e5",
            justify="left",
        ).grid(row=1, column=0, pady=(0, 28), padx=40, sticky="w")

        # Folder picker row
        picker_row = ctk.CTkFrame(self, fg_color="transparent")
        picker_row.grid(row=2, column=0, sticky="ew", padx=40)
        picker_row.grid_columnconfigure(0, weight=1)

        self._path_var = ctk.StringVar()
        self._entry = ctk.CTkEntry(
            picker_row,
            textvariable=self._path_var,
            fg_color=_ENTRY_BG,
            border_color="#2c4a6e",
            text_color="#e0e0e0",
            height=38,
            font=ctk.CTkFont(size=12),
        )
        self._entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        ctk.CTkButton(
            picker_row, text="Browse…", width=100, height=38,
            fg_color="#2c4a6e", hover_color="#3a5f8a",
            command=self._browse,
        ).grid(row=0, column=1)

        # Status label
        self._status_label = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=12),
            text_color="#e74c3c",
        )
        self._status_label.grid(row=3, column=0, pady=(10, 0), padx=40, sticky="w")

        # Backup checkbox
        self._backup_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            self,
            text="Create backup of original .rpa files (recommended)",
            variable=self._backup_var,
            font=ctk.CTkFont(size=13),
            text_color="#c8d6e5",
            fg_color=_ACCENT,
            hover_color="#922b21",
        ).grid(row=4, column=0, pady=(32, 0), padx=40, sticky="w")

        ctk.CTkLabel(
            self,
            text="Backups are saved as <archive>.rpa.bak in the same folder.",
            font=ctk.CTkFont(size=11),
            text_color="#7f8c8d",
        ).grid(row=5, column=0, pady=(4, 0), padx=52, sticky="w")

    def _browse(self) -> None:
        folder = filedialog.askdirectory(title="Select Ren'Py game folder")
        if folder:
            self._path_var.set(folder)
            self._status_label.configure(text="")

    def on_show(self) -> None:
        existing = self._wizard.app_state.get("game_folder", "")
        if existing:
            self._path_var.set(existing)

    def on_next(self) -> None:
        folder = self._path_var.get().strip()
        if not folder:
            self._status_label.configure(text="Please select a folder first.")
            return

        path = Path(folder)
        if not path.is_dir():
            self._status_label.configure(text="Folder does not exist.")
            return

        if not (path / "renpy").is_dir():
            self._status_label.configure(
                text="No /renpy/ directory found — this doesn't look like a Ren'Py game."
            )
            return

        if not (path / "game").is_dir():
            self._status_label.configure(
                text="No /game/ directory found — this doesn't look like a Ren'Py game."
            )
            return

        rpas = list((path / "game").glob("*.rpa"))
        if not rpas:
            self._status_label.configure(
                text="No .rpa files found in /game/. Nothing to compress."
            )
            return

        self._status_label.configure(text="")
        self._wizard.app_state["game_folder"] = folder
        self._wizard.app_state["backup"] = self._backup_var.get()
        self._wizard.navigate_to("validate")
