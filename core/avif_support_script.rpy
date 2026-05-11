init -999 python:
    import io, os, struct, subprocess, sys, threading
    import renpy.display.pgrender as _pgrender
    import renpy.loader as _loader

    _original_load_image  = _pgrender.load_image
    _original_loader_load = _loader.load
    _IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")

    _worker_proc = None
    _worker_lock = threading.Lock()
    _WORKER_CODE = (
        "import sys,struct,io,pillow_heif\n"
        "from PIL import Image\n"
        "pillow_heif.register_heif_opener()\n"
        "sys.stdout.buffer.write(b'RDY\\n')\n"
        "sys.stdout.buffer.flush()\n"
        "while True:\n"
        "    h=sys.stdin.buffer.read(4)\n"
        "    if len(h)<4:break\n"
        "    sz=struct.unpack('>I',h)[0]\n"
        "    if sz==0:break\n"
        "    d=sys.stdin.buffer.read(sz)\n"
        "    if len(d)<sz:break\n"
        "    try:\n"
        "        img=Image.open(io.BytesIO(d))\n"
        "        if img.mode not in('RGB','RGBA'):img=img.convert('RGBA')\n"
        "        out=io.BytesIO()\n"
        "        img.save(out,format='BMP')\n"
        "        data=out.getvalue()\n"
        "        sys.stdout.buffer.write(struct.pack('>I',len(data)))\n"
        "        sys.stdout.buffer.write(data)\n"
        "        sys.stdout.buffer.flush()\n"
        "    except Exception as e:\n"
        "        sys.stderr.write(str(e)+'\\n')\n"
        "        sys.stdout.buffer.write(struct.pack('>I',0))\n"
        "        sys.stdout.buffer.flush()\n"
    )
    _system_python = None

    def _find_system_python():
        import shutil as _shutil
        for _cand in ("python3", "python"):
            _p = _shutil.which(_cand)
            if _p and _p != sys.executable:
                return _p
        return None

    def _start_worker():
        global _worker_proc, _system_python
        try:
            _system_python = _find_system_python()
            if _system_python is None:
                return
            _proc = subprocess.Popen(
                [_system_python, "-c", _WORKER_CODE],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            _ready = _proc.stdout.read(4)
            if _ready == b"RDY\n":
                with _worker_lock:
                    _worker_proc = _proc
        except Exception as _e:
            renpy.display.log.write("[avif_support] Worker start failed: %s" % _e)

    def _worker_decode(avif_bytes):
        with _worker_lock:
            _proc = _worker_proc
        if _proc is None or _proc.poll() is not None:
            return None
        try:
            _proc.stdin.write(struct.pack(">I", len(avif_bytes)))
            _proc.stdin.write(avif_bytes)
            _proc.stdin.flush()
            _sz_b = _proc.stdout.read(4)
            if len(_sz_b) < 4:
                return None
            _sz = struct.unpack(">I", _sz_b)[0]
            if _sz == 0:
                return None
            return _proc.stdout.read(_sz)
        except Exception:
            return None

    def _ffmpeg_decode(avif_bytes):
        import tempfile as _tempfile
        try:
            with _tempfile.TemporaryDirectory() as _tmpdir:
                _in  = os.path.join(_tmpdir, "input.avif")
                _out = os.path.join(_tmpdir, "output.bmp")
                with open(_in, "wb") as _f:
                    _f.write(avif_bytes)
                _r = subprocess.run(
                    ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                     "-i", _in, _out],
                    capture_output=True,
                )
                if _r.returncode == 0 and os.path.exists(_out):
                    with open(_out, "rb") as _f:
                        return _f.read(), ".bmp"
        except Exception:
            pass
        return None, ".bmp"

    threading.Thread(target=_start_worker, daemon=True).start()

    def _avif_load_image(f, filename):
        data = f.read() if hasattr(f, "read") else bytes(f)
        is_avif = len(data) >= 12 and data[4:8] == b"ftyp"
        if not is_avif:
            return _original_load_image(io.BytesIO(data), filename)
        img_data = _worker_decode(data)
        ext = ".bmp"
        if img_data is None:
            img_data, ext = _ffmpeg_decode(data)
        if img_data:
            base = filename[:filename.rfind(".")] if "." in filename else filename
            return _original_load_image(io.BytesIO(img_data), base + ext)
        renpy.display.log.write("[avif_support] Failed to decode %s" % filename)
        try:
            import pygame_sdl2 as _pygame
            surf = _pygame.Surface((1, 1))
            surf.fill((255, 0, 255))
            return surf
        except Exception:
            return _original_load_image(io.BytesIO(data), filename)

    def _avif_aware_loader_load(fn, *args, **kwargs):
        try:
            return _original_loader_load(fn, *args, **kwargs)
        except IOError:
            if not isinstance(fn, str):
                raise
            fn_lower = fn.lower()
            for ext in _IMAGE_EXTS:
                if fn_lower.endswith(ext):
                    avif_fn = fn[:-len(ext)] + ".avif"
                    try:
                        return _original_loader_load(avif_fn, *args, **kwargs)
                    except Exception:
                        pass
                    break
            raise

    _pgrender.load_image = _avif_load_image
    _loader.load = _avif_aware_loader_load
    sys.modules["renpy.loader"].load = _avif_aware_loader_load
    sys.modules["renpy.display.pgrender"].load_image = _avif_load_image

init 1901 python:
    import os as _os
    _img_dir = (config.images_directory or "images").rstrip("/") + "/"
    for _fn in renpy.list_files():
        if not _fn.startswith(_img_dir):
            continue
        _base, _ext = _os.path.splitext(_os.path.basename(_fn))
        if _ext.lower() != ".avif":
            continue
        _base = _base.lower()
        if not renpy.has_image(_base, exact=True):
            renpy.image(_base, _fn)
