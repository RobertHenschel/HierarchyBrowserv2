#!/usr/bin/env python3
import os
import shutil
import subprocess
import webbrowser
from typing import Any, Dict

from PyQt5 import QtCore, QtWidgets


def launch_terminal_with_command(command: str) -> bool:
    """Launch a terminal emulator to run the given shell command.

    Tries several common terminal emulators and environment hints. Returns True on first
    successful spawn, False if none can be launched.
    """
    def is_available(exe: str) -> bool:
        return shutil.which(exe) is not None

    # Command executed inside an interactive shell; keep the window open afterwards
    shell_cmd = ["bash", "-lc", f"{command}; exec bash"]

    candidates: list[list[str]] = []

    env_terminal = os.environ.get("TERMINAL")
    if env_terminal and is_available(env_terminal):
        candidates.append([env_terminal, "-e", *shell_cmd])

    if is_available("x-terminal-emulator"):
        candidates.append(["x-terminal-emulator", "-e", *shell_cmd])

    if is_available("gnome-terminal"):
        candidates.append(["gnome-terminal", "--", *shell_cmd])
    if is_available("konsole"):
        candidates.append(["konsole", "-e", *shell_cmd])
    if is_available("xfce4-terminal"):
        candidates.append(["xfce4-terminal", "-e", *shell_cmd])
    if is_available("kitty"):
        candidates.append(["kitty", *shell_cmd])
    if is_available("alacritty"):
        candidates.append(["alacritty", "-e", *shell_cmd])
    if is_available("terminator"):
        candidates.append(["terminator", "-x", *shell_cmd])
    if is_available("mate-terminal"):
        candidates.append(["mate-terminal", "--", *shell_cmd])
    if is_available("lxterminal"):
        candidates.append(["lxterminal", "-e", *shell_cmd])
    if is_available("xterm"):
        candidates.append(["xterm", "-e", *shell_cmd])

    for args in candidates:
        try:
            subprocess.Popen(args)
            return True
        except Exception:
            continue
    return False


def execute_context_action(parent: QtWidgets.QWidget, entry: Dict[str, Any], pos: QtCore.QPoint) -> None:
    """Handle a single context menu entry.

    - Copies entry['command'] to clipboard if present
    - Executes terminal if entry['action'] == 'terminal'
    """
    cmd = entry.get("command")
    if isinstance(cmd, str) and cmd:
        QtWidgets.QApplication.clipboard().setText(cmd)
        QtWidgets.QToolTip.showText(pos, "Command copied to clipboard")

    action = entry.get("action")
    if isinstance(action, str):
        action_lower = action.lower()
        if action_lower == "terminal" and isinstance(cmd, str) and cmd:
            launch_terminal_with_command(cmd)
        elif action_lower == "browser":
            url = entry.get("url")
            if isinstance(url, str) and url:
                try:
                    webbrowser.open(url)
                except Exception:
                    pass


