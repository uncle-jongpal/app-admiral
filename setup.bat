@echo off
:: 이 파일이 있는 폴더 = 프로젝트 폴더(어디에 받아도 됨)
for %%I in ("%~dp0.") do set "P=%%~fI"
set "UV_CACHE_DIR=%P%\.uv-cache"
set "UV_PYTHON_INSTALL_DIR=%P%\.uv-python"
cd /d "%P%"
tools\uv.exe sync --python 3.12
