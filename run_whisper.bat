@echo off
REM ============================================================
REM  未明子视频 Whisper 转写 — Windows 一键运行脚本
REM  设备: GTX 1050 Ti (4GB VRAM) | 模型: medium + INT8
REM ============================================================

cd /d "%~dp0"

echo.
echo ============================================================
echo   未明子视频 Whisper ASR 转写工具
echo   设备: GTX 1050 Ti (4GB VRAM)
echo   模型: medium + INT8 量化 (~2.5GB VRAM)
echo ============================================================
echo.
echo   [1] 获取视频列表 (从B站API)
echo   [2] 生成无字幕 BV 列表
echo   [3] 下载音频 (yt-dlp批量)
echo   [4] 开始 Whisper 转写
echo   [5] 全流程一键运行
echo   [6] 复制结果到字幕目录
echo   [0] 退出
echo.

set /p choice="请选择 [0-6]: "

if "%choice%"=="1" goto :fetch
if "%choice%"=="2" goto :genbv
if "%choice%"=="3" goto :download
if "%choice%"=="4" goto :transcribe
if "%choice%"=="5" goto :all
if "%choice%"=="6" goto :copy
if "%choice%"=="0" goto :end
echo 无效选择 & goto :end

:fetch
echo.
echo >>> 获取视频列表...
uv run fetch_bilibili_videos.py 23191782 未明子
goto :end

:genbv
echo.
echo >>> 生成无字幕 BV 列表...
uv run whisper_transcribe.py --gen-bv-list
goto :end

:download
echo.
echo >>> 下载音频 (可能需要很长时间)...
uv run whisper_transcribe.py --download-audio
goto :end

:transcribe
echo.
echo >>> 开始 Whisper 转写...
uv run whisper_transcribe.py --transcribe
goto :end

:all
echo.
echo >>> 全流程: 生成列表 + 下载音频 + 转写...
uv run whisper_transcribe.py --all
goto :end

:copy
echo.
echo >>> 复制结果到 raw/subtitles/whisper/...
uv run whisper_transcribe.py --copy
goto :end

:end
echo.
pause
