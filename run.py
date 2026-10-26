"""Admiral 실행 진입점(PyInstaller 도 이 파일로 묶는다)."""
from admiral.core import paths  # noqa: F401  경로·CUDA DLL 준비를 가장 먼저
from admiral.app import main

if __name__ == "__main__":
    main()
