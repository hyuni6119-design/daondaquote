#!/bin/bash
# macOS / Linux cron 에서 매일 실행하는 파일
cd "$(dirname "$0")"
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi
"$PY" main.py post >> logs/cron.log 2>&1
