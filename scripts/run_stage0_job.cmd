@echo off
setlocal

REM Repo root = one level above this script
set "REPO_ROOT=%~dp0.."
cd /d "%REPO_ROOT%"

REM Ensure logs directory exists
if not exist "logs" mkdir "logs"

REM Use venv Python (adjust if your venv path differs)
set "PY=%REPO_ROOT%\.venv\Scripts\python.exe"

if not exist "%PY%" (
  echo [%DATE% %TIME%] ERROR: python not found at %PY%>> "logs\stage0_scheduler.log"
  exit /b 1
)

"%PY%" -m src.stage0.job >> "logs\stage0_scheduler.log" 2>&1
exit /b %ERRORLEVEL%