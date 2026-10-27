@echo off
chcp 65001 >nul
cd /d C:\Users\PC\daondaquote
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p = Get-Content -Raw -Encoding UTF8 'C:\Users\PC\daondaquote\youtube-goldtv\도구\자동확인-지시.md'; $p | & 'C:\Users\PC\.local\bin\claude.exe' -p --allowedTools Bash Read Write Edit Glob Grep 2>&1 | Out-File -Append -Encoding UTF8 'C:\Users\PC\daondaquote\youtube-goldtv\도구\보드확인-기록.txt'"
