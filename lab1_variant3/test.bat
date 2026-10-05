@echo off
chcp 65001 >nul
py -m unittest discover -s tests -v
if errorlevel 1 python -m unittest discover -s tests -v
pause
