#!/usr/bin/env python3
from __future__ import annotations

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
            return {"RootName": self.options.root_name}
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


