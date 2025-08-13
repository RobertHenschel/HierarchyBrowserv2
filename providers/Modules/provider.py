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
try:
    from providers.Modules.model import WPLmodDependency, WPLmodSoftware  # type: ignore[import-not-found]
except Exception:
    try:
        from .model import WPLmodDependency, WPLmodSoftware  # type: ignore[no-redef]
    except Exception:
        from model import WPLmodDependency, WPLmodSoftware  # type: ignore[no-redef]


PROVIDER_DIR = Path(__file__).resolve().parent
# The instruction references "./resources/Box.png". Use a conventional
# Resources directory as in other providers; either works when authored.
ICON_PATH = PROVIDER_DIR / "Resources" / "Box.png"
SOFTWARE_ICON_PATH = PROVIDER_DIR / "Resources" / "Software.png"

# Base directory that Lmod module families are stored under
LMOD_ROOT = Path("/N/soft/rhel8/modules/quartz")


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


class ModulesProvider(ObjectProvider):
    def get_root_objects_payload(self) -> Dict[str, List[Dict]]:
        names = _list_lmod_top_dirs()
        icon_name = f"./resources/{ICON_PATH.name}"
        objects: List[Dict[str, object]] = []
        for name in names:
            count = _count_module_children(LMOD_ROOT / name)
            obj = WPLmodDependency(
                id=f"/{name}",
                title=name,
                icon=icon_name,
                objects=int(count),
            )
            objects.append(obj.to_dict())
        return {"objects": objects}


    def get_objects_for_path(self, path_str: str) -> Dict[str, List[Dict]]:
        if path_str.strip() == "/" or path_str.strip() == "":
            return self.get_root_objects_payload()
        rel = path_str.lstrip("/")
        base = LMOD_ROOT / rel
        objects: List[Dict[str, object]] = []
        icon_name = f"./resources/{ICON_PATH.name}"
        icon_sw_name = f"./resources/{SOFTWARE_ICON_PATH.name}"
        try:
            if base.exists() and base.is_dir():
                for entry in sorted(base.iterdir()):
                    if not entry.is_dir():
                        continue
                    if entry.name == "modulefiles":
                        continue
                    count = _count_module_children(entry)
                    obj_id = f"/{rel}/{entry.name}" if rel else f"/{entry.name}"
                    obj = WPLmodDependency(
                        id=obj_id,
                        title=entry.name,
                        icon=icon_name,
                        objects=int(count),
                    )
                    objects.append(obj.to_dict())

                # Also expose software entries under immediate "modulefiles" directories
                for mf in [p for p in base.iterdir() if p.is_dir() and p.name == "modulefiles"]:
                    try:
                        for sw in sorted(mf.iterdir()):
                            if not sw.is_dir():
                                continue
                            sw_id = f"/{rel}/{sw.name}" if rel else f"/{sw.name}"
                            obj = WPLmodSoftware(
                                id=sw_id,
                                title=sw.name,
                                icon=icon_sw_name,
                                objects=0,
                            )
                            objects.append(obj.to_dict())
                    except Exception:
                        continue
        except Exception:
            pass
        return {"objects": objects}


def main() -> None:
    parser = argparse.ArgumentParser(description="Lmod Modules Provider")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8888, help="Port to bind (default: 8888)")
    args = parser.parse_args()

    provider = ModulesProvider(
        ProviderOptions(
            root_name="Available Software",
            provider_dir=PROVIDER_DIR,
            resources_dir=PROVIDER_DIR / "Resources",
        )
    )
    provider.serve(args.host, args.port)


if __name__ == "__main__":
    main()


