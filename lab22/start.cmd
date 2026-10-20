@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto use_python
py -3 lab1.py %*
goto finished
:use_python
python lab1.py %*
:finished
if errorlevel 1 pause
