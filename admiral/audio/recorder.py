"""녹음. 말소리 판정·자동 멈춤·마이크 끊김 처리."""
import queue
import time
import wave
from dataclasses import dataclass

import numpy as np
import sounddevice as sd

from ..core.log import log
from ..core.paths import LOG_DIR

RATE = 16000
BLOCK = 800  # 0.05초


def rms(block):
    return float(np.sqrt(np.mean((block.astype(np.float32) / 32768) ** 2)))


class NoSpeech(Exception):
    def __init__(self, peak):
        super().__init__(f"말소리 없음(최대 음량 {peak:.3f})")
        self.peak = peak


class MicError(Exception):
    pass


@dataclass
class RecordOptions:
    silence: float = 3.0      # 말 끝나고 이만큼 조용하면 멈춤(0 = 자동 멈춤 끔)
    no_speech: float = 10.0   # 이 시간 동안 말이 없으면 취소
    max_sec: float = 120.0
    min_level: float = 0.004  # 녹음 전체가 이보다 작으면 소리가 안 잡힌 것(마이크 테스트용)
    voice_level: float = 0.0009  # 블록 하나가 이보다 크면 말소리일 수 있음(작게 말해도 0.001~0.003)


class VoiceGate:
    """블록 음량을 받아 말하는 중인지 판정. 말소리 기준 = max(주변 소음 × 3, voice_level).

    예전엔 기준이 min_level(0.004)이라 작게 말한 구간이 조용한 걸로 잡혀,
    마지막으로 크게 말한 순간부터 멈춤 시간을 세서 말하는 도중에 끊겼다.
    """

    def __init__(self, opts):
        self.opts = opts
        self.levels = []
        self.spoke = False
        self.t0 = None
        self.last_voice = None

    def feed(self, v, now):
        """'stop' = 자동 멈춤, 'nospeech' = 말이 없어 취소, None = 계속."""
        if self.t0 is None:
            self.t0 = self.last_voice = now
        self.levels.append(v)
        if now - self.t0 < 0.5:
            return None
        # 주변 소음 = 지금까지 음량의 하위 20% (처음부터 말해도 소음을 크게 잡지 않게)
        floor = float(np.percentile(self.levels, 20))
        if v > max(floor * 3, self.opts.voice_level):
            self.spoke = True
            self.last_voice = now
        if self.spoke and self.opts.silence > 0 and now - self.last_voice > self.opts.silence:
            return "stop"
        if not self.spoke and now - self.t0 > self.opts.no_speech:
            return "nospeech"
        if now - self.t0 > self.opts.max_sec:
            return "stop"
        return None


def record(dev, stop_event, opts, on_level=lambda v: None):
    """stop_event 가 켜지거나 자동 멈춤 조건이 되면 끝. int16 배열 반환."""
    q = queue.Queue()
    chunks = []
    status_err = []

    def cb(data, frames, t, status):
        if status:
            status_err.append(str(status))
        q.put(data.copy())

    try:
        stream = sd.InputStream(samplerate=RATE, channels=1, dtype="int16", device=dev, blocksize=BLOCK, callback=cb)
    except Exception as e:
        raise MicError(f"마이크를 열 수 없어요: {e}") from e

    gate = VoiceGate(opts)
    peak = 0.0
    last_data = time.time()
    with stream:
        while not stop_event.is_set():
            try:
                d = q.get(timeout=0.2)
            except queue.Empty:
                if time.time() - last_data > 2.0:  # 2초 동안 소리 데이터가 안 옴 = 마이크가 끊김
                    log("녹음 중 마이크 데이터 끊김")
                    if chunks and gate.spoke:
                        break  # 그때까지 말한 건 살린다
                    raise MicError("녹음 중에 마이크 연결이 끊겼어요")
                continue
            last_data = time.time()
            chunks.append(d)
            v = rms(d)
            peak = max(peak, v)
            on_level(v)
            res = gate.feed(v, last_data)
            if res == "nospeech":
                raise NoSpeech(peak)
            if res == "stop":
                break
    levels = gate.levels
    if status_err:
        log(f"녹음 중 장치 경고 {len(status_err)}회: {status_err[0]}")
    if levels:
        log(f"음량 하위20% {np.percentile(levels, 20):.4f} 중간 {np.median(levels):.4f} 최대 {peak:.4f}")
    if not chunks:
        raise NoSpeech(peak)
    return np.concatenate(chunks).reshape(-1)


def measure(dev, seconds, stop_event, on_level=lambda v: None):
    """마이크 테스트: seconds 동안 음량만 재서 최대값 반환."""
    peak = 0.0
    try:
        with sd.InputStream(samplerate=RATE, channels=1, dtype="int16", device=dev, blocksize=BLOCK) as s:
            t0 = time.time()
            while time.time() - t0 < seconds and not stop_event.is_set():
                d, _ = s.read(BLOCK)
                v = rms(d)
                peak = max(peak, v)
                on_level(v)
    except Exception as e:
        raise MicError(f"마이크를 열 수 없어요: {e}") from e
    return peak


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
