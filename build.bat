@echo off
set P=C:\path\to\admiral
set UV_CACHE_DIR=%P%\.uv-cache
set UV_PYTHON_INSTALL_DIR=%P%\.uv-python
cd /d %P%
tools\uv.exe pip install --python .venv\Scripts\python.exe pyinstaller
.venv\Scripts\pyinstaller.exe --noconfirm --clean --windowed --name Admiral --icon %P%\admiral.ico --version-file %P%\version.txt ^
  --workpath %P%\tmp\build --distpath %P%\dist --specpath %P%\tmp ^
  --collect-data faster_whisper --collect-binaries ctranslate2 --collect-data customtkinter ^
  --collect-binaries nvidia.cublas --collect-binaries nvidia.cudnn --collect-binaries nvidia.cuda_nvrtc ^
  --hidden-import pystray._win32 %P%\admiral.py
