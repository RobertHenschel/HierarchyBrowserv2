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
    with socket.create_connection((h, p), timeout=10) as s:
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
    with socket.create_connection((h, p), timeout=10) as s:
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

    diameter = max(22, int(min(composed.width(), composed.height()) * 0.35))
    margin = 0  # keep tight to the corner for consistency

    # Configure text styling
    painter.setPen(QtGui.QPen(QtCore.Qt.black))
    font = painter.font()
    font.setBold(True)
    font.setPointSizeF(max(9.0, diameter * 0.50))
    painter.setFont(font)

    text = str(count)
    fm = painter.fontMetrics()
    text_width = fm.horizontalAdvance(text)

    # Create a horizontally expanding ellipse (pill) so full number fits
    horizontal_padding = max(8, int(diameter * 0.30))
    badge_width = max(diameter, text_width + 2 * horizontal_padding)

    x = composed.width() - badge_width - margin
    y = composed.height() - diameter - margin

    # Draw ellipse background
    badge_color = QtGui.QColor("#cfe8ff")  # light pastel blue
    painter.setBrush(badge_color)
    painter.setPen(QtCore.Qt.NoPen)
    painter.drawEllipse(QtCore.QRectF(x, y, badge_width, diameter))

    # Draw number text in black, centered within ellipse
    painter.setPen(QtGui.QPen(QtCore.Qt.black))
    painter.drawText(QtCore.QRectF(x, y, badge_width, diameter), QtCore.Qt.AlignCenter, text)
    painter.end()
    return composed


class ObjectItemWidget(QtWidgets.QWidget):
    activated = pyqtSignal(dict)
    clicked = pyqtSignal(dict)
    pressed = pyqtSignal(dict)
    contextActionRequested = pyqtSignal(dict, dict)

    def __init__(
        self,
        obj: Dict[str, Any],
        parent: QtWidgets.QWidget | None = None,
        icon_lookup: Optional[Callable[[str], QtGui.QPixmap]] = None,
        zoom_level: float = 1.0,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("objectItemWidget")
        self.setToolTip(obj.get("class", ""))
        self._obj = obj
        self._icon_lookup = icon_lookup
        self._click_timer: Optional[QtCore.QTimer] = None
        # Ensure stylesheet backgrounds/borders are painted on QWidget
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        layout.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignHCenter)

        icon_label = QtWidgets.QLabel(self)
        icon_label.setAlignment(QtCore.Qt.AlignCenter)
        icon_label.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        icon_label.setFixedSize(ICON_BOX_PX, ICON_BOX_PX)
        icon_label.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        icon_label.setStyleSheet("border: none; background: transparent;")

        title_label = QtWidgets.QLabel(self)
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        title_label.setWordWrap(True)
        title_label.setText(obj.get("title", ""))
        title_label.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        title_label.setStyleSheet("border: none; background: transparent;")
        title_label.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)

        # Determine object count and underline folder-like items
        try:
            objects_count = int(obj.get("objects", 0))
        except Exception:
            objects_count = 0
        title_font = title_label.font()
        title_font.setUnderline(objects_count > 0)
        # Apply zoom to font size
        base_size = 9.0  # Base font size
        title_font.setPointSizeF(base_size * zoom_level)
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
        # Keep reference for selection styling
        self._title_label = title_label
        # Base, unselected visual so selection doesn't shift layout
        self.setStyleSheet("border: 2px solid transparent; border-radius: 8px; background-color: transparent;")

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:  # type: ignore[override]
        # Cancel pending single-click if it hasn't fired yet
        try:
            if self._click_timer is not None:
                self._click_timer.stop()
                self._click_timer.deleteLater()
        except Exception:
            pass
        self._click_timer = None
        self.activated.emit(self._obj)
        super().mouseDoubleClickEvent(event)

    def set_selected(self, selected: bool) -> None:
        if selected:
            self.setStyleSheet("border: 2px solid #2D7CFF; border-radius: 8px; background-color: rgba(45, 124, 255, 0.08);")
            try:
                self._title_label.setStyleSheet("border: none; background: transparent; color: #2D7CFF;")
            except Exception:
                pass
        else:
            self.setStyleSheet("border: 2px solid transparent; border-radius: 8px; background-color: transparent;")
            try:
                self._title_label.setStyleSheet("border: none; background: transparent;")
            except Exception:
                pass

    def _emit_deferred_click(self) -> None:
        self._click_timer = None
        self.clicked.emit(self._obj)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # type: ignore[override]
        # Emit immediate pressed signal for instant visual selection
        if event.button() == QtCore.Qt.LeftButton:
            self.pressed.emit(self._obj)
        # Defer single-click emission until we know it's not a double-click
        if event.button() == QtCore.Qt.LeftButton:
            try:
                if self._click_timer is not None:
                    self._click_timer.stop()
                    self._click_timer.deleteLater()
            except Exception:
                pass
            self._click_timer = QtCore.QTimer(self)
            self._click_timer.setSingleShot(True)
            try:
                interval = QtWidgets.QApplication.doubleClickInterval()
            except Exception:
                interval = 250
            self._click_timer.setInterval(int(interval))
            self._click_timer.timeout.connect(self._emit_deferred_click)
            self._click_timer.start()
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
        self.resize(820, 480)
        
        # Top-level layout with breadcrumb spanning full width
        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)
        root_layout = QtWidgets.QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Breadcrumb across the full window width
        self.breadcrumb = BreadcrumbBar(central)
        self.breadcrumb.crumbClicked.connect(self.on_breadcrumb_clicked)
        root_layout.addWidget(self.breadcrumb)

        # Below breadcrumb: horizontal splitter with object view and details
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal, central)
        root_layout.addWidget(splitter)

        # Left side: toolbar + grid in a scroll area
        left_panel = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        # Toolbar directly below breadcrumb
        toolbar = ObjectToolbar(left_panel)
        toolbar.action_group.setToolTip("Group")
        toolbar.action_group.triggered.connect(self.on_group_action_triggered)
        toolbar.get_state = lambda: (self.nav_stack, self.current_host, self.current_port)
        # Table toggle
        toolbar.action_table.triggered.connect(self.on_table_toggle)
        # Details toggle
        try:
            toolbar.action_details.triggered.connect(self.on_details_toggle)
        except Exception:
            pass
        # Zoom buttons
        try:
            toolbar.action_zoom_in.triggered.connect(self._zoom_in)
            toolbar.action_zoom_out.triggered.connect(self._zoom_out)
            # Set tooltips with keyboard shortcuts
            toolbar.action_zoom_in.setToolTip("Zoom In (⌘+)")
            toolbar.action_zoom_out.setToolTip("Zoom Out (⌘-)")
        except Exception:
            pass
        left_layout.addWidget(toolbar)

        self.nav_stack: List[Dict[str, str]] = []
        # Persist the endpoint used to load data for this window
        self.root_host: str = PROVIDER_HOST
        self.root_port: int = PROVIDER_PORT
        self.current_host: str = self.root_host
        self.current_port: int = self.root_port
        self.selected_item: ObjectItemWidget | None = None
        self.current_objects: List[Dict[str, Any]] = []

        # Container for either grid view or table view
        self.view_container = QtWidgets.QStackedWidget(left_panel)
        left_layout.addWidget(self.view_container)

        # Grid view
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        grid_host = QtWidgets.QWidget()
        grid_layout = QtWidgets.QGridLayout(grid_host)
        grid_layout.setContentsMargins(4, 4, 4, 4)
        grid_layout.setHorizontalSpacing(6)
        grid_layout.setVerticalSpacing(4)
        scroll.setWidget(grid_host)
        self.view_container.addWidget(scroll)
        # Capture background clicks in the scroll viewport to clear selection
        self.grid_host = grid_host
        self.scroll_area = scroll
        try:
            self.scroll_area.viewport().installEventFilter(self)
        except Exception:
            pass
        # Track current computed column count and debounce reflow
        self._grid_columns: int = 0
        self._reflow_timer: Optional[QtCore.QTimer] = None
        # Zoom level for UI scaling (1.0 = normal, 1.2 = 120%, etc.)
        self._zoom_level: float = 1.0
        # Track current object displayed in details panel
        self._current_details_obj: Optional[Dict[str, Any]] = None

        # Table view
        table = QtWidgets.QTableWidget()
        table.setSortingEnabled(True)
        table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        table.horizontalHeader().setStretchLastSection(True)
        self.view_container.addWidget(table)

        splitter.addWidget(left_panel)

        # Right side: details panel, visible at startup
        self.details_panel = DetailsPanel(splitter)
        splitter.addWidget(self.details_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([600, 300])
        # Keep a reference and monitor size changes to auto-collapse details
        self.splitter = splitter
        self._details_saved_width: int = 300
        try:
            self.splitter.splitterMoved.connect(self.on_splitter_moved)
        except Exception:
            pass

        # Fetch info for root name and icons, then populate
        info = {}
        try:
            info = fetch_info()
        except Exception:
            info = {}
        root_name = info.get("RootName") if isinstance(info, dict) else None
        self.root_name = str(root_name) if root_name else "Root"
        self._update_breadcrumb()

        # Decode and store icons announced by provider
        self.icon_store: Dict[str, QtGui.QPixmap] = {}
        self.add_icons_from_info(info)

        self.grid_layout = grid_layout
        self.table_widget = table
        self.icon_mode = True
        
        # Set up zoom keyboard shortcuts
        self._setup_zoom_shortcuts()
        
        # Restore saved settings
        self._restore_settings()
        
        self.load_root(self.root_host, self.root_port)

    def navigate_to_path(self, full_path: str) -> None:
        # Expected: /[host:port]/seg/... with optional multiple [host:port] mid-path
        path = full_path.strip()
        if not path.startswith("/"):
            path = "/" + path

        def _is_host_token(seg: str) -> bool:
            if not (seg.startswith("[") and seg.endswith("]") and len(seg) > 2):
                return False
            inner = seg[1:-1]
            return ":" in inner  # host tokens require host:port

        def _parse_host_token(seg: str) -> tuple[Optional[str], Optional[int]]:
            inner = seg[1:-1]
            if ":" in inner:
                h, p = inner.split(":", 1)
                try:
                    return h, int(p)
                except Exception:
                    return h, None
            return inner, None

        def _is_command_token(seg: str) -> bool:
            return seg.startswith("<") and seg.endswith(">") and len(seg) > 2

        current_id = "/"
        last_obj: Optional[Dict[str, Any]] = None
        segs = [s for s in path.split("/") if s != ""]
        processed_any = False
        for idx, seg in enumerate(segs):
            # Special action token: [openaction]
            if isinstance(seg, str) and seg.lower() == "[openaction]":
                if isinstance(last_obj, dict):
                    try:
                        self.perform_openaction(last_obj)
                    except Exception:
                        pass
                break
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
                        # Fix A: treat the first deep-linked provider as the root endpoint
                        self.root_host, self.root_port = new_host, new_port
                        self.nav_stack = []
                        self._update_breadcrumb()
                    else:
                        title = root_name if isinstance(root_name, str) and root_name else f"{new_host}:{new_port}"
                        self.nav_stack.append({
                            "id": "/",
                            "title": title,
                            "host": new_host,
                            "port": str(new_port),
                            "remote_id": "/",
                        })
                        self._update_breadcrumb()
                    self.current_host, self.current_port = new_host, new_port
                    self.load_root(self.current_host, self.current_port)
                current_id = "/"
                continue

            # Command token like <GroupBy:prop> or <Show:prop:value>
            if _is_command_token(seg):
                # Special command token: <OpenAction>
                if isinstance(seg, str) and seg.lower() == "<openaction>":
                    if isinstance(last_obj, dict):
                        try:
                            self.perform_openaction(last_obj)
                        except Exception:
                            pass
                    break
                # Apply other command tokens to current path
                target_remote = current_id.rstrip("/") + "/" + seg
                # Derive a human title for breadcrumb when possible
                title = seg
                try:
                    if seg.startswith("<GroupBy:") and seg.endswith(">"):
                        title = f"Group by {seg[len('<GroupBy:'):-1]}"
                    elif seg.startswith("<Show:") and seg.endswith(">"):
                        # Format: <Show:prop:value>
                        parts = seg[1:-1].split(":", 2)
                        if len(parts) == 3:
                            _, prop, value = parts
                            title = f"Show {prop} = {value}"
                        else:
                            title = seg
                except Exception:
                    pass
                self.nav_stack.append({
                    "id": current_id,
                    "title": title,
                    "host": self.current_host,
                    "port": str(self.current_port),
                    "remote_id": target_remote,
                })
                self._update_breadcrumb()
                processed_any = True
                current_id = target_remote
                self.load_children(current_id, self.current_host, self.current_port)
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
            last_obj = match if isinstance(match, dict) else None
            try:
                objects_count = int(match.get("objects", 0))
            except Exception:
                objects_count = 0
            object_id = match.get("id")
            title = match.get("title")
            remote_id = match.get("remote_id") or object_id
            # Humanize <Show:...> tokens for breadcrumb if present in id or remote_id
            human_title = title
            try:
                if isinstance(remote_id, str) and remote_id:
                    seg = remote_id.strip("/").split("/")[-1]
                    if seg.startswith("<GroupBy:") and seg.endswith(">"):
                        human_title = f"Group by {seg[len('<GroupBy:'):-1]}"
                    elif seg.startswith("<Show:") and seg.endswith(">"):
                        parts = seg[1:-1].split(":", 2)
                        if len(parts) == 3:
                            _, prop, value = parts
                            human_title = f"Show {prop} = {value}"
            except Exception:
                pass
            if not isinstance(object_id, str) or not isinstance(human_title, str):
                break
            self.nav_stack.append({"id": object_id, "title": human_title, "host": self.current_host, "port": str(self.current_port), "remote_id": object_id})
            self._update_breadcrumb()
            processed_any = True
            # If the next segment is a command token (e.g., <OpenAction>), allow it even for leaf objects
            next_seg = segs[idx + 1] if (idx + 1) < len(segs) else None
            if objects_count == 0 and not (isinstance(next_seg, str) and _is_command_token(next_seg)):
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

    def on_table_toggle(self) -> None:
        self.icon_mode = not self.icon_mode
        # 0 = grid scroll, 1 = table
        self.view_container.setCurrentIndex(0 if self.icon_mode else 1)
        # Re-render current objects in the active view
        try:
            objs = list(self.current_objects)
        except Exception:
            objs = []
        self.populate_objects(objs)

    def populate_objects(self, objects: List[Any]) -> None:
        # Keep a copy of the raw objects currently displayed for toolbar actions
        try:
            self.current_objects = list(objects)
        except Exception:
            self.current_objects = []

        if self.icon_mode:
            self.clear_grid()
            # Compute dynamic column count based on available viewport width
            try:
                viewport_w = self.scroll_area.viewport().width()
            except Exception:
                viewport_w = self.width()
            columns = self._compute_columns(viewport_w)
            self._grid_columns = columns
            row = 0
            col = 0
            for obj in objects:
                widget = ObjectItemWidget(_obj_to_dict(obj), icon_lookup=self.get_icon_pixmap, zoom_level=self._zoom_level)
                widget.activated.connect(self.on_item_activated)
                widget.pressed.connect(self.on_item_pressed)
                widget.clicked.connect(self.on_item_clicked)
                self.grid_layout.addWidget(widget, row, col, alignment=QtCore.Qt.AlignTop | QtCore.Qt.AlignHCenter)
                col += 1
                if col >= columns:
                    col = 0
                    row += 1
        else:
            # Build union of keys across all objects
            rows = [_obj_to_dict(o) for o in objects]
            keys: List[str] = []
            seen: set[str] = set()
            for r in rows:
                if isinstance(r, dict):
                    for k in r.keys():
                        if isinstance(k, str) and k not in seen:
                            seen.add(k)
                            keys.append(k)
            # Optional: move core fields to front
            core = ["class", "id", "title", "objects", "icon"]
            ordered_keys = [k for k in core if k in seen] + [k for k in keys if k not in core]

            self.table_widget.clear()
            self.table_widget.setRowCount(len(rows))
            self.table_widget.setColumnCount(len(ordered_keys))
            self.table_widget.setHorizontalHeaderLabels(ordered_keys)

            for r_idx, r in enumerate(rows):
                if not isinstance(r, dict):
                    continue
                for c_idx, k in enumerate(ordered_keys):
                    val = r.get(k)
                    text = "" if val is None else str(val)
                    item = QtWidgets.QTableWidgetItem(text)
                    # Keep original for sorting
                    item.setData(QtCore.Qt.UserRole, val)
                    self.table_widget.setItem(r_idx, c_idx, item)
            self.table_widget.resizeColumnsToContents()

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
        # Clear selection and details when navigating to a new root/path
        try:
            self.selected_item = None
            self._current_details_obj = None
            self.details_panel.clear()
        except Exception:
            pass
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
        # Clear selection and details when navigating into a child path
        try:
            self.selected_item = None
            self._current_details_obj = None
            self.details_panel.clear()
        except Exception:
            pass

    def on_item_activated(self, obj: Dict[str, Any]) -> None:
        # If object defines an openaction, perform it and stop
        try:
            oa = obj.get("openaction")
            if isinstance(oa, list) and len(oa) > 0:
                self.perform_openaction(obj)
                return
        except Exception:
            pass
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

        # Humanize breadcrumb title when navigating into command tokens (GroupBy/Show)
        human_title = title
        try:
            if isinstance(remote_id, str) and remote_id:
                seg = remote_id.strip("/").split("/")[-1]
                if seg.startswith("<GroupBy:") and seg.endswith(">"):
                    human_title = f"Group by {seg[len('<GroupBy:'):-1]}"
                elif seg.startswith("<Show:") and seg.endswith(">"):
                    parts = seg[1:-1].split(":", 2)
                    if len(parts) == 3:
                        _, prop, value = parts
                        human_title = f"Show {prop} = {value}"
        except Exception:
            pass

        # Push into stack and navigate using next endpoint
        self.nav_stack.append({"id": object_id, "title": human_title, "host": next_host, "port": str(next_port), "remote_id": remote_id})
        self._update_breadcrumb()
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
        # Push a breadcrumb level representing the grouping view
        self.nav_stack.append({
            "id": base_path,
            "title": f"Group by {prop}",
            "host": self.current_host,
            "port": str(self.current_port),
            "remote_id": target_path,
        })
        self._update_breadcrumb()
        self.load_children(target_path, self.current_host, self.current_port)

    # Deep link building moved into toolbar.py

    def on_item_clicked(self, obj: Dict[str, Any]) -> None:
        sender = self.sender()
        if not isinstance(sender, ObjectItemWidget):
            return
        # Populate details panel with selected object's properties
        obj_dict = _obj_to_dict(obj)
        self._current_details_obj = obj_dict
        self.details_panel.set_object(obj_dict, self._zoom_level)

    def on_item_pressed(self, obj: Dict[str, Any]) -> None:
        sender = self.sender()
        if not isinstance(sender, ObjectItemWidget):
            return
        if self.selected_item is sender:
            return
        if self.selected_item is not None:
            try:
                self.selected_item.set_selected(False)
            except RuntimeError:
                pass
        sender.set_selected(True)
        self.selected_item = sender

    def _clear_selection_and_details(self) -> None:
        # Unselect any selected tile and clear the details view
        try:
            if self.selected_item is not None:
                try:
                    self.selected_item.set_selected(False)
                except Exception:
                    pass
            self.selected_item = None
            self._current_details_obj = None
            self.details_panel.clear()
        except Exception:
            pass

    def on_details_toggle(self) -> None:
        # Toggle the visibility of the details panel (fold in/out) and manage splitter sizes
        try:
            is_visible = self.details_panel.isVisible()
        except Exception:
            is_visible = True
        if is_visible:
            # Save current width before hiding
            try:
                sizes = list(self.splitter.sizes())
                if len(sizes) >= 2 and sizes[1] > 0:
                    self._details_saved_width = max(150, sizes[1])
                total = sum(sizes) if sizes else self.width()
                self.details_panel.setVisible(False)
                # Collapse details to near-zero
                self.splitter.setSizes([max(1, total - 1), 1])
            except Exception:
                self.details_panel.setVisible(False)
        else:
            # Show and restore a reasonable width
            self.details_panel.setVisible(True)
            try:
                sizes = list(self.splitter.sizes())
                total = sum(sizes) if sizes else self.width()
                desired = min(max(150, self._details_saved_width), max(150, int(total * 0.45)))
                left = max(1, total - desired)
                self.splitter.setSizes([left, desired])
            except Exception:
                pass
        
        # Save the new visibility state
        try:
            settings = QtCore.QSettings("HierarchyBrowser", "MainWindow")
            settings.setValue("detailsVisible", self.details_panel.isVisible())
        except Exception:
            pass

    def on_splitter_moved(self, pos: int, index: int) -> None:
        # Auto-toggle details when collapsed below threshold; track last good width
        try:
            sizes = self.splitter.sizes()
            if len(sizes) < 2:
                return
            details_w = sizes[1]
            if details_w < 10 and self.details_panel.isVisible():
                # Enter collapsed state, same as toolbar toggle
                self.on_details_toggle()
            elif details_w >= 10 and self.details_panel.isVisible():
                # Update saved width while user resizes
                self._details_saved_width = details_w
                # Save splitter sizes
                try:
                    settings = QtCore.QSettings("HierarchyBrowser", "MainWindow")
                    settings.setValue("splitterSizes", sizes)
                except Exception:
                    pass
        except Exception:
            pass

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:  # type: ignore[override]
        # Clear selection when clicking on empty area of the icon view
        try:
            viewport = getattr(self, "scroll_area", None).viewport() if hasattr(self, "scroll_area") else None
        except Exception:
            viewport = None
        # Reflow icon grid when the viewport is resized (e.g., window or splitter changes)
        try:
            if obj is viewport and event.type() == QtCore.QEvent.Resize:
                self._schedule_reflow()
        except Exception:
            pass
        try:
            if obj is viewport and event.type() == QtCore.QEvent.MouseButtonPress:
                if isinstance(event, QtGui.QMouseEvent) and event.button() == QtCore.Qt.LeftButton:
                    # Map click position from viewport to grid_host coordinates
                    try:
                        pos_in_view = event.pos()
                        global_pos = self.scroll_area.viewport().mapToGlobal(pos_in_view)
                        pos_in_grid = self.grid_host.mapFromGlobal(global_pos)
                    except Exception:
                        pos_in_grid = None
                    w = None
                    try:
                        if pos_in_grid is not None:
                            w = self.grid_host.childAt(pos_in_grid)
                    except Exception:
                        w = None
                    # Ascend to find an ObjectItemWidget, if any
                    node = w
                    found_tile = False
                    try:
                        while node is not None:
                            if isinstance(node, ObjectItemWidget):
                                found_tile = True
                                break
                            node = node.parent()
                    except Exception:
                        found_tile = False
                    if not found_tile:
                        self._clear_selection_and_details()
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # type: ignore[override]
        # Save settings before closing
        self._save_settings()
        super().closeEvent(event)

    def _save_settings(self) -> None:
        try:
            settings = QtCore.QSettings("HierarchyBrowser", "MainWindow")
            settings.setValue("geometry", self.saveGeometry())
            settings.setValue("windowState", self.saveState())
            settings.setValue("zoomLevel", self._zoom_level)
            settings.setValue("detailsVisible", self.details_panel.isVisible())
            if hasattr(self, 'splitter'):
                settings.setValue("splitterSizes", self.splitter.sizes())
        except Exception:
            pass

    def _restore_settings(self) -> None:
        try:
            settings = QtCore.QSettings("HierarchyBrowser", "MainWindow")
            
            # Restore window geometry and state
            geometry = settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
            
            state = settings.value("windowState")
            if state:
                self.restoreState(state)
            
            # Restore zoom level
            zoom_level = settings.value("zoomLevel", 1.0, type=float)
            if zoom_level != 1.0:
                self._zoom_level = zoom_level
                self._apply_zoom()
            
            # Restore details panel visibility
            details_visible = settings.value("detailsVisible", True, type=bool)
            if not details_visible:
                self.details_panel.setVisible(False)
            
            # Restore splitter sizes
            if hasattr(self, 'splitter'):
                splitter_sizes = settings.value("splitterSizes")
                if splitter_sizes:
                    try:
                        # Convert to list of ints if needed
                        if isinstance(splitter_sizes, list):
                            sizes = [int(s) for s in splitter_sizes]
                            self.splitter.setSizes(sizes)
                    except Exception:
                        pass
        except Exception:
            pass

    def _setup_zoom_shortcuts(self) -> None:
        # Use standard zoom shortcuts that work cross-platform
        # Qt automatically maps these to Cmd+ on Mac and Ctrl+ on other platforms
        
        # Zoom in: Standard zoom in shortcut
        zoom_in_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence.ZoomIn, self)
        zoom_in_shortcut.activated.connect(self._zoom_in)
        
        # Zoom out: Standard zoom out shortcut  
        zoom_out_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence.ZoomOut, self)
        zoom_out_shortcut.activated.connect(self._zoom_out)
        
        # Also add Ctrl/Cmd + Plus for zoom in (since + might require shift)
        zoom_in_plus = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+="), self)
        zoom_in_plus.activated.connect(self._zoom_in)
        
        # Reset zoom: Ctrl/Cmd+0
        zoom_reset_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+0"), self)
        zoom_reset_shortcut.activated.connect(self._zoom_reset)

    def _zoom_in(self) -> None:
        self._zoom_level = min(3.0, self._zoom_level * 1.1)
        self._apply_zoom()
        self._save_zoom_level()

    def _zoom_out(self) -> None:
        self._zoom_level = max(0.5, self._zoom_level / 1.1)
        self._apply_zoom()
        self._save_zoom_level()

    def _zoom_reset(self) -> None:
        self._zoom_level = 1.0
        self._apply_zoom()
        self._save_zoom_level()

    def _save_zoom_level(self) -> None:
        try:
            settings = QtCore.QSettings("HierarchyBrowser", "MainWindow")
            settings.setValue("zoomLevel", self._zoom_level)
        except Exception:
            pass

    def _apply_zoom(self) -> None:
        # Apply zoom to breadcrumb
        self._zoom_breadcrumb()
        
        # Apply zoom to details panel
        self._zoom_details_panel()
        
        # Repopulate grid to apply zoom to icon labels
        if self.icon_mode:
            try:
                objs = list(self.current_objects)
                self.populate_objects(objs)
            except Exception:
                pass

    def _zoom_breadcrumb(self) -> None:
        # Trigger breadcrumb refresh with current zoom level
        self._update_breadcrumb()

    def _zoom_details_panel(self) -> None:
        try:
            # Update Details label font
            title_widget = None
            layout = self.details_panel.layout()
            if layout and layout.count() > 0:
                item = layout.itemAt(0)
                if item and item.widget():
                    title_widget = item.widget()
            
            if title_widget and isinstance(title_widget, QtWidgets.QLabel):
                font = title_widget.font()
                base_size = 9  # Assume base font size
                font.setPointSizeF(base_size * self._zoom_level)
                title_widget.setFont(font)
            
            # Refresh the current object in details panel with new zoom level
            if self._current_details_obj is not None:
                try:
                    self.details_panel.set_object(self._current_details_obj, self._zoom_level)
                except Exception:
                    pass
        except Exception:
            pass

    def _get_zoomed_font(self, base_font: QtGui.QFont, base_size: float = 9.0) -> QtGui.QFont:
        font = QtGui.QFont(base_font)
        font.setPointSizeF(base_size * self._zoom_level)
        return font

    def _tile_width_hint(self) -> int:
        # Estimate a reasonable tile width using icon size and typical text width
        try:
            fm = self.fontMetrics()
            text_width = fm.horizontalAdvance("M" * 8)
        except Exception:
            text_width = 80
        base = max(ICON_BOX_PX, text_width)
        # Add widget layout margins (4px left + 4px right = 8px) plus some padding
        return base + 16

    def _compute_columns(self, viewport_width: int) -> int:
        try:
            margins = self.grid_layout.contentsMargins()
            spacing = self.grid_layout.horizontalSpacing()
            spacing = 0 if spacing is None else max(0, spacing)
            available = max(0, viewport_width - (margins.left() + margins.right()))
        except Exception:
            available = max(0, viewport_width - 8)
            spacing = 6
        tile = max(1, self._tile_width_hint())
        
        # Correct formula: For N columns, we need N*tile_width + (N-1)*spacing <= available
        # Solving: N <= (available + spacing) / (tile + spacing)
        # But we need to be conservative to avoid overflow
        if available <= tile:
            return 1
        
        # Calculate maximum columns that definitely fit
        columns = max(1, int(available // (tile + spacing)))
        
        # Verify the calculation fits within available width
        total_width_needed = columns * tile + (columns - 1) * spacing
        if total_width_needed > available and columns > 1:
            columns -= 1
            
        return columns

    def _schedule_reflow(self) -> None:
        try:
            if self._reflow_timer is None:
                self._reflow_timer = QtCore.QTimer(self)
                self._reflow_timer.setSingleShot(True)
                self._reflow_timer.timeout.connect(self._reflow_grid)
            # Small delay to coalesce rapid resize events
            self._reflow_timer.start(50)
        except Exception:
            # Fallback: immediate reflow if timer setup fails
            self._reflow_grid()

    def _reflow_grid(self) -> None:
        if not self.icon_mode:
            return
        try:
            viewport_w = self.scroll_area.viewport().width()
        except Exception:
            viewport_w = self.width()
        new_cols = self._compute_columns(viewport_w)
        if new_cols != self._grid_columns:
            try:
                objs = list(self.current_objects)
            except Exception:
                objs = []
            self.populate_objects(objs)

    def perform_openaction(self, obj: Dict[str, Any]) -> None:
        """Execute the object's openaction as if the user activated it.

        Supports:
        - action == "objectbrowser": switch to target provider and load its root
        - any other actions: delegated to execute_context_action
        """
        if not isinstance(obj, dict):
            return
        open_action = obj.get("openaction")
        if not isinstance(open_action, list) or not open_action:
            return
        entry = None
        for item in open_action:
            if isinstance(item, dict):
                entry = item
                break
        if not isinstance(entry, dict):
            return
        act = str(entry.get("action", "")).lower()
        if act == "objectbrowser":
            next_host: str = self.current_host
            next_port: int = self.current_port
            candidate_host = entry.get("hostname") or entry.get("host")
            if isinstance(candidate_host, str) and candidate_host:
                next_host = candidate_host
            try:
                if entry.get("port") is not None:
                    next_port = int(entry.get("port"))
            except Exception:
                pass
            switching = (next_host != self.current_host) or (next_port != self.current_port)
            remote_id = "/"
            # Push breadcrumb level and switch
            print(f"title: {title}, next_host: {next_host}, next_port: {next_port}")
            title = entry.get("title") or f"{next_host}:{next_port}"
            self.nav_stack.append({
                "id": obj.get("id") or "/",
                "title": str(title),
                "host": next_host,
                "port": str(next_port),
                "remote_id": remote_id,
            })
            self._update_breadcrumb()
            self.current_host, self.current_port = next_host, next_port
            if switching:
                try:
                    info = fetch_info(self.current_host, self.current_port)
                    self.add_icons_from_info(info)
                except Exception:
                    pass
            self.load_children(remote_id, next_host, next_port)
        else:
            # Fallback: execute via context action helper
            try:
                # Position near center of the window
                pos = self.mapToGlobal(self.rect().center())  # type: ignore[arg-type]
            except Exception:
                pos = QtGui.QCursor.pos()
            try:
                execute_context_action(self, entry, pos)  # type: ignore[arg-type]
            except Exception:
                pass

    def on_breadcrumb_clicked(self, index: int) -> None:
        # index 0 is root
        if index <= 0:
            self.nav_stack = []
            self._update_breadcrumb()
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
        self._update_breadcrumb()
        self.current_host, self.current_port = target_host, target_port
        self.load_children(target_remote_id, target_host, target_port)

    def _update_breadcrumb(self) -> None:
        parts = [self.root_name] + [e["title"] for e in self.nav_stack]
        bold_indices: set[int] = set()
        try:
            for idx, entry in enumerate(self.nav_stack, start=1):
                remote_id = entry.get("remote_id")
                if isinstance(remote_id, str) and remote_id == "/":
                    bold_indices.add(idx)
        except Exception:
            pass
        self.breadcrumb.set_path(parts, bold_indices, self._zoom_level)


def fetch_objects_for_id(object_id: str, host: Optional[str] = None, port: Optional[int] = None) -> Dict[str, Any]:
    h = host or PROVIDER_HOST
    p = port or PROVIDER_PORT
    payload = {"method": "GetObjects", "id": object_id}
    message = json.dumps(payload, separators=(",", ":")) + "\n"
    with socket.create_connection((h, p), timeout=10) as s:
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

    # Set application icon so it appears in Alt-Tab/task switchers
    icon = None
    try:
        icon_path = _THIS.parent / "Resources" / "Browser.png"
        if icon_path.exists():
            icon = QtGui.QIcon(str(icon_path))
            app.setWindowIcon(icon)
    except Exception:
        icon = None

    win = MainWindow()
    try:
        if icon is not None:
            win.setWindowIcon(icon)
    except Exception:
        pass
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


