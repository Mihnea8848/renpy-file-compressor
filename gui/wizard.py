from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont

if TYPE_CHECKING:
    from gui.pages.welcome import WelcomePage
    from gui.pages.folder_select import FolderSelectPage
    from gui.pages.validate import ValidatePage
    from gui.pages.compress import CompressPage
    from gui.pages.done import DonePage

BANNER_W = 220
WIN_W = 820
WIN_H = 520

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

_ACCENT = "#c0392b"
_BANNER_BG = "#1a1a2e"
_CONTENT_BG = "#16213e"
_DARK_BG = "#0f3460"


def _make_banner_image(width: int, height: int) -> ctk.CTkImage:
    assets_dir = Path(__file__).parent.parent / "assets"
    banner_path = assets_dir / "banner.png"

    if banner_path.exists():
        pil = Image.open(banner_path).resize((width, height), Image.LANCZOS)
    else:
        pil = _generate_banner(width, height)

    return ctk.CTkImage(light_image=pil, dark_image=pil, size=(width, height))


def _generate_banner(width: int, height: int) -> Image.Image:
    img = Image.new("RGB", (width, height), color=_BANNER_BG)
    draw = ImageDraw.Draw(img)

    # Decorative gradient-like stripes
    for i in range(0, height, 4):
        alpha = int(30 + 20 * abs((i / height) - 0.5))
        draw.line([(0, i), (width, i)], fill=(26, 26, 62))

    # Accent bar on the right edge
    draw.rectangle([(width - 4, 0), (width, height)], fill=_ACCENT)

    # Title text — use default PIL font (no external font required)
    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
    except Exception:
        font_large = ImageFont.load_default()
        font_small = font_large

    title = "Hero's\nHarem\nGuild"
    sub = "File Compressor"

    draw.text((20, height // 2 - 60), title, fill="#e0e0e0", font=font_large)
    draw.text((20, height // 2 + 20), sub, fill=_ACCENT, font=font_small)

    return img


class Wizard(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Hero's Harem Guild — File Compressor")
        self.geometry(f"{WIN_W}x{WIN_H}")
        self.resizable(False, False)
        self.configure(fg_color=_CONTENT_BG)

        # Shared state passed between pages
        self.app_state: dict = {
            "game_folder": "",
            "backup": True,
            "scan_results": None,   # set by ValidatePage
            "compress_results": None,  # set by CompressPage
        }

        self._build_layout()
        self._pages: dict[str, ctk.CTkFrame] = {}
        self._history: list[str] = []
        self._load_pages()
        self.show_page("welcome")

    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, minsize=BANNER_W, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, minsize=60, weight=0)

        # Left banner
        self._banner_frame = ctk.CTkFrame(self, width=BANNER_W, fg_color=_BANNER_BG, corner_radius=0)
        self._banner_frame.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self._banner_frame.grid_propagate(False)

        self._banner_img = _make_banner_image(BANNER_W, WIN_H)
        self._banner_label = ctk.CTkLabel(self._banner_frame, image=self._banner_img, text="")
        self._banner_label.place(x=0, y=0, relwidth=1, relheight=1)

        # Right content area
        self._content_frame = ctk.CTkFrame(self, fg_color=_CONTENT_BG, corner_radius=0)
        self._content_frame.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)

        # Footer with Back / Next buttons
        self._footer = ctk.CTkFrame(self, fg_color=_DARK_BG, height=60, corner_radius=0)
        self._footer.grid(row=1, column=1, sticky="nsew")
        self._footer.grid_propagate(False)

        self._btn_back = ctk.CTkButton(
            self._footer, text="← Back", width=110, height=36,
            fg_color="#2c2c54", hover_color="#3d3d6b",
            command=self._go_back,
        )
        self._btn_back.place(relx=0.65, rely=0.5, anchor="center")

        self._btn_next = ctk.CTkButton(
            self._footer, text="Next →", width=130, height=36,
            fg_color=_ACCENT, hover_color="#922b21",
            command=self._go_next,
        )
        self._btn_next.place(relx=0.85, rely=0.5, anchor="center")

    def _load_pages(self) -> None:
        from gui.pages.welcome import WelcomePage
        from gui.pages.folder_select import FolderSelectPage
        from gui.pages.validate import ValidatePage
        from gui.pages.compress import CompressPage
        from gui.pages.done import DonePage

        for name, cls in [
            ("welcome", WelcomePage),
            ("folder_select", FolderSelectPage),
            ("validate", ValidatePage),
            ("compress", CompressPage),
            ("done", DonePage),
        ]:
            page = cls(self._content_frame, wizard=self)
            page.place(x=0, y=0, relwidth=1, relheight=1)
            self._pages[name] = page

    # ------------------------------------------------------------------
    def show_page(self, name: str) -> None:
        if self._history and self._history[-1] == name:
            return
        self._history.append(name)
        for p in self._pages.values():
            p.lower()
        page = self._pages[name]
        page.lift()
        page.on_show()
        self._update_nav(name)

    def _update_nav(self, name: str) -> None:
        nav_map = {
            "welcome":       (False, True,  "Next →"),
            "folder_select": (True,  True,  "Next →"),
            "validate":      (True,  True,  "Start Compression"),
            "compress":      (False, False, ""),
            "done":          (False, True,  "Close"),
        }
        show_back, show_next, next_label = nav_map.get(name, (True, True, "Next →"))
        self._btn_back.configure(state="normal" if show_back else "disabled",
                                  fg_color="#2c2c54" if show_back else "#1a1a2e")
        self._btn_next.configure(state="normal" if show_next else "disabled",
                                  text=next_label)

    def set_next_enabled(self, enabled: bool) -> None:
        self._btn_next.configure(state="normal" if enabled else "disabled")

    def _go_back(self) -> None:
        if len(self._history) > 1:
            self._history.pop()
            prev = self._history[-1]
            self._history.pop()
            self.show_page(prev)

    def _go_next(self) -> None:
        if not self._history:
            return
        current = self._history[-1]
        page = self._pages[current]
        page.on_next()

    def navigate_to(self, name: str) -> None:
        self.show_page(name)
