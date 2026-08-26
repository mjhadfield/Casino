@echo off
setlocal EnableExtensions
title Hadfield Casino

cd /d "%~dp0"

:: ============================================================
:: Hadfield Casino
:: Combined launcher + Python prerequisite installer
:: ============================================================

:: ---- Colours ------------------------------------------------
color 0B

cls
call :banner

echo.
echo  Checking system...
echo  Checking for Python

:: ============================================================
:: Check for a working Python installation
:: ============================================================

set "PYTHON_CMD="

where py >nul 2>&1
if not errorlevel 1 (
    py -3 -c "import tkinter" >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_CMD=py -3"
        goto :python_found
    )
)

where python >nul 2>&1
if not errorlevel 1 (
    python -c "import tkinter" >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_CMD=python"
        goto :python_found
    )
)

:: ============================================================
:: Python not found
:: ============================================================

cls
call :banner

echo.
echo  +--------------------------------------------------------+
echo  ^|                                                        ^|
echo  ^|   Python was not found.                               ^|
echo  ^|                                                        ^|
echo  ^|   Hadfield Casino requires Python 3 with Tkinter.     ^|
echo  ^|   Tkinter is included with the official Python build. ^|
echo  ^|                                                        ^|
echo  +--------------------------------------------------------+
echo.
echo  I can download and install Python automatically.
echo.
echo  The installation will be:
echo.
echo    - Official Python from python.org
echo    - Python 3.13.15
echo    - Installed for your Windows user account only
echo    - No administrator privileges required
echo    - Tkinter included
echo.
echo  Do you want to install Python and continue?
echo.
choice /C YN /N /M "  Install Python? [Y/N]: "

if errorlevel 2 goto :user_declined
if errorlevel 1 goto :install_python

:: ============================================================
:: Install Python
:: ============================================================

:install_python

cls
call :banner

echo.
echo  +--------------------------------------------------------+
echo  ^|              PYTHON INSTALLATION                     ^|
echo  +--------------------------------------------------------+
echo.

set "PYTHON_VERSION=3.13.15"
set "PYTHON_INSTALLER_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/python-%PYTHON_VERSION%-amd64.exe"
set "INSTALLER_PATH=%TEMP%\hadfield-python-%PYTHON_VERSION%-installer.exe"

echo  [1/3] Preparing download...
echo.
echo        %PYTHON_INSTALLER_URL%
echo.

echo.
echo  [2/3] Downloading Python...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
"[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; ^
 $ProgressPreference='SilentlyContinue'; ^
 try { Invoke-WebRequest -Uri '%PYTHON_INSTALLER_URL%' -OutFile '%INSTALLER_PATH%' } ^
 catch { exit 1 }"

if not exist "%INSTALLER_PATH%" goto :download_failed

echo  Download complete.
echo.

echo  [3/3] Installing Python...
echo.
echo        This may take a few moments.
echo.

"%INSTALLER_PATH%" /quiet InstallAllUsers=0 PrependPath=1 Include_tcltk=1 Include_test=0

set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python313\python.exe"

if not exist "%PYTHON_EXE%" (
    del "%INSTALLER_PATH%" >nul 2>&1
    goto :install_failed
)

echo  Installation complete.
echo.
echo  Checking Python installation
echo.

"%PYTHON_EXE%" -c "import tkinter" >nul 2>&1
if errorlevel 1 (
    del "%INSTALLER_PATH%" >nul 2>&1
    goto :install_failed
)

set "PYTHON_CMD=%PYTHON_EXE%"

del "%INSTALLER_PATH%" >nul 2>&1

echo.
echo  Python is ready.
echo  Tkinter is available.
echo.

timeout /t 2 /nobreak >nul

goto :launch_game


:: ============================================================
:: Python was already installed
:: ============================================================

:python_found

echo.
echo  Python found.
echo  Tkinter is available.
echo.
echo  Preparing Hadfield Casino
echo.

goto :launch_game


:: ============================================================
:: Launch game
:: ============================================================

:launch_game

cls
call :banner

echo.
echo  Dealer is at the table.
echo  Cards are being shuffled...
echo.

echo  Starting casino
echo.

echo.
echo  Good luck.
echo.

%PYTHON_CMD% main.py

if errorlevel 1 goto :game_error

echo.
echo  +--------------------------------------------------------+
echo  ^|  Hadfield Casino closed normally.                    ^|
echo  +--------------------------------------------------------+
echo.
pause
goto :end


:: ============================================================
:: User declined installation
:: ============================================================

:user_declined

cls
call :banner

echo.
echo  No worries.
echo.
echo  Python is required to run Hadfield Casino.
echo  Nothing has been installed.
echo.
echo  Install Python manually and run this launcher again.
echo.
pause
goto :end


:: ============================================================
:: Download failed
:: ============================================================

:download_failed

echo.
echo  +--------------------------------------------------------+
echo  ^|  DOWNLOAD FAILED                                     ^|
echo  +--------------------------------------------------------+
echo.
echo  Python could not be downloaded.
echo.
echo  Check your internet connection and try again.
echo.
echo  You can also install Python manually from:
echo.
echo  https://www.python.org/downloads/windows/
echo.
echo  Make sure Tkinter / Tcl-Tk is included during setup.
echo.
pause
goto :end


:: ============================================================
:: Installation failed
:: ============================================================

:install_failed

echo.
echo  +--------------------------------------------------------+
echo  ^|  INSTALLATION FAILED                                 ^|
echo  +--------------------------------------------------------+
echo.
echo  Python was downloaded, but the installation could not
echo  be verified.
echo.
echo  Try running this launcher again, or install Python
echo  manually from:
echo.
echo  https://www.python.org/downloads/windows/
echo.
pause
goto :end


:: ============================================================
:: Game error
:: ============================================================

:game_error

echo.
echo  +--------------------------------------------------------+
echo  ^|  HADFIELD CASINO CLOSED WITH AN ERROR                ^|
echo  +--------------------------------------------------------+
echo.
echo  Python returned an error while running the game.
echo  The error message should be visible above.
echo.
pause
goto :end


:: ============================================================
:: Casino banner
:: ============================================================

:banner
chcp 437 >nul

echo.
echo.
echo. ###   ###   ####   ######    ####### #####  ####### ###      ######  
echo. ###   ### ######## ######## ########  ###  ######## ###      ######## 
echo. ######### ###  ### ###  ### #####     ###  #####    ###      ###  ### 
echo. ######### ######## ###  ### #####     ###  ###      ###      ###  ### 
echo. ###   ### ###  ### #######  ###      ##### ######## ######## ####### 
echo.
echo                             C A S I N O

:loading

echo DONE
endlocal
exit /b


:end

endlocal
exit /b