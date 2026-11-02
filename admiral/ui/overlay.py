"""녹음 중 화면 오른쪽 아래 빨간 표시 + 마이크 소리 막대(메인 창을 닫아 놔도 떠 있음)."""
import math
from collections import deque

import customtkinter as ctk

from .theme import FONT, STATE_COLORS

BARS = 12
BAR_W, GAP, BAR_H = 4, 3, 22
QUIET_LABEL = "소리 안 들림"


class LevelTrack:
    """0.05초마다 오는 음량으로 막대 높이(0~1)와 '소리가 들리는지'를 정한다. 화면과 떼어 놔서 시험 가능."""
    LOW, HIGH = 0.0005, 0.1  # 이 사이를 로그 눈금으로(작게 말하면 0.001~0.003, 크게 말하면 0.05 이상)
    HEARD = 0.0015            # 이보다 크면 소리가 들어오는 중
    QUIET_SEC = 2.0           # 이만큼 안 들리면 '소리 안 들림'

    def __init__(self):
        self.reset()

    def reset(self):
        self.heights = deque([0.0] * BARS, maxlen=BARS)
        self.since_heard = 0.0

    def feed(self, v, dt=0.05):
        h = (math.log10(max(v, 1e-6)) - math.log10(self.LOW)) / (math.log10(self.HIGH) - math.log10(self.LOW))
        self.heights.append(min(max(h, 0.0), 1.0))
        self.since_heard = 0.0 if v > self.HEARD else self.since_heard + dt

    @property
    def heard(self):
        return self.since_heard == 0.0

    @property
    def quiet(self):
        return self.since_heard >= self.QUIET_SEC


class Overlay:
    def __init__(self, root):
        self.root = root
        self.track = LevelTrack()
        self.shown = False
        bg = STATE_COLORS["rec"]
        self.win = ctk.CTkToplevel(root, fg_color=bg)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        row = ctk.CTkFrame(self.win, fg_color=bg)
        row.pack(padx=14, pady=8)
        self.dot = ctk.CTkLabel(row, text="●", text_color="white", font=(FONT, 14, "bold"))
        self.dot.pack(side="left")
        self.label = ctk.CTkLabel(row, text="녹음 중", width=84, anchor="w", text_color="white", font=(FONT, 14, "bold"))
        self.label.pack(side="left", padx=(6, 8))
        self.canvas = ctk.CTkCanvas(row, width=BARS * (BAR_W + GAP) - GAP, height=BAR_H, bg=bg, highlightthickness=0)
        self.canvas.pack(side="left")
        self.win.withdraw()

    def show(self, on):
        self.shown = on
        if on:
            self.track.reset()
            self._draw()
            self.win.update_idletasks()
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            self.win.geometry(f"+{sw - self.win.winfo_reqwidth() - 24}+{sh - 120}")
            self.win.deiconify()
        else:
            self.win.withdraw()

    def level(self, v):
        if not self.shown:
            return
        self.track.feed(v)
        self._draw()

    def _draw(self):
        c = self.canvas
        c.delete("all")
        for i, h in enumerate(self.track.heights):
            bh = max(2, round(h * BAR_H))
            x = i * (BAR_W + GAP)
            c.create_rectangle(x, BAR_H - bh, x + BAR_W, BAR_H, fill="white", width=0)
        quiet = self.track.quiet
        self.label.configure(text=QUIET_LABEL if quiet else "녹음 중")
        # 소리가 들어오는 동안 동그라미가 밝게, 아니면 흐리게
        self.dot.configure(text_color="white" if self.track.heard else "#f4a6a8")
