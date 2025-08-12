#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path
from typing import Dict, List

# Allow running this file directly: add project root to sys.path
_THIS = Path(__file__).resolve()
_PROVIDERS_DIR = _THIS.parent.parent
_PROJECT_ROOT = _PROVIDERS_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from providers.base import ObjectProvider, ProviderOptions


PROVIDER_DIR = Path(__file__).resolve().parent
DIR_ICON_PATH = PROVIDER_DIR / "Resources" / "Directory.png"
FILE_ICON_PATH = PROVIDER_DIR / "Resources" / "File.png"


class HomeDirectoryProvider(ObjectProvider):
    def get_root_objects_payload(self) -> Dict[str, List[Dict]]:
        home = Path.home()
        dir_icon_name = f"./resources/{DIR_ICON_PATH.name}"
        file_icon_name = f"./resources/{FILE_ICON_PATH.name}"
        objects: List[Dict[str, object]] = []

        try:
            entries = sorted(home.iterdir(), key=lambda p: p.name.lower())
        except Exception:
            entries = []

        for entry in entries:
            name = entry.name
            if name in (".", ".."):
                continue
            if entry.is_dir():
                try:
                    count = sum(1 for _ in entry.iterdir())
                except Exception:
                    count = 0
                objects.append(
                    {
                        "class": "WPDirectory",
                        "id": f"/{name}",
                        "icon": dir_icon_name,
                        "title": name,
                        "objects": int(count),
                    }
                )
            elif entry.is_file():
                objects.append(
                    {
                        "class": "WPFile",
                        "id": f"/{name}",
                        "icon": file_icon_name,
                        "title": name,
                        "objects": 0,
                    }
                )

        return {"objects": objects}

    def get_objects_for_path(self, path_str: str) -> Dict[str, List[Dict]]:
        if path_str.strip() == "/" or path_str.strip() == "":
            return self.get_root_objects_payload()
        home = Path.home().resolve()
        rel = path_str.lstrip("/")
        target = (home / rel).resolve()

        try:
            target.relative_to(home)
        except Exception:
            return {"objects": []}

        dir_icon_name = f"./resources/{DIR_ICON_PATH.name}"
        file_icon_name = f"./resources/{FILE_ICON_PATH.name}"
        objects: List[Dict[str, object]] = []

        if not target.exists() or not target.is_dir():
            return {"objects": objects}

        try:
            entries = sorted(target.iterdir(), key=lambda p: p.name.lower())
        except Exception:
            entries = []

        for entry in entries:
            name = entry.name
            if entry.is_dir():
                try:
                    count = sum(1 for _ in entry.iterdir())
                except Exception:
                    count = 0
                objects.append(
                    {
                        "class": "WPDirectory",
                        "id": f"/{rel}/{name}" if rel else f"/{name}",
                        "icon": dir_icon_name,
                        "title": name,
                        "objects": int(count),
                    }
                )
            elif entry.is_file():
                objects.append(
                    {
                        "class": "WPFile",
                        "id": f"/{rel}/{name}" if rel else f"/{name}",
                        "icon": file_icon_name,
                        "title": name,
                        "objects": 0,
                    }
                )

        return {"objects": objects}


def main() -> None:
    parser = argparse.ArgumentParser(description="Home Directory Provider")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8888, help="Port to bind (default: 8888)")
    args = parser.parse_args()

    provider = HomeDirectoryProvider(
        ProviderOptions(
            root_name="Quartz Home Directory",
            provider_dir=PROVIDER_DIR,
            resources_dir=PROVIDER_DIR / "Resources",
        )
    )
    provider.serve(args.host, args.port)


if __name__ == "__main__":
    main()


