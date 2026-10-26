"""설정 화면: 다른 기능들이 내놓는 설정 카드(build_settings)를 차례로 붙이고, 맨 아래에 프로그램 설정."""
import os

from ...core.paths import LOG_DIR
from ...system import autostart
from ...ui import widgets as w
from ..base import Feature


class SettingsFeature(Feature):
    key = "settings"
    page_title = "설정"
    page_icon = "⚙"
    scrollable = True

    def build_page(self, f):
        for feat in self.app.features:
            if feat is not self:
                feat.build_settings(f)
        wrapper = self.app.shell.wrapper
        c = w.card(f, "프로그램")
        r = w.setting_row(c, "윈도우 켜질 때 자동 실행", wrapper=wrapper)
        w.switch(r, autostart.enabled(), autostart.set_enabled)
        r = w.setting_row(c, "기록 폴더", str(LOG_DIR), wrapper)
        w.button(r, "열기", lambda: os.startfile(LOG_DIR), width=60).pack()
