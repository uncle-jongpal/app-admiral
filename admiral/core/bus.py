"""이벤트 버스: 작업 스레드 → 화면(메인 스레드) 전달.
화면은 tkinter 라 메인 스레드에서만 고칠 수 있다. 다른 스레드는 post() 만 하고,
메인 창이 0.05초마다 pump() 로 꺼내서 등록된 처리기에 넘긴다."""
import queue

from .log import log_exc


class Bus:
    def __init__(self):
        self._q = queue.Queue()
        self._handlers = {}

    def on(self, kind, handler):
        self._handlers.setdefault(kind, []).append(handler)

    def post(self, kind, *args):
        self._q.put((kind, args))

    def pump(self, limit=200):
        for _ in range(limit):
            try:
                kind, args = self._q.get_nowait()
            except queue.Empty:
                return
            for h in self._handlers.get(kind, []):
                try:
                    h(*args)
                except Exception:
                    log_exc(f"화면 처리 {kind}")
