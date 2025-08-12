#!/usr/bin/env python3
import argparse
import base64
import json
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
# The instruction references "./resources/Box.png". Use a conventional
# Resources directory as in other providers; either works when authored.
ICON_PATH = PROVIDER_DIR / "Resources" / "Box.png"
SOFTWARE_ICON_PATH = PROVIDER_DIR / "Resources" / "Software.png"

# Base directory that Lmod module families are stored under
LMOD_ROOT = Path("/N/soft/rhel8/modules/quartz")


def _encode_icon_to_base64(icon_path: Path) -> Optional[str]:
    try:
        with icon_path.open("rb") as f:
            raw = f.read()
        return base64.b64encode(raw).decode("ascii")
    except FileNotFoundError:
        return None


def _list_lmod_top_dirs() -> List[str]:
    try:
        if not LMOD_ROOT.exists() or not LMOD_ROOT.is_dir():
            return []
        names: List[str] = []
        for entry in sorted(LMOD_ROOT.iterdir()):
            if entry.is_dir():
                names.append(entry.name)
        return names
    except Exception:
        return []


def _count_module_children(base: Path) -> int:
    total = 0
    try:
        for mf in base.rglob("modulefiles"):
            if mf.is_dir():
                try:
                    total += sum(1 for e in mf.iterdir() if e.is_dir())
                except Exception:
                    continue
    except Exception:
        return 0
    return total


def get_root_objects_payload() -> Dict[str, Any]:
    names = _list_lmod_top_dirs()
    icon_b64 = _encode_icon_to_base64(ICON_PATH)
    objects: List[Dict[str, Any]] = []
    for name in names:
        count = _count_module_children(LMOD_ROOT / name)
        objects.append(
            {
                "class": "WPLmodDependency",
                "id": f"/{name}",
                "icon": icon_b64,
                "title": name,
                "objects": int(count),
            }
        )
    return {"objects": objects}


def get_objects_for_path(path_str: str) -> Dict[str, Any]:
    rel = path_str.lstrip("/")
    base = (LMOD_ROOT / rel)
    objects: List[Dict[str, Any]] = []
    icon_b64 = _encode_icon_to_base64(ICON_PATH)
    icon_sw_b64 = _encode_icon_to_base64(SOFTWARE_ICON_PATH)
    try:
        if base.exists() and base.is_dir():
            for entry in sorted(base.iterdir()):
                if not entry.is_dir():
                    continue
                if entry.name == "modulefiles":
                    continue
                count = _count_module_children(entry)
                obj_id = f"/{rel}/{entry.name}" if rel else f"/{entry.name}"
                objects.append(
                    {
                        "class": "WPLmodDependency",
                        "id": obj_id,
                        "icon": icon_b64,
                        "title": entry.name,
                        "objects": int(count),
                    }
                )

            # Also expose software entries under immediate "modulefiles" directories
            for mf in [p for p in base.iterdir() if p.is_dir() and p.name == "modulefiles"]:
                try:
                    for sw in sorted(mf.iterdir()):
                        if not sw.is_dir():
                            continue
                        sw_id = f"/{rel}/{sw.name}" if rel else f"/{sw.name}"
                        objects.append(
                            {
                                "class": "WPLmodSoftware",
                                "id": sw_id,
                                "icon": icon_sw_b64,
                                "title": sw.name,
                                "objects": 0,
                            }
                        )
                except Exception:
                    continue
    except Exception:
        pass
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
            self._send_json({"RootName": "Available Software"})
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
    parser = argparse.ArgumentParser(description="Lmod Modules Provider")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8888, help="Port to bind (default: 8888)")
    args = parser.parse_args()
    serve(args.host, args.port)


