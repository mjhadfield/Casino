@echo off
rem Hadfield Casino launcher.
rem Just double-click this file. If Python isn't installed yet, run
rem "Install prerequisites.bat" first (once), then use this from then on.

title Hadfield Casino
cd /d "%~dp0"

where py >nul 2>&1
if not errorlevel 1 (
    py -3 main.py
    goto :end
)

where python >nul 2>&1
if not errorlevel 1 (
    python main.py
    goto :end
)

echo.
echo Python wasn't found on this PC.
echo Run "Install prerequisites.bat" first, then try this again.
echo.
pause
goto :eof

:end
if errorlevel 1 (
    echo.
    echo Hadfield Casino closed with an error -- see above.
    pause
)
