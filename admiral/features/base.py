"""기능(feature) 뼈대. 새 기능은 이걸 상속해 features/<이름>/ 에 만들고 features/__init__.py 에 등록한다.

  page_title/icon 이 있으면 왼쪽 메뉴에 화면이 생긴다(build_page).
  build_settings 를 채우면 설정 화면에 그 기능의 설정 카드가 붙는다.
  start/stop 은 실제 실행 때만 불린다(미리보기 때는 안 불림).
"""


class Feature:
    key = ""
    page_title = None
    page_icon = ""
    scrollable = False

    def __init__(self, app):
        self.app = app

    def build_page(self, parent):
        pass

    def build_settings(self, parent):
        pass

    def start(self):
        pass

    def stop(self):
        pass
