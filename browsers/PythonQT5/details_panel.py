#!/usr/bin/env python3
import json
from pathlib import Path
from typing import Any, Dict, Optional

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWebEngineWidgets import QWebEngineView
from jinja2 import Environment, FileSystemLoader, select_autoescape


class _TemplateManager:
    def __init__(self, templates_root: Path) -> None:
        self.templates_root = templates_root
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_root)),
            autoescape=select_autoescape(["html", "htm"]),
            enable_async=False,
        )

    def select_template_for_class(self, obj_class: Optional[str]) -> str:
        if isinstance(obj_class, str) and obj_class:
            candidate = Path("classes") / f"{obj_class}.html"
            full = self.templates_root / candidate
            if full.exists():
                return str(candidate)
        return "default.html"

    def render(self, template_name: str, context: Dict[str, Any]) -> str:
        tpl = self.env.get_template(template_name)
        return tpl.render(**context)


class DetailsPanel(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        title = QtWidgets.QLabel("Details", self)
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        # Web view for rich HTML rendering
        self.web = QWebEngineView(self)
        layout.addWidget(self.web, stretch=1)

        self._placeholder = QtWidgets.QLabel("Select an item to see details", self)
        pal = self._placeholder.palette()
        pal.setColor(self._placeholder.foregroundRole(), pal.mid().color())
        self._placeholder.setPalette(pal)
        self._placeholder.setAlignment(QtCore.Qt.AlignHCenter)
        layout.addWidget(self._placeholder)
        self._placeholder.setVisible(True)

        # Initialize template manager from Templates directory
        this_dir = Path(__file__).resolve().parent
        self.templates_root = this_dir / "Templates"
        self.templates_root.mkdir(parents=True, exist_ok=True)
        self.tpl_mgr = _TemplateManager(self.templates_root)

    def clear(self) -> None:
        #self._placeholder.setVisible(True)
        self.web.setHtml("<html><body></body></html>")
        print("Cleared details panel")
        self._placeholder.setVisible(False)
        # force a repaint
        self.update()

    def set_object(self, obj: Dict[str, Any]) -> None:
        try:
            obj_class = obj.get("class")
            template_name = self.tpl_mgr.select_template_for_class(obj_class)
            html = self.tpl_mgr.render(template_name, {"obj": obj, "json": json})
            self.web.setHtml(html)
            self._placeholder.setVisible(False)
        except Exception:
            # Fallback to a simple JSON dump if rendering fails
            safe = QtWidgets.QLabel(json.dumps(obj, ensure_ascii=False, indent=2), self)
            safe.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            layout: QtWidgets.QVBoxLayout = self.layout()  # type: ignore[assignment]
            # Remove old web view content and show fallback
            self.web.setHtml("")
            layout.addWidget(safe)
            self._placeholder.setVisible(False)


