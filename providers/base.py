#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import socketserver
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ProviderOptions:
    """Configuration for a provider instance.

    Only the minimal options required by current providers are included.
    Extend as needed when adding new providers.
    """

    root_name: str
    provider_dir: Path
    resources_dir: Path


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
            full_name = Path(__file__)
            print(f"Starting {full_name}", flush=True)
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
        except Exception:
            return []
        return icons



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

