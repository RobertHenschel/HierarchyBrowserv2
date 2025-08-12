#!/usr/bin/env python3
import argparse
import json
import socketserver
from typing import Any, Dict, Optional


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


def get_root_objects_payload() -> Dict[str, Any]:
    return {"objects": []}


def get_objects_for_path(_path_str: str) -> Dict[str, Any]:
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
            self._send_json({"RootName": "Slurm Batch System"})
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
    parser = argparse.ArgumentParser(description="Slurm Object Provider")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8888, help="Port to bind (default: 8888)")
    args = parser.parse_args()
    serve(args.host, args.port)


