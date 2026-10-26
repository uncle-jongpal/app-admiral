@echo off
set P=C:\path\to\admiral
set UV_CACHE_DIR=%P%\.uv-cache
set UV_PYTHON_INSTALL_DIR=%P%\.uv-python
cd /d %P%
tools\uv.exe sync --python 3.12
