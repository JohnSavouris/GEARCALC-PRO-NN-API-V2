# Run from backend/ folder
# Optional MATLAB mode:
#   $env:USE_MATLAB="1"
#   $env:MATLAB_EXE="C:\Program Files\MATLAB\R2024b\bin\matlab.exe"
python -m uvicorn api_server:app --reload --host 127.0.0.1 --port 8000
