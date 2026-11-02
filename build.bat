@echo off
:: 이 파일이 있는 폴더 = 프로젝트 폴더(어디에 받아도 됨)
for %%I in ("%~dp0.") do set "P=%%~fI"
set "UV_CACHE_DIR=%P%\.uv-cache"
set "UV_PYTHON_INSTALL_DIR=%P%\.uv-python"
cd /d "%P%"
.venv\Scripts\pyinstaller.exe --noconfirm --clean --windowed --name Admiral --icon "%P%\admiral.ico" --version-file "%P%\version.txt" ^
  --workpath "%P%\tmp\build" --distpath "%P%\dist" --specpath "%P%\tmp" ^
  --collect-data faster_whisper --collect-binaries ctranslate2 --collect-data customtkinter ^
  --collect-binaries nvidia.cublas --collect-binaries nvidia.cudnn --collect-binaries nvidia.cuda_nvrtc ^
  --hidden-import pystray._win32 "%P%\run.py"
