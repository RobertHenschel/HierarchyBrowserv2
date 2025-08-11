#!/usr/bin/env python3
import base64
import json
import socket
import sys
from typing import Any, Dict, List

from PyQt5 import QtCore, QtGui, QtWidgets


PROVIDER_HOST = "127.0.0.1"
PROVIDER_PORT = 8888


def fetch_root_objects(host: str = PROVIDER_HOST, port: int = PROVIDER_PORT) -> List[Dict[str, Any]]:
    payload = {"method": "GetRootObjects"}
    message = json.dumps(payload, separators=(",", ":")) + "\n"
    with socket.create_connection((host, port), timeout=3) as s:
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


def fetch_info(host: str = PROVIDER_HOST, port: int = PROVIDER_PORT) -> Dict[str, Any]:
    payload = {"method": "GetInfo"}
    message = json.dumps(payload, separators=(",", ":")) + "\n"
    with socket.create_connection((host, port), timeout=3) as s:
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


def pixmap_from_base64(b64_png: str, size: int = 96) -> QtGui.QPixmap:
    try:
        raw = base64.b64decode(b64_png)
        image = QtGui.QImage.fromData(raw, "PNG")
        if image.isNull():
            return QtGui.QPixmap()
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
    def __init__(self, obj: Dict[str, Any], parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setToolTip(obj.get("class", ""))
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        layout.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignHCenter)

        icon_label = QtWidgets.QLabel(self)
        icon_label.setAlignment(QtCore.Qt.AlignCenter)
        icon_label.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)

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

        icon_b64 = obj.get("icon") or ""
        pix = pixmap_from_base64(icon_b64, size=48)
        pix = add_badge_to_pixmap(pix, objects_count)
        if not pix.isNull():
            icon_label.setPixmap(pix)

        layout.addWidget(icon_label, alignment=QtCore.Qt.AlignHCenter)
        layout.addWidget(title_label, alignment=QtCore.Qt.AlignHCenter)


class BreadcrumbBar(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(6)
        self._container = QtWidgets.QWidget(self)
        self._h = QtWidgets.QHBoxLayout(self._container)
        self._h.setContentsMargins(0, 0, 0, 0)
        self._h.setSpacing(6)
        layout.addWidget(self._container)
        # Visual hint like a very flat toolbar
        self.setAutoFillBackground(True)
        pal = self.palette()
        pal.setColor(self.backgroundRole(), pal.window().color().lighter(102))
        self.setPalette(pal)
        self.setFixedHeight(28)

    def set_path(self, parts: List[str]) -> None:
        # Clear
        while self._h.count():
            item = self._h.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        # Build new crumbs
        for idx, part in enumerate(parts):
            label = QtWidgets.QLabel(part, self)
            font = label.font()
            font.setBold(idx == 0)
            label.setFont(font)
            self._h.addWidget(label)
            if idx != len(parts) - 1:
                sep = QtWidgets.QLabel("›", self)
                self._h.addWidget(sep)
        self._h.addStretch(1)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Hierarchy Browser")
        self.resize(720, 480)
        container = QtWidgets.QWidget(self)
        self.setCentralWidget(container)

        # Breadcrumb bar at the very top
        self.breadcrumb = BreadcrumbBar(container)

        scroll = QtWidgets.QScrollArea(container)
        scroll.setWidgetResizable(True)

        grid_host = QtWidgets.QWidget()
        grid_layout = QtWidgets.QGridLayout(grid_host)
        grid_layout.setContentsMargins(12, 12, 12, 12)
        grid_layout.setHorizontalSpacing(18)
        grid_layout.setVerticalSpacing(12)

        scroll.setWidget(grid_host)

        outer = QtWidgets.QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self.breadcrumb)
        outer.addWidget(scroll)

        # Fetch info for root name and populate
        info = {}
        try:
            info = fetch_info()
        except Exception:
            info = {}
        root_name = info.get("RootName") if isinstance(info, dict) else None
        self.breadcrumb.set_path([str(root_name) if root_name else "Root"])

        self.populate_grid(grid_layout)

    def populate_grid(self, grid_layout: QtWidgets.QGridLayout) -> None:
        objects = fetch_root_objects()
        columns = 4
        row = 0
        col = 0
        for obj in objects:
            widget = ObjectItemWidget(obj)
            grid_layout.addWidget(widget, row, col, alignment=QtCore.Qt.AlignTop | QtCore.Qt.AlignHCenter)
            col += 1
            if col >= columns:
                col = 0
                row += 1


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()


