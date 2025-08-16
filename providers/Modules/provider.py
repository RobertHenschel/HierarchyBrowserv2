#!/usr/bin/env python3
import argparse
import os
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

    def search(self, search_input: str, recursive: bool = True, search_handle: Optional[dict] = None) -> List[WPLmodSoftware]:
        """
        Search for software modules using 'module spider'.
        """
        print(f"DEBUG: Starting search for '{search_input}', recursive={recursive}")
        print(f"DEBUG: search_handle={search_handle}")
        
        # Determine search ID - use existing one from handle or generate new one
        if search_handle and isinstance(search_handle, dict) and "id" in search_handle:
            search_id = search_handle["id"]
            print(f"DEBUG: Using existing search_id from handle: {search_id}")
        else:
            search_id = str(uuid.uuid4())
            print(f"DEBUG: Generated new search_id: {search_id}")
        
        # Check if search is already completed
        if search_id in self._search_status and self._search_status[search_id] == "done":
            print(f"DEBUG: Search {search_id} already done, returning {len(self._search_results[search_id])} results")
            # Return completion progress object + results
            results = self._search_results[search_id]
            completion_objects = [WPLmodSearchProgress(
                id=f"/search_progress/{search_id}",
                title=f"Search for '{search_input}' completed",
                state="done",
                icon=f"./resources/{ICON_PATH.name}",
                objects=len(results)
            )]
            return completion_objects + results
        
        # If search is not running yet, start it
        if search_id not in self._search_status or self._search_status[search_id] != "running":
            print(f"DEBUG: Starting new search thread for {search_id}")
            self._search_status[search_id] = "running"
            self._search_results[search_id] = []
            thread = threading.Thread(
                target=self._run_module_spider,
                args=(search_id, search_input, recursive)
            )
            thread.daemon = True
            thread.start()
        
        # For initial request (no search_handle), return search handle to trigger async mode
        if not search_handle:
            print(f"DEBUG: Initial search request, returning search handle")
            return [WPLmodSearchHandle(
                id=search_id,
                title=f"Searching for '{search_input}'...",
                search_string=search_input,
                recursive=recursive,
                icon=f"./resources/{ICON_PATH.name}",
                objects=0
            )]
        
        # For polling requests (with search_handle), return progress object if still running
        if self._search_status[search_id] == "running":
            print(f"DEBUG: Search {search_id} still running, returning progress object")
            return [WPLmodSearchProgress(
                id=f"/search_progress/{search_id}",
                title=f"Searching for '{search_input}'...",
                state="ongoing",
                icon=f"./resources/{ICON_PATH.name}",
                objects=0
            )]
        
        # Return results if completed - include a completion progress object
        results = self._search_results.get(search_id, [])
        print(f"DEBUG: Search {search_id} completed, returning {len(results)} results")
        
        # Add completion progress object so browser knows search is done
        completion_objects = [WPLmodSearchProgress(
            id=f"/search_progress/{search_id}",
            title=f"Search for '{search_input}' completed",
            state="done",
            icon=f"./resources/{ICON_PATH.name}",
            objects=len(results)
        )]
        
        return completion_objects + results

    def _run_module_spider(self, search_id: str, search_input: str, recursive: bool) -> None:
        """
        Run 'module spider' command and parse results into WPLmodSoftware objects.
        """
        print(f"DEBUG: _run_module_spider starting for search_id={search_id}, search_input='{search_input}'")
        try:
            # The 'module' command is a shell function, not a binary. We need to run it through the shell.
            # Use stderr redirect to stdout as shown by user: module spider python 2>&1
            command = f"module spider {search_input} 2>&1"
            print(f"DEBUG: Running command: {command}")
            
            # Run through shell to access the module function
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
                env=os.environ.copy(),  # Ensure environment variables are passed
                executable="/bin/bash"   # Use bash explicitly
            )
            
            print(f"DEBUG: Command completed. Exit code: {result.returncode}")
            print(f"DEBUG: Stdout length: {len(result.stdout)}")
            print(f"DEBUG: Stderr length: {len(result.stderr)}")
            if result.stdout:
                print(f"DEBUG: First 200 chars of stdout: {result.stdout[:200]}...")
            
            # Parse the output (now comes from stdout due to 2>&1 redirect)
            software_list = self._parse_module_spider_output(result.stdout, search_input)
            print(f"DEBUG: Parsed {len(software_list)} software items")
            
            # Store results
            self._search_results[search_id] = software_list
            self._search_status[search_id] = "done"
            print(f"DEBUG: Search {search_id} marked as done")
            
        except Exception as e:
            # On error, still mark as done but with empty results
            print(f"DEBUG: Error running module spider: {e}")
            self._search_results[search_id] = []
            self._search_status[search_id] = "done"

    def _parse_module_spider_output(self, output: str, search_input: str) -> List[WPLmodSoftware]:
        """
        Parse module spider output to extract software modules.
        LMOD spider output looks like:
        
        -----------------------------------------------------------------------------------------------------------------------------------------
          python:
        -----------------------------------------------------------------------------------------------------------------------------------------
            Description:
              Specifically for use on GPU nodes, The Deep Learning software stack...
        
             Versions:
                python/gpu/3.10.10
                python/gpu/3.11.5
                python/3.11.4
                python/3.12.4
                python/3.13.5
             Other possible modules matches:
                spyder/python3.12  spyder/python3.13  vibrant/python3.7  wxpython
        """
        software_list: List[WPLmodSoftware] = []
        icon_name = f"./resources/{SOFTWARE_ICON_PATH.name}"
        
        if not output:
            return software_list
            
        lines = output.split('\n')
        i = 0
        in_versions_section = False
        in_other_matches_section = False
        
        while i < len(lines):
            line = lines[i].strip()
            i += 1
            
            if not line:
                continue
                
            # Skip separator lines
            if line.startswith('-' * 10):
                continue
                
            # Check for Versions section
            if line.lower().strip().startswith("versions:"):
                in_versions_section = True
                in_other_matches_section = False
                continue
                
            # Check for Other possible modules matches section
            if "other possible modules matches:" in line.lower():
                in_versions_section = False
                in_other_matches_section = True
                continue
                
            # End sections when we hit explanatory text or commands
            if any(marker in line.lower() for marker in [
                "to find other possible", "for detailed information", 
                "note that names", "for example:", "$ module"
            ]):
                in_versions_section = False
                in_other_matches_section = False
                continue
            
            # Parse versions section - these are the full module names
            if in_versions_section and line and not line.lower().startswith('description:'):
                # Look for module names like "python/gpu/3.10.10" or "python/3.11.4"
                # Split by whitespace and check each token
                tokens = line.split()
                for token in tokens:
                    # Only include tokens that look like module names (contain / or match search exactly)
                    if ('/' in token and search_input.lower() in token.lower()) or token.lower() == search_input.lower():
                        # Skip tokens that look like commands or paths starting with special chars
                        if not token.startswith(('$', '#', '/', '.', '-')) and len(token) > 1:
                            software = WPLmodSoftware(
                                id=f"/search/{token}",
                                title=token,
                                icon=icon_name,
                                objects=0
                            )
                            software_list.append(software)
            
            # Parse other matches section - these might be related modules
            elif in_other_matches_section and line:
                tokens = line.split()
                for token in tokens:
                    # Include if it contains our search term and looks like a module name
                    if (search_input.lower() in token.lower() and 
                        not token.startswith(('$', '#', '/', '.', '-', '(', ')')) and
                        len(token) > 1 and
                        not token.lower() in ['the', 'and', 'or', 'with', 'for', 'to', 'of', 'in', 'on']):
                        software = WPLmodSoftware(
                            id=f"/search/{token}",
                            title=token,
                            icon=icon_name,
                            objects=0
                        )
                        software_list.append(software)
            
            # Also look for main module header (like "python:")
            elif (line.endswith(':') and 
                  search_input.lower() in line.lower() and 
                  not in_versions_section and 
                  not in_other_matches_section):
                module_base = line[:-1].strip()
                if module_base and module_base.lower() == search_input.lower():
                    software = WPLmodSoftware(
                        id=f"/search/{module_base}",
                        title=module_base,
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


