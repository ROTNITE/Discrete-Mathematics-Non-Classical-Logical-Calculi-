@echo off
chcp 65001 >nul
py main.py
if errorlevel 1 python main.py
pause
