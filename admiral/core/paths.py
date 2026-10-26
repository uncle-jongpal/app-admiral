r"""경로와 실행 준비. 다른 모듈보다 먼저 import 된다(run.py 맨 앞).

실행 파일(dist\Admiral\Admiral.exe)로 돌 때도 설정·기록·모델은 프로젝트 폴더에 둔다.
"""
import importlib.util
import os
import sys
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)
BASE = Path(sys.executable).resolve().parents[2] if FROZEN else Path(__file__).resolve().parents[2]
LOG_DIR = Path(os.environ.get("ADMIRAL_LOG_DIR") or BASE / "logs")  # 시험 때는 임시 폴더로
CONFIG_PATH = BASE / "config.json"
ICON_PATH = BASE / "admiral.ico"
MODEL_DIR = BASE / "models"

LOG_DIR.mkdir(exist_ok=True)
os.environ.setdefault("HF_HOME", str(MODEL_DIR))


def add_cuda_dlls():
    """pip 로 깐 cuBLAS·cuDNN DLL 을 찾게 경로 추가(받아쓰기 서버와 같은 방식)."""
    dirs = []
    roots = [Path(getattr(sys, "_MEIPASS", ""))] if FROZEN else []
    for pkg in ("nvidia.cublas", "nvidia.cudnn", "nvidia.cuda_nvrtc"):
        try:
            spec = importlib.util.find_spec(pkg)
        except Exception:
            spec = None
        if spec and spec.submodule_search_locations:
            roots.append(Path(list(spec.submodule_search_locations)[0]).parent.parent)
    for r in roots:
        for d in r.glob("nvidia/*/bin"):
            if d.is_dir() and str(d) not in dirs:
                dirs.append(str(d))
    for d in dirs:
        try:
            os.add_dll_directory(d)
        except Exception:
            pass
    if dirs:
        os.environ["PATH"] = os.pathsep.join(dirs) + os.pathsep + os.environ.get("PATH", "")


add_cuda_dlls()
