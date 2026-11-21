@echo off
setlocal EnableExtensions
rem ============================================================
rem  The Ward Ledger - one-shot developer environment setup
rem  Usage:  setup.bat            set everything up
rem          setup.bat --test     set up, then run backend + frontend checks
rem          setup.bat --start    set up, then launch both servers
rem  Safe to re-run: every step skips work that is already done.
rem ============================================================

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "BACKEND=%ROOT%\backend"
set "FRONTEND=%ROOT%\frontend"
set "VENV_PY=%BACKEND%\.venv\Scripts\python.exe"
set "DO_TEST=0"
set "DO_START=0"
if /I "%~1"=="--test"  set "DO_TEST=1"
if /I "%~1"=="--start" set "DO_START=1"

echo.
echo === [1/7] Checking prerequisites ===
where python >nul 2>nul || (echo [ERROR] Python 3.11+ not found on PATH. Install from https://www.python.org/downloads/ & goto :fail)
python -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" || (echo [ERROR] Python 3.11 or newer is required. & goto :fail)
where node >nul 2>nul || (echo [ERROR] Node.js 18+ not found on PATH. Install from https://nodejs.org/ & goto :fail)
where npm  >nul 2>nul || (echo [ERROR] npm not found on PATH. & goto :fail)
where git  >nul 2>nul || (echo [ERROR] Git not found on PATH. Install from https://git-scm.com/ & goto :fail)
for /f "delims=" %%v in ('python --version') do echo   %%v
for /f "delims=" %%v in ('node --version') do echo   node %%v

echo.
echo === [2/7] Fetching dataset into data\ ===
if exist "%ROOT%\data\complaints.csv" (
  echo   data\ already populated, skipping.
) else (
  call :fetch_data || goto :fail
)

echo.
echo === [3/7] Creating backend virtualenv ===
if exist "%VENV_PY%" (
  echo   backend\.venv already exists, skipping.
) else (
  python -m venv "%BACKEND%\.venv" || goto :fail
)

echo.
echo === [4/7] Installing backend dependencies ===
pushd "%BACKEND%"
"%VENV_PY%" -m pip install --upgrade pip --quiet
"%VENV_PY%" -m pip install -e ".[test]" || (popd & goto :fail)

echo.
echo === [5/7] Building the database (pipeline) ===
"%VENV_PY%" -m pipeline.run --force || (popd & goto :fail)
popd

echo.
echo === [6/7] Installing frontend dependencies ===
if not exist "%FRONTEND%\.env.local" (
  copy /Y "%FRONTEND%\.env.example" "%FRONTEND%\.env.local" >nul
  echo   created frontend\.env.local from .env.example
)
pushd "%FRONTEND%"
call npm install || (popd & goto :fail)
popd

echo.
echo === [7/7] Done ===
echo   Backend  : backend\.venv ready, backend\ward_ledger.db built
echo   Frontend : frontend\node_modules installed
echo.
echo   Run the API : cd backend ^&^& .venv\Scripts\python -m uvicorn app.main:app --port 8000
echo   Run the UI  : cd frontend ^&^& npm run dev     (http://localhost:3000)
echo   Optional    : set ANTHROPIC_API_KEY in the shell that runs uvicorn (see .env.example)
echo.

if "%DO_TEST%"=="1" (
  echo === Running checks ===
  pushd "%BACKEND%"
  "%VENV_PY%" -m pytest || (popd & goto :fail)
  popd
  pushd "%FRONTEND%"
  call node scripts\check-i18n.mjs || (popd & goto :fail)
  call npx tsc --noEmit || (popd & goto :fail)
  popd
)

if "%DO_START%"=="1" (
  echo === Starting servers in new windows ===
  start "Ward Ledger API" /D "%BACKEND%" cmd /k ""%VENV_PY%" -m uvicorn app.main:app --port 8000"
  start "Ward Ledger UI"  /D "%FRONTEND%" cmd /k "npm run dev"
  echo   API: http://localhost:8000/docs   UI: http://localhost:3000
)

endlocal
exit /b 0

:fetch_data
set "TMPDIR=%TEMP%\wl_data_%RANDOM%"
git clone --depth 1 https://github.com/SumeetGDoshi/Claude-Impact-Labs-data-2.git "%TMPDIR%" || exit /b 1
if not exist "%ROOT%\data" mkdir "%ROOT%\data"
xcopy /Y /Q "%TMPDIR%\data\*" "%ROOT%\data\" >nul || exit /b 1
rmdir /S /Q "%TMPDIR%"
echo   dataset copied to data\
exit /b 0

:fail
echo.
echo [FAILED] Setup did not complete. See the error above.
endlocal
exit /b 1
