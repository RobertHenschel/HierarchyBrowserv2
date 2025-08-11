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

        icon_b64 = obj.get("icon") or ""
        pix = pixmap_from_base64(icon_b64, size=48)
        if not pix.isNull():
            icon_label.setPixmap(pix)

        layout.addWidget(icon_label, alignment=QtCore.Qt.AlignHCenter)
        layout.addWidget(title_label, alignment=QtCore.Qt.AlignHCenter)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Hierarchy Browser")
        self.resize(720, 480)
        container = QtWidgets.QWidget(self)
        self.setCentralWidget(container)

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
        outer.addWidget(scroll)

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


