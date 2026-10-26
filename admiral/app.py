"""앱 조립: 설정·버스·엔진·단축키·창·트레이를 만들고 기능들을 붙인다."""
import sys

from . import APP_NAME, APP_VERSION
from .core import log as logmod
from .core.bus import Bus
from .core.config import Config
from .core.log import log
from .core.stt import Engine
from .features import FEATURES
from .system import instance
from .system.hotkeys import Hotkeys
from .ui.overlay import Overlay
from .ui.shell import Shell
from .ui.tray import Tray


class App:
    def __init__(self, preview=None):
        self.preview = preview  # 화면 확인용: 단축키·모델·트레이 없이 화면만 띄웠다가 닫힘
        self.cfg = Config()
        self.bus = Bus()
        self.engine = Engine(on_change=lambda: self.bus.post("engine"))
        self.hotkeys = Hotkeys()
        self.tray = None
        self.shell = Shell(APP_NAME if not preview else f"{APP_NAME} 미리보기")
        self.overlay = Overlay(self.shell.root)
        self.features = [F(self) for F in FEATURES]
        for feat in self.features:
            if feat.page_title:
                page = self.shell.add_page(feat.key, feat.page_title, feat.page_icon, feat.scrollable)
                feat.build_page(page)
        self.bus.on("show", self.shell.show)
        self.bus.on("quit", self.quit)
        self.shell.every(50, self.bus.pump)

    def run(self):
        root = self.shell.root
        if self.preview:
            page = self.preview.replace("-bottom", "")
            self.engine.status = "미리보기"
            self.bus.post("engine")
            self.shell.show_page(page)
            if self.preview.endswith("-bottom"):
                root.after(800, lambda: self.shell.scroll_bottom(page))
            root.after(8000, root.destroy)
            root.mainloop()
            return

        root.protocol("WM_DELETE_WINDOW", self.shell.hide)  # 닫으면 트레이로 숨김
        self.tray = Tray(APP_NAME, on_open=lambda: self.bus.post("show"), on_quit=lambda: self.bus.post("quit"))
        self.tray.start()
        self.shell.show_page(self.features[0].key)
        for feat in self.features:
            feat.start()
        self.shell.every(5000, self.hotkeys.watch)
        log(f"시작 v{APP_VERSION} (단축키 {self.cfg['hotkey'].upper()}, 엔진 {self.cfg['engine']}, 마이크 {self.cfg['mic']})")
        root.mainloop()

    def quit(self):
        log("종료")
        for feat in self.features:
            try:
                feat.stop()
            except Exception:
                logmod.log_exc(f"{feat.key} 종료")
        if self.tray:
            self.tray.stop()
        self.shell.root.destroy()


def main(argv=None):
    argv = sys.argv if argv is None else argv
    logmod.install_crash_hooks()
    if "--preview" in argv:
        App(preview=argv[argv.index("--preview") + 1]).run()
        return
    instance.exit_if_running(APP_NAME)
    instance.set_app_id()
    logmod.cleanup_old()
    App().run()
