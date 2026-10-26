"""메인 창: 왼쪽 메뉴 + 오른쪽 기능 화면. 기능 화면은 같은 자리에 겹쳐 두고 앞으로 올리기만 한다
(떼었다 붙이면 전체를 다시 배치해서 탭 이동이 버벅임)."""
import customtkinter as ctk

from .. import APP_NAME, APP_VERSION
from ..core.log import log_exc
from ..core.paths import ICON_PATH
from .theme import FONT, LOGO_FONT, THEME
from .widgets import Wrapper

SIDE_W = 170
PAD = 18


class Shell:
    def __init__(self, title):
        ctk.set_appearance_mode("dark")
        self.root = ctk.CTk(fg_color=THEME["bg"])
        self.root.title(title)
        self.root.geometry("720x640")
        self.root.minsize(680, 600)
        self.root.report_callback_exception = lambda t, e, tb: log_exc("화면 콜백", t, e, tb)
        try:
            self.root.iconbitmap(str(ICON_PATH))
        except Exception:
            pass
        self.wrapper = Wrapper()
        self.pages = {}
        self.nav = {}
        self._last_width = None
        self._resize_job = None

        side = ctk.CTkFrame(self.root, fg_color=THEME["side"], corner_radius=0, width=SIDE_W)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        logo = ctk.CTkFrame(side, fg_color="transparent")
        logo.pack(fill="x", padx=18, pady=(22, 26))
        ctk.CTkLabel(logo, text=APP_NAME, text_color=THEME["text"], font=(LOGO_FONT, 22, "bold"),
                     anchor="w").pack(fill="x")
        ctk.CTkLabel(logo, text="에이전트 함대 지휘", text_color=THEME["sub"], font=(FONT, 11),
                     anchor="w").pack(fill="x")
        self.side = side
        ctk.CTkLabel(side, text=f"v{APP_VERSION}", text_color=THEME["sub"], font=(FONT, 10)).pack(side="bottom", pady=12)

        self.body = ctk.CTkFrame(self.root, fg_color="transparent")
        self.body.pack(side="left", fill="both", expand=True)
        self.body.grid_rowconfigure(0, weight=1)
        self.body.grid_columnconfigure(0, weight=1)
        self.root.bind("<Configure>", self._on_configure)

    @property
    def content_width(self):
        return self.root.winfo_width() - SIDE_W - PAD * 2

    def add_page(self, key, title, icon, scrollable=False):
        page = (ctk.CTkScrollableFrame if scrollable else ctk.CTkFrame)(self.body, fg_color=THEME["bg"])
        page.grid(row=0, column=0, sticky="nsew", padx=PAD, pady=PAD)
        self.pages[key] = page
        b = ctk.CTkButton(self.side, text=f"{icon}  {title}", anchor="w", height=40, corner_radius=10,
                          font=(FONT, 13), fg_color="transparent", hover_color=THEME["field"],
                          text_color=THEME["text"], command=lambda: self.show_page(key))
        b.pack(fill="x", padx=10, pady=2)
        self.nav[key] = b
        return page

    def show_page(self, key):
        for k, b in self.nav.items():
            b.configure(fg_color=THEME["field"] if k == key else "transparent")
        page = self.pages[key]
        getattr(page, "_parent_frame", page).tkraise()

    def scroll_bottom(self, key):
        page = self.pages[key]
        if hasattr(page, "_parent_canvas"):
            page._parent_canvas.yview_moveto(1.0)

    def _on_configure(self, e):
        # <Configure> 는 안쪽 칸 하나만 바뀌어도 수십 번 온다 → 창 폭이 바뀔 때만, 0.1초 모아서 한 번
        if e.widget is not self.root:
            return
        w = self.root.winfo_width()
        if w == self._last_width:
            return
        self._last_width = w
        if self._resize_job:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(100, self._apply_wrap)

    def _apply_wrap(self):
        self._resize_job = None
        self.wrapper.apply(self.content_width)

    def every(self, ms, fn):
        """ms 마다 fn 실행(오류가 나도 반복은 계속)."""
        def tick():
            try:
                fn()
            except Exception:
                log_exc(f"반복 작업 {getattr(fn, '__name__', fn)}")
            self.root.after(ms, tick)
        self.root.after(ms, tick)

    def show(self):
        self.root.deiconify()
        self.root.lift()

    def hide(self):
        self.root.withdraw()
