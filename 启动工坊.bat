@echo off
setlocal enabledelayedexpansion
title EPUB 精排工坊
cd /d "%~dp0"

echo 正在检测 Python 环境...
set "PY="

REM ============ 0) 手动指定：同目录下 python_path.txt 里写 python.exe 的完整路径 ============
if exist "python_path.txt" (
    set /p PYC=<python_path.txt
    if defined PYC if exist "!PYC!" call :trypy "!PYC!"
)

REM ============ 1) 本项目专用：D:\APP安装\Python313 ============
if not defined PY call :trypy "D:\APP安装\Python313\python.exe"

REM ============ 2) python-manager（py 管理器）安装的运行时 ============
if not defined PY (
    for /d %%V in ("%LocalAppData%\Python\pythoncore-3*") do (
        if not defined PY call :trypy "%%~V\python.exe"
    )
)

REM ============ 3) 官方安装包默认位置 ============
if not defined PY (
    for /d %%V in ("%LocalAppData%\Programs\Python\Python3*") do (
        if not defined PY call :trypy "%%~V\python.exe"
    )
)
if not defined PY (
    for /d %%V in ("%SystemDrive%\Python3*") do (
        if not defined PY call :trypy "%%~V\python.exe"
    )
)
if not defined PY (
    for /d %%V in ("%ProgramFiles%\Python3*") do (
        if not defined PY call :trypy "%%~V\python.exe"
    )
)

REM ============ 4) WorkBuddy 自带 Python 兜底 ============
if not defined PY (
    for /d %%V in ("%USERPROFILE%\.workbuddy\binaries\python\versions\3*") do (
        if not defined PY call :trypy "%%~V\python.exe"
    )
)

if not defined PY (
    echo.
    echo [错误] 没有找到可用的 Python 3.10+
    echo.
    echo 解决办法（任选一种）：
    echo   1. 打开“终端/命令提示符”执行：  py install 3.13
    echo   2. 或到 https://www.python.org/downloads/ 下载安装，
    echo      安装时勾选 "Add python.exe to PATH"
    echo   3. 或在本脚本同目录新建 python_path.txt，
    echo      里面写一行 python.exe 的完整路径
    echo.
    pause
    exit /b 1
)

echo 使用解释器：%PY%
%PY% --version
echo.

REM ============ 端口占用检查 ============
netstat -ano | findstr /c:":8642" | findstr /c:"LISTENING" >nul
if not errorlevel 1 (
    echo [提示] 端口 8642 已被占用，程序可能已经在运行，直接打开页面。
    start "" http://localhost:8642
    exit /b 0
)

REM ============ 依赖检查（缺则安装） ============
%PY% -c "import flask, PIL, fontTools, lxml" >nul 2>&1
if errorlevel 1 (
    echo 正在安装依赖，请稍候（首次可能需要几分钟）...
    %PY% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [错误] 依赖安装失败，请检查网络后重新运行本脚本
        pause
        exit /b 1
    )
)

echo 正在启动 EPUB 精排工坊...
echo 页面地址：http://localhost:8642 （3 秒后自动打开浏览器）
echo 关闭本窗口即退出程序。
echo.
start "" /min cmd /c "timeout /t 3 >nul & explorer http://localhost:8642"
%PY% server.py 8642
echo.
echo 服务已停止。
pause
exit /b 0

:trypy
if defined PY goto :eof
if not exist %1 goto :eof
%1 -c "import sys" >nul 2>&1
if not errorlevel 1 set "PY=%~1"
goto :eof
