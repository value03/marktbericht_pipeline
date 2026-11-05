@echo off
rem Start the Marktbericht GUI without a console window.
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0app.py"
