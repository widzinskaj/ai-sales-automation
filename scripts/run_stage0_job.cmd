@echo off
setlocal

REM Repo root = one level above this script
set "REPO_ROOT=%~dp0.."

REM Ensure logs directory exists using absolute path
if not exist "%REPO_ROOT%\logs" mkdir "%REPO_ROOT%\logs"

set "LOG=%REPO_ROOT%\logs\stage0_scheduler.log"

REM Use venv Python (adjust if your venv path differs)
set "PY=%REPO_ROOT%\.venv\Scripts\python.exe"

if not exist "%PY%" (
  echo [%DATE% %TIME%] ERROR: python not found at %PY%>> "%LOG%"
  exit /b 1
)

cd /d "%REPO_ROOT%"
"%PY%" -m src.stage0.job >> "%LOG%" 2>&1
exit /b %ERRORLEVEL%