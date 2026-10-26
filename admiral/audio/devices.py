"""마이크 목록. 녹음은 MME(윈도우가 16kHz 로 바꿔 줌)로 하고, 이름은 WASAPI 쪽 전체 이름으로 보여 준다
(MME 이름은 31자에서 잘림)."""
import sounddevice as sd

from ..core.config import DEFAULT_MIC
from ..core.log import log


def refresh():
    """PortAudio 를 다시 초기화해 새로 꽂거나 켠 장치를 읽는다(헤드셋 껐다 켜도 다시 잡힘)."""
    try:
        sd._terminate()
    except Exception:
        pass
    sd._initialize()


def _hostapi(name):
    return next((i for i, h in enumerate(sd.query_hostapis()) if name in h["name"]), None)


def full_name(short):
    wasapi = _hostapi("WASAPI")
    for d in sd.query_devices():
        if d["hostapi"] == wasapi and d["max_input_channels"] > 0 and d["name"].startswith(short):
            return d["name"]
    return short


def list_mics():
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


def resolve(name):
    """고른 마이크 이름 → 녹음 장치 번호(None = 윈도우 기본)."""
    if not name or name == DEFAULT_MIC:
        return None
    mme = _hostapi("MME")
    for i, d in enumerate(sd.query_devices()):
        if d["hostapi"] == mme and d["max_input_channels"] > 0 and name.startswith(d["name"]):
            return i
    log(f"마이크 '{name}' 없음 → 윈도우 기본 마이크 사용")
    return None


def label(dev):
    try:
        return full_name(sd.query_devices(dev if dev is not None else sd.default.device[0])["name"])
    except Exception:
        return "마이크 없음"


def default_name():
    try:
        return full_name(sd.query_devices(kind="input")["name"])
    except Exception:
        return "없음"
