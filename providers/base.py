#!/usr/bin/env python3
from __future__ import annotations

import base64
from io import BytesIO
import json
import sys
import socketserver
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Callable, Iterable
from PIL import Image  # type: ignore[import-not-found]


@dataclass(frozen=True)
class ProviderOptions:
    """Configuration for a provider instance.

    Only the minimal options required by current providers are included.
    Extend as needed when adding new providers.
    """

    root_name: str
    provider_dir: Path
    resources_dir: Path
    # Optional semicolon-separated list of icon base names to customize
    customize_icons: Optional[str] = None


class ObjectProvider(ABC):
    """Base class that centralizes protocol parsing and server glue.

    Subclasses implement data retrieval methods.
    """

    # ---- Protocol helpers (class-level, shared) ----
    @staticmethod
    def is_get_root_objects(message: Any) -> bool:
        if isinstance(message, str):
            return message.strip() == "GetRootObjects"
        if isinstance(message, dict):
            candidate_keys = [
                "method",
                "message",
                "type",
                "command",
                "action",
            ]
            if any(message.get(k) == "GetRootObjects" for k in candidate_keys):
                return True
            if "GetRootObjects" in message:
                value = message.get("GetRootObjects")
                return bool(value) if value is not None else True
        return False

    @staticmethod
    def is_get_info(message: Any) -> bool:
        if isinstance(message, str):
            return message.strip() == "GetInfo"
        if isinstance(message, dict):
            candidate_keys = [
                "method",
                "message",
                "type",
                "command",
                "action",
            ]
            if any(message.get(k) == "GetInfo" for k in candidate_keys):
                return True
            if "GetInfo" in message:
                value = message.get("GetInfo")
                return bool(value) if value is not None else True
        return False

    @staticmethod
    def is_get_objects(message: Any) -> bool:
        if isinstance(message, dict):
            candidate_keys = [
                "method",
                "message",
                "type",
                "command",
                "action",
            ]
            return any(message.get(k) == "GetObjects" for k in candidate_keys)
        if isinstance(message, str):
            return message.strip() == "GetObjects"
        return False  

    @staticmethod
    def extract_object_id(message: Any) -> Optional[str]:
        if isinstance(message, dict):
            for key in ["id", "path", "object", "objectId", "ObjectId"]:
                value = message.get(key)
                if isinstance(value, str):
                    return value
        return None

    # ---- Instance lifecycle ----
    def __init__(self, options: ProviderOptions) -> None:
        self.options = options

    # ---- Message handling ----
    def handle_message(self, incoming: Any) -> Dict[str, Any]:
        if self.is_get_root_objects(incoming):
            try:
                return self.get_root_objects_payload()
            except Exception as exc:  # pragma: no cover - defensive
                import traceback
                traceback.print_exc()
                return {"error": f"Failed to serve objects: {exc}"}
        if self.is_get_info(incoming):
            return {
                "RootName": self.options.root_name,
                "icons": self._collect_icons_payload(),
            }
        if self.is_get_objects(incoming):
            object_id = self.extract_object_id(incoming)
            if not object_id:
                return {"error": "Missing id"}
            try:
                return self.get_objects_for_path(object_id)
            except Exception as exc:  # pragma: no cover - defensive
                import traceback
                traceback.print_exc()
                return {"error": f"Failed to list objects: {exc}"}
        return {"error": "Unknown message"}

    # ---- Abstract data retrieval ----
    @abstractmethod
    def get_root_objects_payload(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_objects_for_path(self, path_str: str) -> Dict[str, Any]:
        pass

    # ---- Server bootstrap ----
    def serve(self, host: str = "127.0.0.1", port: int = 8888) -> None:
        provider = self

        class JsonLineHandler(socketserver.StreamRequestHandler):  # type: ignore[misc]
            def handle(self) -> None:  # noqa: D401
                line = self.rfile.readline()
                if not line:
                    return
                try:
                    text = line.decode("utf-8").strip()
                    print(f"Incoming: {text}", flush=True)
                    incoming = json.loads(text)
                except Exception:
                    self._send_json({"error": "Invalid JSON"})
                    return

                payload = provider.handle_message(incoming)
                self._send_json(payload)

            def _send_json(self, payload: Dict[str, Any]) -> None:
                data = json.dumps(payload, separators=(",", ":")) + "\n"
                self.wfile.write(data.encode("utf-8"))

        class ReusableTCPServer(socketserver.ThreadingTCPServer):  # type: ignore[misc]
            allow_reuse_address = True

        with ReusableTCPServer((host, port), JsonLineHandler) as server:
            # Show the path of the script that was actually invoked
            main_module = sys.modules.get("__main__")
            candidate_path: str = getattr(
                main_module, "__file__", sys.argv[0] if sys.argv else __file__
            )
            invoked_path = Path(candidate_path).resolve()
            print(f"Starting {invoked_path}", flush=True)
            print(f"Provider listening on {host}:{port}", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass

    # ---- Helpers ----
    def _collect_icons_payload(self) -> list[dict[str, str]]:
        icons: list[dict[str, str]] = []
        resources_dir: Path = self.options.resources_dir
        try:
            if resources_dir.exists() and resources_dir.is_dir():
                for entry in sorted(resources_dir.iterdir(), key=lambda p: p.name.lower()):
                    if not entry.is_file():
                        continue
                    if entry.suffix.lower() != ".png":
                        continue
                    try:
                        data = entry.read_bytes()
                        b64 = base64.b64encode(data).decode("ascii")
                        # Expose a normalized client filename with lowercase 'resources'
                        filename = f"./resources/{entry.name}"
                        icons.append({"filename": filename, "data": b64})
                    except Exception:
                        continue
                if self.options.customize_icons:
                    # Attempt to composite IDCard.png over each icon at 1/3 scale in bottom-right
                    idcard_path = resources_dir / "IDCard.png"
                    idcard_img = None
                    if Image is not None and idcard_path.exists():
                        try:
                            idcard_img = Image.open(str(idcard_path)).convert("RGBA")
                        except Exception:
                            idcard_img = None
                    customize_icons = self.options.customize_icons.split(";")
                    for entry_name in customize_icons:
                        entry = resources_dir / entry_name
                        if not entry.is_file():
                            continue
                        if entry.suffix.lower() != ".png":
                            continue
                        try:
                            base_img_data = entry.read_bytes()
                            if Image is None or idcard_img is None:
                                # Fallback: if Pillow not available or IDCard not readable, just duplicate original
                                b64 = base64.b64encode(base_img_data).decode("ascii")
                                customName = entry.name.replace(".png", "_IDCard.png")
                                filename = f"./resources/{customName}"
                                icons.append({"filename": filename, "data": b64})
                                continue
                            # Composite using Pillow
                            base_img = Image.open(BytesIO(base_img_data)).convert("RGBA")
                            bw, bh = base_img.size
                            # Scale overlay to 1/3 of the shorter side for a balanced badge size
                            target = max(1, int(min(bw, bh) / 1.75))
                            # Preserve aspect ratio; IDCard is square typically, but be safe
                            ow, oh = idcard_img.size
                            if ow >= oh:
                                new_w = target
                                new_h = max(1, int(oh * (target / float(ow))))
                            else:
                                new_h = target
                                new_w = max(1, int(ow * (target / float(oh))))
                            overlay = idcard_img.resize((new_w, new_h), Image.LANCZOS)
                            # Bottom-right placement
                            x = max(0, bw - new_w)
                            y = max(0, bh - new_h)
                            composed = base_img.copy()
                            composed.alpha_composite(overlay, (x, y))
                            # Encode to PNG
                            buf = BytesIO()
                            composed.save(buf, format="PNG")
                            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
                            customName = entry.name.replace(".png", "_IDCard.png")
                            filename = f"./resources/{customName}"
                            icons.append({"filename": filename, "data": b64})
                        except Exception:
                            continue

        except Exception:
            return []
        return icons

    # ---- Command path processing (optional helpers for subclasses) ----
    def build_objects_for_path(
        self,
        path_str: str,
        list_for_base: Callable[[str], Iterable["ProviderObject"]],
        *,
        allowed_group_fields: set[str] | None = None,
        group_icon_filename: str = "./resources/Group.png",
        make_group: Callable[[str, str, int], "ProviderObject"] | None = None,
    ) -> Dict[str, Any]:
        base_clean, tokens = _parse_command_pipeline(path_str)
        # Normalize drill-through sequences like <GroupBy:X>/<Show:X:V>
        # so that subsequent operations work on leaf objects again.
        tokens = _normalize_groupby_show_tokens(tokens)
        if base_clean == "":
            base_clean = "/"
        # No commands: list base
        if not tokens:
            typed = list_for_base(base_clean)
            return {"objects": [o.to_dict() for o in typed]}

        # Backward-compatible single command handling (including Search)
        if len(tokens) == 1:
            command, prop, value = tokens[0]
            typed_objects = list(list_for_base(base_clean))
            if command == "GroupBy" and isinstance(prop, str):
                if allowed_group_fields is not None and prop not in allowed_group_fields:
                    return {"objects": []}
                groups = _group_objects_by_property(base_clean, typed_objects, prop, group_icon_filename, make_group, path_str = path_str)
                return {"objects": groups}
            if command == "Show" and isinstance(prop, str) and value is not None:
                filtered: list[dict[str, object]] = []
                for o in typed_objects:
                    try:
                        v = o.to_dict().get(prop)
                    except Exception:
                        v = None
                    if v is None:
                        continue
                    if str(v) == str(value):
                        filtered.append(o.to_dict())
                return {"objects": filtered}
            if command == "Search":
                # Legacy format value="prop:string" or split prop/value
                if value is not None and ":" in value:
                    prop_string = value.split(":", 1)[0]
                    value_string = value.split(":", 1)[1]
                else:
                    prop_string = prop if isinstance(prop, str) else "all"
                    value_string = value if isinstance(value, str) else ""
                filtered: list[dict[str, object]] = []
                for o in typed_objects:
                    try:
                        if o.search(prop_string, value_string):
                            filtered.append(o.to_dict())
                    except Exception:
                        continue
                return {"objects": filtered}
            return {"objects": []}

        # Multi-command pipeline
        typed_objects = list(list_for_base(base_clean))

        # Special-case: Show* -> GroupBy:P -> Show:P:V (drill into that group and return leaf objects)
        last_cmd, last_prop, last_value = tokens[-1]
        if last_cmd == "Show" and isinstance(last_prop, str) and last_value is not None:
            # Find a GroupBy token earlier in the sequence
            gb_index = -1
            gb_prop: Optional[str] = None
            for i in range(len(tokens) - 2, -1, -1):
                if tokens[i][0] == "GroupBy":
                    gb_index = i
                    gb_prop = tokens[i][1]
                    break
            if gb_index != -1 and isinstance(gb_prop, str) and gb_prop == last_prop:
                # Ensure all other tokens (excluding that GroupBy and the trailing Show) are Show filters
                for j, (c, p, v) in enumerate(tokens[:-1]):
                    if j == gb_index:
                        continue
                    if c != "Show" or not isinstance(p, str) or v is None:
                        return {"objects": []}
                # Apply all Show filters including the last one; ignore the GroupBy
                for c, p, v in tokens:
                    if c != "Show":
                        continue
                    typed_objects = [
                        o for o in typed_objects
                        if (lambda vv: vv is not None and str(vv) == str(v))(  # inline to avoid repeating try/except
                            (lambda od: (od.get(p) if isinstance(od, dict) else None))(
                                (lambda t: (t.to_dict() if hasattr(t, "to_dict") else {}))(o)
                            )
                        )
                    ]
                return {"objects": [o.to_dict() for o in typed_objects]}

        # General case: apply zero or more Show filters, then optional trailing GroupBy or Show
        for cmd, prop, value in tokens[:-1]:
            if cmd != "Show" or not isinstance(prop, str) or value is None:
                return {"objects": []}
            typed_objects = [
                o for o in typed_objects
                if (lambda vv: vv is not None and str(vv) == str(value))(  # inline to avoid repeating try/except
                    (lambda od: (od.get(prop) if isinstance(od, dict) else None))(
                        (lambda t: (t.to_dict() if hasattr(t, "to_dict") else {}))(o)
                    )
                )
            ]

        # Apply trailing token
        last_cmd, last_prop, last_value = tokens[-1]
        if last_cmd == "GroupBy" and isinstance(last_prop, str):
            if allowed_group_fields is not None and last_prop not in allowed_group_fields:
                return {"objects": []}
            groups = _group_objects_by_property(base_clean, typed_objects, last_prop, group_icon_filename, make_group, path_str = path_str)
            return {"objects": groups}
        if last_cmd == "Show" and isinstance(last_prop, str) and last_value is not None:
            filtered: list[dict[str, object]] = []
            for o in typed_objects:
                try:
                    v = o.to_dict().get(last_prop)
                except Exception:
                    v = None
                if v is None:
                    continue
                if str(v) == str(last_value):
                    filtered.append(o.to_dict())
            return {"objects": filtered}
        return {"objects": []}



# ---- Object model for provider responses ----
@dataclass
class ProviderObject:
    """Base strongly-typed object for provider responses.

    Subclasses should override the class_name property and may add extra
    typed fields. Serialization is controlled via to_dict().
    """

    id: str
    title: str
    icon: Optional[str] = None
    objects: int = 0

    @property
    def class_name(self) -> str:
        return "WPObject"

    def search(self,prop_string: str, value_string: str) -> bool:
        """Return True if value_string is a substring match.

        - If prop_string == "all": search all properties emitted by to_dict().
        - Otherwise: search only the named property if present.
        Matching is case-insensitive and converts values to strings as needed.
        """
        try:
            payload = self.to_dict()
        except Exception:
            return False

        needle = "" if value_string is None else str(value_string)
        needle_lc = needle.lower()

        if prop_string == "all":
            for v in payload.values():
                if v is None:
                    continue
                try:
                    if needle_lc in str(v).lower():
                        return True
                except Exception:
                    continue
            return False

        # Specific property search
        try:
            value = payload.get(prop_string)
        except Exception:
            value = None
        if value is None:
            return False
        try:
            return needle_lc in str(value).lower()
        except Exception:
            return False

    def _extra_fields(self) -> dict[str, object]:
        """Override in subclasses to emit additional fields."""
        return {}

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "class": self.class_name,
            "id": self.id,
            "title": self.title,
            "icon": self.icon if self.icon is not None else None,
            "objects": int(self.objects),
        }
        payload.update(self._extra_fields())
        return payload


@dataclass
class WPGroup(ProviderObject):
    @property
    def class_name(self) -> str:  # noqa: D401
        return "WPGroup"


def _parse_command_path(path_str: str) -> tuple[str, Optional[str], Optional[str], Optional[str]]:
    if not path_str.count("/") == 1:
        base = path_str.lstrip("/")
    else:
        base = path_str
    command: Optional[str] = None
    prop: Optional[str] = None
    value: Optional[str] = None
    if "/<" in base and base.endswith(">"):
        try:
            head, tail = base.rsplit("/<", 1)
            token = tail[:-1]
            parts = token.split(":", 2)
            if len(parts) >= 2:
                command = parts[0]
                prop = parts[1]
                value = parts[2] if len(parts) == 3 else None
                base = head
        except Exception:
            pass
    return base, command, prop, value


def _parse_command_pipeline(path_str: str) -> tuple[str, list[tuple[str, Optional[str], Optional[str]]]]:
    """Parse base and all trailing command tokens from a path.

    Returns (base, tokens) where tokens are in left-to-right order as they
    appear in the path.
    """
    base = path_str.lstrip("/")
    tokens: list[tuple[str, Optional[str], Optional[str]]] = []
    while base.endswith(">"):
        try:
            if "/<" in base:
                head, tail = base.rsplit("/<", 1)
                token = tail[:-1]
                base = head
            elif base.startswith("<"):
                # Handle a single leading token with no preceding slash
                token = base[1:-1]
                base = ""
            else:
                break
            parts = token.split(":", 2)
            cmd = parts[0]
            prop = parts[1] if len(parts) >= 2 else None
            value = parts[2] if len(parts) == 3 else None
            tokens.insert(0, (cmd, prop, value))
        except Exception:
            break
    if base == "":
        base = "/"
    elif path_str.startswith("/") and not base.startswith("/"):
        base = "/" + base
    return base, tokens

def _normalize_groupby_show_tokens(
    tokens: list[tuple[str, Optional[str], Optional[str]]]
) -> list[tuple[str, Optional[str], Optional[str]]]:
    """Collapse GroupBy:X followed immediately by Show:X:V into just Show:X:V.

    This enables pipelines like <GroupBy:cpus>/<Show:cpus:16>/<GroupBy:userid>
    by removing the grouping step that is semantically just a drill-into of the
    Show filter, letting subsequent operations apply to leaf objects again.
    """
    if not tokens:
        return tokens
    normalized: list[tuple[str, Optional[str], Optional[str]]] = []
    i = 0
    while i < len(tokens):
        cmd, prop, value = tokens[i]
        if (
            cmd == "GroupBy"
            and i + 1 < len(tokens)
            and tokens[i + 1][0] == "Show"
            and tokens[i + 1][1] == prop
            and tokens[i + 1][2] is not None
        ):
            # Skip GroupBy and keep the Show (drill-into behavior)
            normalized.append(tokens[i + 1])
            i += 2
            continue
        normalized.append(tokens[i])
        i += 1
    return normalized


def _group_objects_by_property(
    base: str,
    objects: Iterable["ProviderObject"],
    prop: str,
    group_icon_filename: str,
    make_group: Callable[[str, str, int], "ProviderObject"] | None = None,
    path_str: str = "",
) -> list[dict[str, object]]:
    counts: dict[object, int] = {}
    for o in objects:
        try:
            v = o.to_dict().get(prop)
        except Exception:
            v = None
        if v is None:
            continue
        counts[v] = counts.get(v, 0) + 1
    results: list[dict[str, object]] = []
    for value, count in counts.items():
        if make_group is not None:
            grp_obj = make_group(str(value), prop, count)
            results.append(grp_obj.to_dict())
        else:
            id = f"{path_str}/<Show:{prop}:{value}>"
            #if base == "/":
            #    id = f"/<Show:{prop}:{value}>"
            if id.startswith("//"):
                id = id[1:]
            grp_obj = WPGroup(
                id=id,
                title=str(value),
                icon=group_icon_filename,
                objects=int(count),
            )
            results.append(grp_obj.to_dict())
    return results

