"""받아쓰기 엔진. Admiral 안에서 모델을 계속 올려 두고 쓴다.

  빠름  large-v3-turbo / 그래픽카드 float16  (8초 음성 약 0.4초, 메모리 약 2.1GB)
  정확  large-v3 / 그래픽카드 int8_float16    (8초 음성 약 1.5초, 메모리 약 2.2GB)
  CPU   medium / int8                          (게임 영향 없음, 말한 길이만큼 걸림)

안정화
  - 그래픽카드 모델을 못 올리면 CPU 로 자동 전환
  - 받아쓰기 중 그래픽카드 오류(드라이버 재시작 등으로 연결이 깨짐, 10/25 받아쓰기 서버 장애와 같은 종류)가
    나면 모델을 다시 올리고 한 번 더 시도. 그래도 안 되면 CPU 로.
"""
import gc
import re
import threading
import time

import numpy as np

from .log import log

ENGINES = {"gpu": ("large-v3-turbo", "cuda", "float16"),
           "gpu_acc": ("large-v3", "cuda", "int8_float16"),
           "cpu": ("medium", "cpu", "int8")}
ENGINE_LABELS = {"gpu": "빠름", "gpu_acc": "정확", "cpu": "CPU"}
# 받아쓰기 한 번에 걸리는 시간(화면 안내용). 모델을 올리는 시간은 켤 때 한 번뿐이라 기록에만 남긴다.
ENGINE_SPEED = {"gpu": "보낼 때 1초 안쪽", "gpu_acc": "보낼 때 1~2초", "cpu": "보낼 때 말한 길이만큼"}


def normalize(pcm):
    """작은 소리를 키운다(마이크 입력이 작으면 비슷한 단어로 헷갈림). 최대 20배."""
    audio = pcm.astype(np.float32) / 32768
    peak = float(np.percentile(np.abs(audio), 99.9)) if len(audio) else 0.0
    if peak > 1e-4:
        audio = np.clip(audio * min(0.5 / peak, 20.0), -1.0, 1.0)
    return audio


# 말이 끝난 직후 모델이 지어내는 문장(유튜브 자막으로 학습한 흔적). 끝부분에서만 잘라 낸다.
HALLUCINATIONS = [r"자막\s*제공", r"광고를\s*포함하고\s*있습니다", r"시청\s*해\s*주셔서\s*감사합니다",
                  r"구독과\s*좋아요", r"한글\s*자막", r"자막\s*by"]
TAIL_CHARS = 80  # 끝에서 이 글자 수 안에 나온 것만 지어낸 걸로 본다


def clean(text, hotwords=""):
    """지어낸 부분을 뺀다. (남은 글, 뺀 조각 목록)

    - 끝에 자주 쓰는 단어가 쉼표로 3개 이상 이어지면 힌트를 그대로 읽은 것(문장 중간은 실제로 부른 걸 수 있어 둠)
    - 끝부분의 알려진 환각 문장
    """
    removed = []
    names = [re.escape(w.strip()) for w in hotwords.split(",") if w.strip()]
    if len(names) >= 3:
        name = "(?:" + "|".join(names) + ")"
        m = re.search(name + r"(?:\s*,\s*" + name + r"){2,}[.,!?]?\s*$", text)
        if m:
            removed.append(m.group().strip())
            text = text[:m.start()]
    while True:
        cuts = [m.start() for pat in HALLUCINATIONS for m in [re.search(pat, text)]
                if m and len(text) - m.start() <= TAIL_CHARS]
        if not cuts:
            break
        at = min(cuts)
        removed.append(text[at:].strip())
        text = text[:at]
    return re.sub(r"\s{2,}", " ", text).strip(), removed


class Engine:
    def __init__(self, on_change=lambda: None):
        self.model = None
        self.kind = None
        self.wanted = None
        self.status = "준비 전"
        self.ready = threading.Event()
        self._lock = threading.Lock()
        self._on_change = on_change

    @property
    def label(self):
        return ENGINE_LABELS.get(self.kind, "?")

    def load(self, kind):
        """다른 스레드에서 모델을 올린다(화면이 안 멈추게)."""
        if kind not in ENGINES:
            kind = "gpu_acc"
        self.wanted = kind
        threading.Thread(target=self._load, args=(kind,), name="stt-load", daemon=True).start()

    def _load(self, kind):
        with self._lock:
            self.ready.clear()
            self.model = None
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
                    self._set(f"{ENGINE_LABELS[kind]} 모델 준비됨 · {ENGINE_SPEED[kind]}")
                    log(f"받아쓰기 모델 준비 {name}/{device} ({took:.1f}초)")
                    break
                except Exception as e:
                    log(f"받아쓰기 모델 실패 {name}/{device}: {e}")
                    if kind != "cpu":
                        kind = "cpu"
                        continue
                    self.kind = None
                    self._set(f"받아쓰기 모델 실패: {str(e)[:80]}")
                    break
            self.ready.set()

    def _set(self, s):
        self.status = s
        self._on_change()

    def _run(self, audio, hotwords):
        segs, _ = self.model.transcribe(audio, language="ko", beam_size=1 if self.kind == "cpu" else 5,
                                        vad_filter=True, condition_on_previous_text=False,
                                        hotwords=hotwords or None)
        kept = []
        for seg in segs:
            # 모델 스스로 "말소리 아님"이라 보고 자신도 없는 조각 = 지어낸 것(Whisper 기본 판정 기준)
            if seg.no_speech_prob > 0.6 and seg.avg_logprob < -1.0:
                log(f"말소리 아닌 조각 버림: {seg.text.strip()}")
                continue
            kept.append(seg.text)
        text, removed = clean("".join(kept).strip(), hotwords)
        for r in removed:
            log(f"지어낸 부분 뺌: {r}")
        return text

    def transcribe(self, pcm, hotwords=""):
        self.ready.wait()
        if self.model is None:
            raise RuntimeError("받아쓰기 모델이 없어요. 설정에서 엔진을 다시 골라 주세요")
        audio = normalize(pcm)
        try:
            return self._run(audio, hotwords)
        except Exception as e:
            if self.kind == "cpu":
                raise
            # 그래픽카드 연결이 깨진 경우: 같은 모델을 다시 올려 한 번 더, 그래도 안 되면 CPU
            log(f"그래픽카드 받아쓰기 오류 → 모델 다시 올림: {e}")
            self._load(self.kind)
            if self.model is None:
                raise
            return self._run(audio, hotwords)
