"""작업 표시줄 오른쪽 아이콘. 상태 색을 보여 주고, 열기·종료 메뉴."""
import threading

import pystray

from ..core.log import log
from .theme import STATE_COLORS, make_icon


class Tray:
    def __init__(self, title, on_open, on_quit):
        self._title = title
        self.icon = pystray.Icon("admiral", make_icon(STATE_COLORS["idle"]), title, menu=pystray.Menu(
            pystray.MenuItem("열기", lambda: on_open(), default=True),
            pystray.MenuItem("종료", lambda: on_quit())))

    def start(self):
        threading.Thread(target=self.icon.run, name="tray", daemon=True).start()

    def set_state(self, kind, text):
        try:
            self.icon.icon = make_icon(STATE_COLORS[kind])
            self.icon.title = f"{self._title}: {text}"
        except Exception as e:
            log(f"트레이 갱신 실패: {e}")

    def stop(self):
        try:
            self.icon.stop()
        except Exception:
            pass
