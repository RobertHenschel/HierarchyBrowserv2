#!/usr/bin/env python3
import argparse
import base64
import json
import socketserver
from pathlib import Path
from typing import Any, Dict, List, Union


PROVIDER_DIR = Path(__file__).resolve().parent
ROOT_OBJECTS_FILE = PROVIDER_DIR / "RootObjects.json"


def _encode_icon_to_base64(icon_path: Union[str, Path]) -> str:
    path = Path(icon_path)
    if not path.is_absolute():
        path = (PROVIDER_DIR / path).resolve()
    with path.open("rb") as f:
        raw = f.read()
    b64 = base64.b64encode(raw).decode("ascii")
    return b64


def get_root_objects_payload() -> Dict[str, Any]:
    with ROOT_OBJECTS_FILE.open("r", encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)

    objects: List[Dict[str, Any]] = data.get("objects", [])  # type: ignore[assignment]
    for obj in objects:
        icon_value = obj.get("icon")
        if isinstance(icon_value, str) and icon_value:
            try:
                obj["icon"] = _encode_icon_to_base64(icon_value)
            except FileNotFoundError:
                obj["icon"] = None
        # else: leave as-is

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


class JsonLineHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        line = self.rfile.readline()
        if not line:
            return
        try:
            text = line.decode("utf-8").strip()
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


