"""윈도우 없이 돌아가는 핵심 부품 확인: python -m pytest tests"""
import json

import numpy as np

from admiral.core.bus import Bus
from admiral.core.config import Config
from admiral.core.stt import normalize


def test_config_save_and_reload(tmp_path):
    p = tmp_path / "config.json"
    c = Config(p)
    c.set("hotkey", "f8")
    assert Config(p)["hotkey"] == "f8"
    assert json.loads(p.read_text(encoding="utf-8"))["hotkey"] == "f8"
    assert not (tmp_path / "config.json.tmp").exists()


def test_config_broken_file_falls_back_to_defaults(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("{깨진", encoding="utf-8")
    assert Config(p)["hotkey"] == "f9"


def test_bus_handler_error_does_not_stop_others():
    b, got = Bus(), []
    b.on("x", lambda: 1 / 0)
    b.on("x", lambda: got.append("ok"))
    b.post("x")
    b.pump()
    assert got == ["ok"]


def test_normalize_boosts_quiet_audio_but_caps_gain():
    t = np.linspace(0, 100, 16000)
    medium = (np.sin(t) * 3000).astype(np.int16)  # 최대 약 0.09 → 0.5 근처까지 키움
    assert 0.45 < np.abs(normalize(medium)).max() <= 0.51
    tiny = (np.sin(t) * 300).astype(np.int16)     # 최대 약 0.009 → 20배 상한에 걸림
    assert abs(np.abs(normalize(tiny)).max() - 300 / 32768 * 20) < 0.01
    assert np.abs(normalize(np.zeros(16000, dtype=np.int16))).max() == 0
