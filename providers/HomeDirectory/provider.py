#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path
from typing import Dict, List
import pwd
import grp

# Allow running this file directly: add project root to sys.path
_THIS = Path(__file__).resolve()
_PROVIDERS_DIR = _THIS.parent.parent
_PROJECT_ROOT = _PROVIDERS_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from providers.base import ObjectProvider, ProviderOptions, ProviderObject
try:
    from providers.HomeDirectory.model import WPDirectory, WPFile  # type: ignore[import-not-found]
except Exception:
    try:
        from .model import WPDirectory, WPFile  # type: ignore[no-redef]
    except Exception:
        from model import WPDirectory, WPFile  # type: ignore[no-redef]


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
                dir_owner = None
                dir_group = None
                try:
                    st = entry.stat()
                    dir_owner = pwd.getpwuid(st.st_uid).pw_name
                    dir_group = grp.getgrgid(st.st_gid).gr_name
                except Exception:
                    pass
                obj = WPDirectory(
                    id=f"/{name}",
                    title=name,
                    icon=dir_icon_name,
                    objects=int(count),
                    owner=dir_owner,
                    group=dir_group,
                )
                objects.append(obj.to_dict())
            elif entry.is_file():
                owner_name = None
                group_name = None
                try:
                    st = entry.stat()
                    owner_name = pwd.getpwuid(st.st_uid).pw_name
                    group_name = grp.getgrgid(st.st_gid).gr_name
                except Exception:
                    pass
                obj = WPFile(
                    id=f"/{name}",
                    title=name,
                    icon=file_icon_name,
                    objects=0,
                    owner=owner_name,
                    group=group_name,
                )
                objects.append(obj.to_dict())

        return {"objects": objects}

    def get_objects_for_path(self, path_str: str) -> Dict[str, List[Dict]]:
        if path_str.strip() == "/" or path_str.strip() == "":
            return self.get_root_objects_payload()

        home = Path.home().resolve()
        dir_icon_name = f"./resources/{DIR_ICON_PATH.name}"
        file_icon_name = f"./resources/{FILE_ICON_PATH.name}"

        def list_for_base(base_rel: str) -> List[ProviderObject]:
            rel = base_rel
            target = (home / rel).resolve()
            try:
                target.relative_to(home)
            except Exception:
                return []
            if not target.exists() or not target.is_dir():
                return []
            try:
                entries = sorted(target.iterdir(), key=lambda p: p.name.lower())
            except Exception:
                entries = []
            typed: List[ProviderObject] = []
            for entry in entries:
                name = entry.name
                if entry.is_dir():
                    try:
                        count = sum(1 for _ in entry.iterdir())
                    except Exception:
                        count = 0
                    d_owner = None
                    d_group = None
                    try:
                        st = entry.stat()
                        d_owner = pwd.getpwuid(st.st_uid).pw_name
                        d_group = grp.getgrgid(st.st_gid).gr_name
                    except Exception:
                        pass
                    typed.append(
                        WPDirectory(
                            id=f"/{rel}/{name}" if rel else f"/{name}",
                            title=name,
                            icon=dir_icon_name,
                            objects=int(count),
                            owner=d_owner,
                            group=d_group,
                        )
                    )
                elif entry.is_file():
                    owner_name = None
                    group_name = None
                    try:
                        st = entry.stat()
                        owner_name = pwd.getpwuid(st.st_uid).pw_name
                        group_name = grp.getgrgid(st.st_gid).gr_name
                    except Exception:
                        pass
                    typed.append(
                        WPFile(
                            id=f"/{rel}/{name}" if rel else f"/{name}",
                            title=name,
                            icon=file_icon_name,
                            objects=0,
                            owner=owner_name,
                            group=group_name,
                        )
                    )
            return typed

        return self.build_objects_for_path(
            path_str,
            list_for_base,
            group_icon_filename="./resources/Group.png",
        )


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


