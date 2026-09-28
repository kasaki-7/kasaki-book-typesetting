@echo off
REM EPUB 精排工坊 一键启动（Windows）
cd /d "%~dp0"
python --version >nul 2>&1
if errorlevel 1 (
    echo 未找到 Python，请先安装 Python 3.10+ 并勾选 Add to PATH
    pause
    exit /b 1
)
if not exist .deps_installed (
    python -m pip install -r requirements.txt && echo ok > .deps_installed
)
start "" http://localhost:8642
python server.py 8642
