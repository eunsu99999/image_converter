import os, sys, traceback

OUTPUT_DIR = r"C:\negative"
os.makedirs(OUTPUT_DIR, exist_ok=True)

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox
    from PIL import Image, ImageOps
    import threading, ctypes
    from ctypes import wintypes
except Exception as _e:
    with open(os.path.join(OUTPUT_DIR, "crash.log"), "w", encoding="utf-8") as _f:
        _f.write(traceback.format_exc())
    sys.exit(1)

SUPPORTED = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff", ".gif"}

# ── 모노톤 팔레트 ─────────────────────────────────────────────────
BG      = "#141414"
SURF    = "#1e1e1e"
SURF2   = "#282828"
BORDER  = "#383838"
TEXT    = "#e0e0e0"
SUB     = "#707070"
DIM     = "#484848"
WHITE   = "#f0f0f0"
BTN_ACT = "#505050"

WM_DROPFILES   = 0x0233
GWL_WNDPROC    = -4
WNDPROCTYPE    = ctypes.WINFUNCTYPE(
    ctypes.c_longlong,
    wintypes.HWND, ctypes.c_uint,
    wintypes.WPARAM, wintypes.LPARAM,
)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Image Converter")
        self.resizable(False, False)
        self.configure(bg=BG)

        self.files: list[str] = []
        self.mode = tk.StringVar(value="mono")

        self._build()
        self._center()
        self._setup_drop()

        self.lift()
        self.attributes("-topmost", True)
        self.after(300, lambda: self.attributes("-topmost", False))
        self.focus_force()

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"+{x}+{y}")

    # ── UI ────────────────────────────────────────────────────────
    def _build(self):
        # 헤더
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=24, pady=(22, 0))
        tk.Label(hdr, text="Image Converter",
                 font=("Segoe UI", 15, "bold"), fg=WHITE, bg=BG).pack(side="left")
      

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=24, pady=(10, 0))

        # 드롭 존
        self.drop_outer = tk.Frame(self, bg=BORDER, padx=1, pady=1)
        self.drop_outer.pack(padx=24, pady=14)

        self.drop_frame = tk.Frame(self.drop_outer, bg=SURF, width=430, height=148)
        self.drop_frame.pack()
        self.drop_frame.pack_propagate(False)

        self.ico_lbl = tk.Label(self.drop_frame, text="+",
                                font=("Segoe UI", 28), fg=DIM, bg=SURF, cursor="hand2")
        self.ico_lbl.pack(pady=(26, 4))

        self.main_lbl = tk.Label(self.drop_frame,
                                 text="이미지를 끌어다 놓거나 클릭해서 선택",
                                 font=("Segoe UI", 10), fg=SUB, bg=SURF, cursor="hand2")
        self.main_lbl.pack()

        self.sub_lbl = tk.Label(self.drop_frame,
                                text="JPG · PNG · BMP · WEBP · TIFF  |  여러 파일 가능",
                                font=("Segoe UI", 8), fg=DIM, bg=SURF)
        self.sub_lbl.pack(pady=(3, 0))

        for w in (self.drop_frame, self.ico_lbl, self.main_lbl):
            w.bind("<Button-1>", lambda e: self._browse())

        # 구분선
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=24)

        # 모드 선택
        mf = tk.Frame(self, bg=BG, pady=10)
        mf.pack(padx=24, fill="x")

        modes = [
            ("mono",          "흑백"),
            ("negative",      "반전"),
            ("mono_negative", "흑백 반전"),
        ]
        for val, label in modes:
            rb = tk.Radiobutton(
                mf, text=label, variable=self.mode, value=val,
                font=("Segoe UI", 10),
                fg=SUB, bg=BG,
                selectcolor=BG,
                activeforeground=WHITE, activebackground=BG,
                cursor="hand2",
                indicatoron=0,
                relief="flat", bd=0, padx=14, pady=6,
                command=self._refresh_mode_btns,
            )
            rb.pack(side="left", padx=(0, 6))

        self._mode_btns = mf.winfo_children()
        self._refresh_mode_btns()

        # 구분선
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=24)

        # 상태
        self.status_var = tk.StringVar(value="파일을 선택하거나 드래그해서 시작하세요.")
        self.status_lbl = tk.Label(self, textvariable=self.status_var,
                                   font=("Segoe UI", 8), fg=DIM, bg=BG,
                                   wraplength=430, justify="center")
        self.status_lbl.pack(pady=(8, 4))

        # 버튼
        bf = tk.Frame(self, bg=BG)
        bf.pack(pady=(0, 22))

        self.go_btn = tk.Button(
            bf, text="변환 시작",
            font=("Segoe UI", 10, "bold"),
            fg=BG, bg=WHITE, activeforeground=BG, activebackground=TEXT,
            relief="flat", cursor="hand2", padx=20, pady=7,
            state="disabled", command=self._start_convert,
        )
        self.go_btn.pack(side="left", padx=(0, 6))

        tk.Button(bf, text="초기화",
                  font=("Segoe UI", 10), fg=SUB, bg=SURF2,
                  activeforeground=TEXT, activebackground=BTN_ACT,
                  relief="flat", cursor="hand2", padx=14, pady=7,
                  command=self._clear).pack(side="left", padx=(0, 6))

        tk.Button(bf, text="폴더 열기",
                  font=("Segoe UI", 10), fg=SUB, bg=SURF2,
                  activeforeground=TEXT, activebackground=BTN_ACT,
                  relief="flat", cursor="hand2", padx=14, pady=7,
                  command=lambda: os.startfile(OUTPUT_DIR)).pack(side="left")

    def _refresh_mode_btns(self):
        sel = self.mode.get()
        modes = [("mono", "흑백"), ("negative", "반전"), ("mono_negative", "흑백 반전")]
        for btn, (val, _) in zip(self._mode_btns, modes):
            if val == sel:
                btn.config(fg=WHITE, bg=SURF2, relief="flat")
            else:
                btn.config(fg=SUB, bg=BG, relief="flat")

    # ── 드래그앤드롭 (WndProc 서브클래싱) ──────────────────────────
    def _setup_drop(self):
        try:
            hwnd = self.winfo_id()
            ctypes.windll.shell32.DragAcceptFiles(hwnd, True)

            def wnd_proc(hwnd, msg, wparam, lparam):
                if msg == WM_DROPFILES:
                    hDrop = wparam
                    count = ctypes.windll.shell32.DragQueryFileW(
                        hDrop, 0xFFFFFFFF, None, 0)
                    paths = []
                    for i in range(count):
                        buf = ctypes.create_unicode_buffer(260)
                        ctypes.windll.shell32.DragQueryFileW(hDrop, i, buf, 260)
                        paths.append(buf.value)
                    ctypes.windll.shell32.DragFinish(hDrop)
                    self.after(0, lambda p=paths: self._load_files(p))
                    return 0
                return ctypes.windll.user32.CallWindowProcW(
                    self._old_wnd_proc, hwnd, msg, wparam, lparam)

            self._wnd_proc_cb = WNDPROCTYPE(wnd_proc)
            self._old_wnd_proc = ctypes.windll.user32.SetWindowLongPtrW(
                hwnd, GWL_WNDPROC, self._wnd_proc_cb)
        except Exception:
            pass  # 드래그앤드롭 미지원 환경에서는 클릭으로만 사용

    # ── 파일 처리 ─────────────────────────────────────────────────
    def _browse(self):
        paths = filedialog.askopenfilenames(
            title="이미지 파일 선택",
            filetypes=[
                ("이미지 파일", "*.jpg *.jpeg *.png *.bmp *.webp *.tiff *.gif"),
                ("모든 파일", "*.*"),
            ])
        if paths:
            self._load_files(list(paths))

    def _load_files(self, paths: list[str]):
        valid = [p for p in paths if os.path.splitext(p)[1].lower() in SUPPORTED]
        if not valid:
            self._set_status("지원하지 않는 파일 형식입니다.")
            return
        self.files = valid
        names = [os.path.basename(f) for f in valid]
        label = ", ".join(names[:2]) + (f" 외 {len(names)-2}개" if len(names) > 2 else "")
        self.main_lbl.config(text=label, fg=TEXT)
        self.sub_lbl.config(text=f"{len(valid)}개 파일 선택됨")
        self.ico_lbl.config(text="✓", fg=TEXT)
        self._set_status(f"{len(valid)}개 파일 준비됨.")
        self.go_btn.config(state="normal")

    def _clear(self):
        self.files = []
        self.ico_lbl.config(text="+", fg=DIM)
        self.main_lbl.config(text="이미지를 끌어다 놓거나 클릭해서 선택", fg=SUB)
        self.sub_lbl.config(text="JPG · PNG · BMP · WEBP · TIFF  |  여러 파일 가능")
        self.go_btn.config(state="disabled")
        self._set_status("파일을 선택하거나 드래그해서 시작하세요.")

    def _set_status(self, msg, color=DIM):
        self.status_var.set(msg)
        self.status_lbl.config(fg=color)

    # ── 변환 ──────────────────────────────────────────────────────
    def _start_convert(self):
        if not self.files:
            return
        self.go_btn.config(state="disabled", text="변환 중...")
        threading.Thread(target=self._convert, daemon=True).start()

    def _convert(self):
        mode = self.mode.get()
        ok, fail, results = 0, 0, []

        for path in self.files:
            try:
                img  = Image.open(path)
                stem = os.path.splitext(os.path.basename(path))[0]
                ext  = os.path.splitext(path)[1].lower() or ".jpg"
                if ext == ".webp":
                    ext = ".png"

                if mode == "mono":
                    dst = os.path.join(OUTPUT_DIR, f"{stem}_grayscale{ext}")
                    img.convert("L").save(dst)
                    results.append(("ok", os.path.basename(dst)))

                elif mode == "negative":
                    dst = os.path.join(OUTPUT_DIR, f"{stem}_invert{ext}")
                    ImageOps.invert(img.convert("RGB")).save(dst)
                    results.append(("ok", os.path.basename(dst)))

                elif mode == "mono_negative":
                    dst = os.path.join(OUTPUT_DIR, f"{stem}_bw_invert{ext}")
                    ImageOps.invert(img.convert("L")).save(dst)
                    results.append(("ok", os.path.basename(dst)))

                ok += 1
            except Exception:
                fail += 1
                results.append(("err", os.path.basename(path)))

        self.after(0, lambda: self._show_result(ok, fail, results))

    def _show_result(self, ok, fail, results):
        self.go_btn.config(state="normal", text="변환 시작")
        self._clear()

        win = tk.Toplevel(self)
        win.title("완료")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text=f"완료  {ok}개 성공" + (f"  /  {fail}개 실패" if fail else ""),
                 font=("Segoe UI", 11, "bold"), fg=WHITE, bg=BG).pack(pady=(20, 12))

        tk.Frame(win, bg=BORDER, height=1).pack(fill="x", padx=20)

        fr = tk.Frame(win, bg=SURF, padx=14, pady=10)
        fr.pack(padx=20, pady=10, fill="both")
        for status, name in results:
            color = TEXT if status == "ok" else SUB
            mark  = "✓" if status == "ok" else "✗"
            tk.Label(fr, text=f"  {mark}  {name}",
                     font=("Segoe UI", 9), fg=color, bg=SURF, anchor="w"
                     ).pack(fill="x", pady=1)

        tk.Frame(win, bg=BORDER, height=1).pack(fill="x", padx=20)

        bf2 = tk.Frame(win, bg=BG)
        bf2.pack(pady=14)
        tk.Button(bf2, text="폴더 열기",
                  font=("Segoe UI", 10, "bold"),
                  fg=BG, bg=WHITE, activeforeground=BG, activebackground=TEXT,
                  relief="flat", cursor="hand2", padx=16, pady=6,
                  command=lambda: os.startfile(OUTPUT_DIR)).pack(side="left", padx=(0, 6))
        tk.Button(bf2, text="닫기",
                  font=("Segoe UI", 10), fg=SUB, bg=SURF2,
                  activeforeground=TEXT, activebackground=BTN_ACT,
                  relief="flat", cursor="hand2", padx=16, pady=6,
                  command=win.destroy).pack(side="left")

        win.update_idletasks()
        px = self.winfo_x() + (self.winfo_width()  - win.winfo_width())  // 2
        py = self.winfo_y() + (self.winfo_height() - win.winfo_height()) // 2
        win.geometry(f"+{px}+{py}")


if __name__ == "__main__":
    try:
        App().mainloop()
    except Exception:
        with open(os.path.join(OUTPUT_DIR, "crash.log"), "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
