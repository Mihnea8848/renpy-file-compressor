from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import customtkinter as ctk
from PIL import Image

# ── Palette ────────────────────────────────────────────────────────────────
BANNER_W    = 230
WIN_W       = 860
WIN_H       = 620

C_BANNER_BG  = "#f0f0f0"   # light fallback — banner column bg
C_WHITE      = "#ffffff"
C_FOOTER_BG  = "#f0f0f0"
C_FOOTER_SEP = "#d0d0d0"
C_ACCENT     = "#0078d4"   # Windows blue
C_ACCENT_HOV = "#005fa3"
C_BTN_SEC    = "#e1e1e1"
C_BTN_SEC_H  = "#c8c8c8"
C_TEXT       = "#1a1a1a"
C_TEXT_SUB   = "#555555"

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


def _load_banner(w: int, h: int) -> ctk.CTkImage:
    from PIL import ImageDraw
    # Gradient background: light gray (#e0e0e0) at top → white at bottom
    bg = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(bg)
    for y in range(h):
        t = y / max(h - 1, 1)
        v = int(224 + (255 - 224) * t)  # 224=#e0e0e0 → 255=#ffffff
        draw.line([(0, y), (w - 1, y)], fill=(v, v, v))
    bg = bg.convert("RGBA")

    path = Path(__file__).parent.parent / "assets" / "banner.png"
    if path.exists():
        pil = Image.open(path).convert("RGBA")
        aspect = pil.width / pil.height
        target_aspect = w / h
        if aspect > target_aspect:
            new_w = int(pil.height * target_aspect)
            left = (pil.width - new_w) // 2
            pil = pil.crop((left, 0, left + new_w, pil.height))
        else:
            new_h = int(pil.width / target_aspect)
            pil = pil.crop((0, 0, pil.width, new_h))
        pil = pil.resize((w, h), Image.LANCZOS)
        bg.paste(pil, (0, 0), pil)

    return ctk.CTkImage(light_image=bg.convert("RGB"), size=(w, h))


class Wizard(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Hero's Harem Guild — File Compressor")
        self.geometry(f"{WIN_W}x{WIN_H}")
        self.resizable(False, False)
        self.configure(fg_color=C_WHITE)

        self.app_state: dict = {
            "game_folder": "",
            "backup": True,
            "turbo_workers": max(1, (os.cpu_count() or 4) - 2),
            "scan_results": None,
            "compress_results": None,
        }

        self._pages: dict[str, ctk.CTkFrame] = {}
        self._history: list[str] = []
        self._build_layout()
        self._load_pages()
        self.show_page("welcome")

    # ── Layout ─────────────────────────────────────────────────────────────
    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, minsize=BANNER_W, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, minsize=54, weight=0)

        # Left banner
        self._banner_frame = ctk.CTkFrame(
            self, width=BANNER_W, fg_color=C_WHITE, corner_radius=0
        )
        self._banner_frame.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self._banner_frame.grid_propagate(False)

        banner_img = _load_banner(BANNER_W, WIN_H)
        ctk.CTkLabel(self._banner_frame, image=banner_img, text="").place(
            x=0, y=0, relwidth=1, relheight=1
        )

        # Right content area
        self._content_frame = ctk.CTkFrame(
            self, fg_color=C_WHITE, corner_radius=0
        )
        self._content_frame.grid(row=0, column=1, sticky="nsew")

        # Footer
        self._footer = ctk.CTkFrame(
            self, fg_color=C_FOOTER_BG, corner_radius=0,
            border_width=0,
        )
        self._footer.grid(row=1, column=1, sticky="nsew")
        self._footer.grid_propagate(False)

        # Thin top separator line on footer
        ctk.CTkFrame(
            self._footer, height=1, fg_color=C_FOOTER_SEP, corner_radius=0
        ).place(x=0, y=0, relwidth=1)

        self._btn_back = ctk.CTkButton(
            self._footer, text="< Back", width=90, height=32,
            fg_color=C_BTN_SEC, hover_color=C_BTN_SEC_H,
            text_color=C_TEXT, font=ctk.CTkFont(size=12),
            border_width=1, border_color=C_FOOTER_SEP,
            corner_radius=2, command=self._go_back,
        )
        self._btn_back.place(relx=0.68, rely=0.56, anchor="center")

        self._btn_next = ctk.CTkButton(
            self._footer, text="Next >", width=100, height=32,
            fg_color=C_ACCENT, hover_color=C_ACCENT_HOV,
            text_color="#ffffff", font=ctk.CTkFont(size=12),
            corner_radius=2, command=self._go_next,
        )
        self._btn_next.place(relx=0.84, rely=0.56, anchor="center")

    def _load_pages(self) -> None:
        from gui.pages.welcome import WelcomePage
        from gui.pages.folder_select import FolderSelectPage
        from gui.pages.validate import ValidatePage
        from gui.pages.compress import CompressPage
        from gui.pages.done import DonePage

        for name, cls in [
            ("welcome",       WelcomePage),
            ("folder_select", FolderSelectPage),
            ("validate",      ValidatePage),
            ("compress",      CompressPage),
            ("done",          DonePage),
        ]:
            page = cls(self._content_frame, wizard=self)
            page.place(x=0, y=0, relwidth=1, relheight=1)
            self._pages[name] = page

    # ── Navigation ─────────────────────────────────────────────────────────
    def show_page(self, name: str) -> None:
        if self._history and self._history[-1] == name:
            return
        self._history.append(name)
        for p in self._pages.values():
            p.lower()
        page = self._pages[name]
        page.lift()
        page.on_show()
        self._refresh_nav(name)

    def _refresh_nav(self, name: str) -> None:
        cfg = {
            "welcome":       (False, True,  "Next >"),
            "folder_select": (True,  True,  "Next >"),
            "validate":      (True,  True,  "Start"),
            "compress":      (False, False, ""),
            "done":          (False, True,  "Close"),
        }
        show_back, show_next, label = cfg.get(name, (True, True, "Next >"))
        self._btn_back.configure(
            state="normal" if show_back else "disabled",
            fg_color=C_BTN_SEC if show_back else "#e8e8e8",
            text_color=C_TEXT if show_back else "#aaaaaa",
        )
        self._btn_next.configure(
            state="normal" if show_next else "disabled",
            text=label,
            fg_color=C_ACCENT if show_next else "#aaaaaa",
        )

    def set_next_enabled(self, enabled: bool) -> None:
        self._btn_next.configure(
            state="normal" if enabled else "disabled",
            fg_color=C_ACCENT if enabled else "#aaaaaa",
        )

    def _go_back(self) -> None:
        if len(self._history) > 1:
            self._history.pop()
            prev = self._history.pop()
            self.show_page(prev)

    def _go_next(self) -> None:
        if self._history:
            self._pages[self._history[-1]].on_next()

    def navigate_to(self, name: str) -> None:
        self.show_page(name)
