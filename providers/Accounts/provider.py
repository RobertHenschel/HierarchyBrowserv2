#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Allow running this file directly: add project root to sys.path
_THIS = Path(__file__).resolve()
_PROVIDERS_DIR = _THIS.parent.parent
_PROJECT_ROOT = _PROVIDERS_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from providers.base import ObjectProvider, ProviderOptions
try:
    # When running as a package/module
    from providers.Accounts.model import WPAccount  # type: ignore[import-not-found]
except Exception:
    # Fallback for direct script execution
    try:
        from .model import WPAccount  # type: ignore[no-redef]
    except Exception:
        _dir = Path(__file__).resolve().parent
        if str(_dir) not in sys.path:
            sys.path.insert(0, str(_dir))
        from model import WPAccount  # type: ignore[no-redef]


PROVIDER_DIR = Path(__file__).resolve().parent
IDCARD_ICON_PATH = PROVIDER_DIR / "Resources" / "IDCard.png"


def _compute_systems() -> List[Tuple[str, str]]:
    return [
        ("Quartz", "quartz.uits.iu.edu"),
        ("Big Red 200", "bigred200.uits.iu.edu"),
        ("Research Desktop", "quartz.uits.iu.edu"),
    ]


def _has_ssh_account(hostname: str) -> bool:
    """Return True if we can batch-SSH to the host as the current user.

    Uses a short timeout, no password prompts, and avoids host key prompts.
    """
    cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "ConnectTimeout=5",
        hostname,
        "true",
    ]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=7)
        return proc.returncode == 0
    except Exception:
        return False


class AccountsProvider(ObjectProvider):
    def get_root_objects_payload(self) -> Dict[str, List[Dict]]:
        icon_name = f"./resources/{IDCARD_ICON_PATH.name}"
        objects: List[Dict[str, object]] = []
        for system_name, hostname in _compute_systems():
            try:
                ok = _has_ssh_account(hostname)
            except Exception:
                ok = False
            if not ok:
                continue
            obj = WPAccount(
                id=f"/{system_name}",
                title=system_name,
                icon=icon_name,
                objects=0,
            )
            objects.append(obj.to_dict())
        return {"objects": objects}

    def get_objects_for_path(self, path_str: str) -> Dict[str, List[Dict]]:
        # Accounts are leaves; only root listing is supported for now
        return self.get_root_objects_payload()


def main() -> None:
    parser = argparse.ArgumentParser(description="Accounts Object Provider")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8888, help="Port to bind (default: 8888)")
    args = parser.parse_args()

    provider = AccountsProvider(
        ProviderOptions(
            root_name="Accounts",
            provider_dir=PROVIDER_DIR,
            resources_dir=PROVIDER_DIR / "Resources",
        )
    )
    provider.serve(args.host, args.port)


if __name__ == "__main__":
    main()


