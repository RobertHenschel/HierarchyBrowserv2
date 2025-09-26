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
        self._placeholder.setVisible(False)
        # force a repaint
        self.update()

    def set_object(self, obj: Dict[str, Any], zoom_level: float = 1.0) -> None:
        try:
            obj_class = obj.get("class")
            template_name = self.tpl_mgr.select_template_for_class(obj_class)
            html = self.tpl_mgr.render(template_name, {"obj": obj, "json": json})
            
            # Inject CSS to scale font sizes based on zoom level
            base_font_size = 11  # Slightly larger base size for better readability in web view
            scaled_html = self._inject_zoom_css(html, base_font_size, zoom_level)
            
            self.web.setHtml(scaled_html)
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

    def _inject_zoom_css(self, html: str, base_font_size: float, zoom_level: float) -> str:
        """Inject CSS to scale font sizes consistently with the Qt UI"""
        try:
            # Calculate scaled font sizes
            body_size = base_font_size * zoom_level
            h1_size = (base_font_size * 1.4) * zoom_level  # Slightly larger than body
            
            # CSS to override template font sizes
            zoom_css = f"""
            <style>
            body {{ font-size: {body_size}px !important; }}
            h1 {{ font-size: {h1_size}px !important; }}
            .subtitle {{ font-size: {body_size}px !important; }}
            .key {{ font-size: {body_size}px !important; }}
            .mono {{ font-size: {body_size * 0.9}px !important; }}
            </style>
            """
            
            # Insert the CSS before the closing </head> tag
            if "</head>" in html:
                html = html.replace("</head>", zoom_css + "</head>")
            else:
                # If no head tag, insert at the beginning
                html = zoom_css + html
                
            return html
        except Exception:
            return html


