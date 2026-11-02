"""Admiral — 형이 에이전트 함대(fleet)를 지휘하는 윈도우 데스크톱 도구.

구조
  core/      앱 뼈대: 경로·기록·설정·이벤트 버스·받아쓰기 엔진
  system/    윈도우 연동: 단축키·자동 실행·한 번만 실행·앞 창 확인
  audio/     마이크 목록·녹음·소리 가공
  ui/        공통 화면: 테마·부품·메인 창·트레이·녹음 표시
  features/  왼쪽 메뉴에 붙는 기능들. 기능 하나 = 폴더 하나(features/__init__.py 에 등록)
"""
APP_NAME = "Admiral"
APP_VERSION = "1.2.5"
