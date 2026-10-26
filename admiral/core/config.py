"""설정(config.json). 여러 스레드에서 읽고, 저장은 임시 파일에 쓴 뒤 바꿔치기(도중에 꺼져도 안 깨짐)."""
import json
import os
import threading

from .log import log
from .paths import CONFIG_PATH

DEFAULT_MIC = "윈도우 기본 마이크"
DEFAULTS = {
    # 음성 전송
    "mic": DEFAULT_MIC, "hotkey": "f9", "auto_send": True, "silence": 3.0, "no_speech": 10.0,
    "max_sec": 120.0, "min_level": 0.004, "sound": True, "overlay": True,
    # 받아쓰기
    "engine": "gpu_acc", "hotwords": "쫑팔, 자비스, 트론, 타스, 사만다, 베이맥스, 프라이데이",
}


class Config:
    def __init__(self, path=CONFIG_PATH, defaults=DEFAULTS):
        self.path = path
        self._lock = threading.Lock()
        self._d = dict(defaults)
        try:
            self._d.update(json.loads(path.read_text(encoding="utf-8")))
        except FileNotFoundError:
            pass
        except Exception as e:
            log(f"설정 파일을 못 읽어 기본값으로 시작: {e}")

    def __getitem__(self, key):
        with self._lock:
            return self._d[key]

    def get(self, key, default=None):
        with self._lock:
            return self._d.get(key, default)

    def set(self, key, value):
        with self._lock:
            if self._d.get(key) == value:
                return
            self._d[key] = value
            self._save()
        log(f"설정 {key} = {value}")

    def _save(self):
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self._d, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)
