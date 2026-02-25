@echo off
REM Run from backend\ folder
REM Optional:
REM   set USE_MATLAB=1
REM   set MATLAB_EXE=C:\Program Files\MATLAB\R2024b\bin\matlab.exe
python -m uvicorn api_server:app --reload --host 127.0.0.1 --port 8000
