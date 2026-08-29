#!/usr/bin/env bash
# ============================================================
# Hadfield Casino -- Linux launcher
# Linux equivalent of "Launch Casino (windows).bat": checks for a working
# Python 3 + Tkinter, then runs the game. Unlike the Windows script, this
# does NOT attempt to install anything itself -- a system Python package is
# a distro-wide, root-owned thing on Linux (unlike Windows' official
# per-user installer, which needs no admin rights), so the right move here
# is to name the exact command for your distro and let you run it yourself.
# ============================================================
set -u
cd "$(dirname "${BASH_SOURCE[0]}")"

banner() {
    echo
    echo
    echo " ###   ###   ####   ######    ####### #####  ####### ###      ######  "
    echo " ###   ### ######## ######## ########  ###  ######## ###      ######## "
    echo " ######### ###  ### ###  ### #####     ###  #####    ###      ###  ### "
    echo " ######### ######## ###  ### #####     ###  ###      ###      ###  ### "
    echo " ###   ### ###  ### #######  ###      ##### ######## ######## ####### "
    echo
    echo "                             C A S I N O"
}

install_hint() {
    # Prints the right "install Python 3 + Tkinter" command for whatever
    # package manager is actually on this system -- mirrors the README's
    # own Debian/Arch examples, extended to the other common ones.
    if command -v apt >/dev/null 2>&1; then
        echo "    sudo apt install python3 python3-tk"
    elif command -v pacman >/dev/null 2>&1; then
        echo "    sudo pacman -S python tk"
    elif command -v dnf >/dev/null 2>&1; then
        echo "    sudo dnf install python3 python3-tkinter"
    elif command -v zypper >/dev/null 2>&1; then
        echo "    sudo zypper install python3 python3-tk"
    elif command -v apk >/dev/null 2>&1; then
        echo "    sudo apk add python3 py3-tkinter"
    else
        echo "    (install Python 3 and its Tkinter/Tcl-Tk package via your distro's package manager)"
    fi
}

clear
banner
echo
echo "  Checking system..."
echo "  Checking for Python"
echo

# ------------------------------------------------------------
# Find a python3 (or python, if that's actually Python 3) with tkinter
# ------------------------------------------------------------
PYTHON_CMD=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        if "$candidate" -c "import sys; sys.exit(0 if sys.version_info[0] == 3 else 1)" 2>/dev/null; then
            if "$candidate" -c "import tkinter" >/dev/null 2>&1; then
                PYTHON_CMD="$candidate"
                break
            fi
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "  +--------------------------------------------------------+"
    echo "  |                                                        |"
    echo "  |   Python 3 with Tkinter was not found.                 |"
    echo "  |                                                        |"
    echo "  |   Hadfield Casino requires Python 3 with Tkinter.       |"
    echo "  |                                                        |"
    echo "  +--------------------------------------------------------+"
    echo
    echo "  Install it with:"
    echo
    install_hint
    echo
    echo "  Then run this launcher again."
    echo
    exit 1
fi

echo "  Python found ($PYTHON_CMD)."
echo "  Tkinter is available."
echo
echo "  Preparing Hadfield Casino"
echo
clear
banner
echo
echo "  Dealer is at the table."
echo "  Cards are being shuffled..."
echo
echo "  Starting casino"
echo
echo "  Good luck."
echo

"$PYTHON_CMD" main.py
status=$?

if [ $status -ne 0 ]; then
    echo
    echo "  +--------------------------------------------------------+"
    echo "  |  HADFIELD CASINO CLOSED WITH AN ERROR                   |"
    echo "  +--------------------------------------------------------+"
    echo
    echo "  Python returned an error while running the game."
    echo "  The error message should be visible above."
    echo
    read -r -p "  Press Enter to close..." _
    exit $status
fi

echo
echo "  +--------------------------------------------------------+"
echo "  |  Hadfield Casino closed normally.                       |"
echo "  +--------------------------------------------------------+"
echo
