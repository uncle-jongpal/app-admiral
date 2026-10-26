"""기능 목록. 왼쪽 메뉴·설정 화면이 이 순서대로 만들어진다.
새 기능 추가: features/<이름>/ 에 Feature 를 상속한 클래스를 만들고 아래 목록에 넣는다."""
from .settings import SettingsFeature
from .voice import VoiceFeature

FEATURES = [VoiceFeature, SettingsFeature]
