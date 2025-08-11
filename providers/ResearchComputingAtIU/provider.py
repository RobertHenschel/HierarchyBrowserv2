#!/usr/bin/env python3
import argparse
import base64
import json
import socketserver
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


PROVIDER_DIR = Path(__file__).resolve().parent
OBJECTS_DIR = PROVIDER_DIR / "Objects"


def _encode_icon_to_base64(icon_path: Union[str, Path], base_dir: Optional[Path] = None) -> str:
    path = Path(icon_path)
    if not path.is_absolute():
        root = base_dir or PROVIDER_DIR
        path = (root / path).resolve()
    with path.open("rb") as f:
        raw = f.read()
    b64 = base64.b64encode(raw).decode("ascii")
    return b64


def _gather_objects_from_directory(directory: Path) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    if not directory.exists() or not directory.is_dir():
        return results

    for entry in sorted(directory.iterdir()):
        if not (entry.is_file() and entry.suffix.lower() == ".json"):
            continue
        try:
            with entry.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        # Determine companion directory name based on file stem
        companion_dir = directory / entry.stem
        objects_count = 0
        if companion_dir.exists() and companion_dir.is_dir():
            try:
                objects_count = sum(1 for p in companion_dir.iterdir() if p.is_file() and p.suffix.lower() == ".json")
            except Exception:
                objects_count = 0

        def push(obj: Any) -> None:
            if isinstance(obj, dict):
                # Inline icon
                icon_value = obj.get("icon")
                if isinstance(icon_value, str) and icon_value:
                    try:
                        # Always resolve relative to the provider's directory
                        obj["icon"] = _encode_icon_to_base64(icon_value, base_dir=PROVIDER_DIR)
                    except FileNotFoundError:
                        obj["icon"] = None
                # Attach objects count inferred from companion directory
                obj["objects"] = int(objects_count)
                results.append(obj)

        if isinstance(data, list):
            for item in data:
                push(item)
        elif isinstance(data, dict):
            if isinstance(data.get("objects"), list):
                for item in data["objects"]:
                    push(item)
            else:
                push(data)

    return results


def get_root_objects_payload() -> Dict[str, Any]:
    objects = _gather_objects_from_directory(OBJECTS_DIR)
    return {"objects": objects}


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


def get_objects_for_path(path_str: str) -> Dict[str, Any]:
    # Normalize and resolve inside OBJECTS_DIR safely
    rel = path_str.lstrip("/")
    base = OBJECTS_DIR.resolve()
    target = (base / rel).resolve()
    try:
        target.relative_to(base)
    except Exception:
        # Path escape attempt or invalid
        return {"objects": []}
    objects = _gather_objects_from_directory(target)
    return {"objects": objects}


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
            self._send_json({"RootName": "Research Computing"})
        elif _is_get_objects(incoming):
            object_id = _extract_object_id(incoming)
            if not object_id:
                self._send_json({"error": "Missing id"})
            else:
                try:
                    payload = get_objects_for_path(object_id)
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
    parser = argparse.ArgumentParser(description="ResearchComputingAtIU Object Provider")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8888, help="Port to bind (default: 8888)")
    args = parser.parse_args()
    serve(args.host, args.port)


