"""음성 전송 기능: 화면(상태·마이크·최근 문장) + 설정 카드(녹음·받아쓰기·전송) + 단축키 등록."""
import threading
from datetime import datetime

import customtkinter as ctk

from ...audio import devices
from ...core.config import DEFAULT_MIC
from ...core.stt import ENGINE_LABELS
from ...ui import widgets as w
from ...ui.theme import FONT, STATE_COLORS, STATE_ICONS, THEME
from ..base import Feature
from .controller import VoiceController

HISTORY_MAX = 8
SILENCE_OPTS = {"2초": 2.0, "3초": 3.0, "5초": 5.0, "끄기": 0.0}


class VoiceFeature(Feature):
    key = "voice"
    page_title = "음성 전송"
    page_icon = "🎙"

    def __init__(self, app):
        super().__init__(app)
        self.ctrl = VoiceController(app)
        self.history = []
        self._last_status = None
        bus = app.bus
        bus.on("status", self._on_status)
        bus.on("level", self._on_level)
        bus.on("sent", self._on_sent)
        bus.on("overlay", lambda on: app.overlay and app.overlay.show(on))
        bus.on("engine", self._on_engine)
        bus.on("hotkey", self._on_hotkey)

    # ── 화면 ──
    def build_page(self, f):
        wrapper = self.app.shell.wrapper
        self.state_card = ctk.CTkFrame(f, fg_color=STATE_COLORS["idle"], corner_radius=16)
        self.state_card.pack(fill="x", pady=(0, 12))
        top = ctk.CTkFrame(self.state_card, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=(16, 4))
        self.state_icon = ctk.CTkLabel(top, text="●", text_color="white", font=(FONT, 20, "bold"), width=24)
        self.state_icon.pack(side="left")
        self.state_label = ctk.CTkLabel(top, text="", text_color="white", font=(FONT, 20, "bold"), anchor="w")
        self.state_label.pack(side="left", padx=(8, 0), fill="x", expand=True)
        self.hotkey_badge = ctk.CTkLabel(top, text=self.app.cfg["hotkey"].upper(), text_color="white",
                                         fg_color=THEME["badge"], corner_radius=8, font=(FONT, 12, "bold"),
                                         width=44, height=26)
        self.hotkey_badge.pack(side="right")
        self.detail_label = w.label(self.state_card, "", wrapper, size=12, color="text", margin=40)
        self.detail_label.pack(fill="x", padx=18, pady=(0, 16))

        mic = w.card(f, "마이크")
        row = ctk.CTkFrame(mic, fg_color="transparent")
        row.pack(fill="x", padx=16)
        self.mic_var = ctk.StringVar(value=self.app.cfg["mic"])
        self.mic_box = ctk.CTkOptionMenu(row, variable=self.mic_var, values=[DEFAULT_MIC], command=self._on_mic,
                                         font=(FONT, 12), dropdown_font=(FONT, 12), height=34,
                                         fg_color=THEME["field"], button_color=THEME["field_hover"],
                                         button_hover_color=THEME["field_press"], dynamic_resizing=False)
        self.mic_box.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(row, text="↻", width=34, height=34, font=(FONT, 16), fg_color=THEME["field_hover"],
                      hover_color=THEME["field_press"], command=self.reload_mics).pack(side="left", padx=(8, 0))
        row2 = ctk.CTkFrame(mic, fg_color="transparent")
        row2.pack(fill="x", padx=16, pady=(10, 14))
        self.meter = ctk.CTkProgressBar(row2, height=10, corner_radius=5, progress_color=THEME["track"],
                                        fg_color=THEME["track"])
        self.meter.set(0)
        self.meter.pack(side="left", fill="x", expand=True)
        w.button(row2, "테스트", self.ctrl.mic_test, primary=True).pack(side="left", padx=(10, 0))

        last = w.card(f, "최근 보낸 문장", grow=True)
        self.engine_label = w.label(last, "", wrapper, margin=40)
        self.engine_label.pack(fill="x", padx=16, pady=(6, 12), side="bottom")
        self.history_box = ctk.CTkTextbox(last, wrap="word", font=(FONT, 13), fg_color=THEME["box"],
                                          text_color=THEME["text"], corner_radius=10, border_width=0)
        self.history_box.pack(fill="both", expand=True, padx=16)
        self._set_history("아직 없음")
        self.reload_mics()
        self._on_status("idle", "대기 중", f"{self.app.cfg['hotkey'].upper()} 누르고 말하면 바로 전송돼요")
        self._on_engine()

    def build_settings(self, f):
        cfg, wrapper = self.app.cfg, self.app.shell.wrapper
        c = w.card(f, "녹음")
        r = w.setting_row(c, "단축키", "누르면 녹음 시작, 한 번 더 누르면 바로 전송", wrapper)
        self.hotkey_btn = ctk.CTkButton(r, text=cfg["hotkey"].upper(), width=110, height=32, font=(FONT, 12, "bold"),
                                        fg_color=THEME["field"], hover_color=THEME["field_hover"],
                                        command=self._capture_hotkey)
        self.hotkey_btn.pack()
        r = w.setting_row(c, "자동 멈춤", "말을 멈추고 이 시간이 지나면 자동 전송. 끄면 단축키를 다시 눌러야 전송", wrapper)
        cur = next((k for k, v in SILENCE_OPTS.items() if v == cfg["silence"]), "3초")
        w.segmented(r, list(SILENCE_OPTS), cur, lambda v: cfg.set("silence", SILENCE_OPTS[v]), width=210)
        r = w.setting_row(c, "효과음", "녹음 시작·끝에 '삑' 소리", wrapper)
        w.switch(r, cfg["sound"], lambda v: cfg.set("sound", v))
        r = w.setting_row(c, "녹음 중 표시", "화면 오른쪽 아래에 빨간 '녹음 중' 표시", wrapper)
        w.switch(r, cfg["overlay"], lambda v: cfg.set("overlay", v))

        c = w.card(f, "받아쓰기")
        r = w.setting_row(c, "엔진", "빠름: 그래픽카드, 1초 안쪽\n정확: 그래픽카드, 1~2초, 더 정확\n"
                                    "CPU: 게임 영향 없음, 말한 길이만큼 걸림", wrapper)
        w.segmented(r, list(ENGINE_LABELS.values()), ENGINE_LABELS.get(cfg["engine"], "정확"), self._on_engine_pick)
        self.engine_status = w.label(c, "", wrapper, margin=40)
        self.engine_status.pack(fill="x", padx=16, pady=(0, 8))
        w.label(c, "자주 쓰는 단어", size=13, color="text").pack(fill="x", padx=16)
        w.label(c, "이름·용어를 쉼표로 적으면 그 단어로 더 잘 알아들어요", wrapper, margin=40).pack(fill="x", padx=16)
        hw = ctk.CTkFrame(c, fg_color="transparent")
        hw.pack(fill="x", padx=16, pady=(6, 14))
        entry = ctk.CTkEntry(hw, font=(FONT, 12), height=32, fg_color=THEME["field"], border_color=THEME["line"])
        entry.insert(0, cfg["hotwords"])
        entry.pack(side="left", fill="x", expand=True)
        save = w.button(hw, "저장", None, primary=True, width=60, height=32)

        def on_save():
            cfg.set("hotwords", entry.get().strip())
            save.configure(text="저장됨")
            save.after(1500, lambda: save.configure(text="저장"))
        save.configure(command=on_save)
        save.pack(side="left", padx=(8, 0))

        c = w.card(f, "전송")
        r = w.setting_row(c, "디스코드면 바로 전송", "앞 창이 디스코드일 때 엔터까지 침. 다른 창이면 글자만 넣음", wrapper)
        w.switch(r, cfg["auto_send"], lambda v: cfg.set("auto_send", v))
        self._on_engine()

    # ── 실행 ──
    def start(self):
        self.app.engine.load(self.app.cfg["engine"])
        self.app.hotkeys.register("voice", self.app.cfg["hotkey"], self.ctrl.toggle)

    # ── 화면 갱신(메인 스레드) ──
    def _on_status(self, kind, title, detail):
        if (kind, title, detail) == self._last_status:
            return
        self._last_status = (kind, title, detail)
        self.state_card.configure(fg_color=STATE_COLORS[kind])
        self.state_icon.configure(text=STATE_ICONS[kind])
        self.state_label.configure(text=title)
        self.detail_label.configure(text=detail)
        if self.app.tray:
            self.app.tray.set_state(kind, title)

    def _on_level(self, v):
        v = min(v * 8, 1.0)
        self.meter.configure(progress_color=STATE_COLORS["ok"] if v > 0.02 else THEME["track"])
        self.meter.set(v)

    def _on_sent(self, text):
        self.history.insert(0, f"{datetime.now():%H:%M}  {text}")
        del self.history[HISTORY_MAX:]
        self._set_history("\n\n".join(self.history))

    def _set_history(self, text):
        self.history_box.configure(state="normal")
        self.history_box.delete("1.0", "end")
        self.history_box.insert("1.0", text)
        self.history_box.configure(state="disabled")

    def _on_engine(self):
        st = self.app.engine.status
        if hasattr(self, "engine_label"):
            self.engine_label.configure(text=f"받아쓰기 {st}  ·  마이크: {self._mic_name}")
        if hasattr(self, "engine_status"):
            self.engine_status.configure(text=f"상태: {st}")

    def _on_hotkey(self, combo):
        self.hotkey_btn.configure(text=combo.upper())
        self.hotkey_badge.configure(text=combo.upper())
        self._on_status("idle", "대기 중", f"{combo.upper()} 누르고 말하면 바로 전송돼요")

    # ── 조작 ──
    def reload_mics(self):
        if self.ctrl.active:
            return
        devices.refresh()
        names = [DEFAULT_MIC] + devices.list_mics()
        self.mic_box.configure(values=names)
        if self.mic_var.get() not in names:
            self.mic_var.set(DEFAULT_MIC)
        cur = self.mic_var.get()
        self._mic_name = devices.default_name() if cur == DEFAULT_MIC else cur
        self._on_engine()

    _mic_name = ""

    def _on_mic(self, name):
        self.app.cfg.set("mic", name)
        self.reload_mics()

    def _on_engine_pick(self, label):
        kind = next(k for k, v in ENGINE_LABELS.items() if v == label)
        if kind == self.app.cfg["engine"] and self.app.engine.kind == kind:
            return
        self.app.cfg.set("engine", kind)
        self.app.engine.load(kind)

    def _capture_hotkey(self):
        if self.ctrl.active or self.app.preview:
            return
        self.hotkey_btn.configure(text="키를 누르세요…")

        def wait():
            combo = self.app.hotkeys.read_new_combo()
            if combo in ("esc", "enter", "space", ""):
                combo = self.app.cfg["hotkey"]
            else:
                self.app.cfg.set("hotkey", combo)
                self.app.hotkeys.change("voice", combo)
            self.app.bus.post("hotkey", combo)
        threading.Thread(target=wait, name="hotkey-capture", daemon=True).start()
