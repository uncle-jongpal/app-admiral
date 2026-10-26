"""앞에 있는 창 확인, 글자 붙여넣기."""
import ctypes
import ctypes.wintypes as wt
import time

import keyboard
import psutil
import pyperclip

from ..core.log import log

DISCORD_APPS = {"discord.exe", "discordptb.exe", "discordcanary.exe"}


def foreground_exe():
    u = ctypes.windll.user32
    pid = wt.DWORD()
    u.GetWindowThreadProcessId(u.GetForegroundWindow(), ctypes.byref(pid))
    try:
        return psutil.Process(pid.value).name().lower()
    except Exception:
        return ""


def _copy(text, tries=5):
    # 다른 프로그램이 클립보드를 잡고 있으면 잠깐 실패할 수 있어 몇 번 다시 시도
    for i in range(tries):
        try:
            pyperclip.copy(text)
            return True
        except Exception as e:
            if i == tries - 1:
                log(f"클립보드 쓰기 실패: {e}")
            time.sleep(0.1)
    return False


def paste_text(text, press_enter_in=DISCORD_APPS, auto_send=True):
    """앞 창 입력칸에 붙여넣고, 그 창이 디스코드면 엔터까지. (앞 창 이름, 엔터 쳤는지) 반환.
    원래 클립보드 내용은 되돌려 놓는다."""
    exe = foreground_exe()
    try:
        old = pyperclip.paste()
    except Exception:
        old = None
    if not _copy(text):
        raise RuntimeError("클립보드를 못 써서 붙여넣지 못했어요")
    time.sleep(0.05)
    keyboard.send("ctrl+v")
    sent = auto_send and exe in press_enter_in
    if sent:
        time.sleep(0.15)
        keyboard.send("enter")
    time.sleep(0.3)
    if old is not None:
        _copy(old, tries=2)
    return exe, sent
