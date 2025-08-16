#!/usr/bin/env python3
import argparse
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

# Allow running this file directly: add project root to sys.path
_THIS = Path(__file__).resolve()
_PROVIDERS_DIR = _THIS.parent.parent
_PROJECT_ROOT = _PROVIDERS_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from providers.base import ObjectProvider, ProviderOptions
try:
    from providers.Modules.model import WPLmodDependency, WPLmodSoftware  # type: ignore[import-not-found]
    from providers.Modules.search_objects import WPLmodSearchHandle, WPLmodSearchProgress  # type: ignore[import-not-found]
except Exception:
    try:
        from .model import WPLmodDependency, WPLmodSoftware  # type: ignore[no-redef]
        from .search_objects import WPLmodSearchHandle, WPLmodSearchProgress  # type: ignore[no-redef]
    except Exception:
        from model import WPLmodDependency, WPLmodSoftware  # type: ignore[no-redef]
        from search_objects import WPLmodSearchHandle, WPLmodSearchProgress  # type: ignore[no-redef]


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
    def __init__(self, options: ProviderOptions) -> None:
        super().__init__(options)
        # Track ongoing searches
        self._search_results: Dict[str, List[WPLmodSoftware]] = {}
        self._search_status: Dict[str, str] = {}  # 'ongoing' or 'done'

    def search(self, search_input: str, recursive: bool = True, search_handle: Optional[dict] = None) -> list:
        """
        Search for modules using 'module spider'. Always returns a search handle object first,
        then processes results asynchronously.
        """
        if search_handle is not None:
            # This is a status check for an existing search
            handle_id = search_handle.get("id", "")
            if handle_id in self._search_status:
                status = self._search_status[handle_id]
                results = self._search_results.get(handle_id, [])
                
                # Always include progress object
                progress = WPLmodSearchProgress(
                    id=handle_id,
                    title=f"Search progress for '{search_input}'",
                    icon=f"./resources/{SOFTWARE_ICON_PATH.name}",
                    objects=0,
                    state=status
                )
                
                # Return results + progress
                return results + [progress]
            else:
                # Unknown search handle
                return []
        
        # New search request - create search handle and start async search
        search_id = str(uuid.uuid4())
        self._search_status[search_id] = "ongoing"
        self._search_results[search_id] = []
        
        # Start search in background thread
        search_thread = threading.Thread(
            target=self._run_module_spider,
            args=(search_id, search_input, recursive)
        )
        search_thread.daemon = True
        search_thread.start()
        
        # Return search handle object
        handle = WPLmodSearchHandle(
            id=search_id,
            title=f"Searching for '{search_input}'...",
            icon=f"./resources/{ICON_PATH.name}",
            objects=0,
            search_string=search_input,
            recursive=recursive
        )
        return [handle]

    def _run_module_spider(self, search_id: str, search_input: str, recursive: bool) -> None:
        """
        Run 'module spider' command and parse results into WPLmodSoftware objects.
        """
        try:
            # Run module spider command
            # Note: module output goes to stderr, not stdout
            result = subprocess.run(
                ["module", "spider", search_input],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Parse the output (comes from stderr)
            software_list = self._parse_module_spider_output(result.stderr, search_input)
            
            # Store results
            self._search_results[search_id] = software_list
            self._search_status[search_id] = "done"
            
        except Exception as e:
            # On error, still mark as done but with empty results
            print(f"Error running module spider: {e}")
            self._search_results[search_id] = []
            self._search_status[search_id] = "done"

    def _parse_module_spider_output(self, output: str, search_input: str) -> List[WPLmodSoftware]:
        """
        Parse module spider output to extract software modules.
        """
        software_list: List[WPLmodSoftware] = []
        icon_name = f"./resources/{SOFTWARE_ICON_PATH.name}"
        
        if not output:
            return software_list
            
        # Module spider output format varies, but typically shows module names
        # Let's look for lines that contain module names
        lines = output.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Skip header/informational lines
            if any(skip in line.lower() for skip in ["the following", "use", "where:", "help", "versions:"]):
                continue
                
            # Look for module names (typically start with a letter/number and contain version info)
            if search_input.lower() in line.lower():
                # Extract module name (before any description or version info)
                module_name = line.split()[0] if line.split() else line
                
                # Clean up module name
                module_name = module_name.strip('.:-()')
                
                if module_name and len(module_name) > 0:
                    software = WPLmodSoftware(
                        id=f"/search/{module_name}",
                        title=module_name,
                        icon=icon_name,
                        objects=0
                    )
                    software_list.append(software)
        
        # Remove duplicates based on title
        seen = set()
        unique_software = []
        for sw in software_list:
            if sw.title not in seen:
                seen.add(sw.title)
                unique_software.append(sw)
                
        return unique_software[:50]  # Limit to 50 results
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


