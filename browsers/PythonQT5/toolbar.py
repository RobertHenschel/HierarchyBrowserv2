from __future__ import annotations

from typing import Optional, Callable
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

        # Callback to obtain current deep-link path from host window
        self.get_current_deeplink: Optional[Callable[[], str]] = None
        self.action_link.triggered.connect(self._on_create_shortcut)

    def _on_create_shortcut(self) -> None:
        deeplink = "/"
        try:
            if callable(self.get_current_deeplink):
                deeplink = self.get_current_deeplink() or "/"
        except Exception:
            deeplink = "/"
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


