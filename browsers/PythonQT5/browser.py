#!/usr/bin/env python3
import base64
import argparse
import json
import socket
import sys
from typing import Any, Dict, List, Optional

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import pyqtSignal

# Import breadcrumb bar from separate module
try:
    from .breadcrumbs import BreadcrumbBar  # type: ignore[import-not-found]
except Exception:
    # Fallback for direct script execution
    from breadcrumbs import BreadcrumbBar  # type: ignore[no-redef]

# Support running both as a module and as a standalone script
try:
    from .details_panel import DetailsPanel  # type: ignore[import-not-found]
    from .context_actions import execute_context_action  # type: ignore[import-not-found]
except Exception:
    # Fallback for `./browser.py` execution (no package context)
    import os as _os
    import sys as _sys
    _this_dir = _os.path.dirname(_os.path.abspath(__file__))
    if _this_dir not in _sys.path:
        _sys.path.insert(0, _this_dir)
    from details_panel import DetailsPanel  # type: ignore[no-redef]
    from context_actions import execute_context_action  # type: ignore[no-redef]


PROVIDER_HOST = "127.0.0.1"
PROVIDER_PORT = 8888

# Visual constants for consistent icon layout
ICON_BOX_PX = 64
ICON_IMAGE_PX = 48


def fetch_root_objects(host: Optional[str] = None, port: Optional[int] = None) -> List[Dict[str, Any]]:
    h = host or PROVIDER_HOST
    p = port or PROVIDER_PORT
    payload = {"method": "GetRootObjects"}
    message = json.dumps(payload, separators=(",", ":")) + "\n"
    with socket.create_connection((h, p), timeout=3) as s:
        s.sendall(message.encode("utf-8"))
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(16384)
            if not chunk:
                break
            buf += chunk
    if not buf:
        return []
    data = json.loads(buf.decode("utf-8").strip())
    return data.get("objects", [])


def fetch_info(host: Optional[str] = None, port: Optional[int] = None) -> Dict[str, Any]:
    h = host or PROVIDER_HOST
    p = port or PROVIDER_PORT
    payload = {"method": "GetInfo"}
    message = json.dumps(payload, separators=(",", ":")) + "\n"
    with socket.create_connection((h, p), timeout=3) as s:
        s.sendall(message.encode("utf-8"))
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(4096)
            if not chunk:
                break
            buf += chunk
    if not buf:
        return {}
    return json.loads(buf.decode("utf-8").strip())


def _trim_transparent_margins(image: QtGui.QImage) -> QtGui.QImage:
    # Convert to ARGB to reliably inspect alpha channel
    if image.format() != QtGui.QImage.Format_ARGB32:
        image = image.convertToFormat(QtGui.QImage.Format_ARGB32)
    width = image.width()
    height = image.height()
    left = width
    right = -1
    top = height
    bottom = -1
    for y in range(height):
        for x in range(width):
            if QtGui.QColor(image.pixel(x, y)).alpha() > 0:
                if x < left:
                    left = x
                if x > right:
                    right = x
                if y < top:
                    top = y
                if y > bottom:
                    bottom = y
    if right < left or bottom < top:
        # Entire image is fully transparent; return as-is
        return image
    rect = QtCore.QRect(left, top, right - left + 1, bottom - top + 1)
    return image.copy(rect)


def pixmap_from_base64(b64_png: str, size: int = 96) -> QtGui.QPixmap:
    try:
        raw = base64.b64decode(b64_png)
        image = QtGui.QImage.fromData(raw, "PNG")
        if image.isNull():
            return QtGui.QPixmap()
        # Normalize by trimming transparent borders so icons align visually
        image = _trim_transparent_margins(image)
        pix = QtGui.QPixmap.fromImage(image)
        if size:
            pix = pix.scaled(size, size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        return pix
    except Exception:
        return QtGui.QPixmap()


def add_badge_to_pixmap(pixmap: QtGui.QPixmap, count: int) -> QtGui.QPixmap:
    if count <= 0 or pixmap.isNull():
        return pixmap

    # Copy to preserve original
    composed = QtGui.QPixmap(pixmap)
    painter = QtGui.QPainter(composed)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)

    diameter = max(14, int(min(composed.width(), composed.height()) * 0.35))
    margin = max(2, int(diameter * 0.1))
    x = composed.width() - diameter - margin
    y = composed.height() - diameter - margin

    badge_color = QtGui.QColor("#cfe8ff")  # light pastel blue
    painter.setBrush(badge_color)
    painter.setPen(QtCore.Qt.NoPen)
    painter.drawEllipse(QtCore.QRectF(x, y, diameter, diameter))

    # Draw number text in black, centered in the circle
    painter.setPen(QtGui.QPen(QtCore.Qt.black))
    font = painter.font()
    font.setBold(True)
    # Scale font relative to badge; tweak for readability
    font.setPointSizeF(max(7.0, diameter * 0.45))
    painter.setFont(font)
    text = str(count if count < 100 else "99+")
    painter.drawText(QtCore.QRectF(x, y, diameter, diameter), QtCore.Qt.AlignCenter, text)
    painter.end()
    return composed


class ObjectItemWidget(QtWidgets.QWidget):
    activated = pyqtSignal(dict)
    clicked = pyqtSignal(dict)
    contextActionRequested = pyqtSignal(dict, dict)

    def __init__(self, obj: Dict[str, Any], parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("objectItemWidget")
        self.setToolTip(obj.get("class", ""))
        self._obj = obj
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        layout.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignHCenter)

        icon_label = QtWidgets.QLabel(self)
        icon_label.setAlignment(QtCore.Qt.AlignCenter)
        icon_label.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        icon_label.setFixedSize(ICON_BOX_PX, ICON_BOX_PX)

        title_label = QtWidgets.QLabel(self)
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        title_label.setWordWrap(True)
        title_label.setText(obj.get("title", ""))
        title_label.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)

        # Determine object count and underline folder-like items
        try:
            objects_count = int(obj.get("objects", 0))
        except Exception:
            objects_count = 0
        title_font = title_label.font()
        title_font.setUnderline(objects_count > 0)
        title_label.setFont(title_font)

        # Visual affordance for clickable folder-like items
        if objects_count > 0:
            self.setCursor(QtCore.Qt.PointingHandCursor)

        icon_b64 = obj.get("icon") or ""
        pix = pixmap_from_base64(icon_b64, size=ICON_IMAGE_PX)
        pix = add_badge_to_pixmap(pix, objects_count)
        if not pix.isNull():
            icon_label.setPixmap(pix)

        # Add widgets to layout (ensure they are children so they render)
        layout.addWidget(icon_label, alignment=QtCore.Qt.AlignHCenter)
        layout.addWidget(title_label, alignment=QtCore.Qt.AlignHCenter)
        # Base, non-selected visual so selection doesn't shift layout
        self.setStyleSheet("border: 1px solid transparent; border-radius: 6px;")

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:  # type: ignore[override]

        self.activated.emit(self._obj)
        super().mouseDoubleClickEvent(event)

    def set_selected(self, selected: bool) -> None:
        if selected:
            self.setStyleSheet("border: 1px solid #007aff; border-radius: 6px; background-color: rgba(0, 122, 255, 0.08);")
        else:
            self.setStyleSheet("border: 1px solid transparent; border-radius: 6px; background-color: transparent;")

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # type: ignore[override]
        self.clicked.emit(self._obj)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event: QtGui.QContextMenuEvent) -> None:  # type: ignore[override]
        # Ensure right-click also selects the item and updates details panel
        self.clicked.emit(self._obj)
        menu_spec = self._obj.get("contextmenu")
        if not isinstance(menu_spec, list) or len(menu_spec) == 0:
            return
        # Use a parentless menu so it doesn't inherit the tile's stylesheet
        menu = QtWidgets.QMenu()
        menu.setStyleSheet("")
        for entry in menu_spec:
            if not isinstance(entry, dict):
                continue
            title = entry.get("title")
            if not isinstance(title, str) or not title:
                continue
            action = menu.addAction(title)
            # Capture entry and cursor position for feedback
            action.triggered.connect(lambda _=False, e=entry, pos=event.globalPos(): self._on_context_action(e, pos))
        if not menu.isEmpty():
            menu.exec_(event.globalPos())
            

    def _on_context_action(self, entry: Dict[str, Any], pos: QtCore.QPoint) -> None:
        # Emit for higher-level handling and execute the action
        self.contextActionRequested.emit(self._obj, entry)
        execute_context_action(self, entry, pos)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Hierarchy Browser")
        self.resize(720, 480)
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self)
        self.setCentralWidget(splitter)

        # Left side: breadcrumb + grid in a scroll area
        left_panel = QtWidgets.QWidget(splitter)
        left_layout = QtWidgets.QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self.breadcrumb = BreadcrumbBar(left_panel)
        self.breadcrumb.crumbClicked.connect(self.on_breadcrumb_clicked)
        left_layout.addWidget(self.breadcrumb)

        self.nav_stack: List[Dict[str, str]] = []
        # Persist the endpoint used to load data for this window
        self.root_host: str = PROVIDER_HOST
        self.root_port: int = PROVIDER_PORT
        self.current_host: str = self.root_host
        self.current_port: int = self.root_port
        self.selected_item: ObjectItemWidget | None = None

        scroll = QtWidgets.QScrollArea(left_panel)
        scroll.setWidgetResizable(True)
        left_layout.addWidget(scroll)

        grid_host = QtWidgets.QWidget()
        grid_layout = QtWidgets.QGridLayout(grid_host)
        grid_layout.setContentsMargins(12, 12, 12, 12)
        grid_layout.setHorizontalSpacing(18)
        grid_layout.setVerticalSpacing(12)
        scroll.setWidget(grid_host)

        splitter.addWidget(left_panel)

        # Right side: details panel, visible at startup
        self.details_panel = DetailsPanel(splitter)
        splitter.addWidget(self.details_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([500, 300])

        # Fetch info for root name and populate
        info = {}
        try:
            info = fetch_info()
        except Exception:
            info = {}
        root_name = info.get("RootName") if isinstance(info, dict) else None
        self.root_name = str(root_name) if root_name else "Root"
        self.breadcrumb.set_path([self.root_name])

        self.grid_layout = grid_layout
        self.load_root(self.root_host, self.root_port)

    def clear_grid(self) -> None:
        # Reset selection because existing widgets will be deleted
        self.selected_item = None
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def populate_objects(self, objects: List[Dict[str, Any]]) -> None:
        self.clear_grid()
        columns = 4
        row = 0
        col = 0
        for obj in objects:
            widget = ObjectItemWidget(obj)
            widget.activated.connect(self.on_item_activated)
            widget.clicked.connect(self.on_item_clicked)
            self.grid_layout.addWidget(widget, row, col, alignment=QtCore.Qt.AlignTop | QtCore.Qt.AlignHCenter)
            col += 1
            if col >= columns:
                col = 0
                row += 1

    def load_root(self, host: Optional[str] = None, port: Optional[int] = None) -> None:
        objects = []
        try:
            objects = fetch_root_objects(host, port)
        except Exception:
            objects = []
        self.populate_objects(objects)
        if host is not None:
            self.current_host = host
        if port is not None:
            self.current_port = port

    def load_children(self, object_id: str, host: Optional[str] = None, port: Optional[int] = None) -> None:
        data: Dict[str, Any] = {}
        try:
            data = fetch_objects_for_id(object_id, host, port)
        except Exception:
            data = {}
        objects = data.get("objects", []) if isinstance(data, dict) else []
        self.populate_objects(objects)

    def on_item_activated(self, obj: Dict[str, Any]) -> None:
        try:
            objects_count = int(obj.get("objects", 0))
        except Exception:
            objects_count = 0
        object_id = obj.get("id")
        title = obj.get("title")
        if not isinstance(object_id, str) or not isinstance(title, str):
            return
        # Determine next endpoint from optional openaction
        next_host: str = self.current_host
        next_port: int = self.current_port
        open_action = None
        try:
            open_action = obj.get("openaction")
            if isinstance(open_action, list) and open_action:
                for entry in open_action:
                    if not isinstance(entry, dict):
                        continue
                    act = str(entry.get("action", "")).lower()
                    if act == "objectbrowser":
                        candidate_host = entry.get("hostname") or entry.get("host")
                        if isinstance(candidate_host, str) and candidate_host:
                            next_host = candidate_host
                        try:
                            next_port = int(entry.get("port")) if entry.get("port") is not None else next_port
                        except Exception:
                            pass
                        break
        except Exception:
            pass
        if open_action is None and objects_count == 0:
            return
        # Push into stack and navigate using next endpoint
        self.nav_stack.append({"id": object_id, "title": title, "host": next_host, "port": str(next_port)})
        self.breadcrumb.set_path([self.root_name] + [e["title"] for e in self.nav_stack])
        self.current_host, self.current_port = next_host, next_port
        self.load_children(object_id, next_host, next_port)

    def on_item_clicked(self, obj: Dict[str, Any]) -> None:
        sender = self.sender()
        if not isinstance(sender, ObjectItemWidget):
            return
        if self.selected_item is sender:
            return
        if self.selected_item is not None:
            try:
                self.selected_item.set_selected(False)
            except RuntimeError:
                # Previously selected widget was already deleted by a reload
                pass
        sender.set_selected(True)
        self.selected_item = sender
        # Populate details panel with selected object's properties
        self.details_panel.set_object(obj)

    def on_breadcrumb_clicked(self, index: int) -> None:
        # index 0 is root
        if index <= 0:
            self.nav_stack = []
            self.breadcrumb.set_path([self.root_name])
            self.current_host, self.current_port = self.root_host, self.root_port
            self.load_root(self.root_host, self.root_port)
            return
        # Navigate to a depth
        depth = index  # since root occupies 0
        if depth - 1 < len(self.nav_stack):
            self.nav_stack = self.nav_stack[: depth]
        target = self.nav_stack[depth - 1]
        target_id = target["id"]
        target_host = target.get("host") or self.root_host
        try:
            target_port = int(target.get("port")) if target.get("port") is not None else self.root_port
        except Exception:
            target_port = self.root_port
        self.breadcrumb.set_path([self.root_name] + [e["title"] for e in self.nav_stack])
        self.current_host, self.current_port = target_host, target_port
        self.load_children(target_id, target_host, target_port)


def fetch_objects_for_id(object_id: str, host: Optional[str] = None, port: Optional[int] = None) -> Dict[str, Any]:
    h = host or PROVIDER_HOST
    p = port or PROVIDER_PORT
    payload = {"method": "GetObjects", "id": object_id}
    message = json.dumps(payload, separators=(",", ":")) + "\n"
    with socket.create_connection((h, p), timeout=3) as s:
        s.sendall(message.encode("utf-8"))
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(16384)
            if not chunk:
                break
            buf += chunk
    if not buf:
        return {}
    return json.loads(buf.decode("utf-8").strip())



def main() -> None:
    global PROVIDER_HOST, PROVIDER_PORT
    parser = argparse.ArgumentParser(description="Hierarchy Browser (Qt5)")
    parser.add_argument("--host", default=PROVIDER_HOST, help="Provider host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=PROVIDER_PORT, help="Provider port (default: 8888)")
    args, unknown = parser.parse_known_args()
    PROVIDER_HOST = args.host
    PROVIDER_PORT = args.port

    app = QtWidgets.QApplication([sys.argv[0]] + unknown)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()


