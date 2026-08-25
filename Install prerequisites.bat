@echo off
rem Hadfield Casino needs only Python 3.9+ with tkinter (part of the
rem standard library -- no other packages to install). This checks for
rem that and, if it's missing, downloads and installs the official
rem Python build for the current user only (no admin rights needed).
rem Run this once, then use "Launch Casino.bat" from then on.

title Hadfield Casino - Install Prerequisites

echo ============================================================
echo  Hadfield Casino - Prerequisite Installer
echo ============================================================
echo.
echo Checking for an existing Python installation with tkinter...
echo.

where py >nul 2>&1
if errorlevel 1 goto :try_python
py -3 -c "import tkinter" >nul 2>&1
if errorlevel 1 goto :try_python
echo Found a working Python installation via the "py" launcher.
echo Nothing to do -- you're ready to run "Launch Casino.bat".
goto :end

:try_python
where python >nul 2>&1
if errorlevel 1 goto :not_found
python -c "import tkinter" >nul 2>&1
if errorlevel 1 goto :not_found
echo Found a working Python installation via "python".
echo Nothing to do -- you're ready to run "Launch Casino.bat".
goto :end

:not_found
echo No Python installation with tkinter was found.
echo Downloading the official Python installer...
echo.

rem Pinned to a known-good release rather than "latest" so this script's
rem behaviour doesn't silently change later -- bump it every so often
rem (check https://www.python.org/downloads/windows/ for the current one).
set "PYTHON_VERSION=3.13.15"
set "PYTHON_INSTALLER_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/python-%PYTHON_VERSION%-amd64.exe"
set "INSTALLER_PATH=%TEMP%\python-%PYTHON_VERSION%-installer.exe"

echo   %PYTHON_INSTALLER_URL%
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -Uri '%PYTHON_INSTALLER_URL%' -OutFile '%INSTALLER_PATH%' } catch { exit 1 }"

if not exist "%INSTALLER_PATH%" goto :download_failed

echo Download complete. Installing for your user account only
echo (this includes tkinter, and adds Python to your PATH)...
echo.

"%INSTALLER_PATH%" /quiet InstallAllUsers=0 PrependPath=1 Include_tcltk=1 Include_test=0

echo.
echo Install finished.
echo.
echo Close and reopen any open Command Prompt / File Explorer windows so
echo the updated PATH takes effect, then run "Launch Casino.bat".

del "%INSTALLER_PATH%" >nul 2>&1
goto :end

:download_failed
echo.
echo Download failed -- check your internet connection, or install Python
echo manually from https://www.python.org/downloads/ (tick "tcl/tk and
echo IDLE" during setup), then re-run this script.

:end
echo.
pause
