@echo off
chcp 65001 > nul
title 다온다견적서 - 데스크톱 앱 만들기
echo.
echo  다온다견적서 데스크톱 앱을 만듭니다.
echo  인터넷에서 약 120MB 를 받으므로 몇 분 걸립니다.
echo.

where node > nul 2>&1
if errorlevel 1 (
  echo  [오류] Node.js 가 설치돼 있지 않습니다.
  echo         https://nodejs.org 에서 LTS 버전을 설치한 뒤 다시 실행하세요.
  echo.
  pause
  exit /b 1
)

if not exist "index.html" (
  echo  [오류] 이 폴더에 index.html 이 없습니다.
  echo         견적서 html 파일을 index.html 로 이름을 바꿔서 넣어주세요.
  echo.
  pause
  exit /b 1
)

echo  [1/2] 필요한 도구를 받는 중...
call npm install --no-audit --no-fund electron @electron/packager
if errorlevel 1 goto failed

echo.
echo  [2/2] 앱을 만드는 중...
call npx @electron/packager . 다온다견적서 --platform=win32 --arch=x64 --overwrite --ignore="^/node_modules$"
if errorlevel 1 goto failed

echo.
echo  ===== 완료 =====
echo  다온다견적서-win32-x64 폴더 안의 exe 파일을 실행하세요.
echo.
pause
exit /b 0

:failed
echo.
echo  [실패] 중간에 오류가 났습니다. 위의 메시지를 확인해 주세요.
echo.
pause
exit /b 1
