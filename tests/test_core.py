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


def test_voice_gate_keeps_quiet_speech():
    """작업PC 실제 녹음 음량(0.05초 블록): 0.001~0.003으로 작게 말하는 구간을 말소리로 쳐야 함."""
    from admiral.audio.recorder import RecordOptions, VoiceGate

    quiet_room = [0.0002, 0.0001, 0.0003, 0.0002] * 3   # 0.6초 조용
    loud = [0.0051, 0.0062, 0.0031, 0.0047] * 5          # 1초 크게
    soft = [0.0014, 0.0020, 0.0017, 0.0005, 0.0013, 0.0031, 0.0015] * 9  # 약 3.2초 작게 계속 말함
    gate = VoiceGate(RecordOptions(silence=3.0))
    t = 0.0
    for v in quiet_room + loud + soft:
        assert gate.feed(v, t) is None, f"{t:.2f}초에 말하는 도중 끊김"
        t += 0.05
    res = None
    for _ in range(int(3.5 / 0.05)):  # 말 끝나고 조용히 3.5초
        res = res or gate.feed(0.0002, t)
        t += 0.05
    assert res == "stop"


def test_voice_gate_room_noise_is_not_speech():
    from admiral.audio.recorder import RecordOptions, VoiceGate

    gate = VoiceGate(RecordOptions(no_speech=2.0))
    t, res = 0.0, None
    for i in range(60):
        res = res or gate.feed([0.0002, 0.0004, 0.0001, 0.0006][i % 4], t)
        t += 0.05
    assert res == "nospeech"


HOTWORDS = "쫑팔, 자비스, 트론, 타스, 사만다, 베이맥스, 프라이데이"


def test_clean_drops_hotword_list_echo():
    """2026-10-28 실제 결과: 힌트 단어 목록을 그대로 읽어 끝에 붙임."""
    from admiral.core.stt import clean

    text, removed = clean("메모리 남겨놓는 게 아니라 이거 내가 훅으로 걸어놓은 적 없어 자비스, 트론, 타스, 사만다, 베이맥스, 프라이데이", HOTWORDS)
    assert text == "메모리 남겨놓는 게 아니라 이거 내가 훅으로 걸어놓은 적 없어"
    assert removed == ["자비스, 트론, 타스, 사만다, 베이맥스, 프라이데이"]


def test_clean_drops_trailing_subtitle_phrase():
    from admiral.core.stt import clean

    text, removed = clean("에이스가 이거 왜 이렇게 만든 건지 설명해 자막 제공 및 자막 제공 및 광고를 포함하고 있습니다.", HOTWORDS)
    assert text == "에이스가 이거 왜 이렇게 만든 건지 설명해"
    assert removed


def test_clean_keeps_real_speech():
    from admiral.core.stt import clean

    for s in ["베이맥스한테 답하라고 그래", "자비스, 트론, 타스 셋이 같이 확인해", "자비스랑 트론한테 물어봐"]:
        assert clean(s, HOTWORDS) == (s, [])
