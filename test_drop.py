"""WndProc DnD 설치 확인 테스트"""
import ctypes, os, queue
from ctypes import wintypes
import tkinter as tk

OUTPUT_DIR        = r"C:\negative"
WM_DROPFILES      = 0x0233
WM_COPYGLOBALDATA = 0x0049
MSGFLT_ALLOW      = 1
GWL_WNDPROC       = -4

WNDPROCTYPE = ctypes.WINFUNCTYPE(
    ctypes.c_longlong,
    wintypes.HWND, ctypes.c_uint,
    wintypes.WPARAM, wintypes.LPARAM,
)

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

root      = tk.Tk()
root.title("DnD Test")
root.update_idletasks()

hwnd      = root.winfo_id()
parent    = user32.GetParent(hwnd)
log_path  = os.path.join(OUTPUT_DIR, "test_drop.log")
cbs       = []
drop_q    = queue.SimpleQueue()

def make_proc(label, old_ref):
    def wnd_proc(h, msg, wp, lp):
        if msg == WM_DROPFILES:
            # Tcl가 GIL을 풀어놓은 상태 → Tcl 경유 호출 없이 queue에만 넣음
            count = shell32.DragQueryFileW(wp, 0xFFFFFFFF, None, 0)
            paths = []
            for i in range(count):
                buf = ctypes.create_unicode_buffer(260)
                shell32.DragQueryFileW(wp, i, buf, 260)
                paths.append(buf.value)
            shell32.DragFinish(wp)
            drop_q.put_nowait((label, h, paths))
            return 0
        return user32.CallWindowProcW(old_ref[0], h, msg, wp, lp)
    return wnd_proc

def poll():
    try:
        while True:
            label, h, paths = drop_q.get_nowait()
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"WM_DROPFILES → {label} ({h:#x}): {paths}\n")
            print(f"DROPPED via {label}: {paths}")
    except Exception:
        pass
    root.after(50, poll)

lines = [f"hwnd={hwnd:#010x}  parent={parent:#010x}"]
for label, h in [("inner", hwnd), ("outer", parent)]:
    if not h:
        continue
    shell32.DragAcceptFiles(h, True)
    try:
        user32.ChangeWindowMessageFilterEx(h, WM_DROPFILES,      MSGFLT_ALLOW, None)
        user32.ChangeWindowMessageFilterEx(h, WM_COPYGLOBALDATA, MSGFLT_ALLOW, None)
    except Exception:
        pass

    old_ref    = [0]
    cb         = WNDPROCTYPE(make_proc(label, old_ref))
    cb_addr    = ctypes.cast(cb, ctypes.c_void_p).value
    old_ref[0] = user32.SetWindowLongPtrW(h, GWL_WNDPROC, cb_addr)
    cbs.append(cb)
    lines.append(f"  [{label} {h:#010x}] old={old_ref[0]:#018x} {'OK' if old_ref[0] else 'FAIL'}")

with open(log_path, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n--- 파일을 드래그해서 놓아보세요 ---\n")

print("\n".join(lines))
print("파일을 드래그해 놓으세요.")

root.after(50, poll)
root.mainloop()
