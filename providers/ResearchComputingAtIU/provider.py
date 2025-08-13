#!/usr/bin/env python3
import argparse
import base64
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Allow running this file directly: add project root to sys.path
_THIS = Path(__file__).resolve()
_PROVIDERS_DIR = _THIS.parent.parent
_PROJECT_ROOT = _PROVIDERS_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from providers.base import ObjectProvider, ProviderOptions
try:
    from providers.ResearchComputingAtIU.model import WPObject  # type: ignore[import-not-found]
except Exception:
    try:
        from .model import WPObject  # type: ignore[no-redef]
    except Exception:
        from model import WPObject  # type: ignore[no-redef]


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
                # Inline icon and normalize to resource filename
                icon_value = obj.get("icon")
                norm_icon: Optional[str] = None
                if isinstance(icon_value, str) and icon_value:
                    try:
                        icon_path = Path(icon_value)
                        if not icon_path.is_absolute():
                            icon_path = (PROVIDER_DIR / icon_path).resolve()
                        norm_icon = f"./resources/{icon_path.name}"
                    except Exception:
                        norm_icon = None

                # Build typed object with passthrough of extra fields
                core_keys = {"class", "id", "title", "icon", "objects"}
                extra = {k: v for k, v in obj.items() if k not in core_keys}
                typed = WPObject(
                    id=str(obj.get("id", "")),
                    title=str(obj.get("title", "")),
                    icon=norm_icon,
                    objects=int(objects_count),
                    extra=extra,
                )
                results.append(typed.to_dict())

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


class ResearchComputingProvider(ObjectProvider):
    def get_root_objects_payload(self) -> Dict[str, List[Dict[str, Any]]]:
        objects = _gather_objects_from_directory(OBJECTS_DIR)
        return {"objects": objects}


    def get_objects_for_path(self, path_str: str) -> Dict[str, List[Dict[str, Any]]]:
        if path_str.strip() == "/" or path_str.strip() == "":
            return self.get_root_objects_payload()
        rel = path_str.lstrip("/")
        base = OBJECTS_DIR.resolve()
        target = (base / rel).resolve()
        try:
            target.relative_to(base)
        except Exception:
            return {"objects": []}
        objects = _gather_objects_from_directory(target)
        return {"objects": objects}


def main() -> None:
    parser = argparse.ArgumentParser(description="ResearchComputingAtIU Object Provider")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8888, help="Port to bind (default: 8888)")
    args = parser.parse_args()

    provider = ResearchComputingProvider(
        ProviderOptions(
            root_name="Research Computing",
            provider_dir=PROVIDER_DIR,
            resources_dir=PROVIDER_DIR / "Resources",
        )
    )
    provider.serve(args.host, args.port)


if __name__ == "__main__":
    main()


