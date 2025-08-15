from __future__ import annotations

from typing import Optional, Callable, List, Dict, Tuple
import os
import sys
from datetime import datetime

from PyQt5 import QtCore, QtGui, QtWidgets


class ObjectToolbar(QtWidgets.QToolBar):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setMovable(False)
        self.setFloatable(False)
        self.setIconSize(QtCore.QSize(25, 25))
        self.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        self.setStyleSheet("QToolBar{spacing:0; margin:0; padding:0; border:0;} QToolButton{margin:0; padding:0; border:0;}")
        self.setContentsMargins(0, 0, 0, 0)
        self.setFixedHeight(25)

        # Group button
        spacer = QtWidgets.QWidget(self)
        spacer.setFixedWidth(8)
        self.addWidget(spacer)
        self.action_group = self.addAction(QtGui.QIcon("./Resources/Group.png"), "Group")
        btn = self.widgetForAction(self.action_group)
        if isinstance(btn, QtWidgets.QToolButton):
            btn.setFixedSize(25, 25)
            btn.setIconSize(QtCore.QSize(25, 25))
        # Spacer between icons
        spacer = QtWidgets.QWidget(self)
        spacer.setFixedWidth(8)
        self.addWidget(spacer)
        # Link button
        self.action_link = self.addAction(QtGui.QIcon("./Resources/Link.png"), "Link")
        btn2 = self.widgetForAction(self.action_link)
        if isinstance(btn2, QtWidgets.QToolButton):
            btn2.setFixedSize(25, 25)
            btn2.setIconSize(QtCore.QSize(25, 25))

        # Callback to obtain navigation state from host window: (nav_stack, host, port)
        self.get_state: Optional[Callable[[], Tuple[List[Dict[str, str]], str, int]]] = None
        self.action_link.triggered.connect(self._on_create_shortcut)

    def _on_create_shortcut(self) -> None:
        deeplink = self._build_current_deeplink_from_state()
        # Resolve executable and script path
        try:
            exe = sys.executable
            # Use the current script path if available; falls back to sys.argv[0]
            script_path = os.path.abspath(sys.argv[0])
            # Compose .desktop content
            desktop_dir = os.path.expanduser("~/Desktop")
            os.makedirs(desktop_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            file_path = os.path.join(desktop_dir, f"HierarchyBrowser-{timestamp}.desktop")
            # Run by changing directory to where browser.py lives, then invoking it
            browser_dir = os.path.abspath(os.path.dirname(script_path))
            exec_line = f"/bin/bash -lc 'cd \"{browser_dir}\" && \"{exe}\" browser.py --path \"{deeplink}\"'"
            # Icon path (absolute) for desktop entry
            this_dir = os.path.abspath(os.path.dirname(__file__))
            icon_path = os.path.join(this_dir, "Resources", "Browser.png")
            content = (
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=Hierarchy Browser Link\n"
                f"Exec={exec_line}\n"
                f"Icon={icon_path}\n"
                "Terminal=false\n"
            )
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            os.chmod(file_path, 0o755)
            QtWidgets.QMessageBox.information(self, "Shortcut created", f"Created shortcut at:\n{file_path}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Shortcut error", f"Failed to create shortcut:\n{e}")

    def _build_current_deeplink_from_state(self) -> str:
        # Build /[host:port]/seg/... inserting provider switch tokens when host:port changes
        try:
            if not callable(self.get_state):
                return "/"
            nav_stack, current_host, current_port = self.get_state()  # type: ignore[assignment]
            parts: List[str] = []
            if not isinstance(nav_stack, list) or len(nav_stack) == 0:
                return f"/[{current_host}:{current_port}]/"
            prev_host: Optional[str] = None
            prev_port: Optional[int] = None
            for entry in nav_stack:
                entry_host = entry.get("host") or current_host
                try:
                    entry_port = int(entry.get("port")) if entry.get("port") is not None else current_port
                except Exception:
                    entry_port = current_port
                if entry_host != prev_host or entry_port != prev_port:
                    parts.append(f"[{entry_host}:{entry_port}]")
                    prev_host, prev_port = entry_host, entry_port
                # Skip provider root markers
                oid = entry.get("id")
                if isinstance(oid, str) and oid == "/":
                    continue
                remote_id = entry.get("remote_id")
                if isinstance(remote_id, str) and remote_id == "/":
                    continue
                title = entry.get("title")
                if isinstance(title, str) and title and title != "/":
                    parts.append(title)
            return "/" + "/".join(parts) + "/"
        except Exception:
            return "/"


