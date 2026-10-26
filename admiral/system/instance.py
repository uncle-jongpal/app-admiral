"""한 번만 실행. 이미 켜져 있으면 그 창을 앞으로 꺼내고 새로 켠 쪽은 끝낸다."""
import ctypes
import ctypes.wintypes as wt
import os
import threading

_MUTEX = None


def acquire(name="Local\\jarvis-admiral"):
    global _MUTEX
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.restype = wt.HANDLE
    _MUTEX = k32.CreateMutexW(None, False, name)
    return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS


def bring_to_front(title):
    u = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(h, _):
        b = ctypes.create_unicode_buffer(256)
        u.InternalGetWindowText(h, b, 256)  # 다른 창에 메시지를 안 보내서 멈춘 창이 있어도 안 걸림
        r = wt.RECT()
        u.GetWindowRect(h, ctypes.byref(r))
        if b.value == title and r.right - r.left > 300:
            found.append(h)
        return True

    u.EnumWindows(cb, 0)
    for h in found:
        u.ShowWindowAsync(h, 9)  # SW_RESTORE
        u.SetForegroundWindow(h)


def exit_if_running(title):
    if acquire():
        return
    t = threading.Thread(target=bring_to_front, args=(title,), daemon=True)
    t.start()
    t.join(3)
    os._exit(0)


def set_app_id(app_id="jongpal.admiral"):
    """작업 표시줄에서 파이썬이 아닌 Admiral 로 묶이게."""
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass
