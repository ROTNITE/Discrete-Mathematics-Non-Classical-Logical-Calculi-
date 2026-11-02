@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto use_python
py -3 lab2.py %*
exit /b %errorlevel%
:use_python
python lab2.py %*
exit /b %errorlevel%
