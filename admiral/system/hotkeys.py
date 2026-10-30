"""전역 단축키 관리.

안정화: 윈도우가 절전·잠금에서 돌아오면 키보드 후킹이 풀려 단축키가 안 먹는 경우가 있다.
watch() 를 주기적으로 부르면, 시계가 크게 건너뛴 것(=잠들었다 깬 것)을 보고 단축키를 다시 건다.
"""
import time

import keyboard

from ..core.log import log


class Hotkeys:
    def __init__(self):
        self._items = {}   # 이름 → (조합, 콜백)
        self._handles = {}
        self._last_tick = time.time()
        self.paused = False

    def register(self, name, combo, callback):
        self._items[name] = (combo, callback)
        self._bind(name)

    def unregister(self, name):
        self._unbind(name)
        self._items.pop(name, None)

    def change(self, name, combo):
        _, cb = self._items[name]
        self._unbind(name)
        self._items[name] = (combo, cb)
        self._bind(name)

    def combo(self, name):
        return self._items[name][0]

    def _bind(self, name):
        combo, cb = self._items[name]
        self._handles[name] = keyboard.add_hotkey(combo, lambda: None if self.paused else cb(), suppress=True)

    def _unbind(self, name):
        h = self._handles.pop(name, None)
        if h is not None:
            try:
                keyboard.remove_hotkey(h)
            except Exception:
                pass

    def rebind_all(self, why):
        log(f"단축키 다시 걸기 ({why})")
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        self._handles.clear()
        for name in list(self._items):
            self._bind(name)

    def watch(self):
        now = time.time()
        if now - self._last_tick > 30:  # 몇 초마다 불리는데 30초 넘게 비었으면 잠들었다 깬 것
            self.rebind_all(f"절전에서 돌아옴, {now - self._last_tick:.0f}초 공백")
        self._last_tick = now

    def read_new_combo(self):
        """다음에 누르는 키 조합을 돌려준다(단축키 바꾸기용). 그동안 기존 단축키는 잠시 멈춤."""
        self.paused = True
        try:
            return keyboard.read_hotkey(suppress=False)
        finally:
            self.paused = False
