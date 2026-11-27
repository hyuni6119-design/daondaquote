@echo off
REM 윈도우 작업 스케줄러에서 매일 실행하는 파일
chcp 65001 > nul
cd /d "%~dp0"
if exist .venv\Scripts\python.exe (
  .venv\Scripts\python.exe main.py post
) else (
  python main.py post
)
