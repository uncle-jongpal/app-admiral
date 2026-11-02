# Admiral

에이전트 함대(fleet)를 지휘하는 윈도우 데스크톱 도구. 첫 기능은 **음성 전송**이다.

디스코드 PC 앱에는 음성 메시지가 없다. 단축키(기본 F9)를 누르고 말하면 Admiral이 받아쓴 다음, 앞에 있는 입력창에 붙여 넣는다. 앞 창이 디스코드면 엔터까지 쳐서 바로 보낸다. 키보드로 직접 친 것과 같아서 내 계정 메시지로 나가고, 에이전트들이 평소처럼 받는다(봇·웹후크 메시지는 에이전트가 무시함).

## 기능

- **음성 전송**: 단축키 → 녹음 → 받아쓰기 → 붙여넣기(+디스코드면 엔터)
  - 말이 끝나고 정해진 시간(2·3·5초) 동안 조용하면 자동으로 멈춘다. 끌 수도 있다.
  - 녹음 중에는 화면 오른쪽 아래에 표시가 뜬다. 효과음도 낸다.
  - 녹음할 때마다 마이크 목록을 새로 읽는다. 헤드셋을 껐다 켜도 다시 잡는다.
- **받아쓰기 엔진**(설정에서 선택)
  - 정확(기본): `large-v3`(int8_float16). 8초 음성 약 1.5초. 그래픽카드 메모리 약 2.2GB.
  - 빠름: `large-v3-turbo`(float16). 8초 음성 약 0.4초. 그래픽카드 메모리 약 2.1GB.
  - CPU: `medium`(int8). 게임에 영향이 없다. 말한 길이만큼 걸린다.
  - 그래픽카드 모델을 못 올리면 CPU로 자동으로 바뀐다. 받아쓰기 중 그래픽카드 오류가 나면 모델을 다시 올려 한 번 더 시도한다.
  - 작은 소리는 받아쓰기 전에 자동으로 키운다(최대 20배).
  - 자주 쓰는 단어(이름·용어)를 등록하면 그 단어를 더 잘 알아듣는다.
- 트레이 상주(창을 닫으면 숨김), 윈도우 로그온 시 자동 실행, 한 번만 실행(다시 켜면 기존 창을 앞으로 꺼냄)

## 구조

```
run.py                     실행 진입점(PyInstaller도 이 파일로 묶음)
admiral/
  app.py                   조립: 설정·버스·엔진·단축키·창·트레이를 만들고 기능을 붙임
  core/                    뼈대
    paths.py               경로(실행 파일로 돌아도 설정·기록·모델은 프로젝트 폴더), CUDA DLL 준비
    log.py                 하루 단위 기록, 14일 지난 기록 정리, 처리 안 된 오류 기록
    config.py              config.json(여러 스레드 안전, 임시 파일에 쓴 뒤 바꿔치기)
    bus.py                 작업 스레드 → 화면 이벤트 전달(처리기 하나가 실패해도 나머지는 계속)
    stt.py                 받아쓰기 엔진(빠름/정확/CPU, 그래픽카드 오류 시 다시 올리기 → CPU)
  system/                  윈도우 연동
    hotkeys.py             전역 단축키(절전에서 돌아오면 다시 걸기)
    windows.py             앞 창 확인, 붙여넣기(클립보드 다시 시도, 원래 내용 되돌림)
    autostart.py           로그온 자동 실행(작업 스케줄러)
    instance.py            한 번만 실행, 이미 켜져 있으면 창을 앞으로
  audio/
    devices.py             마이크 목록(WASAPI 전체 이름 표시, MME로 녹음)
    recorder.py            녹음(말소리 판정, 자동 멈춤, 마이크 끊김 처리), 마이크 테스트
  ui/                      공통 화면: theme(색·아이콘), widgets(카드·설정 줄), shell(메인 창), tray, overlay
  features/                왼쪽 메뉴 기능. 기능 하나 = 폴더 하나
    base.py                Feature 뼈대(build_page / build_settings / start / stop)
    voice/                 음성 전송(controller=흐름, feature=화면·설정)
    settings/              설정 화면(각 기능의 build_settings를 모아서 붙임)
tests/                     윈도우 없이 도는 핵심 시험(pytest)
```

### 새 기능 붙이기

1. `admiral/features/<이름>/`에 `Feature`를 상속한 클래스를 만든다. 화면이 있으면 `page_title`과 `page_icon`을 정하고 `build_page`를 채운다. 설정이 있으면 `build_settings`를 채운다.
2. `admiral/features/__init__.py`의 `FEATURES` 목록에 넣는다.
3. 작업 스레드에서는 화면을 직접 건드리지 않는다. `app.bus.post(...)`로 보내고, 화면 쪽에서 `app.bus.on(...)`으로 받는다.

### 파일

| 파일 | 역할 |
|---|---|
| `pyproject.toml`, `uv.lock` | 의존성(uv). cuBLAS·cuDNN은 pip 패키지로 받음. 개발용 pytest·pyinstaller는 `dev` 그룹 |
| `setup.bat` | 프로젝트 폴더 안에 파이썬·가상환경 설치(`tools\uv.exe` 필요, 사용자 폴더를 더럽히지 않음) |
| `build.bat` | PyInstaller로 `dist\Admiral\Admiral.exe` 생성 |
| `install.ps1` | 처음 한 번: 로그온 자동 실행 등록, 바탕화면·시작 메뉴 바로가기 생성, 실행 |
| `restart.ps1` | 다시 켜기 |
| `deploy.sh` | 개발 서버 → 작업PC 배포(소스 복사 → 시험 → 사용 중이 아니면 끄고 → 빌드 → 실행). 대상 PC·폴더는 `deploy.env`(깃에 안 올림, `deploy.env.example` 참고) |
| `version.txt` | 실행 파일 속성(이름·버전) |

실행 중에 생기는 것(깃에 안 올림): `config.json`(설정), `logs\admiral-날짜.log`(기록), `logs\last.wav`(마지막 녹음 1개), `models\`(받아쓰기 모델 캐시), `.venv\`, `dist\`.

## 설치(작업PC)

```bat
:: 1) 아무 폴더에 소스를 받고 tools\uv.exe 를 넣는다(설치 위치는 bat 파일이 있는 폴더로 자동)
:: 2) 환경 설치 → 빌드 → 설치
setup.bat
build.bat
powershell -ExecutionPolicy Bypass -File install.ps1
```

## 업데이트

개발 서버에서 고치고 커밋한 다음 `./deploy.sh`를 실행한다. 녹음이나 변환이 진행 중이면 끝날 때까지 기다렸다가 교체한다.

## 화면 확인

`run.py --preview voice|settings|settings-bottom`를 실행하면 단축키·모델·트레이 없이 창만 띄웠다가 8초 뒤에 닫힌다. 화면을 고친 뒤 캡처해서 확인할 때 쓴다.

## 알아 둘 것

- 실행 파일이 켜져 있으면 빌드가 실패한다(파일 잠김). `deploy.sh`가 먼저 끈다.
- 윈도우 MME 장치 이름은 31자에서 잘린다. 화면에는 WASAPI 장치의 전체 이름을 보여 주고, 녹음은 MME로 한다(16kHz 변환을 윈도우가 해 준다).
- `faster-whisper`에 파일 경로를 넘기면 `av` 버전 오류가 나서, numpy 배열로 넘긴다.
- 오른쪽 Alt는 한글 키보드에서 한/영 키라 단축키로 쓰지 않는다.
