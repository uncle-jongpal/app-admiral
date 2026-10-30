"""녹음 중 Esc 취소: 아무것도 붙여넣지 않고, 취소 키는 끝나면 풀린다."""
import threading
import time

import numpy as np
import pytest

from admiral.audio import devices, recorder
from admiral.features.voice import controller as vc
from admiral.system import windows


class FakeBus:
    def __init__(self):
        self.posts = []

    def post(self, *a):
        self.posts.append(a)


class FakeHotkeys:
    def __init__(self):
        self.items = {}

    def register(self, name, combo, cb):
        self.items[name] = (combo, cb)

    def unregister(self, name):
        self.items.pop(name, None)


class FakeEngine:
    status = label = "시험"

    def transcribe(self, pcm, hotwords):
        return "시험 문장"


class FakeApp:
    def __init__(self):
        self.cfg = {"hotkey": "f9", "mic": "", "sound": False, "overlay": False, "silence": 3.0,
                    "no_speech": 10.0, "max_sec": 120.0, "min_level": 0.004, "hotwords": "", "auto_send": True}
        self.bus = FakeBus()
        self.hotkeys = FakeHotkeys()
        self.engine = FakeEngine()


@pytest.fixture
def ctrl(monkeypatch):
    monkeypatch.setattr(devices, "refresh", lambda: None)
    monkeypatch.setattr(devices, "resolve", lambda name: None)
    monkeypatch.setattr(devices, "label", lambda dev: "시험 마이크")
    monkeypatch.setattr(recorder, "save_last", lambda pcm: None)
    pasted = []
    monkeypatch.setattr(windows, "paste_text", lambda text, auto_send: pasted.append(text) or ("x.exe", True))
    c = vc.VoiceController(FakeApp())
    c.pasted = pasted
    return c


def _start(c):
    assert c._begin()
    t = threading.Thread(target=c._run_safe)
    t.start()
    for _ in range(200):
        if "voice_cancel" in c.app.hotkeys.items:
            break
        time.sleep(0.01)
    return t


def _titles(c):
    return [p[2] for p in c.app.bus.posts if p[0] == "status"]


def _rec_returns(dev, stop, opts, on_level):
    stop.wait(2)
    return np.ones(16000, dtype=np.int16)


def test_cancel_after_speaking_sends_nothing(ctrl, monkeypatch):
    monkeypatch.setattr(recorder, "record", _rec_returns)
    t = _start(ctrl)
    combo, cb = ctrl.app.hotkeys.items["voice_cancel"]
    assert combo == vc.CANCEL_KEY
    cb()  # Esc
    t.join(2)
    assert ctrl.pasted == []
    assert _titles(ctrl)[-1] == "취소했어요"
    assert "voice_cancel" not in ctrl.app.hotkeys.items
    assert not ctrl.active


def test_cancel_before_speaking_is_cancel_not_no_speech(ctrl, monkeypatch):
    def rec(dev, stop, opts, on_level):
        stop.wait(2)
        raise recorder.NoSpeech(0.0)
    monkeypatch.setattr(recorder, "record", rec)
    t = _start(ctrl)
    ctrl.app.hotkeys.items["voice_cancel"][1]()
    t.join(2)
    assert _titles(ctrl)[-1] == "취소했어요"


def test_f9_again_still_sends(ctrl, monkeypatch):
    monkeypatch.setattr(recorder, "record", _rec_returns)
    t = _start(ctrl)
    ctrl.toggle()  # F9 다시
    t.join(2)
    assert ctrl.pasted == ["시험 문장"]
    assert "voice_cancel" not in ctrl.app.hotkeys.items
