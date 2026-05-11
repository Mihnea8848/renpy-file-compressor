from __future__ import annotations

import os
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import customtkinter as ctk

from core.converter import avif_path, convert_to_avif, is_image
from core.rpa import iter_files, write_rpa
from core.script_patcher import is_rpy, is_rpyc, patch_rpy_with_map
from core.video_converter import video_path, convert_video, is_video
from gui.wizard import C_ACCENT, C_BTN_SEC, C_BTN_SEC_H, C_FOOTER_SEP, C_TEXT, C_TEXT_SUB, C_WHITE

if TYPE_CHECKING:
    from gui.wizard import Wizard


def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _fmt_time(secs: float) -> str:
    s = int(secs)
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}m {s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}m"


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _pct_str(original: int, output: int) -> str:
    pct = (original - output) / max(original, 1) * 100
    return f"-{pct:.0f}%" if pct >= 0 else f"+{abs(pct):.0f}% larger"


class CompressPage(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame, wizard: "Wizard") -> None:
        super().__init__(parent, fg_color=C_WHITE, corner_radius=0)
        self._wizard = wizard
        self._cancel_event = threading.Event()
        self._build()

    # ── Layout ─────────────────────────────────────────────────────────────
    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)

        # Blue header strip
        header = ctk.CTkFrame(self, fg_color="#003087", corner_radius=0, height=80)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        ctk.CTkLabel(
            header, text="Compressing…",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#ffffff", anchor="w",
        ).place(x=28, y=14)
        self._header_sub = ctk.CTkLabel(
            header, text="Preparing…",
            font=ctk.CTkFont(size=12), text_color="#c8d6e5", anchor="w")
        self._header_sub.place(x=28, y=44)

        ctk.CTkFrame(self, height=1, fg_color="#d0d0d0", corner_radius=0).grid(
            row=1, column=0, sticky="ew")

        # Progress section
        prog = ctk.CTkFrame(self, fg_color=C_WHITE, corner_radius=0)
        prog.grid(row=2, column=0, sticky="ew", padx=28, pady=(14, 0))
        prog.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(prog, text="Overall progress",
                     font=ctk.CTkFont(size=11), text_color=C_TEXT_SUB,
                     anchor="w").grid(row=0, column=0, sticky="w")

        self._overall_bar = ctk.CTkProgressBar(
            prog, height=14, corner_radius=3,
            fg_color="#e8e8e8", progress_color=C_ACCENT)
        self._overall_bar.set(0)
        self._overall_bar.grid(row=1, column=0, sticky="ew", pady=(3, 3))

        self._overall_label = ctk.CTkLabel(
            prog, text="", font=ctk.CTkFont(size=11), text_color=C_TEXT_SUB, anchor="w")
        self._overall_label.grid(row=2, column=0, sticky="w")

        # ETA / speed / elapsed row
        self._eta_label = ctk.CTkLabel(
            prog, text="",
            font=ctk.CTkFont(size=11), text_color=C_TEXT_SUB, anchor="w")
        self._eta_label.grid(row=3, column=0, sticky="w", pady=(1, 6))

        # Archive context
        self._arch_label = ctk.CTkLabel(
            prog, text="",
            font=ctk.CTkFont(size=11), text_color=C_TEXT_SUB, anchor="w")
        self._arch_label.grid(row=4, column=0, sticky="w")

        self._file_bar = ctk.CTkProgressBar(
            prog, height=8, corner_radius=2,
            fg_color="#e8e8e8", progress_color="#27ae60")
        self._file_bar.set(0)
        self._file_bar.grid(row=5, column=0, sticky="ew", pady=(3, 2))

        self._file_pct_label = ctk.CTkLabel(
            prog, text="",
            font=ctk.CTkFont(size=11), text_color=C_TEXT_SUB, anchor="w")
        self._file_pct_label.grid(row=6, column=0, sticky="w")

        # Console log
        ctk.CTkLabel(self, text="Log",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=C_TEXT_SUB, anchor="w").grid(
            row=3, column=0, sticky="w", padx=28, pady=(10, 2))

        self._log = ctk.CTkTextbox(
            self,
            fg_color="#1e1e1e",
            text_color="#d4d4d4",
            font=ctk.CTkFont(family="Courier", size=11),
            corner_radius=4,
            border_width=1,
            border_color="#d0d0d0",
            state="disabled",
            wrap="word",
        )
        self._log.grid(row=5, column=0, sticky="nsew", padx=28, pady=(0, 8))

        self._cancel_btn = ctk.CTkButton(
            self, text="Cancel", width=90, height=28,
            fg_color=C_BTN_SEC, hover_color=C_BTN_SEC_H,
            text_color=C_TEXT, font=ctk.CTkFont(size=11),
            border_width=1, border_color=C_FOOTER_SEP,
            corner_radius=2, command=self._cancel,
        )
        self._cancel_btn.grid(row=6, column=0, padx=28, pady=(0, 8), sticky="w")

    # ── Lifecycle ──────────────────────────────────────────────────────────
    def on_show(self) -> None:
        self._cancel_event.clear()
        self._overall_bar.set(0)
        self._file_bar.set(0)
        self._overall_label.configure(text="")
        self._eta_label.configure(text="")
        self._arch_label.configure(text="")
        self._file_pct_label.configure(text="")
        self._header_sub.configure(text="Preparing…")
        self._cancel_btn.configure(state="normal", text="Cancel")
        self._log_clear()
        threading.Thread(target=self._run, daemon=True).start()

    def on_next(self) -> None:
        pass

    def _cancel(self) -> None:
        self._cancel_event.set()
        self._cancel_btn.configure(state="disabled", text="Cancelling…")

    # ── Logging helpers ────────────────────────────────────────────────────
    def _log_clear(self) -> None:
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")

    def _log_write(self, msg: str, color: str = "#d4d4d4") -> None:
        def _do():
            self._log.configure(state="normal")
            tag = f"col_{color.replace('#', '')}"
            self._log.tag_config(tag, foreground=color)
            self._log.insert("end", f"[{_ts()}] {msg}\n", tag)
            self._log.see("end")
            self._log.configure(state="disabled")
        self.after(0, _do)

    def _log_info(self, msg: str) -> None: self._log_write(msg, "#d4d4d4")
    def _log_ok(self,   msg: str) -> None: self._log_write(msg, "#4ec9b0")
    def _log_warn(self, msg: str) -> None: self._log_write(msg, "#ce9178")
    def _log_error(self,msg: str) -> None: self._log_write(msg, "#f44747")

    # ── Progress update helpers ────────────────────────────────────────────
    def _update_overall(self, processed: int, total: int, saved: int,
                        start_time: float) -> None:
        frac = processed / max(total, 1)
        elapsed = time.time() - start_time

        # Speed / ETA
        if processed > 0 and elapsed > 0.5:
            speed = processed / elapsed
            remaining = (total - processed) / speed
            eta_text = (
                f"Elapsed: {_fmt_time(elapsed)}  •  "
                f"{speed:.1f} img/s  •  "
                f"ETA: ~{_fmt_time(remaining)}"
            )
        elif elapsed > 0:
            eta_text = f"Elapsed: {_fmt_time(elapsed)}"
        else:
            eta_text = ""

        self.after(0, self._overall_bar.set, frac)
        self.after(0, self._overall_label.configure, {
            "text": (
                f"{frac * 100:.0f}%  •  "
                f"Saved {_fmt_size(max(0, saved))}  •  "
                f"{processed} / {total} files"
            )
        })
        self.after(0, self._eta_label.configure, {"text": eta_text})

    def _update_arch(self, arch_desc: str, arch_conv: int,
                     arch_saved: int, arch_skipped: int, extra: str = "") -> None:
        parts = [arch_desc + extra]
        if arch_conv > 0:
            pct = arch_saved / arch_conv * 100
            sign = "-" if pct >= 0 else "+"
            parts.append(f"savings: {sign}{abs(pct):.0f}%")
        if arch_skipped:
            parts.append(f"{arch_skipped} kept original")
        self.after(0, self._arch_label.configure, {"text"  : "  |  ".join(parts)})

    # ── Main compression thread ────────────────────────────────────────────
    def _run(self) -> None:
        results     = self._wizard.app_state.get("scan_results", [])
        backup      = self._wizard.app_state.get("backup", True)
        n_workers   = self._wizard.app_state.get(
            "turbo_workers", max(1, (os.cpu_count() or 4) - 2)
        )
        game_dir    = Path(self._wizard.app_state["game_folder"]) / "game"
        start_time  = time.time()

        stage_dir = game_dir / ".hhg_compress_stage"
        try:
            stage_dir.mkdir(exist_ok=True)
        except OSError as e:
            self._log_error(f"Cannot create staging directory: {e}")
            return

        staged: dict[Path, Path] = {}
        compress_results: list[dict] = []
        total_items = sum(r["images"] + r["videos"] for r in results)
        processed = 0
        saved_bytes = 0
        # Global map accumulates across ALL archives so scripts in one archive
        # can reference images converted in a different archive.
        global_path_map: dict[str, str] = {}

        try:
            for arch_idx, r in enumerate(results):
                if self._cancel_event.is_set():
                    raise InterruptedError("Cancelled by user.")

                rpa_path: Path = r["path"]
                staged_path = stage_dir / rpa_path.name

                parts = []
                if r["images"]:  parts.append(f"{r['images']} images → AVIF")
                if r["videos"]:  parts.append(f"{r['videos']} videos → VP9")
                if r["scripts"]: parts.append(f"{r['scripts']} scripts")
                arch_desc = (
                    f"{rpa_path.name}  ({arch_idx + 1}/{len(results)})"
                    + (f"  —  {', '.join(parts)}" if parts else "")
                )
                self.after(0, self._arch_label.configure, {"text": arch_desc})
                self.after(0, self._header_sub.configure, {
                    "text": f"Archive {arch_idx + 1}/{len(results)}: {rpa_path.name}"
                })
                self._log_info(
                    f"Processing {rpa_path.name}  "
                    f"({_fmt_size(r['size'])}  •  "
                    f"{r['images']} images  •  {r['videos']} video(s))"
                )

                if r["images"] == 0 and r["videos"] == 0 and r["scripts"] == 0:
                    self._log_info("  No compressible content — skipping.")
                    compress_results.append({**r, "new_size": r["size"]})
                    continue

                new_files: dict[str, bytes] = {}
                file_list = list(iter_files(rpa_path))

                # gui/ images are referenced by hardcoded paths compiled into .rpyc bytecode,
                # which our script patcher cannot update. Keep them as-is.
                image_items  = [(fp, d) for fp, d in file_list if is_image(fp) and not fp.startswith("gui/")]
                video_items  = [(fp, d) for fp, d in file_list if is_video(fp)]
                script_items = [(fp, d) for fp, d in file_list if is_rpy(fp)]

                arch_conv_bytes  = 0
                arch_saved_bytes = 0
                arch_skipped     = 0
                arch_path_map: dict[str, str] = {}  # conversions within this archive

                # ── Pass-through files (non-image, non-video, non-script) ──
                for fpath, data in file_list:
                    if (not is_image(fpath) and not is_video(fpath)
                            and not is_rpy(fpath) and not is_rpyc(fpath)):
                        new_files[fpath] = data
                    elif is_rpyc(fpath):
                        new_files[fpath] = data  # keep compiled scripts intact
                    elif is_image(fpath) and fpath.startswith("gui/"):
                        new_files[fpath] = data  # gui/ images have hardcoded .rpyc paths

                # ── Images ───────────────────────────────────────────────
                if n_workers > 1 and len(image_items) > 1:
                    # Parallel path
                    self._log_info(
                        f"  Converting {len(image_items)} images in parallel "
                        f"({n_workers} threads)…"
                    )
                    self.after(0, self._arch_label.configure,
                               {"text": arch_desc + f"  |  {n_workers} threads"})

                    executor = ThreadPoolExecutor(max_workers=n_workers)
                    future_map = {
                        executor.submit(convert_to_avif, data): (fpath, data)
                        for fpath, data in image_items
                    }
                    img_done = 0
                    cancelled = False
                    for future in as_completed(future_map):
                        if self._cancel_event.is_set():
                            for f in future_map:
                                f.cancel()
                            cancelled = True
                            break

                        fpath, data = future_map[future]
                        img_done += 1
                        try:
                            out = future.result()
                            if len(out) < len(data):
                                new_path = avif_path(fpath)
                                new_files[new_path] = out
                                arch_path_map[fpath] = new_path
                                delta = len(data) - len(out)
                                arch_conv_bytes  += len(data)
                                arch_saved_bytes += delta
                                saved_bytes      += delta
                                self._log_ok(
                                    f"  IMG  {Path(fpath).name}  "
                                    f"{_fmt_size(len(data))} → {_fmt_size(len(out))}  "
                                    f"({_pct_str(len(data), len(out))})"
                                )
                            else:
                                new_files[fpath] = data
                                arch_skipped += 1
                                self._log_info(
                                    f"  KEPT {Path(fpath).name}  "
                                    f"({_fmt_size(len(data))}, AVIF would be {_fmt_size(len(out))})"
                                )
                        except Exception as e:
                            new_files[fpath] = data
                            self._log_warn(f"  SKIP {Path(fpath).name}: {e}")
                        processed += 1

                        img_frac = img_done / max(len(image_items), 1)
                        self.after(0, self._file_bar.set, img_frac)
                        self.after(0, self._file_pct_label.configure, {
                            "text": (
                                f"parallel: {img_done} / {len(image_items)} images"
                                f"  ({img_frac * 100:.0f}%)  •  {n_workers} threads"
                            )
                        })
                        self._update_overall(processed, total_items, saved_bytes, start_time)
                        self._update_arch(arch_desc, arch_conv_bytes, arch_saved_bytes,
                                          arch_skipped, f"  |  {n_workers} threads")

                    executor.shutdown(wait=False)
                    if cancelled:
                        raise InterruptedError("Cancelled by user.")

                else:
                    # Sequential path
                    for fi, (fpath, data) in enumerate(image_items):
                        if self._cancel_event.is_set():
                            raise InterruptedError("Cancelled by user.")

                        img_frac = fi / max(len(image_items) - 1, 1) if len(image_items) > 1 else 1.0
                        self.after(0, self._file_bar.set, img_frac)
                        self.after(0, self._file_pct_label.configure, {
                            "text": f"image {fi + 1} of {len(image_items)}  ({img_frac * 100:.0f}%)"
                        })
                        self._log_info(f"  IMG  {fpath}")
                        try:
                            out = convert_to_avif(data)
                            if len(out) < len(data):
                                new_path = avif_path(fpath)
                                new_files[new_path] = out
                                arch_path_map[fpath] = new_path
                                delta = len(data) - len(out)
                                arch_conv_bytes  += len(data)
                                arch_saved_bytes += delta
                                saved_bytes      += delta
                                self._log_ok(
                                    f"       → {Path(new_path).name}  "
                                    f"{_fmt_size(len(data))} → {_fmt_size(len(out))}  "
                                    f"({_pct_str(len(data), len(out))})"
                                )
                            else:
                                new_files[fpath] = data
                                arch_skipped += 1
                                self._log_info(
                                    f"       KEPT  {_fmt_size(len(data))}, "
                                    f"AVIF would be {_fmt_size(len(out))}"
                                )
                        except Exception as e:
                            new_files[fpath] = data
                            self._log_warn(f"       SKIP (convert failed): {e}")
                        processed += 1

                        self._update_overall(processed, total_items, saved_bytes, start_time)
                        self._update_arch(arch_desc, arch_conv_bytes, arch_saved_bytes, arch_skipped)

                # ── Videos (sequential; ffmpeg is internally multi-threaded) ──
                for fi, (fpath, data) in enumerate(video_items):
                    if self._cancel_event.is_set():
                        raise InterruptedError("Cancelled by user.")

                    ext = Path(fpath).suffix
                    self._log_info(f"  VID  {fpath}")
                    vid_frac = fi / max(len(video_items) - 1, 1) if len(video_items) > 1 else 1.0
                    self.after(0, self._file_bar.set, vid_frac)
                    self.after(0, self._file_pct_label.configure, {
                        "text": f"video {fi + 1} of {len(video_items)}"
                    })
                    try:
                        out = convert_video(data, ext)
                        if len(out) < len(data):
                            new_path = video_path(fpath)
                            new_files[new_path] = out
                            arch_path_map[fpath] = new_path
                            delta = len(data) - len(out)
                            saved_bytes += delta
                            self._log_ok(
                                f"       → {Path(new_path).name}  "
                                f"{_fmt_size(len(data))} → {_fmt_size(len(out))}  "
                                f"({_pct_str(len(data), len(out))})"
                            )
                        else:
                            new_files[fpath] = data
                            arch_skipped += 1
                            self._log_info(
                                f"       KEPT  {_fmt_size(len(data))}, "
                                f"VP9 would be {_fmt_size(len(out))}"
                            )
                    except Exception as e:
                        new_files[fpath] = data
                        self._log_warn(f"       SKIP (encode failed): {e}")
                    processed += 1

                    self._update_overall(processed, total_items, saved_bytes, start_time)
                    self._update_arch(arch_desc, arch_conv_bytes, arch_saved_bytes, arch_skipped)

                # ── Accumulate into global map (for cross-archive patching) ──
                global_path_map.update(arch_path_map)

                # ── Scripts: patch with global map so scripts in one archive ──
                # ── can reference images converted in a different archive     ──
                for fpath, data in script_items:
                    self._log_info(
                        f"  SCR  {fpath}  ({len(global_path_map)} path substitutions)"
                    )
                    new_files[fpath] = patch_rpy_with_map(data, global_path_map)

                # Write staged archive
                self._log_info("  Writing staged archive…")
                write_rpa(staged_path, new_files)
                new_size = staged_path.stat().st_size
                staged[rpa_path] = staged_path
                compress_results.append({**r, "new_size": new_size})
                self._log_ok(
                    f"  Staged: {_fmt_size(r['size'])} → {_fmt_size(new_size)}"
                    + (f"  ({arch_skipped} file(s) kept as original)" if arch_skipped else "")
                )

            # ── All archives staged — atomic swap ──────────────────────────
            if self._cancel_event.is_set():
                raise InterruptedError("Cancelled by user.")

            self._log_info("All archives processed. Applying changes…")
            for orig_path, s_path in staged.items():
                if backup:
                    bak = orig_path.with_suffix(".rpa.bak")
                    if bak.exists():
                        bak.unlink()
                    orig_path.rename(bak)
                    self._log_info(f"  Backup: {orig_path.name} → {bak.name}")
                else:
                    orig_path.unlink()
                s_path.rename(orig_path)
                self._log_ok(f"  Replaced: {orig_path.name}")

            # Deploy AVIF runtime support script so the game can load .avif files.
            # Overwrite every run so a stale/missing copy is never an issue.
            _script_src = Path(__file__).parent.parent.parent / "core" / "avif_support_script.rpy"
            _script_dst = game_dir / "hhg_avif_support.rpy"
            _rpyc_dst   = game_dir / "hhg_avif_support.rpyc"
            try:
                shutil.copy2(_script_src, _script_dst)
                if _rpyc_dst.exists():
                    _rpyc_dst.unlink()
                self._log_ok("Deployed hhg_avif_support.rpy → game/")
            except Exception as _e:
                self._log_warn(f"Could not deploy avif support script: {_e}")

            total_elapsed = time.time() - start_time
            self._log_ok(
                f"Done in {_fmt_time(total_elapsed)}  •  "
                f"Saved {_fmt_size(max(0, saved_bytes))} total"
            )
            shutil.rmtree(stage_dir, ignore_errors=True)
            self._wizard.app_state["compress_results"] = compress_results
            self.after(0, self._on_done, True)

        except InterruptedError:
            self._log_warn("Cancelled — cleaning up staging directory…")
            shutil.rmtree(stage_dir, ignore_errors=True)
            self._log_ok("Staging cleaned up. Original files are untouched.")
            self.after(0, self._on_done, False)

        except Exception as e:
            self._log_error(f"Unexpected error: {e}")
            shutil.rmtree(stage_dir, ignore_errors=True)
            self._log_warn("Staging cleaned up. Original files are untouched.")
            self.after(0, self._on_done, False)

    def _on_done(self, success: bool) -> None:
        self._file_bar.set(1 if success else 0)
        if success:
            self._overall_bar.set(1)
            self._header_sub.configure(text="Done — click Next to see results.")
            self._cancel_btn.configure(state="disabled")
            self._wizard.navigate_to("done")
        else:
            self._header_sub.configure(text="Cancelled. Original files are untouched.")
            self._cancel_btn.configure(state="disabled", text="Cancelled")
