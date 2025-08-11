#!/usr/bin/env python3
import json
from typing import Any, Dict

from PyQt5 import QtCore, QtWidgets


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

        self.table = QtWidgets.QTableWidget(self)
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Property", "Value"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        layout.addWidget(self.table)

        self._placeholder = QtWidgets.QLabel("Select an item to see details", self)
        pal = self._placeholder.palette()
        pal.setColor(self._placeholder.foregroundRole(), pal.mid().color())
        self._placeholder.setPalette(pal)
        self._placeholder.setAlignment(QtCore.Qt.AlignHCenter)
        layout.addWidget(self._placeholder)
        self._placeholder.setVisible(True)

    def clear(self) -> None:
        self.table.setRowCount(0)
        self._placeholder.setVisible(True)

    def set_object(self, obj: Dict[str, Any]) -> None:
        self.table.setRowCount(0)
        keys = sorted(obj.keys())
        for key in keys:
            value = obj.get(key)
            row_index = self.table.rowCount()
            self.table.insertRow(row_index)

            key_item = QtWidgets.QTableWidgetItem(str(key))
            key_item.setFlags(key_item.flags() & ~QtCore.Qt.ItemIsEditable)
            self.table.setItem(row_index, 0, key_item)

            value_str = self._stringify_value(value)
            value_item = QtWidgets.QTableWidgetItem(value_str)
            value_item.setToolTip(self._stringify_value(value, truncate=False))
            value_item.setFlags(value_item.flags() & ~QtCore.Qt.ItemIsEditable)
            self.table.setItem(row_index, 1, value_item)

        self.table.resizeColumnsToContents()
        self._placeholder.setVisible(self.table.rowCount() == 0)

    @staticmethod
    def _stringify_value(value: Any, truncate: bool = True) -> str:
        try:
            if isinstance(value, (dict, list)):
                text = json.dumps(value, ensure_ascii=False)
            else:
                text = str(value)
        except Exception:
            text = "<unprintable>"
        if truncate and isinstance(text, str) and len(text) > 200:
            return text[:200] + "\u2026"
        return text


