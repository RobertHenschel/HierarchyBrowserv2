import json
import socket
from typing import Any, Dict


def request_get_root_objects(host: str = "127.0.0.1", port: int = 8888) -> Dict[str, Any]:
    payload = {"method": "GetRootObjects"}
    message = json.dumps(payload, separators=(",", ":")) + "\n"

    with socket.create_connection((host, port), timeout=5) as s:
        s.sendall(message.encode("utf-8"))
        # Read one line response
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(4096)
            if not chunk:
                break
            buf += chunk

    text = buf.decode("utf-8").strip()
    return json.loads(text) if text else {}


if __name__ == "__main__":
    response = request_get_root_objects()
    print(json.dumps(response, indent=2))


