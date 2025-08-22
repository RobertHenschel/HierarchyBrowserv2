import json
import socket
from typing import Any, Dict


def request_get_root_objects(host: str = "127.0.0.1", port: int = 8888) -> Dict[str, Any]:
    payload = {"method": "GetRootObjects"}
    message = json.dumps(payload, separators=(",", ":")) + "\n"

    with socket.create_connection((host, port), timeout=10) as s:
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


def request_get_info(host: str = "127.0.0.1", port: int = 8888) -> Dict[str, Any]:
    payload = {"method": "GetInfo"}
    message = json.dumps(payload, separators=(",", ":")) + "\n"

    with socket.create_connection((host, port), timeout=10) as s:
        s.sendall(message.encode("utf-8"))
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(4096)
            if not chunk:
                break
            buf += chunk

    text = buf.decode("utf-8").strip()
    return json.loads(text) if text else {}


def request_get_objects(object_id: str, host: str = "127.0.0.1", port: int = 8888) -> Dict[str, Any]:
    payload = {"method": "GetObjects", "id": object_id}
    message = json.dumps(payload, separators=(",", ":")) + "\n"

    with socket.create_connection((host, port), timeout=10) as s:
        s.sendall(message.encode("utf-8"))
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
    # Truncate icon strings for brevity
    if isinstance(response, dict) and isinstance(response.get("objects"), list):
        for obj in response["objects"]:
            icon_value = obj.get("icon")
            if isinstance(icon_value, str):
                obj["icon"] = icon_value[:50] + ("..." if len(icon_value) > 50 else "")
    print("GetRootObjects:")
    print(json.dumps(response, indent=2))

    info = request_get_info()
    print("\nGetInfo:")
    print(json.dumps(info, indent=2))

    objects_cs = request_get_objects("/ComputeSystems")
    # Truncate icons in this listing as well
    if isinstance(objects_cs, dict) and isinstance(objects_cs.get("objects"), list):
        for obj in objects_cs["objects"]:
            icon_value = obj.get("icon")
            if isinstance(icon_value, str):
                obj["icon"] = icon_value[:50] + ("..." if len(icon_value) > 50 else "")
    print("\nGetObjects(/ComputeSystems):")
    print(json.dumps(objects_cs, indent=2))


