import os, sys, traceback, math
from datetime import datetime

OUTPUT_DIR = r"C:\negative"
os.makedirs(OUTPUT_DIR, exist_ok=True)

try:
    import tkinter as tk
    from tkinter import filedialog
    from PIL import Image, ImageOps, ImageTk
    import ctypes, queue
    from ctypes import wintypes
except Exception as _e:
    with open(os.path.join(OUTPUT_DIR, "crash.log"), "w", encoding="utf-8") as _f:
        _f.write(traceback.format_exc())
    sys.exit(1)

SUPPORTED = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff", ".gif"}

BG      = "#141414"
SURF    = "#1e1e1e"
SURF2   = "#282828"
BORDER  = "#383838"
TEXT    = "#e0e0e0"
SUB     = "#707070"
DIM     = "#484848"
WHITE   = "#f0f0f0"
BTN_ACT = "#505050"
TB_BG   = "#111111"

CW = 900
CH = 600

WM_DROPFILES      = 0x0233
WM_COPYGLOBALDATA = 0x0049
MSGFLT_ALLOW      = 1
GWL_WNDPROC       = -4
WNDPROCTYPE = ctypes.WINFUNCTYPE(
    ctypes.c_longlong,
    wintypes.HWND, ctypes.c_uint,
    wintypes.WPARAM, wintypes.LPARAM,
)


def _apply_img(img: Image.Image, mode: str) -> Image.Image:
    if mode == "original":
        return img.convert("RGB")
    elif mode == "mono":
        return img.convert("L").convert("RGB")
    elif mode == "invert":
        return ImageOps.invert(img.convert("RGB"))
    else:
        return ImageOps.invert(img.convert("L")).convert("RGB")


class PhotoItem:
    def __init__(self, path: str, cx: float, cy: float):
        self.path  = path
        self.orig  = Image.open(path).convert("RGB")
        self.mode  = "original"
        self.x     = cx
        self.y     = cy
        w, h       = self.orig.size
        scale      = min(280 / w, 280 / h, 1.0)
        self.w     = max(20, int(w * scale))
        self.h     = max(20, int(h * scale))
        self.angle = 0.0
        self.photo: ImageTk.PhotoImage | None = None
        self.canvas_id: int | None = None


class App(tk.Tk):
    HR = 7

    def __init__(self):
        super().__init__()
        self.title("캔버스 편집기")
        self.resizable(False, False)
        self.configure(bg=TB_BG)

        self._items: list[PhotoItem] = []
        self._sel: PhotoItem | None = None
        self._drag_mode = None
        self._drag_ox = 0.0
        self._drag_oy = 0.0
        self._resize_start_dist = 1.0
        self._resize_start_w = 20
        self._resize_start_h = 20
        self._rotate_start_angle = 0.0
        self._rotate_mouse_angle = 0.0
        self._mode_var = tk.StringVar(value="original")
        self._drop_queue: queue.SimpleQueue = queue.SimpleQueue()
        self._drop_cbs: list = []

        self._build()
        self._center()
        self._setup_drop()
        self.after(100, self._process_drops)

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

    # ── UI ──────────────────────────────────────────────────────────
    def _build(self):
        tb = tk.Frame(self, bg=TB_BG, pady=8)
        tb.pack(fill="x", padx=12)

        tk.Label(tb, text="모드", font=("Segoe UI", 8),
                 fg=SUB, bg=TB_BG).pack(side="left", padx=(0, 4))

        self._mode_btns = []
        for val, label in [("original", "원본"), ("mono", "흑백"),
                            ("invert", "반전"), ("mono_invert", "흑백+반전")]:
            b = tk.Radiobutton(
                tb, text=label, variable=self._mode_var, value=val,
                font=("Segoe UI", 9), fg=SUB, bg=TB_BG, selectcolor=TB_BG,
                activeforeground=WHITE, activebackground=TB_BG,
                cursor="hand2", indicatoron=0, relief="flat", bd=0,
                padx=10, pady=4,
                command=self._on_mode_change,
            )
            b.pack(side="left", padx=2)
            self._mode_btns.append(b)

        tk.Frame(tb, bg=BORDER, width=1).pack(side="left", fill="y", padx=10, pady=2)

        tk.Button(tb, text="+ 사진 추가",
                  font=("Segoe UI", 9), fg=TEXT, bg=SURF2,
                  activeforeground=WHITE, activebackground=BTN_ACT,
                  relief="flat", cursor="hand2", padx=10, pady=4,
                  command=self._browse_add).pack(side="left", padx=2)

        tk.Frame(tb, bg=BORDER, width=1).pack(side="left", fill="y", padx=10, pady=2)

        tk.Label(tb, text="순서", font=("Segoe UI", 8),
                 fg=SUB, bg=TB_BG).pack(side="left", padx=(0, 4))

        for label, cmd in [("맨앞", self._to_front), ("앞", self._forward),
                            ("뒤", self._backward), ("맨뒤", self._to_back)]:
            tk.Button(tb, text=label,
                      font=("Segoe UI", 9), fg=TEXT, bg=SURF2,
                      activeforeground=WHITE, activebackground=BTN_ACT,
                      relief="flat", cursor="hand2", padx=8, pady=4,
                      command=cmd).pack(side="left", padx=2)

        tk.Frame(tb, bg=BORDER, width=1).pack(side="left", fill="y", padx=10, pady=2)

        tk.Button(tb, text="저장",
                  font=("Segoe UI", 9, "bold"), fg=BG, bg=WHITE,
                  activeforeground=BG, activebackground=TEXT,
                  relief="flat", cursor="hand2", padx=14, pady=4,
                  command=self._save).pack(side="left", padx=2)

        self._save_lbl = tk.Label(tb, text="", font=("Segoe UI", 8),
                                   fg=DIM, bg=TB_BG)
        self._save_lbl.pack(side="left", padx=8)

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        cv_frame = tk.Frame(self, bg=TB_BG)
        cv_frame.pack()

        self.cv = tk.Canvas(cv_frame, width=CW, height=CH,
                            bg="#0a0a0a", highlightthickness=0, cursor="arrow")
        self.cv.pack()

        self._placeholder = self.cv.create_text(
            CW // 2, CH // 2,
            text="사진을 여기에 놓거나\n+ 사진 추가 버튼을 눌러주세요",
            fill=DIM, font=("Segoe UI", 13), justify="center",
            tags="placeholder",
        )

        self.cv.bind("<Button-1>",        self._on_press)
        self.cv.bind("<B1-Motion>",       self._on_drag)
        self.cv.bind("<ButtonRelease-1>", self._on_release)
        self.cv.bind("<Button-3>",        self._on_rclick)

        self._refresh_mode_btns()

    def _refresh_mode_btns(self):
        sel  = self._mode_var.get()
        vals = ["original", "mono", "invert", "mono_invert"]
        for btn, val in zip(self._mode_btns, vals):
            btn.config(fg=WHITE if val == sel else SUB,
                       bg=SURF2 if val == sel else TB_BG)

    # ── Mode ────────────────────────────────────────────────────────
    def _on_mode_change(self):
        self._refresh_mode_btns()
        mode = self._mode_var.get()
        for item in self._items:
            item.mode = mode
        self._redraw_all()

    # ── Add files ───────────────────────────────────────────────────
    def _browse_add(self):
        paths = filedialog.askopenfilenames(
            title="사진 추가",
            filetypes=[("이미지 파일", "*.jpg *.jpeg *.png *.bmp *.webp *.tiff *.gif"),
                       ("모든 파일", "*.*")])
        if paths:
            self._add_files(list(paths))

    def _add_files(self, paths: list[str]):
        valid = [p for p in paths if os.path.splitext(p)[1].lower() in SUPPORTED]
        if not valid:
            return
        existing = {item.path for item in self._items}
        mode = self._mode_var.get()
        added = False
        for path in valid:
            if path in existing:
                continue
            try:
                n = len(self._items)
                cx = float(CW // 2 + (n * 24) % 160 - 80)
                cy = float(CH // 2 + (n * 18) % 120 - 60)
                item = PhotoItem(path, cx, cy)
                item.mode = mode
                self._items.append(item)
                added = True
            except Exception:
                pass
        if added:
            self._redraw_all()

    # ── Drag and drop ───────────────────────────────────────────────
    def _setup_drop(self):
        try:
            self.update_idletasks()
            user32  = ctypes.windll.user32
            shell32 = ctypes.windll.shell32

            user32.SetWindowLongPtrW.restype  = ctypes.c_longlong
            user32.SetWindowLongPtrW.argtypes = (wintypes.HWND, ctypes.c_int, ctypes.c_longlong)
            user32.CallWindowProcW.restype    = ctypes.c_longlong
            user32.CallWindowProcW.argtypes   = (ctypes.c_longlong, wintypes.HWND, ctypes.c_uint,
                                                  wintypes.WPARAM, wintypes.LPARAM)

            HDROP = wintypes.HANDLE
            shell32.DragQueryFileW.restype  = ctypes.c_uint
            shell32.DragQueryFileW.argtypes = (HDROP, ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_uint)
            shell32.DragFinish.restype      = None
            shell32.DragFinish.argtypes     = (HDROP,)
            shell32.DragAcceptFiles.restype  = None
            shell32.DragAcceptFiles.argtypes = (wintypes.HWND, wintypes.BOOL)

            hwnd   = self.winfo_id()
            parent = user32.GetParent(hwnd)

            def make_proc(old_ref):
                def wnd_proc(h, msg, wp, lp):
                    if msg == WM_DROPFILES:
                        count = shell32.DragQueryFileW(wp, 0xFFFFFFFF, None, 0)
                        ps = []
                        for i in range(count):
                            buf = ctypes.create_unicode_buffer(260)
                            shell32.DragQueryFileW(wp, i, buf, 260)
                            ps.append(buf.value)
                        shell32.DragFinish(wp)
                        self._drop_queue.put_nowait(ps)
                        return 0
                    return user32.CallWindowProcW(old_ref[0], h, msg, wp, lp)
                return wnd_proc

            for h in filter(None, [hwnd, parent]):
                shell32.DragAcceptFiles(h, True)
                try:
                    user32.ChangeWindowMessageFilterEx(h, WM_DROPFILES,      MSGFLT_ALLOW, None)
                    user32.ChangeWindowMessageFilterEx(h, WM_COPYGLOBALDATA, MSGFLT_ALLOW, None)
                except Exception:
                    pass
                old_ref    = [0]
                cb         = WNDPROCTYPE(make_proc(old_ref))
                cb_addr    = ctypes.cast(cb, ctypes.c_void_p).value
                old_ref[0] = user32.SetWindowLongPtrW(h, GWL_WNDPROC, cb_addr)
                self._drop_cbs.append(cb)
        except Exception:
            pass

    def _process_drops(self):
        try:
            while True:
                paths = self._drop_queue.get_nowait()
                self._add_files(paths)
        except Exception:
            pass
        self.after(100, self._process_drops)

    # ── Render ──────────────────────────────────────────────────────
    def _render_photo(self, item: PhotoItem) -> ImageTk.PhotoImage:
        img = _apply_img(item.orig.copy(), item.mode)
        img = img.resize((item.w, item.h), Image.LANCZOS).convert("RGBA")
        if item.angle % 360 != 0:
            img = img.rotate(-item.angle, expand=True, resample=Image.BICUBIC)
        return ImageTk.PhotoImage(img)

    def _redraw_all(self):
        self.cv.delete("item")
        self.cv.delete("handle")
        if not self._items:
            self.cv.itemconfig("placeholder", state="normal")
            return
        self.cv.itemconfig("placeholder", state="hidden")
        for item in self._items:
            photo = self._render_photo(item)
            item.photo = photo
            item.canvas_id = self.cv.create_image(
                item.x, item.y, image=photo, anchor="center", tags="item"
            )
        if self._sel and self._sel in self._items:
            self._draw_handles(self._sel)

    def _redraw_item(self, item: PhotoItem):
        if item.canvas_id is not None:
            photo = self._render_photo(item)
            item.photo = photo
            self.cv.itemconfig(item.canvas_id, image=photo)
        if self._sel is item:
            self._draw_handles(item)

    # ── Handles ─────────────────────────────────────────────────────
    @staticmethod
    def _rot(cx, cy, x, y, a_deg):
        a = math.radians(a_deg)
        dx, dy = x - cx, y - cy
        return (cx + dx * math.cos(a) - dy * math.sin(a),
                cy + dx * math.sin(a) + dy * math.cos(a))

    def _corners(self, item: PhotoItem):
        hw, hh = item.w / 2, item.h / 2
        return [self._rot(item.x, item.y, item.x + dx, item.y + dy, item.angle)
                for dx, dy in [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]]

    def _rot_handle_pos(self, item: PhotoItem):
        return self._rot(item.x, item.y, item.x, item.y - item.h / 2 - 26, item.angle)

    def _draw_handles(self, item: PhotoItem):
        self.cv.delete("handle")
        corners = self._corners(item)
        pts = [v for c in corners for v in c]
        self.cv.create_polygon(pts, outline="#4fc3f7", fill="", width=1, tags="handle")
        r = self.HR
        for cx, cy in corners:
            self.cv.create_rectangle(cx - r, cy - r, cx + r, cy + r,
                                     outline="#4fc3f7", fill=SURF2, tags="handle")
        rx, ry = self._rot_handle_pos(item)
        top_cx = (corners[0][0] + corners[1][0]) / 2
        top_cy = (corners[0][1] + corners[1][1]) / 2
        self.cv.create_line(top_cx, top_cy, rx, ry, fill="#ffb74d", width=1, tags="handle")
        self.cv.create_oval(rx - r, ry - r, rx + r, ry + r,
                             outline="#ffb74d", fill=SURF2, tags="handle")

    # ── Mouse ───────────────────────────────────────────────────────
    def _on_press(self, event):
        mx, my = float(event.x), float(event.y)

        if self._sel:
            for cx, cy in self._corners(self._sel):
                if math.hypot(mx - cx, my - cy) <= self.HR + 3:
                    dist = math.hypot(cx - self._sel.x, cy - self._sel.y)
                    self._drag_mode         = "resize"
                    self._resize_start_dist = max(dist, 1)
                    self._resize_start_w    = self._sel.w
                    self._resize_start_h    = self._sel.h
                    return
            rx, ry = self._rot_handle_pos(self._sel)
            if math.hypot(mx - rx, my - ry) <= self.HR + 3:
                self._drag_mode           = "rotate"
                self._rotate_start_angle  = self._sel.angle
                self._rotate_mouse_angle  = math.degrees(
                    math.atan2(my - self._sel.y, mx - self._sel.x))
                return

        hit = None
        for item in reversed(self._items):
            if self._hit_test(item, mx, my):
                hit = item
                break

        if hit:
            self._select(hit)
            self._drag_mode = "move"
            self._drag_ox   = mx - hit.x
            self._drag_oy   = my - hit.y
        else:
            self._deselect()

    def _on_drag(self, event):
        if not self._sel or not self._drag_mode:
            return
        mx, my = float(event.x), float(event.y)

        if self._drag_mode == "move":
            self._sel.x = mx - self._drag_ox
            self._sel.y = my - self._drag_oy
            self.cv.coords(self._sel.canvas_id, self._sel.x, self._sel.y)
            self._draw_handles(self._sel)

        elif self._drag_mode == "resize":
            dist  = math.hypot(mx - self._sel.x, my - self._sel.y)
            scale = dist / self._resize_start_dist
            self._sel.w = max(20, int(self._resize_start_w * scale))
            self._sel.h = max(20, int(self._resize_start_h * scale))
            self._redraw_item(self._sel)

        elif self._drag_mode == "rotate":
            cur   = math.degrees(math.atan2(my - self._sel.y, mx - self._sel.x))
            delta = cur - self._rotate_mouse_angle
            self._sel.angle = (self._rotate_start_angle + delta) % 360
            self._redraw_item(self._sel)

    def _on_release(self, event):
        self._drag_mode = None

    def _on_rclick(self, event):
        mx, my = float(event.x), float(event.y)
        hit = None
        for item in reversed(self._items):
            if self._hit_test(item, mx, my):
                hit = item
                break
        if not hit:
            return
        self._select(hit)
        menu = tk.Menu(self, tearoff=0, bg=SURF2, fg=TEXT,
                       activebackground=BTN_ACT, activeforeground=WHITE,
                       relief="flat", bd=0)
        menu.add_command(label="맨앞으로", command=self._to_front)
        menu.add_command(label="앞으로",   command=self._forward)
        menu.add_command(label="뒤로",     command=self._backward)
        menu.add_command(label="맨뒤로",   command=self._to_back)
        menu.add_separator()
        menu.add_command(label="삭제",     command=self._delete_sel)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _hit_test(self, item: PhotoItem, mx: float, my: float) -> bool:
        dx, dy = mx - item.x, my - item.y
        a  = math.radians(-item.angle)
        lx = dx * math.cos(a) - dy * math.sin(a)
        ly = dx * math.sin(a) + dy * math.cos(a)
        return abs(lx) <= item.w / 2 and abs(ly) <= item.h / 2

    def _select(self, item: PhotoItem):
        self._sel = item
        self._draw_handles(item)

    def _deselect(self):
        self._sel = None
        self.cv.delete("handle")

    # ── Layer order ─────────────────────────────────────────────────
    def _to_front(self):
        if not self._sel or self._sel not in self._items:
            return
        self._items.append(self._items.pop(self._items.index(self._sel)))
        self._redraw_all()

    def _forward(self):
        if not self._sel:
            return
        i = self._items.index(self._sel)
        if i < len(self._items) - 1:
            self._items[i], self._items[i + 1] = self._items[i + 1], self._items[i]
            self._redraw_all()

    def _backward(self):
        if not self._sel:
            return
        i = self._items.index(self._sel)
        if i > 0:
            self._items[i], self._items[i - 1] = self._items[i - 1], self._items[i]
            self._redraw_all()

    def _to_back(self):
        if not self._sel or self._sel not in self._items:
            return
        self._items.insert(0, self._items.pop(self._items.index(self._sel)))
        self._redraw_all()

    def _delete_sel(self):
        if not self._sel:
            return
        self._items.remove(self._sel)
        self._sel = None
        self._redraw_all()

    # ── Save ────────────────────────────────────────────────────────
    def _save(self):
        try:
            out = Image.new("RGB", (CW, CH), "black")
            for item in self._items:
                img = _apply_img(item.orig.copy(), item.mode)
                img = img.resize((item.w, item.h), Image.LANCZOS).convert("RGBA")
                if item.angle % 360 != 0:
                    img = img.rotate(-item.angle, expand=True, resample=Image.BICUBIC)
                px = int(item.x - img.width  / 2)
                py = int(item.y - img.height / 2)
                out.paste(img, (px, py), img)
            ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
            dst = os.path.join(OUTPUT_DIR, f"canvas_{ts}.png")
            out.save(dst)
            self._save_lbl.config(text=f"저장됨: {os.path.basename(dst)}", fg=TEXT)
        except Exception as e:
            self._save_lbl.config(text=f"저장 실패: {e}", fg=SUB)


if __name__ == "__main__":
    try:
        App().mainloop()
    except Exception:
        with open(os.path.join(OUTPUT_DIR, "crash.log"), "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
