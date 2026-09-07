@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
echo Starting backend server using explicit virtual environment Python...
.\venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000
pause
