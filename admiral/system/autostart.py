"""윈도우 로그온 시 자동 실행(작업 스케줄러 'admiral', 대화형 /it 로 등록 → 암호 필요 없음)."""
import subprocess
import sys
from pathlib import Path

from ..core.log import log
from ..core.paths import FROZEN

TASK_NAME = "admiral"


def _schtasks(*args):
    return subprocess.run(["schtasks", *args], capture_output=True, creationflags=0x08000000)


def enabled():
    return _schtasks("/query", "/tn", TASK_NAME).returncode == 0


def set_enabled(on):
    if on:
        if FROZEN:
            target = f'"{sys.executable}"'
        else:
            target = f'"{sys.executable}" "{Path(sys.argv[0]).resolve()}"'
        r = _schtasks("/create", "/tn", TASK_NAME, "/sc", "onlogon", "/it", "/rl", "limited", "/tr", target, "/f")
    else:
        r = _schtasks("/delete", "/tn", TASK_NAME, "/f")
    log(f"자동 실행 {'켬' if on else '끔'} (결과 {r.returncode})")
    return r.returncode == 0
