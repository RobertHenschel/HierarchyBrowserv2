#!/usr/bin/env python3
import argparse
import sys
import subprocess
from pathlib import Path
from typing import Dict, List
import getpass

# Allow running this file directly: add project root to sys.path
_THIS = Path(__file__).resolve()
_PROVIDERS_DIR = _THIS.parent.parent
_PROJECT_ROOT = _PROVIDERS_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from providers.base import ObjectProvider, ProviderOptions, WPGroup
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
SOFTWARE_MY_ICON_PATH = PROVIDER_DIR / "Resources" / "Software_IDCard.png"
PERSON_ICON_PATH = PROVIDER_DIR / "Resources" / "IDCard.png"

# Base directory that Lmod module families are stored under
LMOD_ROOT = Path("/N/soft/rhel8/modules/quartz")
MY_USER_ID = getpass.getuser().strip()
LOADED_MODULES_COUNT = 0
LOADED_MODULES = []

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

def _get_active_modules() -> tuple[int, list]:
    """
    Return a tuple: (string, list).
    The string is a summary of loaded modules, the list is the loaded module names.
    """
    try:
        # Use a shell so that the 'module' function is available in HPC environments
        try:
            out = subprocess.check_output(
                ["/bin/bash", "-lc", "module -t list 2>&1"],
                text=True,
                stderr=subprocess.STDOUT
            )
            # In terse mode, module names are one per line (or whitespace separated). Count non-empty lines.
            lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
            modules = []
            for line in lines:
                # split by "/" and take the first, if no "/" then take the whole line
                if "/" in line:
                    parts = line.split("/")
                    modules.append(parts[0])
                else:
                    modules.append(line)
            return len(modules), modules
        except Exception:
            pass
    except Exception:
        pass
    return 0, []

def _get_module_details(module_name: str) -> str:
    try:
        out = subprocess.check_output(
            ["/bin/bash", "-lc", f"module whatis {module_name} 2>&1"],
            text=True,
            stderr=subprocess.STDOUT
        )
        lines = []
        for ln in out.splitlines():
            s = ln.rstrip("\n")
            if not s.strip():
                continue
            idx = s.find(":")
            if idx == -1:
                continue
            # Keep everything after the first ':' and trim leading whitespace
            lines.append(s[idx + 1 :].lstrip())
        return "\n".join(lines)
    except Exception:
        return ""

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
        obj = WPGroup(
            id=f"/<Show:loaded:True>",
            title="My Software",
            icon=f"./resources/{PERSON_ICON_PATH.name}",
            objects=int(LOADED_MODULES_COUNT),
        )
        objects.append(obj.to_dict())
        return {"objects": objects}


    def get_objects_for_path(self, path_str: str) -> Dict[str, List[Dict]]:
        if path_str.strip() == "/" or path_str.strip() == "":
            return self.get_root_objects_payload()
        rel = path_str.lstrip("/")
        base = LMOD_ROOT / rel
        objects: List[Dict[str, object]] = []
        # HACK: Special treatment for the "My Software" group
        if path_str == "/<Show:loaded:True>":
            for sw in LOADED_MODULES:
                sw_id = f"/{sw}"
                details = _get_module_details(sw)
                obj = WPLmodSoftware(
                    id=sw_id,
                    title=sw,
                    icon=f"./resources/{SOFTWARE_MY_ICON_PATH.name}",
                    objects=0,
                    loaded=True,
                    details=details,
                )
                objects.append(obj.to_dict())
            return {"objects": objects}

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
                            loaded=False
                            if sw.name in LOADED_MODULES:
                                icon_sw_name = f"./resources/{SOFTWARE_MY_ICON_PATH.name}"
                                loaded=True
                            else:
                                icon_sw_name = f"./resources/{SOFTWARE_ICON_PATH.name}"
                                loaded=False
                            obj = WPLmodSoftware(
                                id=sw_id,
                                title=sw.name,
                                icon=icon_sw_name,
                                objects=0,
                                loaded=loaded,
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
            customize_icons="Software.png",  # e.g., "Partition.png;Job.png" (semicolon-separated)
        )
    )
    # Parse my loaded modules
    global LOADED_MODULES_COUNT
    global LOADED_MODULES
    LOADED_MODULES_COUNT, LOADED_MODULES = _get_active_modules()


    provider.serve(args.host, args.port)


if __name__ == "__main__":
    main()


