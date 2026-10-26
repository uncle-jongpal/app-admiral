"""기록: logs\admiral-YYYYMMDD.log 에 하루 단위로 쌓고, 오래된 건 지운다.
예상 못 한 오류(어느 스레드든, 화면 콜백 포함)도 전부 여기에 남긴다."""
import sys
import threading
import time
import traceback
from datetime import datetime

from .paths import LOG_DIR

KEEP_DAYS = 14
_lock = threading.Lock()


def log(msg):
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    with _lock:
        try:
            print(line, flush=True)
        except Exception:
            pass  # pythonw 는 stdout 이 없음
        with open(LOG_DIR / f"admiral-{datetime.now():%Y%m%d}.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")


def log_exc(where, exc_type=None, exc=None, tb=None):
    if exc is None:
        exc_type, exc, tb = sys.exc_info()
    log(f"예상 못 한 오류 ({where}): {exc}\n" + "".join(traceback.format_exception(exc_type, exc, tb)).rstrip())


def cleanup_old(days=KEEP_DAYS):
    cutoff = time.time() - days * 86400
    for p in LOG_DIR.glob("admiral-*.log"):
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
        except Exception:
            pass


def install_crash_hooks():
    """처리 안 된 오류가 나도 프로그램이 조용히 죽지 않고 기록에 남게."""
    sys.excepthook = lambda t, e, tb: log_exc("메인", t, e, tb)
    threading.excepthook = lambda a: log_exc(f"스레드 {a.thread.name if a.thread else '?'}",
                                             a.exc_type, a.exc_value, a.exc_traceback)
