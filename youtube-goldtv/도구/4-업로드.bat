@echo off
chcp 65001 >nul
title 골드TV - 유튜브 업로드
if "%~1"=="" (
  echo 작업 폴더를 이 창에 끌어다 놓고 엔터를 누르세요.
  set /p 폴더="폴더: "
) else (
  set "폴더=%~1"
)
python "%~dp0업로드.py" "%폴더%"
pause
