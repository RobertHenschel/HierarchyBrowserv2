#!/usr/bin/env python3
import os
import shutil
import subprocess
import sys
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

    # macOS: prefer Terminal.app or iTerm2 via AppleScript
    if sys.platform == "darwin":
        def _escape_for_applescript(cmd: str) -> str:
            # Escape backslashes and quotes for AppleScript string
            return cmd.replace("\\", "\\\\").replace('"', '\\"')

        escaped = _escape_for_applescript(f"bash -lc \"{command}; exec bash\"")

        # Try Terminal.app – avoid double windows: do not activate before running.
        # If no windows are open, `do script` creates one; otherwise reuse front window (new tab).
        script_terminal = (
            'tell application "Terminal"\n'
            '  if (count of windows) is 0 then\n'
            f'    do script "{escaped}"\n'
            '  else\n'
            f'    do script "{escaped}" in front window\n'
            '  end if\n'
            '  activate\n'
            'end tell'
        )
        try:
            subprocess.Popen(["osascript", "-e", script_terminal])
            return True
        except Exception:
            pass

        # Try iTerm2 (or iTerm) if available
        for app_name in ("iTerm2", "iTerm"):
            script_iterm = (
                f'tell application "{app_name}"\n'
                f'  activate\n'
                f'  try\n'
                f'    create window with default profile\n'
                f'  end try\n'
                f'  tell current session of current window\n'
                f'    write text "{escaped}"\n'
                f'  end tell\n'
                f'end tell'
            )
            try:
                subprocess.Popen(["osascript", "-e", script_iterm])
                return True
            except Exception:
                continue
        # Fall through to generic approaches below

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
        elif action_lower == "objectbrowser":
            # Launch another instance of the Qt object browser with overrides
            host = entry.get("hostname") or entry.get("host") or "127.0.0.1"
            port = entry.get("port")
            try:
                port_str = str(int(port)) if port is not None else "8888"
            except Exception:
                port_str = "8888"

            here = os.path.dirname(os.path.abspath(__file__))
            browser_py = os.path.join(here, "browser.py")
            try:
                subprocess.Popen([sys.executable, browser_py, "--host", str(host), "--port", port_str])
            except Exception:
                QtWidgets.QToolTip.showText(pos, "Failed to launch object browser")


