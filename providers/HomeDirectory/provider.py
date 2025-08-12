#!/usr/bin/env python3
import argparse
import base64
import json
import os
import socketserver
from pathlib import Path
from typing import Any, Dict, List, Optional


def _is_get_root_objects(message: Any) -> bool:
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


def _is_get_info(message: Any) -> bool:
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


def _is_get_objects(message: Any) -> bool:
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


def _extract_object_id(message: Any) -> Optional[str]:
    if isinstance(message, dict):
        for key in ["id", "path", "object", "objectId", "ObjectId"]:
            value = message.get(key)
            if isinstance(value, str):
                return value
    return None


PROVIDER_DIR = Path(__file__).resolve().parent
DIR_ICON_PATH = PROVIDER_DIR / "Resources" / "Directory.png"
FILE_ICON_PATH = PROVIDER_DIR / "Resources" / "File.png"


def _encode_icon_to_base64(icon_path: Path) -> Optional[str]:
    try:
        with icon_path.open("rb") as f:
            raw = f.read()
        return base64.b64encode(raw).decode("ascii")
    except FileNotFoundError:
        return None


def get_root_objects_payload() -> Dict[str, Any]:
    home = Path.home()
    dir_icon_b64 = _encode_icon_to_base64(DIR_ICON_PATH)
    file_icon_b64 = _encode_icon_to_base64(FILE_ICON_PATH)
    objects: List[Dict[str, Any]] = []

    try:
        entries = sorted(home.iterdir(), key=lambda p: p.name.lower())
    except Exception:
        entries = []

    for entry in entries:
        name = entry.name
        if name in (".", ".."):
            continue
        if entry.is_dir():
            # Non-recursive count of files and directories inside
            try:
                count = sum(1 for _ in entry.iterdir())
            except Exception:
                count = 0
            objects.append(
                {
                    "class": "WPDirectory",
                    "id": f"/{name}",
                    "icon": dir_icon_b64,
                    "title": name,
                    "objects": int(count),
                }
            )
        elif entry.is_file():
            objects.append(
                {
                    "class": "WPFile",
                    "id": f"/{name}",
                    "icon": file_icon_b64,
                    "title": name,
                    "objects": 0,
                }
            )

    return {"objects": objects}


def get_objects_for_path(_path_str: str) -> Dict[str, Any]:
    # To be implemented later
    return {"objects": []}


class JsonLineHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
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

        if _is_get_root_objects(incoming):
            try:
                payload = get_root_objects_payload()
                self._send_json(payload)
            except Exception as exc:
                self._send_json({"error": f"Failed to serve objects: {exc}"})
        elif _is_get_info(incoming):
            self._send_json({"RootName": "Quartz Home Directory"})
        elif _is_get_objects(incoming):
            _id = _extract_object_id(incoming)
            if not _id:
                self._send_json({"error": "Missing id"})
            else:
                try:
                    payload = get_objects_for_path(_id)
                    self._send_json(payload)
                except Exception as exc:
                    self._send_json({"error": f"Failed to list objects: {exc}"})
        else:
            self._send_json({"error": "Unknown message"})

    def _send_json(self, payload: Dict[str, Any]) -> None:
        data = json.dumps(payload, separators=(",", ":")) + "\n"
        self.wfile.write(data.encode("utf-8"))


def serve(host: str = "127.0.0.1", port: int = 8888) -> None:
    class ReusableTCPServer(socketserver.ThreadingTCPServer):
        allow_reuse_address = True

    with ReusableTCPServer((host, port), JsonLineHandler) as server:
        print(f"Provider listening on {host}:{port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Home Directory Provider")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8888, help="Port to bind (default: 8888)")
    args = parser.parse_args()
    serve(args.host, args.port)


