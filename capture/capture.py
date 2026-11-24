"""
간단 화면 캡처 프로그램
- 전체 화면 캡처 / 드래그로 영역 캡처
- 지연 캡처(0~10초)
- 미리보기 창에서 저장 · 클립보드 복사(Windows)
필요: Python 3.8+, Pillow  (pip install pillow)
"""
import ctypes
import io
import os
import platform
import subprocess
import queue
import sys
import threading
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox

from PIL import Image, ImageGrab, ImageTk

IS_WIN = platform.system() == "Windows"
LOG_PATH = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"),
                        "capture_error.log")
SAVE_DIR = os.path.join(os.path.expanduser("~"), "Pictures", "Captures")

if IS_WIN:
    try:  # 고해상도(배율) 모니터에서 좌표가 어긋나지 않도록
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def log_error(text):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}]\n{text}\n")
    except Exception:
        pass


def show_fatal(text):
    """Tk 없이도 뜨는 오류 창 (exe에서 조용히 꺼지는 것 방지)."""
    msg = f"{text}\n\n로그: {LOG_PATH}"
    if IS_WIN:
        ctypes.windll.user32.MessageBoxW(None, msg, "캡처 프로그램 오류", 0x10)
    else:
        print(msg, file=sys.stderr)


def looks_blocked(img):
    """화면 전체가 검정이면 보안 프로그램이 캡처를 막은 경우가 많음."""
    small = img.convert("L").resize((64, 64))
    return small.getextrema()[1] < 8


class GlobalHotkeys(threading.Thread):
    """Windows 전역 단축키: 다른 프로그램을 쓰는 중에도 PrtSc가 동작하게 함."""
    WM_HOTKEY, MOD_CONTROL, MOD_NOREPEAT, VK_SNAPSHOT = 0x0312, 0x0002, 0x4000, 0x2C
    KEYS = {1: (0, "region"), 2: (MOD_CONTROL, "full")}  # PrtSc / Ctrl+PrtSc

    def __init__(self):
        super().__init__(daemon=True)
        self.events = queue.Queue()
        self.ready = threading.Event()
        self.failed = []

    def run(self):
        from ctypes import wintypes
        u32 = ctypes.windll.user32
        for hid, (mod, mode) in self.KEYS.items():
            if not u32.RegisterHotKey(None, hid, mod | self.MOD_NOREPEAT, self.VK_SNAPSHOT):
                self.failed.append(mode)
        self.ready.set()
        msg = wintypes.MSG()
        while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == self.WM_HOTKEY and msg.wParam in self.KEYS:
                self.events.put(self.KEYS[msg.wParam][1])


def virtual_screen():
    """모든 모니터를 합친 영역 (x, y, w, h)."""
    if IS_WIN:
        u = ctypes.windll.user32
        return (u.GetSystemMetrics(76), u.GetSystemMetrics(77),
                u.GetSystemMetrics(78), u.GetSystemMetrics(79))
    return None


def grab_all():
    try:
        return ImageGrab.grab(all_screens=True)
    except TypeError:
        return ImageGrab.grab()


def copy_to_clipboard(img):
    if not IS_WIN:
        raise RuntimeError("클립보드 복사는 Windows에서만 지원합니다.")
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "BMP")
    data = buf.getvalue()[14:]  # BMP 헤더 제거 -> DIB
    k32, u32 = ctypes.windll.kernel32, ctypes.windll.user32
    k32.GlobalAlloc.restype = ctypes.c_void_p
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalLock.argtypes = [ctypes.c_void_p]
    k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    u32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    h = k32.GlobalAlloc(0x0002, len(data))  # GMEM_MOVEABLE
    p = k32.GlobalLock(h)
    ctypes.memmove(p, data, len(data))
    k32.GlobalUnlock(h)
    if not u32.OpenClipboard(None):
        raise RuntimeError("클립보드를 열 수 없습니다.")
    try:
        u32.EmptyClipboard()
        u32.SetClipboardData(8, h)  # CF_DIB
    finally:
        u32.CloseClipboard()


class RegionSelector(tk.Toplevel):
    """캡처한 전체 화면 위에서 드래그로 영역을 고르는 창."""

    def __init__(self, master, shot, on_done):
        super().__init__(master)
        self.shot, self.on_done = shot, on_done
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        vs = virtual_screen()
        if vs:
            x, y, w, h = vs
        else:
            x, y = 0, 0
            w, h = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}{x:+d}{y:+d}")
        # 화면 크기와 캡처 이미지 크기가 다르면(배율 등) 비율 보정
        self.sx, self.sy = shot.width / w, shot.height / h
        dim = Image.blend(shot.convert("RGB").resize((w, h)),
                          Image.new("RGB", (w, h), "black"), 0.4)
        self.bg = ImageTk.PhotoImage(dim)
        self.bright = ImageTk.PhotoImage(shot.convert("RGB").resize((w, h)))

        self.cv = tk.Canvas(self, width=w, height=h, highlightthickness=0,
                            cursor="crosshair")
        self.cv.pack(fill="both", expand=True)
        self.cv.create_image(0, 0, anchor="nw", image=self.bg)
        self.cv.create_text(w // 2, 30, fill="white",
                            font=("맑은 고딕", 14, "bold"),
                            text="드래그해서 영역 선택 · ESC/우클릭 취소")
        self.start = None
        self.rect = self.label = self.crop_img = None

        self.cv.bind("<ButtonPress-1>", self.press)
        self.cv.bind("<B1-Motion>", self.drag)
        self.cv.bind("<ButtonRelease-1>", self.release)
        self.bind("<Escape>", lambda e: self.finish(None))
        self.cv.bind("<ButtonPress-3>", lambda e: self.finish(None))
        self.after(50, self.focus_force)

    def press(self, e):
        self.start = (e.x, e.y)

    def drag(self, e):
        if not self.start:
            return
        x0, y0 = self.start
        l, t, r, b = min(x0, e.x), min(y0, e.y), max(x0, e.x), max(y0, e.y)
        for item in (self.rect, self.label, self.crop_img):
            if item:
                self.cv.delete(item)
        if r - l > 1 and b - t > 1:
            self._piece = ImageTk.getimage(self.bright).crop((l, t, r, b))
            self._piece_tk = ImageTk.PhotoImage(self._piece)
            self.crop_img = self.cv.create_image(l, t, anchor="nw",
                                                 image=self._piece_tk)
        self.rect = self.cv.create_rectangle(l, t, r, b, outline="#00aaff",
                                             width=2)
        self.label = self.cv.create_text(
            l + 4, t - 4 if t > 20 else b + 14, anchor="sw" if t > 20 else "w",
            fill="white", text=f"{int((r-l)*self.sx)} × {int((b-t)*self.sy)}")

    def release(self, e):
        if not self.start:
            return
        x0, y0 = self.start
        l, t, r, b = min(x0, e.x), min(y0, e.y), max(x0, e.x), max(y0, e.y)
        if r - l < 3 or b - t < 3:
            self.start = None
            return
        box = (int(l * self.sx), int(t * self.sy),
               int(r * self.sx), int(b * self.sy))
        self.finish(self.shot.crop(box))

    def finish(self, img):
        self.destroy()
        self.on_done(img)


class Preview(tk.Toplevel):
    def __init__(self, master, img):
        super().__init__(master)
        self.img = img
        self.title(f"캡처 미리보기 - {img.width}×{img.height}")
        self.attributes("-topmost", True)

        bar = tk.Frame(self, pady=6)
        bar.pack(fill="x")
        tk.Button(bar, text="저장 (Ctrl+S)", command=self.save).pack(side="left", padx=4)
        tk.Button(bar, text="빠른 저장", command=self.quick_save).pack(side="left", padx=4)
        tk.Button(bar, text="복사 (Ctrl+C)", command=self.copy).pack(side="left", padx=4)
        tk.Button(bar, text="닫기", command=self.destroy).pack(side="right", padx=4)

        maxw = int(self.winfo_screenwidth() * 0.8)
        maxh = int(self.winfo_screenheight() * 0.75)
        view = img.copy()
        view.thumbnail((maxw, maxh))
        self.tkimg = ImageTk.PhotoImage(view)
        tk.Label(self, image=self.tkimg, bd=1, relief="solid").pack(padx=8, pady=(0, 8))

        self.status = tk.Label(self, anchor="w", fg="#555")
        self.status.pack(fill="x", padx=8, pady=(0, 6))
        self.bind("<Control-s>", lambda e: self.save())
        self.bind("<Control-c>", lambda e: self.copy())
        self.bind("<Escape>", lambda e: self.destroy())
        self.after(50, self.focus_force)

    @staticmethod
    def default_name():
        return datetime.now().strftime("capture_%Y%m%d_%H%M%S.png")

    def quick_save(self):
        os.makedirs(SAVE_DIR, exist_ok=True)
        path = os.path.join(SAVE_DIR, self.default_name())
        self.img.save(path)
        self.status.config(text=f"저장됨: {path}")

    def save(self):
        path = filedialog.asksaveasfilename(
            parent=self, initialfile=self.default_name(), defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg"), ("BMP", "*.bmp")])
        if path:
            img = self.img.convert("RGB") if path.lower().endswith((".jpg", ".jpeg")) else self.img
            img.save(path)
            self.status.config(text=f"저장됨: {path}")

    def copy(self):
        try:
            copy_to_clipboard(self.img)
            self.status.config(text="클립보드에 복사했습니다. (붙여넣기: Ctrl+V)")
        except Exception as ex:
            messagebox.showerror("복사 실패", str(ex), parent=self)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("캡처")
        self.resizable(False, False)
        self.attributes("-topmost", True)

        f = tk.Frame(self, padx=12, pady=10)
        f.pack()
        tk.Button(f, text="전체 화면 (F1)", width=14, height=2,
                  command=lambda: self.start("full")).grid(row=0, column=0, padx=4)
        tk.Button(f, text="영역 선택 (F2)", width=14, height=2,
                  command=lambda: self.start("region")).grid(row=0, column=1, padx=4)

        opt = tk.Frame(f, pady=8)
        opt.grid(row=1, column=0, columnspan=2, sticky="w")
        tk.Label(opt, text="지연(초):").pack(side="left")
        self.delay = tk.Spinbox(opt, from_=0, to=10, width=4)
        self.delay.pack(side="left", padx=4)
        tk.Button(opt, text="저장 폴더 열기", command=self.open_folder).pack(side="left", padx=8)
        self.autosave = tk.BooleanVar(value=True)
        tk.Checkbutton(f, variable=self.autosave,
                       text="자동 저장 (미리보기 없이 바로 저장 + 클립보드 복사)").grid(
            row=3, column=0, columnspan=2, sticky="w")
        self.status = tk.Label(f, fg="#0a6", anchor="w", justify="left")
        self.status.grid(row=4, column=0, columnspan=2, sticky="w")
        self.busy = False
        self.hotkeys = None
        if IS_WIN:
            self.hotkeys = GlobalHotkeys()
            self.hotkeys.start()
            self.hotkeys.ready.wait(2)
            if self.hotkeys.failed:
                self.status.config(fg="#c00", text=(
                    "PrtSc 단축키를 등록하지 못했습니다. 다른 프로그램이 PrtSc를 쓰고 있어요.\n"
                    "(Windows 설정 > 접근성 > 키보드 > 'PrtSc 단추로 화면 캡처 열기' 끄기,\n"
                    " OneDrive·카톡·알캡처 등의 캡처 단축키 끄기 후 이 프로그램을 다시 켜세요)"))
            else:
                self.status.config(text="PrtSc = 영역 캡처 · Ctrl+PrtSc = 전체 화면 (창을 최소화해도 동작)")
            self.after(100, self.poll_hotkeys)

        self.report_callback_exception = self.on_error
        tk.Label(f, fg="#777", text="단축키: F1 전체 · F2 영역 (이 창이 선택된 상태)").grid(
            row=2, column=0, columnspan=2)
        self.bind("<F1>", lambda e: self.start("full"))
        self.bind("<F2>", lambda e: self.start("region"))

    def poll_hotkeys(self):
        try:
            while True:
                mode = self.hotkeys.events.get_nowait()
                if not self.busy:
                    self.start(mode, use_delay=False)
        except queue.Empty:
            pass
        self.after(100, self.poll_hotkeys)

    def start(self, mode, use_delay=True):
        if self.busy:
            return
        self.busy = True
        self.was_iconic = self.state() == "iconic"
        try:
            sec = max(0, min(10, int(self.delay.get())))
        except ValueError:
            sec = 0
        if not use_delay:
            sec = 0
        self.withdraw()  # 캡처에 이 창이 찍히지 않도록 숨김
        self.after(sec * 1000 + 250, lambda: self.capture(mode))

    def capture(self, mode):
        try:
            shot = grab_all()
        except Exception as ex:
            self.restore()
            messagebox.showerror("캡처 실패", str(ex))
            return
        if looks_blocked(shot):
            log_error("captured image is all black (blocked?)")
            messagebox.showwarning(
                "캡처가 검게 나옴",
                "캡처 결과가 전부 검은색입니다.\n\n"
                "회사 보안 프로그램(DRM·화면 캡처 방지)이나 보안 문서/사이트가\n"
                "열려 있으면 이렇게 막힐 수 있습니다. 해당 창을 닫고 다시 시도해 보세요.")
        if mode == "full":
            self.done(shot)
        else:
            RegionSelector(self, shot, self.done)

    def restore(self):
        self.busy = False
        if self.was_iconic:
            self.iconify()
        else:
            self.deiconify()

    def done(self, img):
        self.restore()
        if img is None:
            return
        if not self.autosave.get():
            Preview(self, img)
            return
        os.makedirs(SAVE_DIR, exist_ok=True)
        path = os.path.join(SAVE_DIR, Preview.default_name())
        img.save(path)
        copied = ""
        try:
            copy_to_clipboard(img)
            copied = " + 클립보드 복사"
        except Exception:
            pass
        self.status.config(fg="#0a6", text=f"저장됨{copied}: {path}")
        self.toast(f"저장됨{copied}\n{os.path.basename(path)}")

    def toast(self, text):
        t = tk.Toplevel(self)
        t.overrideredirect(True)
        t.attributes("-topmost", True)
        tk.Label(t, text=text, bg="#222", fg="white", padx=14, pady=10,
                 justify="left").pack()
        t.update_idletasks()
        x = self.winfo_screenwidth() - t.winfo_width() - 20
        y = self.winfo_screenheight() - t.winfo_height() - 70
        t.geometry(f"+{x}+{y}")
        t.after(2000, t.destroy)

    def on_error(self, exc, val, tb):
        import traceback
        text = "".join(traceback.format_exception(exc, val, tb))
        log_error(text)
        self.busy = False
        self.deiconify()
        messagebox.showerror("오류", f"{val}\n\n로그: {LOG_PATH}")

    def open_folder(self):
        os.makedirs(SAVE_DIR, exist_ok=True)
        if IS_WIN:
            os.startfile(SAVE_DIR)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", SAVE_DIR])
        else:
            subprocess.Popen(["xdg-open", SAVE_DIR])


if __name__ == "__main__":
    try:
        App().mainloop()
    except Exception:
        import traceback
        log_error(traceback.format_exc())
        show_fatal("프로그램을 시작하지 못했습니다.\n" + traceback.format_exc(limit=1))
