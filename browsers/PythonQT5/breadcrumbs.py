#!/usr/bin/env python3
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import pyqtSignal


class BreadcrumbBar(QtWidgets.QWidget):
    crumbClicked = pyqtSignal(int)

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

    def set_path(self, parts: list[str]) -> None:
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
            label.setCursor(QtCore.Qt.PointingHandCursor)
            # Capture index for click
            def handler(i: int) -> None:
                self.crumbClicked.emit(i)
            label.mousePressEvent = (lambda e, i=idx: handler(i))  # type: ignore[assignment]
            self._h.addWidget(label)
            if idx != len(parts) - 1:
                sep = QtWidgets.QLabel("›", self)
                self._h.addWidget(sep)
        self._h.addStretch(1)


