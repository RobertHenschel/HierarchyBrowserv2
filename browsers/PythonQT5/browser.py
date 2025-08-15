#!/usr/bin/env python3
import base64
import argparse
import json
import socket
import sys
from typing import Any, Dict, List, Optional, Callable
from pathlib import Path

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
    from .toolbar import ObjectToolbar  # type: ignore[import-not-found]
except Exception:
    # Fallback for `./browser.py` execution (no package context)
    import os as _os
    import sys as _sys
    _this_dir = _os.path.dirname(_os.path.abspath(__file__))
    if _this_dir not in _sys.path:
        _sys.path.insert(0, _this_dir)
    from details_panel import DetailsPanel  # type: ignore[no-redef]
    from context_actions import execute_context_action  # type: ignore[no-redef]
    from toolbar import ObjectToolbar  # type: ignore[no-redef]
    from toolbar import ObjectToolbar  # type: ignore[no-redef]


# Allow importing shared provider models when running directly
_THIS = Path(__file__).resolve()
_PROJECT_ROOT = _THIS.parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Import shared object model (provider and browser share these classes)
try:
    from providers.base import ProviderObject  # type: ignore[import-not-found]
    from providers.Slurm.model import (
        WPSlurmPartition,
        WPSlurmJob,
        WPSlurmJobGroup,
    )  # type: ignore[import-not-found]
    from providers.Modules.model import (
        WPLmodDependency,
        WPLmodSoftware,
    )  # type: ignore[import-not-found]
    from providers.HomeDirectory.model import (
        WPDirectory,
        WPFile,
    )  # type: ignore[import-not-found]
    from providers.ResearchComputingAtIU.model import (
        WPObject as RCIU_WPObject,
    )  # type: ignore[import-not-found]
    from providers.base import WPGroup  # type: ignore[import-not-found]
except Exception:
    ProviderObject = None  # type: ignore[assignment]
    WPSlurmPartition = None  # type: ignore[assignment]
    WPSlurmJob = None  # type: ignore[assignment]
    WPSlurmJobGroup = None  # type: ignore[assignment]
    WPLmodDependency = None  # type: ignore[assignment]
    WPLmodSoftware = None  # type: ignore[assignment]
    WPDirectory = None  # type: ignore[assignment]
    WPFile = None  # type: ignore[assignment]
    RCIU_WPObject = None  # type: ignore[assignment]
    WPGroup = None  # type: ignore[assignment]

PROVIDER_HOST = "127.0.0.1"
PROVIDER_PORT = 8888

# Visual constants for consistent icon layout
ICON_BOX_PX = 64
ICON_IMAGE_PX = 48


def fetch_root_objects(host: Optional[str] = None, port: Optional[int] = None) -> List[Any]:
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
    raw_objects = data.get("objects", [])
    # Convert to shared typed objects
    return _to_typed_objects(raw_objects)


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

    def __init__(
        self,
        obj: Dict[str, Any],
        parent: QtWidgets.QWidget | None = None,
        icon_lookup: Optional[Callable[[str], QtGui.QPixmap]] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("objectItemWidget")
        self.setToolTip(obj.get("class", ""))
        self._obj = obj
        self._icon_lookup = icon_lookup
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

        # Resolve icon via filename provided in object payload
        pix = QtGui.QPixmap()
        icon_spec = obj.get("icon")
        if isinstance(icon_spec, str) and self._icon_lookup is not None:
            try:
                pix = self._icon_lookup(icon_spec)
            except Exception:
                pix = QtGui.QPixmap()
        # Fallback for legacy providers that still send base64 bitstreams
        if pix.isNull() and isinstance(icon_spec, str) and len(icon_spec) > 64:
            pix = pixmap_from_base64(icon_spec, size=ICON_IMAGE_PX)
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

        # Toolbar directly below breadcrumb
        toolbar = ObjectToolbar(left_panel)
        toolbar.action_group.setToolTip("Group")
        toolbar.action_group.triggered.connect(self.on_group_action_triggered)
        toolbar.get_state = lambda: (self.nav_stack, self.current_host, self.current_port)
        left_layout.addWidget(toolbar)

        self.nav_stack: List[Dict[str, str]] = []
        # Persist the endpoint used to load data for this window
        self.root_host: str = PROVIDER_HOST
        self.root_port: int = PROVIDER_PORT
        self.current_host: str = self.root_host
        self.current_port: int = self.root_port
        self.selected_item: ObjectItemWidget | None = None
        self.current_objects: List[Dict[str, Any]] = []

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

        # Fetch info for root name and icons, then populate
        info = {}
        try:
            info = fetch_info()
        except Exception:
            info = {}
        root_name = info.get("RootName") if isinstance(info, dict) else None
        self.root_name = str(root_name) if root_name else "Root"
        self.breadcrumb.set_path([self.root_name])

        # Decode and store icons announced by provider
        self.icon_store: Dict[str, QtGui.QPixmap] = {}
        self.add_icons_from_info(info)

        self.grid_layout = grid_layout
        self.load_root(self.root_host, self.root_port)

    def navigate_to_path(self, full_path: str) -> None:
        # Expected: /[host:port]/seg/... with optional multiple [host:port] mid-path
        path = full_path.strip()
        if not path.startswith("/"):
            path = "/" + path

        def _is_host_token(seg: str) -> bool:
            return seg.startswith("[") and seg.endswith("]") and len(seg) > 2

        def _parse_host_token(seg: str) -> tuple[Optional[str], Optional[int]]:
            inner = seg[1:-1]
            if ":" in inner:
                h, p = inner.split(":", 1)
                try:
                    return h, int(p)
                except Exception:
                    return h, None
            return inner, None

        current_id = "/"
        segs = [s for s in path.split("/") if s != ""]
        processed_any = False
        for seg in segs:
            if _is_host_token(seg):
                # Switch provider
                h, p = _parse_host_token(seg)
                if isinstance(h, str) and h:
                    new_host = h
                else:
                    new_host = self.root_host
                new_port = self.root_port
                if isinstance(p, int):
                    new_port = p
                if new_host != self.current_host or new_port != self.current_port:
                    # Load info for root name and icons on new endpoint
                    try:
                        info = fetch_info(new_host, new_port)
                        root_name = info.get("RootName") if isinstance(info, dict) else None
                        self.add_icons_from_info(info)
                    except Exception:
                        pass
                    # First provider in path: replace root; subsequent: append a crumb for the new provider root
                    if not processed_any and len(self.nav_stack) == 0:
                        if isinstance(root_name, str) and root_name:
                            self.root_name = root_name
                        self.nav_stack = []
                        self.breadcrumb.set_path([self.root_name])
                    else:
                        title = root_name if isinstance(root_name, str) and root_name else f"{new_host}:{new_port}"
                        self.nav_stack.append({
                            "id": "/",
                            "title": title,
                            "host": new_host,
                            "port": str(new_port),
                            "remote_id": "/",
                        })
                        self.breadcrumb.set_path([self.root_name] + [e["title"] for e in self.nav_stack])
                    self.current_host, self.current_port = new_host, new_port
                    self.load_root(self.current_host, self.current_port)
                current_id = "/"
                continue

            # Normal path segment: traverse
            data = fetch_objects_for_id(current_id, self.current_host, self.current_port)
            children = data.get("objects", []) if isinstance(data, dict) else []
            match = None
            for o in children:
                od = _obj_to_dict(o)
                oid = od.get("id")
                title = od.get("title")
                if isinstance(oid, str) and oid.rstrip("/").endswith("/" + seg):
                    match = od
                    break
                if isinstance(title, str) and title == seg:
                    match = od
                    break
            if not match:
                break
            try:
                objects_count = int(match.get("objects", 0))
            except Exception:
                objects_count = 0
            object_id = match.get("id")
            title = match.get("title")
            if not isinstance(object_id, str) or not isinstance(title, str):
                break
            self.nav_stack.append({"id": object_id, "title": title, "host": self.current_host, "port": str(self.current_port), "remote_id": object_id})
            self.breadcrumb.set_path([self.root_name] + [e["title"] for e in self.nav_stack])
            processed_any = True
            if objects_count == 0:
                break
            current_id = object_id
            self.load_children(current_id, self.current_host, self.current_port)

    def clear_grid(self) -> None:
        # Reset selection because existing widgets will be deleted
        self.selected_item = None
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def populate_objects(self, objects: List[Any]) -> None:
        self.clear_grid()
        # Keep a copy of the raw objects currently displayed for toolbar actions
        try:
            self.current_objects = list(objects)
        except Exception:
            self.current_objects = []
        columns = 4
        row = 0
        col = 0
        for obj in objects:
            widget = ObjectItemWidget(_obj_to_dict(obj), icon_lookup=self.get_icon_pixmap)
            widget.activated.connect(self.on_item_activated)
            widget.clicked.connect(self.on_item_clicked)
            self.grid_layout.addWidget(widget, row, col, alignment=QtCore.Qt.AlignTop | QtCore.Qt.AlignHCenter)
            col += 1
            if col >= columns:
                col = 0
                row += 1

    def get_icon_pixmap(self, icon_filename: str) -> QtGui.QPixmap:
        # Normalize key to the expected './resources/Name.png' form used by providers
        if not isinstance(icon_filename, str):
            return QtGui.QPixmap()
        key = icon_filename
        return self.icon_store.get(key, QtGui.QPixmap())

    def add_icons_from_info(self, info: Dict[str, Any]) -> None:
        try:
            icons = info.get("icons", []) if isinstance(info, dict) else []
            if not isinstance(icons, list):
                return
            for item in icons:
                if not isinstance(item, dict):
                    continue
                filename = item.get("filename")
                data = item.get("data")
                if not isinstance(filename, str) or not isinstance(data, str):
                    continue
                pix = pixmap_from_base64(data, size=ICON_IMAGE_PX)
                if not pix.isNull():
                    # Merge into existing store; overwrites if same key
                    self.icon_store[filename] = pix
        except Exception:
            # Keep existing cache on any parsing error
            pass

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
        # Determine remote id: if switching endpoints, start at root "/"
        switching = (next_host != self.current_host) or (next_port != self.current_port)
        remote_id = "/" if switching else object_id
        # Push into stack and navigate using next endpoint
        self.nav_stack.append({"id": object_id, "title": title, "host": next_host, "port": str(next_port), "remote_id": remote_id})
        self.breadcrumb.set_path([self.root_name] + [e["title"] for e in self.nav_stack])
        # If switching to a different provider endpoint, fetch its info and merge icons
        switching = (next_host != self.current_host) or (next_port != self.current_port)
        self.current_host, self.current_port = next_host, next_port
        if switching:
            try:
                info = fetch_info(self.current_host, self.current_port)
                self.add_icons_from_info(info)
            except Exception:
                pass
        self.load_children(remote_id, next_host, next_port)

    def _get_current_path(self) -> str:
        if not self.nav_stack:
            return "/"
        tail = self.nav_stack[-1]
        # Prefer remote_id because it reflects path on current provider
        path = tail.get("remote_id") or tail.get("id") or "/"
        if not isinstance(path, str) or not path:
            return "/"
        return path

    def on_group_action_triggered(self) -> None:
        # Collect all properties present in the currently displayed objects
        props: set[str] = set()
        for obj in self.current_objects:
            as_dict = _obj_to_dict(obj)
            if isinstance(as_dict, dict):
                for k in as_dict.keys():
                    if isinstance(k, str):
                        props.add(k)
        # Exclude core fields that shouldn't be used for grouping
        reserved = {"class", "id", "title", "icon", "objects"}
        candidates = sorted(p for p in props if p not in reserved)
        if not candidates:
            return
        menu = QtWidgets.QMenu(self)
        for prop in candidates:
            action = menu.addAction(prop)
            action.triggered.connect(lambda _=False, p=prop: self._group_by_property(p))
        menu.exec_(QtGui.QCursor.pos())

    def _group_by_property(self, prop: str) -> None:
        base_path = self._get_current_path()
        target_path = base_path.rstrip("/") + f"/<GroupBy:{prop}>"
        self.load_children(target_path, self.current_host, self.current_port)

    # Deep link building moved into toolbar.py

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
        self.details_panel.set_object(_obj_to_dict(obj))

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
        target_remote_id = target.get("remote_id") or target_id
        target_host = target.get("host") or self.root_host
        try:
            target_port = int(target.get("port")) if target.get("port") is not None else self.root_port
        except Exception:
            target_port = self.root_port
        self.breadcrumb.set_path([self.root_name] + [e["title"] for e in self.nav_stack])
        self.current_host, self.current_port = target_host, target_port
        self.load_children(target_remote_id, target_host, target_port)


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
    data = json.loads(buf.decode("utf-8").strip())
    if isinstance(data, dict) and isinstance(data.get("objects"), list):
        data = {"objects": _to_typed_objects(data["objects"]) }
    return data


def _to_typed_objects(raw_objects: List[Dict[str, Any]]) -> List[Any]:
    """Map incoming dicts to shared typed objects and keep them as objects."""
    typed: List[Any] = []
    for obj in raw_objects:
        if not isinstance(obj, dict):
            continue
        cls_name = obj.get("class")
        try:
            if cls_name == "WPSlurmPartition" and WPSlurmPartition is not None:
                inst = WPSlurmPartition(
                    id=str(obj.get("id", "")),
                    title=str(obj.get("title", "")),
                    icon=obj.get("icon"),
                    objects=int(obj.get("objects", 0)),
                )
                typed.append(inst)
            elif cls_name == "WPSlurmJob" and WPSlurmJob is not None:
                inst = WPSlurmJob(
                    id=str(obj.get("id", "")),
                    title=str(obj.get("title", "")),
                    icon=obj.get("icon"),
                    objects=int(obj.get("objects", 0)),
                    jobarray=bool(obj.get("jobarray", False)),
                    userid=obj.get("userid"),
                    nodecount=int(obj.get("nodecount", 0)),
                    jobstate=obj.get("jobstate"),
                )
                typed.append(inst)
            elif cls_name == "WPSlurmJobGroup" and WPSlurmJobGroup is not None:
                inst = WPSlurmJobGroup(
                    id=str(obj.get("id", "")),
                    title=str(obj.get("title", "")),
                    icon=obj.get("icon"),
                    objects=int(obj.get("objects", 0)),
                )
                typed.append(inst)
            elif cls_name == "WPDirectory" and WPDirectory is not None:
                inst = WPDirectory(
                    id=str(obj.get("id", "")),
                    title=str(obj.get("title", "")),
                    icon=obj.get("icon"),
                    objects=int(obj.get("objects", 0)),
                    owner=obj.get("owner"),
                    group=obj.get("group"),
                )
                typed.append(inst)
            elif cls_name == "WPFile" and WPFile is not None:
                inst = WPFile(
                    id=str(obj.get("id", "")),
                    title=str(obj.get("title", "")),
                    icon=obj.get("icon"),
                    objects=int(obj.get("objects", 0)),
                    owner=obj.get("owner"),
                    group=obj.get("group"),
                )
                typed.append(inst)
            elif cls_name == "WPLmodDependency" and WPLmodDependency is not None:
                inst = WPLmodDependency(
                    id=str(obj.get("id", "")),
                    title=str(obj.get("title", "")),
                    icon=obj.get("icon"),
                    objects=int(obj.get("objects", 0)),
                )
                typed.append(inst)
            elif cls_name == "WPLmodSoftware" and WPLmodSoftware is not None:
                inst = WPLmodSoftware(
                    id=str(obj.get("id", "")),
                    title=str(obj.get("title", "")),
                    icon=obj.get("icon"),
                    objects=int(obj.get("objects", 0)),
                )
                typed.append(inst)
            elif cls_name == "WPGroup" and WPGroup is not None:
                inst = WPGroup(
                    id=str(obj.get("id", "")),
                    title=str(obj.get("title", "")),
                    icon=obj.get("icon"),
                    objects=int(obj.get("objects", 0)),
                )
                typed.append(inst)
            elif cls_name == "WPObject" and RCIU_WPObject is not None:
                extra = {k: v for k, v in obj.items() if k not in {"class", "id", "title", "icon", "objects"}}
                inst = RCIU_WPObject(
                    id=str(obj.get("id", "")),
                    title=str(obj.get("title", "")),
                    icon=obj.get("icon"),
                    objects=int(obj.get("objects", 0)),
                    extra=extra,
                )
                typed.append(inst)
            else:
                typed.append(obj)
        except Exception:
            typed.append(obj)
    return typed


def _obj_to_dict(obj: Any) -> Dict[str, Any]:
    """Convert a typed ProviderObject (or plain dict) to a JSON-friendly dict for UI.

    If the object exposes to_dict(), use it; otherwise return as-is if it's already a dict.
    """
    try:
        if hasattr(obj, "to_dict") and callable(getattr(obj, "to_dict")):
            return obj.to_dict()  # type: ignore[return-value]
    except Exception:
        pass
    return obj if isinstance(obj, dict) else {}



def main() -> None:
    global PROVIDER_HOST, PROVIDER_PORT
    parser = argparse.ArgumentParser(description="Hierarchy Browser (Qt5)")
    parser.add_argument("--host", default=PROVIDER_HOST, help="Provider host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=PROVIDER_PORT, help="Provider port (default: 8888)")
    parser.add_argument("--path", default=None, help="Navigation path: /[host:port]/segment/segment")
    args, unknown = parser.parse_known_args()
    PROVIDER_HOST = args.host
    PROVIDER_PORT = args.port

    app = QtWidgets.QApplication([sys.argv[0]] + unknown)
    win = MainWindow()
    win.show()
    # Optional deep-link navigation
    if isinstance(args.path, str) and args.path:
        try:
            win.navigate_to_path(args.path)
        except Exception:
            pass
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()


