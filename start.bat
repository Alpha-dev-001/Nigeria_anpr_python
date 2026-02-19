@echo off
setlocal EnableDelayedExpansion

echo ============================================================
echo NIGERIAN ANPR SYSTEM - INSTALLATION
echo ============================================================
echo.

:: ─── CONFIG ──────────────────────────────────────────────────
set VENV_DIR=%~dp0venv
set REQ_FILE=%~dp0requirements.txt
set LOG_FILE=%~dp0install_error.log
set MIN_PY_MAJOR=3
set MIN_PY_MINOR=8
:: ─────────────────────────────────────────────────────────────

:: Resolve Python executable (try several known names)
set PYTHON_CMD=
for %%P in (python python3 py) do (
    if "!PYTHON_CMD!"=="" (
        %%P --version >nul 2>&1
        if !ERRORLEVEL! == 0 (
            set PYTHON_CMD=%%P
        )
    )
)

if "!PYTHON_CMD!"=="" (
    echo [ERROR] Python not found. Please install Python %MIN_PY_MAJOR%.%MIN_PY_MINOR%+ and add it to PATH.
    echo         Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Verify minimum Python version
echo [INFO]  Detected Python via: !PYTHON_CMD!
for /f "tokens=2 delims= " %%V in ('!PYTHON_CMD! --version 2^>^&1') do set PY_VER=%%V
echo [INFO]  Python version: !PY_VER!

for /f "tokens=1,2 delims=." %%A in ("!PY_VER!") do (
    set PY_MAJOR=%%A
    set PY_MINOR=%%B
)
if !PY_MAJOR! LSS %MIN_PY_MAJOR% (
    echo [ERROR] Python %MIN_PY_MAJOR%.%MIN_PY_MINOR%+ required. Found !PY_VER!.
    pause & exit /b 1
)
if !PY_MAJOR! EQU %MIN_PY_MAJOR% if !PY_MINOR! LSS %MIN_PY_MINOR% (
    echo [ERROR] Python %MIN_PY_MAJOR%.%MIN_PY_MINOR%+ required. Found !PY_VER!.
    pause & exit /b 1
)

:: Check requirements.txt exists
if not exist "%REQ_FILE%" (
    echo [ERROR] requirements.txt not found at: %REQ_FILE%
    pause & exit /b 1
)

echo.
echo ─────────────────────────────────────────────────────────────
echo  STEP 1: Virtual Environment
echo ─────────────────────────────────────────────────────────────

if exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [INFO]  Existing venv found at: %VENV_DIR%
    echo [INFO]  Skipping creation, activating existing venv...
) else (
    echo [INFO]  Creating virtual environment at: %VENV_DIR%
    !PYTHON_CMD! -m venv "%VENV_DIR%"
    if !ERRORLEVEL! NEQ 0 (
        echo [ERROR] Failed to create virtual environment.
        echo         Try: !PYTHON_CMD! -m pip install virtualenv
        pause & exit /b 1
    )
    echo [OK]    Virtual environment created.
)

:: Activate venv
call "%VENV_DIR%\Scripts\activate.bat"
if !ERRORLEVEL! NEQ 0 (
    echo [ERROR] Failed to activate virtual environment.
    pause & exit /b 1
)
echo [OK]    Virtual environment activated.

echo.
echo ─────────────────────────────────────────────────────────────
echo  STEP 2: Upgrade pip inside venv
echo ─────────────────────────────────────────────────────────────

call :try_pip_upgrade
if !ERRORLEVEL! NEQ 0 (
    echo [WARN]  pip upgrade failed — continuing with existing pip version.
)

echo.
echo ─────────────────────────────────────────────────────────────
echo  STEP 3: Installing dependencies
echo ─────────────────────────────────────────────────────────────
echo [INFO]  This may take 5-10 minutes on first run.
echo.

call :try_install
if !ERRORLEVEL! NEQ 0 (
    echo.
    echo [ERROR] All installation attempts failed.
    echo         Error log saved to: %LOG_FILE%
    echo.
    echo         Possible fixes:
    echo           1. Check your internet connection
    echo           2. Try running this script as Administrator
    echo           3. Review %LOG_FILE% for details
    echo.
    pause & exit /b 1
)

echo.
echo ============================================================
echo  INSTALLATION COMPLETE
echo ============================================================
echo.
echo  To activate the environment manually:
echo    %VENV_DIR%\Scripts\activate
echo.
pause
exit /b 0


:: ══════════════════════════════════════════════════════════════
::  SUBROUTINE: try_install — cascading fallback pip strategies
:: ══════════════════════════════════════════════════════════════
:try_install
    set INSTALL_OK=0

    :: --- Attempt 1: venv pip directly ---
    echo [TRY 1] pip install -r requirements.txt
    pip install -r "%REQ_FILE%" 2>"%LOG_FILE%"
    if !ERRORLEVEL! == 0 ( set INSTALL_OK=1 & goto :install_done )
    echo [FAIL]  Attempt 1 failed, trying next...

    :: --- Attempt 2: python -m pip ---
    echo [TRY 2] python -m pip install -r requirements.txt
    python -m pip install -r "%REQ_FILE%" 2>>"%LOG_FILE%"
    if !ERRORLEVEL! == 0 ( set INSTALL_OK=1 & goto :install_done )
    echo [FAIL]  Attempt 2 failed, trying next...

    :: --- Attempt 3: explicit venv python -m pip ---
    echo [TRY 3] venv python -m pip install -r requirements.txt
    "%VENV_DIR%\Scripts\python.exe" -m pip install -r "%REQ_FILE%" 2>>"%LOG_FILE%"
    if !ERRORLEVEL! == 0 ( set INSTALL_OK=1 & goto :install_done )
    echo [FAIL]  Attempt 3 failed, trying next...

    :: --- Attempt 4: with --user flag (venv fallback) ---
    echo [TRY 4] pip install --user -r requirements.txt
    pip install --user -r "%REQ_FILE%" 2>>"%LOG_FILE%"
    if !ERRORLEVEL! == 0 ( set INSTALL_OK=1 & goto :install_done )
    echo [FAIL]  Attempt 4 failed, trying next...

    :: --- Attempt 5: trusted hosts (proxy/SSL workaround) ---
    echo [TRY 5] pip install with trusted-host flags
    pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r "%REQ_FILE%" 2>>"%LOG_FILE%"
    if !ERRORLEVEL! == 0 ( set INSTALL_OK=1 & goto :install_done )
    echo [FAIL]  Attempt 5 failed. All strategies exhausted.

:install_done
    if !INSTALL_OK! == 1 (
        echo [OK]    Dependencies installed successfully.
        exit /b 0
    )
    exit /b 1


:: ══════════════════════════════════════════════════════════════
::  SUBROUTINE: try_pip_upgrade
:: ══════════════════════════════════════════════════════════════
:try_pip_upgrade
    python -m pip install --upgrade pip >nul 2>&1
    if !ERRORLEVEL! == 0 ( echo [OK]    pip upgraded. & exit /b 0 )
    pip install --upgrade pip >nul 2>&1
    if !ERRORLEVEL! == 0 ( echo [OK]    pip upgraded. & exit /b 0 )
    exit /b 1