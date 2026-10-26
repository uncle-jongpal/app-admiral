r"""
Admiral (작업PC, 2026-10-26 jarvis) — 형이 에이전트 함대(fleet)를 지휘하는 도구 모음. 첫 기능: 음성 전송.
(10/26 이름 변천: 음성 전송 → 콘솔 → Admiral)

음성 전송
  단축키(기본 F9) 누르고 말하면 → 글자로 바꿔서 → 앞에 있는 입력창에 넣고, 디스코드면 엔터까지 쳐서 바로 전송.
  키보드로 직접 친 것과 같아서 형 계정 메시지로 나간다(봇·웹후크 아님 → 에이전트들이 받음).

받아쓰기 엔진(설정에서 선택)
  그래픽카드: Admiral 전용 large-v3-turbo 를 계속 올려 둠(그래픽카드 메모리 약 2GB, 10/26 실측 2.1GB). 말 끝나고 1초 안쪽.
  CPU: medium int8. 그래픽카드를 안 써서 게임 영향 없음. 말한 길이만큼 걸림.
  그래픽카드가 안 되면 CPU 로 자동 전환.

창을 닫으면 작업 표시줄 오른쪽 아이콘(트레이)으로 숨는다. 종료는 트레이 아이콘 우클릭 → 종료.
설정: config.json / 기록: logs\admiral-YYYYMMDD.log  (실행 파일로 돌 때도 프로젝트 폴더에 둠)
"""
import ctypes
import ctypes.wintypes as wt
import importlib.util
import io
import json
import os
import queue
import subprocess
import sys
import threading
import time
import wave
import winsound
from datetime import datetime
from pathlib import Path

APP_NAME = "Admiral"
APP_VERSION = "1.1.0"
TASK_NAME = "admiral"

# 실행 파일(dist\Admiral\Admiral.exe)로 돌 때도 설정·기록·모델은 프로젝트 폴더에 둔다
BASE = (Path(sys.executable).resolve().parents[2] if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parent)
os.environ.setdefault("HF_HOME", str(BASE / "models"))


def _add_cuda_dlls():
    """pip 로 깐 cuBLAS·cuDNN DLL 을 찾게 경로 추가(받아쓰기 서버와 같은 방식)."""
    dirs = []
    roots = [Path(getattr(sys, "_MEIPASS", ""))] if getattr(sys, "frozen", False) else []
    for pkg in ("nvidia.cublas", "nvidia.cudnn", "nvidia.cuda_nvrtc"):
        try:
            spec = importlib.util.find_spec(pkg)
        except Exception:
            spec = None
        if spec and spec.submodule_search_locations:
            roots.append(Path(list(spec.submodule_search_locations)[0]).parent.parent)
    for r in roots:
        for d in r.glob("nvidia/*/bin"):
            if d.is_dir() and str(d) not in dirs:
                dirs.append(str(d))
    for d in dirs:
        try:
            os.add_dll_directory(d)
        except Exception:
            pass
    if dirs:
        os.environ["PATH"] = os.pathsep.join(dirs) + os.pathsep + os.environ.get("PATH", "")


_add_cuda_dlls()

import customtkinter as ctk
import keyboard
import numpy as np
import psutil
import pyperclip
import pystray
import sounddevice as sd
from PIL import Image, ImageDraw

RATE = 16000
SEND_APPS = {"discord.exe", "discordptb.exe", "discordcanary.exe"}
DEFAULT_MIC = "윈도우 기본 마이크"
CONFIG_PATH = BASE / "config.json"
DEFAULTS = {"mic": DEFAULT_MIC, "hotkey": "f9", "auto_send": True, "engine": "gpu_acc", "silence": 3.0,
            "no_speech": 10.0, "max_sec": 120.0, "min_level": 0.004, "sound": True, "overlay": True,
            "hotwords": "쫑팔, 자비스, 트론, 타스, 사만다, 베이맥스, 프라이데이"}
ENGINES = {"gpu": ("large-v3-turbo", "cuda", "float16"),     # 빠름
           "gpu_acc": ("large-v3", "cuda", "int8_float16"),  # 정확(받아쓰기 서버와 같은 모델, 메모리 줄인 형식)
           "cpu": ("medium", "cpu", "int8")}
ENGINE_LABELS = {"gpu": "빠름", "gpu_acc": "정확", "cpu": "CPU"}

LOG_DIR = BASE / "logs"
LOG_DIR.mkdir(exist_ok=True)

FONT = "맑은 고딕"
THEME = {"bg": "#0f1115", "side": "#151821", "card": "#1b1e26", "line": "#2a2f3a", "text": "#e8eaf0",
         "sub": "#9aa1b2", "accent": "#5b8cff", "field": "#252a35", "field_hover": "#2f3542"}
STATE_COLORS = {"idle": "#3a4152", "rec": "#e5484d", "busy": "#f5a524", "ok": "#30a46c", "err": "#8e4ec6"}
STATE_ICONS = {"idle": "●", "rec": "●", "busy": "…", "ok": "✓", "err": "!"}


def log(msg):
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    print(line, flush=True)
    with open(LOG_DIR / f"admiral-{datetime.now():%Y%m%d}.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_config():
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    except Exception:
        pass
    if cfg["engine"] not in ENGINES:  # 옛 음성 전송 설정("auto")에서 넘어온 경우
        cfg["engine"] = "gpu"
    return cfg


def save_config(cfg):
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def foreground_exe():
    user32 = ctypes.windll.user32
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), ctypes.byref(pid))
    try:
        return psutil.Process(pid.value).name().lower()
    except Exception:
        return ""


# ── 윈도우 시작 시 자동 실행(예약 작업) ──────────────────

def _schtasks(*args):
    return subprocess.run(["schtasks", *args], capture_output=True, creationflags=0x08000000)


def autostart_enabled():
    return _schtasks("/query", "/tn", TASK_NAME).returncode == 0


def set_autostart(on):
    if on:
        target = sys.executable if getattr(sys, "frozen", False) else f'"{sys.executable}" "{Path(__file__).resolve()}"'
        r = _schtasks("/create", "/tn", TASK_NAME, "/sc", "onlogon", "/it", "/rl", "limited", "/tr",
                      f'"{target}"' if getattr(sys, "frozen", False) else target, "/f")
    else:
        r = _schtasks("/delete", "/tn", TASK_NAME, "/f")
    log(f"자동 실행 {'켬' if on else '끔'} (결과 {r.returncode})")
    return r.returncode == 0


# ── 마이크 ──────────────────────────────────────────────

def refresh_devices():
    """PortAudio 를 다시 초기화해 새로 꽂거나 켠 장치를 읽는다."""
    try:
        sd._terminate()
    except Exception:
        pass
    sd._initialize()


def _hostapi(name):
    return next((i for i, h in enumerate(sd.query_hostapis()) if name in h["name"]), None)


def full_name(short):
    """MME 장치 이름은 31자에서 잘림 → 같은 장치의 WASAPI 이름(전체)으로 바꿔 보여 준다."""
    wasapi = _hostapi("WASAPI")
    for d in sd.query_devices():
        if d["hostapi"] == wasapi and d["max_input_channels"] > 0 and d["name"].startswith(short):
            return d["name"]
    return short


def list_mics():
    """MME 쪽 입력 장치(윈도우가 16kHz 변환을 해 줌). 이름은 전체 이름으로."""
    names = []
    mme = _hostapi("MME")
    for d in sd.query_devices():
        if d["max_input_channels"] > 0 and (mme is None or d["hostapi"] == mme):
            if "Sound Mapper" in d["name"] or "매퍼" in d["name"]:
                continue
            n = full_name(d["name"])
            if n not in names:
                names.append(n)
    return names


def resolve_mic(name):
    if not name or name == DEFAULT_MIC:
        return None
    mme = _hostapi("MME")
    for i, d in enumerate(sd.query_devices()):
        if d["hostapi"] == mme and d["max_input_channels"] > 0 and name.startswith(d["name"]):
            return i
    log(f"마이크 '{name}' 없음 → 윈도우 기본 마이크 사용")
    return None


def mic_label(dev):
    return full_name(sd.query_devices(dev if dev is not None else sd.default.device[0])["name"])


# ── 받아쓰기 ────────────────────────────────────────────

class Engine:
    """Admiral 안에서 계속 올려 두는 받아쓰기 모델. 그래픽카드 실패 시 CPU 로 바꿈."""

    def __init__(self, on_change):
        self.model = None
        self.kind = None
        self.status = "준비 전"
        self.ready = threading.Event()
        self.lock = threading.Lock()
        self.on_change = on_change

    def load(self, kind):
        threading.Thread(target=self._load, args=(kind,), daemon=True).start()

    def _load(self, kind):
        with self.lock:
            self.ready.clear()
            self.model = None
            import gc
            gc.collect()
            while True:
                name, device, ctype = ENGINES[kind]
                self._set(f"{ENGINE_LABELS[kind]} 모델 올리는 중…")
                t0 = time.time()
                try:
                    from faster_whisper import WhisperModel
                    self.model = WhisperModel(name, device=device, compute_type=ctype,
                                              **({"cpu_threads": 8} if device == "cpu" else {}))
                    self.kind = kind
                    took = time.time() - t0
                    self._set(f"{ENGINE_LABELS[kind]} 모델 준비됨 · 올리는 데 {took:.0f}초")
                    log(f"받아쓰기 모델 준비 {name}/{device} ({took:.1f}초)")
                    break
                except Exception as e:
                    log(f"받아쓰기 모델 실패 {name}/{device}: {e}")
                    if kind != "cpu":
                        kind = "cpu"  # 그래픽카드가 안 되면 CPU 로
                        continue
                    self._set(f"받아쓰기 모델 실패: {str(e)[:80]}")
                    break
            self.ready.set()

    def _set(self, s):
        self.status = s
        self.on_change()

    def transcribe(self, pcm, hotwords):
        self.ready.wait()
        if self.model is None:
            raise RuntimeError("받아쓰기 모델 없음")
        audio = normalize(pcm)
        segs, _ = self.model.transcribe(audio, language="ko", beam_size=1 if self.kind == "cpu" else 5,
                                        vad_filter=True, condition_on_previous_text=False,
                                        hotwords=hotwords or None)
        return "".join(s.text for s in segs).strip()


def normalize(pcm):
    """작은 소리를 키운다(마이크 입력이 작으면 받아쓰기가 비슷한 단어로 헷갈림). 최대 20배."""
    audio = pcm.astype(np.float32) / 32768
    peak = float(np.percentile(np.abs(audio), 99.9)) if len(audio) else 0.0
    if peak > 1e-4:
        audio = np.clip(audio * min(0.5 / peak, 20.0), -1.0, 1.0)
    return audio


def save_last(pcm):
    """마지막 녹음 1개만 남김(받아쓰기 품질 비교용, 매번 덮어씀)."""
    try:
        with wave.open(str(LOG_DIR / "last.wav"), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(pcm.tobytes())
    except Exception as e:
        log(f"마지막 녹음 저장 실패: {e}")


def deliver(text, auto_send):
    exe = foreground_exe()
    old = None
    try:
        old = pyperclip.paste()
    except Exception:
        pass
    pyperclip.copy(text)
    time.sleep(0.05)
    keyboard.send("ctrl+v")
    sent = auto_send and exe in SEND_APPS
    if sent:
        time.sleep(0.15)
        keyboard.send("enter")
    time.sleep(0.3)
    if old is not None:
        try:
            pyperclip.copy(old)
        except Exception:
            pass
    return exe, sent


def make_icon(color, size=64):
    """둥근 사각형 위에 흰 별(제독 계급장). color 로 상태를 표시."""
    import math
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    k = size / 64
    d.rounded_rectangle((2 * k, 2 * k, 62 * k, 62 * k), radius=16 * k, fill=color)
    cx, cy, ro, ri = 32 * k, 33 * k, 21 * k, 8.5 * k
    pts = []
    for i in range(10):
        r = ro if i % 2 == 0 else ri
        ang = -math.pi / 2 + i * math.pi / 5
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    d.polygon(pts, fill="white")
    return img


# ── 화면 ────────────────────────────────────────────────

class App:
    def __init__(self, preview=None):
        self.preview = preview  # 화면 확인용(--preview 페이지): 단축키·모델·트레이 없이 화면만
        self.cfg = load_config()
        self.ui = queue.Queue()
        self.active = False
        self.testing = False
        self.capturing = False
        self.stop_flag = threading.Event()
        self.lock = threading.Lock()
        self.default_mic = ""
        self.history = []
        self.engine = Engine(lambda: self.ui.put(("engine",)))

        ctk.set_appearance_mode("dark")
        self.root = ctk.CTk(fg_color=THEME["bg"])
        self.root.title(APP_NAME if not preview else f"{APP_NAME} 미리보기")
        self.root.geometry("720x640")
        self.root.minsize(680, 600)
        self.root.protocol("WM_DELETE_WINDOW", self.hide)
        try:
            self.root.iconbitmap(str(BASE / "admiral.ico"))
        except Exception:
            pass
        self.wrap_labels = []
        self._build()
        self.root.bind("<Configure>", self._on_resize)

        self.overlay = ctk.CTkToplevel(self.root, fg_color=STATE_COLORS["rec"])
        self.overlay.overrideredirect(True)
        self.overlay.attributes("-topmost", True)
        ctk.CTkLabel(self.overlay, text="●  녹음 중", text_color="white",
                     font=(FONT, 14, "bold")).pack(padx=16, pady=8)
        self.overlay.withdraw()

        if preview:
            self.engine.status = "미리보기"
            self.default_mic = "미리보기"
            self.reload_mics()
            page = preview.replace("-bottom", "")
            self.show_page(page)
            if preview.endswith("-bottom"):
                self.root.after(800, lambda: self.pages[page]._parent_canvas.yview_moveto(1.0))
            self.set_state("idle", "대기 중", f"{self.cfg['hotkey'].upper()} 누르고 말하면 바로 전송돼요")
            self.root.after(50, self.pump)
            self.root.after(8000, self.root.destroy)
            return

        self.tray = pystray.Icon("admiral", make_icon(STATE_COLORS["idle"]), f"{APP_NAME}: 대기 중", menu=pystray.Menu(
            pystray.MenuItem("열기", lambda: self.ui.put(("show",)), default=True),
            pystray.MenuItem("종료", lambda: self.ui.put(("quit",)))))
        threading.Thread(target=self.tray.run, daemon=True).start()

        self.engine.load(self.cfg["engine"])
        self.hotkey_handle = None
        self.bind_hotkey()
        self.reload_mics()
        self.set_state("idle", "대기 중", f"{self.cfg['hotkey'].upper()} 누르고 말하면 바로 전송돼요")
        self.root.after(50, self.pump)
        log(f"시작 v{APP_VERSION} (단축키 {self.cfg['hotkey'].upper()}, 엔진 {self.cfg['engine']}, 마이크 {self.cfg['mic']})")

    # ── 공통 부품 ──
    def _card(self, parent, title=None, grow=False):
        card = ctk.CTkFrame(parent, fg_color=THEME["card"], corner_radius=14,
                            border_width=1, border_color=THEME["line"])
        card.pack(fill="both" if grow else "x", expand=grow, pady=(0, 10 if not grow else 0))
        if title:
            ctk.CTkLabel(card, text=title, text_color=THEME["sub"], font=(FONT, 12, "bold"),
                         anchor="w").pack(fill="x", padx=16, pady=(12, 6))
        return card

    def _wrap(self, label):
        self.wrap_labels.append(label)
        return label

    def _row(self, card, title, desc=None):
        """설정 한 줄: 왼쪽 제목·설명, 오른쪽 조작부(반환 프레임에 넣음)."""
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(4, 10))
        right = ctk.CTkFrame(row, fg_color="transparent")
        right.pack(side="right", padx=(12, 0))
        left = ctk.CTkFrame(row, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(left, text=title, text_color=THEME["text"], font=(FONT, 13), anchor="w").pack(fill="x")
        if desc:
            self._wrap(ctk.CTkLabel(left, text=desc, text_color=THEME["sub"], font=(FONT, 11), anchor="w",
                                    justify="left")).pack(fill="x")
        return right

    def _switch(self, parent, key, command=None):
        var = ctk.BooleanVar(value=self.cfg[key])

        def changed():
            self.cfg[key] = bool(var.get())
            save_config(self.cfg)
            log(f"설정 {key}={self.cfg[key]}")
            if command:
                command()
        ctk.CTkSwitch(parent, text="", variable=var, command=changed, width=46,
                      progress_color=THEME["accent"]).pack()
        return var

    # ── 화면 구성 ──
    def _build(self):
        side = ctk.CTkFrame(self.root, fg_color=THEME["side"], corner_radius=0, width=170)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        logo = ctk.CTkFrame(side, fg_color="transparent")
        logo.pack(fill="x", padx=18, pady=(22, 26))
        ctk.CTkLabel(logo, text="Admiral", text_color=THEME["text"], font=("Segoe UI", 22, "bold"), anchor="w").pack(fill="x")
        ctk.CTkLabel(logo, text="에이전트 함대 지휘", text_color=THEME["sub"], font=(FONT, 11), anchor="w").pack(fill="x")

        self.pages = {}
        self.nav = {}
        body = ctk.CTkFrame(self.root, fg_color="transparent")
        body.pack(side="left", fill="both", expand=True)
        for key, label in (("voice", "🎙  음성 전송"), ("settings", "⚙  설정")):
            b = ctk.CTkButton(side, text=label, anchor="w", height=40, corner_radius=10, font=(FONT, 13),
                              fg_color="transparent", hover_color=THEME["field"], text_color=THEME["text"],
                              command=lambda k=key: self.show_page(k))
            b.pack(fill="x", padx=10, pady=2)
            self.nav[key] = b
        ctk.CTkLabel(side, text=f"v{APP_VERSION}", text_color=THEME["sub"], font=(FONT, 10)).pack(side="bottom", pady=12)

        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)
        self.pages["voice"] = ctk.CTkFrame(body, fg_color=THEME["bg"])
        self.pages["settings"] = ctk.CTkScrollableFrame(body, fg_color=THEME["bg"])
        for p in self.pages.values():
            p.grid(row=0, column=0, sticky="nsew", padx=18, pady=18)
        self._build_voice(self.pages["voice"])
        self._build_settings(self.pages["settings"])
        self.show_page("voice")

    def show_page(self, key):
        # 두 화면을 같은 자리에 겹쳐 두고 앞으로 올리기만 함(떼었다 붙이면 전체를 다시 배치해서 느림)
        for k in self.pages:
            self.nav[k].configure(fg_color=THEME["field"] if k == key else "transparent")
        page = self.pages[key]
        getattr(page, "_parent_frame", page).tkraise()

    def _build_voice(self, f):
        # 상태 카드
        self.state_card = ctk.CTkFrame(f, fg_color=STATE_COLORS["idle"], corner_radius=16)
        self.state_card.pack(fill="x", pady=(0, 12))
        top = ctk.CTkFrame(self.state_card, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=(16, 4))
        self.state_icon = ctk.CTkLabel(top, text="●", text_color="white", font=(FONT, 20, "bold"), width=24)
        self.state_icon.pack(side="left")
        self.state_label = ctk.CTkLabel(top, text="", text_color="white", font=(FONT, 20, "bold"), anchor="w")
        self.state_label.pack(side="left", padx=(8, 0), fill="x", expand=True)
        self.hotkey_badge = ctk.CTkLabel(top, text=self.cfg["hotkey"].upper(), text_color="white",
                                         fg_color="#1f232c", corner_radius=8, font=(FONT, 12, "bold"),
                                         width=44, height=26)
        self.hotkey_badge.pack(side="right")
        self.detail_label = self._wrap(ctk.CTkLabel(self.state_card, text="", text_color="#f1f3f8",
                                                    font=(FONT, 12), anchor="w", justify="left"))
        self.detail_label.pack(fill="x", padx=18, pady=(0, 16))

        # 마이크 카드
        mic = self._card(f, "마이크")
        row = ctk.CTkFrame(mic, fg_color="transparent")
        row.pack(fill="x", padx=16)
        self.mic_var = ctk.StringVar(value=self.cfg["mic"])
        self.mic_box = ctk.CTkOptionMenu(row, variable=self.mic_var, values=[DEFAULT_MIC], command=self.on_mic,
                                         font=(FONT, 12), dropdown_font=(FONT, 12), height=34,
                                         fg_color=THEME["field"], button_color=THEME["field_hover"],
                                         button_hover_color="#3a4152", dynamic_resizing=False)
        self.mic_box.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(row, text="↻", width=34, height=34, font=(FONT, 16), fg_color=THEME["field_hover"],
                      hover_color="#3a4152", command=self.reload_mics).pack(side="left", padx=(8, 0))
        row2 = ctk.CTkFrame(mic, fg_color="transparent")
        row2.pack(fill="x", padx=16, pady=(10, 14))
        self.meter = ctk.CTkProgressBar(row2, height=10, corner_radius=5, progress_color="#2a2f3a",
                                        fg_color="#2a2f3a")
        self.meter.set(0)
        self.meter.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(row2, text="테스트", width=72, height=30, font=(FONT, 12), fg_color=THEME["accent"],
                      command=self.mic_test).pack(side="left", padx=(10, 0))

        # 최근 보낸 문장
        last = self._card(f, "최근 보낸 문장", grow=True)  # 창 아래까지 채워 빈 공간 없게
        self.history_box = ctk.CTkTextbox(last, height=150, wrap="word", font=(FONT, 13), fg_color="#14171d",
                                          text_color=THEME["text"], corner_radius=10, border_width=0)
        self.history_box.pack(fill="both", expand=True, padx=16)
        self.history_box.insert("1.0", "아직 없음")
        self.history_box.configure(state="disabled")
        self.engine_label = self._wrap(ctk.CTkLabel(last, text="", text_color=THEME["sub"], font=(FONT, 11),
                                                    anchor="w", justify="left"))
        self.engine_label.pack(fill="x", padx=16, pady=(6, 12), side="bottom")

    def _build_settings(self, f):
        # 녹음
        c = self._card(f, "녹음")
        r = self._row(c, "단축키", "누르면 녹음 시작, 한 번 더 누르면 바로 전송")
        self.hotkey_btn = ctk.CTkButton(r, text=self.cfg["hotkey"].upper(), width=110, height=32,
                                        font=(FONT, 12, "bold"), fg_color=THEME["field"],
                                        hover_color=THEME["field_hover"], command=self.capture_hotkey)
        self.hotkey_btn.pack()
        r = self._row(c, "자동 멈춤", "말을 멈추고 이 시간이 지나면 자동 전송. 끄면 단축키를 다시 눌러야 전송")
        self.sil_opts = {"2초": 2.0, "3초": 3.0, "5초": 5.0, "끄기": 0.0}
        cur = next((k for k, v in self.sil_opts.items() if v == self.cfg["silence"]), "3초")
        self.sil_var = ctk.StringVar(value=cur)
        ctk.CTkSegmentedButton(r, values=list(self.sil_opts), variable=self.sil_var, command=self.on_silence,
                               font=(FONT, 12), height=30, width=210, selected_color=THEME["accent"],
                               unselected_color=THEME["field"]).pack()
        r = self._row(c, "효과음", "녹음 시작·끝에 '삑' 소리")
        self._switch(r, "sound")
        r = self._row(c, "녹음 중 표시", "화면 오른쪽 아래에 빨간 '녹음 중' 표시")
        self._switch(r, "overlay")

        # 받아쓰기
        c = self._card(f, "받아쓰기")
        r = self._row(c, "엔진", "빠름: 그래픽카드, 1초 안쪽\n정확: 그래픽카드, 1~2초, 더 정확\n"
                                "CPU: 게임 영향 없음, 말한 길이만큼 걸림")
        self.engine_var = ctk.StringVar(value=ENGINE_LABELS[self.cfg["engine"]])
        ctk.CTkSegmentedButton(r, values=list(ENGINE_LABELS.values()), variable=self.engine_var,
                               command=self.on_engine, font=(FONT, 12), height=30, width=200, selected_color=THEME["accent"],
                               unselected_color=THEME["field"]).pack()
        self.engine_status = self._wrap(ctk.CTkLabel(c, text="", text_color=THEME["sub"], font=(FONT, 11),
                                                     anchor="w", justify="left"))
        self.engine_status.pack(fill="x", padx=16, pady=(0, 8))
        ctk.CTkLabel(c, text="자주 쓰는 단어", text_color=THEME["text"], font=(FONT, 13),
                     anchor="w").pack(fill="x", padx=16)
        self._wrap(ctk.CTkLabel(c, text="이름·용어를 쉼표로 적으면 그 단어로 더 잘 알아들어요", text_color=THEME["sub"],
                                font=(FONT, 11), anchor="w", justify="left")).pack(fill="x", padx=16)
        hw = ctk.CTkFrame(c, fg_color="transparent")
        hw.pack(fill="x", padx=16, pady=(6, 14))
        self.hot_entry = ctk.CTkEntry(hw, font=(FONT, 12), height=32, fg_color=THEME["field"],
                                      border_color=THEME["line"])
        self.hot_entry.insert(0, self.cfg["hotwords"])
        self.hot_entry.pack(side="left", fill="x", expand=True)
        self.hot_btn = ctk.CTkButton(hw, text="저장", width=60, height=32, font=(FONT, 12),
                                     fg_color=THEME["accent"], command=self.on_hotwords)
        self.hot_btn.pack(side="left", padx=(8, 0))

        # 전송
        c = self._card(f, "전송")
        r = self._row(c, "디스코드면 바로 전송", "앞 창이 디스코드일 때 엔터까지 침. 다른 창이면 글자만 넣음")
        self._switch(r, "auto_send")

        # 프로그램
        c = self._card(f, "프로그램")
        r = self._row(c, "윈도우 켜질 때 자동 실행")
        self.autostart_var = ctk.BooleanVar(value=autostart_enabled())
        ctk.CTkSwitch(r, text="", variable=self.autostart_var, width=46, progress_color=THEME["accent"],
                      command=lambda: set_autostart(bool(self.autostart_var.get()))).pack()
        r = self._row(c, "기록 폴더", str(LOG_DIR))
        ctk.CTkButton(r, text="열기", width=60, height=30, font=(FONT, 12), fg_color=THEME["field"],
                      hover_color=THEME["field_hover"], command=lambda: os.startfile(LOG_DIR)).pack()

    def _on_resize(self, e=None):
        # <Configure> 는 안쪽 칸 하나만 바뀌어도 수십 번 온다 → 창 폭이 실제로 바뀔 때만, 0.1초 모아서 한 번
        if e is not None and e.widget is not self.root:
            return
        width = self.root.winfo_width()
        if width == getattr(self, "_last_width", None):
            return
        self._last_width = width
        if getattr(self, "_resize_job", None):
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(100, self._apply_wrap)

    def _apply_wrap(self):
        # 긴 글은 창 폭에 맞춰 줄바꿈(잘리지 않게)
        self._resize_job = None
        w = max(self.root.winfo_width() - 170 - 36 - 200, 220)
        for lb in self.wrap_labels:
            lb.configure(wraplength=w)
        self.detail_label.configure(wraplength=max(self.root.winfo_width() - 170 - 80, 260))
        self.engine_label.configure(wraplength=max(self.root.winfo_width() - 170 - 80, 260))

    # 화면 갱신은 전부 메인 스레드에서
    def pump(self):
        try:
            while True:
                msg = self.ui.get_nowait()
                kind = msg[0]
                if kind == "state":
                    self._apply_state(*msg[1:])
                elif kind == "level":
                    v = min(msg[1] * 8, 1.0)
                    self.meter.configure(progress_color=STATE_COLORS["ok"] if v > 0.02 else "#2a2f3a")
                    self.meter.set(v)
                elif kind == "sent":
                    self.history.insert(0, msg[1])
                    self.history = self.history[:8]
                    self.history_box.configure(state="normal")
                    self.history_box.delete("1.0", "end")
                    self.history_box.insert("1.0", "\n\n".join(self.history))
                    self.history_box.configure(state="disabled")
                elif kind == "overlay":
                    self._overlay(msg[1])
                elif kind == "engine":
                    pass
                elif kind == "hotkey":
                    self.hotkey_btn.configure(text=msg[1])
                    self.hotkey_badge.configure(text=self.cfg["hotkey"].upper())
                elif kind == "show":
                    self.root.deiconify()
                    self.root.lift()
                elif kind == "quit":
                    self.quit()
                    return
        except queue.Empty:
            pass
        # 글자가 바뀔 때만 다시 그림(매번 그리면 스크롤·탭 이동이 버벅임)
        status = (self.engine.status, self.default_mic)
        if status != getattr(self, "_last_status", None):
            self._last_status = status
            self.engine_status.configure(text=f"상태: {self.engine.status}")
            self.engine_label.configure(text=f"받아쓰기 {self.engine.status}  ·  마이크: {self.default_mic}")
        self.root.after(50, self.pump)

    def set_state(self, kind, title, detail=""):
        self.ui.put(("state", kind, title, detail))

    def _apply_state(self, kind, title, detail):
        self.state_card.configure(fg_color=STATE_COLORS[kind])
        self.state_icon.configure(text=STATE_ICONS[kind])
        self.state_label.configure(text=title)
        self.detail_label.configure(text=detail)
        try:
            self.tray.icon = make_icon(STATE_COLORS[kind])
            self.tray.title = f"{APP_NAME}: {title}"
        except Exception:
            pass

    def _overlay(self, on):
        if on and self.cfg["overlay"]:
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            self.overlay.geometry(f"+{sw - 190}+{sh - 120}")
            self.overlay.deiconify()
        else:
            self.overlay.withdraw()

    def beep(self, freq, ms):
        if self.cfg["sound"]:
            threading.Thread(target=winsound.Beep, args=(freq, ms), daemon=True).start()

    def hide(self):
        self.root.withdraw()

    def quit(self):
        log("종료")
        self.stop_flag.set()
        try:
            self.tray.stop()
        except Exception:
            pass
        self.root.destroy()

    # ── 설정 처리 ──
    def reload_mics(self):
        if self.active:
            return
        refresh_devices()
        names = [DEFAULT_MIC] + list_mics()
        self.mic_box.configure(values=names)
        if self.mic_var.get() not in names:
            self.mic_var.set(DEFAULT_MIC)
        try:
            cur = full_name(sd.query_devices(kind="input")["name"])
        except Exception:
            cur = "없음"
        self.default_mic = cur if self.mic_var.get() == DEFAULT_MIC else self.mic_var.get()
        if self.preview:
            return
        log(f"마이크 목록 {len(names) - 1}개, 기본={cur}")

    def on_mic(self, _=None):
        self.cfg["mic"] = self.mic_var.get()
        save_config(self.cfg)
        self.reload_mics()
        log(f"마이크 변경: {self.cfg['mic']}")

    def on_silence(self, _=None):
        self.cfg["silence"] = self.sil_opts[self.sil_var.get()]
        save_config(self.cfg)
        log(f"자동 멈춤: {self.sil_var.get()}")

    def on_engine(self, _=None):
        kind = next(k for k, v in ENGINE_LABELS.items() if v == self.engine_var.get())
        if kind == self.cfg["engine"] and self.engine.kind == kind:
            return
        self.cfg["engine"] = kind
        save_config(self.cfg)
        log(f"엔진 변경: {kind}")
        self.engine.load(kind)

    def on_hotwords(self):
        self.cfg["hotwords"] = self.hot_entry.get().strip()
        save_config(self.cfg)
        self.hot_btn.configure(text="저장됨")
        self.root.after(1500, lambda: self.hot_btn.configure(text="저장"))
        log(f"자주 쓰는 단어: {self.cfg['hotwords']}")

    def bind_hotkey(self):
        if self.hotkey_handle is not None:
            try:
                keyboard.remove_hotkey(self.hotkey_handle)
            except Exception:
                pass
        self.hotkey_handle = keyboard.add_hotkey(self.cfg["hotkey"], self.toggle, suppress=True)

    def capture_hotkey(self):
        if self.capturing or self.active:
            return
        self.capturing = True
        self.hotkey_btn.configure(text="키를 누르세요…")

        def wait_key():
            try:
                keyboard.remove_hotkey(self.hotkey_handle)
                self.hotkey_handle = None
                combo = keyboard.read_hotkey(suppress=False)
                if combo in ("esc", "enter", "space"):
                    log(f"단축키로 못 쓰는 키: {combo}")
                else:
                    self.cfg["hotkey"] = combo
                    save_config(self.cfg)
                    log(f"단축키 변경: {combo}")
            finally:
                self.bind_hotkey()
                self.capturing = False
                self.ui.put(("hotkey", self.cfg["hotkey"].upper()))
                self.set_state("idle", "대기 중", f"{self.cfg['hotkey'].upper()} 누르고 말하면 바로 전송돼요")
        threading.Thread(target=wait_key, daemon=True).start()

    # ── 마이크 테스트: 5초 동안 음량만 보여 줌(보내지 않음) ──
    def mic_test(self):
        with self.lock:
            if self.active:
                return
            self.active = True
            self.testing = True
        self.stop_flag.clear()
        threading.Thread(target=self._mic_test, daemon=True).start()

    def _mic_test(self):
        try:
            refresh_devices()
            dev = resolve_mic(self.mic_var.get())
            name = mic_label(dev)
            self.set_state("busy", "마이크 테스트 중", f"{name}\n말해 보세요 (5초)")
            peak = 0.0
            with sd.InputStream(samplerate=RATE, channels=1, dtype="int16", device=dev, blocksize=800) as s:
                t0 = time.time()
                while time.time() - t0 < 5 and not self.stop_flag.is_set():
                    d, _ = s.read(800)
                    rms = float(np.sqrt(np.mean((d.astype(np.float32) / 32768) ** 2)))
                    peak = max(peak, rms)
                    self.ui.put(("level", rms))
            self.ui.put(("level", 0.0))
            if peak < self.cfg["min_level"]:
                self.set_state("err", "소리가 안 잡혀요", f"{name}\n음소거·연결을 확인하거나 다른 마이크를 골라 주세요")
            else:
                self.set_state("ok", "마이크 정상", f"{name}\n최대 음량 {peak:.3f}")
            log(f"마이크 테스트 {name} 최대 {peak:.3f}")
        except Exception as e:
            log(f"마이크 테스트 오류: {e}")
            self.set_state("err", "마이크 오류", str(e)[:120])
        finally:
            self.active = False
            self.testing = False

    # ── 녹음 → 받아쓰기 → 전송 ──
    def toggle(self):
        if self.capturing:
            return
        with self.lock:
            if self.active:
                if not self.testing:
                    self.stop_flag.set()
                return
            self.active = True
        self.stop_flag.clear()
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        try:
            self._run()
        except Exception as e:
            log(f"오류: {e}")
            self.beep(300, 400)
            self.set_state("err", "오류", str(e)[:120])
        finally:
            self.ui.put(("overlay", False))
            self.ui.put(("level", 0.0))
            self.active = False

    def _run(self):
        c = self.cfg
        key = c["hotkey"].upper()
        refresh_devices()  # 헤드셋 껐다 켰어도 다시 잡기
        dev = resolve_mic(self.mic_var.get())
        name = mic_label(dev)
        self.beep(880, 120)
        self.ui.put(("overlay", True))
        self.set_state("rec", "녹음 중", f"{name}\n" + (f"말 끝나면 자동으로 보내요 ({key} 다시 눌러도 됨)" if c["silence"] > 0
                                                       else f"다 말하면 {key}를 다시 누르세요"))
        log(f"녹음 시작 ({name})")

        q = queue.Queue()
        chunks = []
        with sd.InputStream(samplerate=RATE, channels=1, dtype="int16", device=dev, blocksize=800,
                            callback=lambda d, *_: q.put(d.copy())):
            t0 = time.time()
            noise = []
            spoke = False
            last_voice = t0
            peak = 0.0
            while not self.stop_flag.is_set():
                try:
                    d = q.get(timeout=0.2)
                except queue.Empty:
                    continue
                chunks.append(d)
                rms = float(np.sqrt(np.mean((d.astype(np.float32) / 32768) ** 2)))
                peak = max(peak, rms)
                self.ui.put(("level", rms))
                now = time.time()
                noise.append(rms)
                if now - t0 < 0.5:
                    continue
                # 주변 소음 = 지금까지 음량의 하위 20% (처음부터 말해도 소음을 크게 잡지 않게)
                floor = float(np.percentile(noise, 20))
                if rms > max(floor * 2.5, c["min_level"]):
                    spoke = True
                    last_voice = now
                if spoke and c["silence"] > 0 and now - last_voice > c["silence"]:
                    break
                if not spoke and now - t0 > c["no_speech"]:
                    log(f"말소리 없음, 취소 (최대 음량 {peak:.3f})")
                    self.beep(400, 200)
                    self.set_state("err", "소리가 안 잡혔어요",
                                   f"{name}\n최대 음량 {peak:.3f}. 마이크 테스트로 확인해 주세요")
                    return
                if now - t0 > c["max_sec"]:
                    break
        self.ui.put(("overlay", False))
        self.beep(660, 120)
        if noise:
            log(f"음량 하위20% {np.percentile(noise, 20):.4f} 중간 {np.median(noise):.4f} 최대 {peak:.4f}")
        pcm = np.concatenate(chunks).reshape(-1)
        secs = len(pcm) / RATE
        save_last(pcm)

        self.set_state("busy", "글자로 바꾸는 중", f"{secs:.1f}초 녹음 · {self.engine.status}")
        t1 = time.time()
        text = self.engine.transcribe(pcm, c["hotwords"])
        took = time.time() - t1
        engine = ENGINE_LABELS.get(self.engine.kind, "?")
        log(f"변환 {took:.1f}초 [{engine}]: {text}")
        if not text:
            self.beep(400, 200)
            self.set_state("err", "받아쓴 글자가 없어요", "다시 말해 주세요")
            return
        exe, sent = deliver(text, c["auto_send"])
        how = "전송" if sent else "입력창에 넣음"
        log(f"{how} (앞 창: {exe})")
        self.ui.put(("sent", f"{datetime.now():%H:%M}  {text}"))
        self.set_state("ok", "보냈어요" if sent else "입력창에 넣었어요",
                       f"{secs:.1f}초 녹음 → {engine} 모델로 {took:.1f}초 만에 받아씀" if sent
                       else f"앞 창이 디스코드가 아니라 엔터는 안 쳤어요 ({exe})")


def bring_to_front():
    """이미 켜져 있으면(트레이에 숨어 있어도) 그 창을 앞으로 꺼낸다."""
    u = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(h, _):
        b = ctypes.create_unicode_buffer(256)
        u.InternalGetWindowText(h, b, 256)  # 다른 창에 메시지를 안 보내서 멈춘 창이 있어도 안 걸림
        r = wt.RECT()
        u.GetWindowRect(h, ctypes.byref(r))
        if b.value == APP_NAME and r.right - r.left > 300:
            found.append(h)
        return True

    u.EnumWindows(cb, 0)
    for h in found:
        u.ShowWindowAsync(h, 9)  # SW_RESTORE
        u.SetForegroundWindow(h)


def single_instance():
    global _MUTEX
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.restype = wt.HANDLE
    _MUTEX = k32.CreateMutexW(None, False, "Local\\jarvis-admiral")
    return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS


if __name__ == "__main__":
    if "--preview" in sys.argv:
        App(preview=sys.argv[sys.argv.index("--preview") + 1]).root.mainloop()
        sys.exit(0)
    if not single_instance():
        t = threading.Thread(target=bring_to_front, daemon=True)
        t.start()
        t.join(3)
        os._exit(0)
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("jongpal.admiral")
    App().root.mainloop()
