@echo off
pip install pillow -q
start "" pythonw "%~dp0capture.py"
