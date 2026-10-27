@echo off
chcp 65001 >nul
title 골드TV - 처음 한 번만 설치
echo 파이썬 꾸러미를 설치합니다...
python -m pip install --upgrade pip
python -m pip install pillow google-api-python-client google-auth-oauthlib
echo.
echo ffmpeg 설치를 시도합니다...
winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
echo.
echo 끝났습니다. 이 창을 닫고 명령 프롬프트를 새로 열어주세요.
pause
