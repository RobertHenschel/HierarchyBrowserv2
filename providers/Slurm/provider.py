#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import re
from collections import Counter

# Allow running this file directly: add project root to sys.path
_THIS = Path(__file__).resolve()
_PROVIDERS_DIR = _THIS.parent.parent
_PROJECT_ROOT = _PROVIDERS_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from providers.base import ObjectProvider, ProviderOptions, ProviderObject, WPGroup
try:
    # When running as a package/module
    from providers.Slurm.model import WPSlurmPartition, WPSlurmJob  # type: ignore[import-not-found]
except Exception:
    # Fallback for direct script execution
    try:
        from .model import WPSlurmPartition, WPSlurmJob  # type: ignore[no-redef]
    except Exception:
        _dir = Path(__file__).resolve().parent
        if str(_dir) not in sys.path:
            sys.path.insert(0, str(_dir))
        from model import WPSlurmPartition, WPSlurmJob  # type: ignore[no-redef]


PROVIDER_DIR = Path(__file__).resolve().parent
PARTITION_ICON_PATH = PROVIDER_DIR / "Resources" / "Partition.png"
JOB_ICON_PATH = PROVIDER_DIR / "Resources" / "Job.png"


def _get_slurm_partitions() -> List[str]:
    # Prefer scontrol for structured output
    try:
        out = subprocess.check_output(["scontrol", "show", "partition", "-o"], text=True)
        names: List[str] = []
        for line in out.splitlines():
            line = line.strip()
            for token in line.split():
                if token.startswith("PartitionName="):
                    names.append(token.split("=", 1)[1])
                    break
        if names:
            return sorted(set(names))
    except Exception:
        pass

    # Fallback to sinfo
    try:
        out = subprocess.check_output(["sinfo", "-h", "-o", "%P"], text=True)
        names = []
        for line in out.splitlines():
            name = line.strip().rstrip("*")
            if name:
                names.append(name)
        return sorted(set(names))
    except Exception:
        return []


class SlurmProvider(ObjectProvider):
    def get_root_objects_payload(self) -> Dict[str, List[Dict]]:
        partitions = _get_slurm_partitions()
        icon_name = f"./resources/{PARTITION_ICON_PATH.name}"
        objects: List[Dict[str, object]] = []
        for part in partitions:
            try:
                job_count = len(_get_jobs_and_users_for_partition(part))
            except Exception:
                job_count = 0
            obj = WPSlurmPartition(
                id=f"/{part}",
                title=part,
                icon=icon_name,
                objects=int(job_count),
            )
            objects.append(obj.to_dict())
        return {"objects": objects}

    def get_objects_for_path(self, path_str: str) -> Dict[str, List[Dict]]:
        if path_str.strip() == "/" or path_str.strip() == "":
            return self.get_root_objects_payload()

        def list_for_base(base: str) -> List[ProviderObject]:
            part = base
            icon_name = f"./resources/{JOB_ICON_PATH.name}"
            typed: List[ProviderObject] = []
            for jid, user, nodes, state in _get_jobs_and_users_for_partition(part):
                typed.append(
                    WPSlurmJob(
                        id=f"/{part}/{jid}",
                        title=jid,
                        icon=icon_name,
                        objects=0,
                        jobarray=("_" in jid),
                        userid=user,
                        nodecount=int(nodes),
                        jobstate=state,
                    )
                )
            return typed

        allowed = {"userid", "jobarray", "nodecount", "jobstate"}
        return self.build_objects_for_path(
            path_str,
            list_for_base,
            allowed_group_fields=allowed,
            group_icon_filename=f"./resources/{JOB_ICON_PATH.name}",
x``        )

def _handle_show(base: str, prop_name: str, prop_value: str) -> Dict[str, List[Dict]]:
    # Deprecated: handled by ObjectProvider.build_objects_for_path
    return {"objects": []}

def _handle_group_by(base: str, prop_name: str) -> Dict[str, List[Dict]]:
    # Deprecated: handled by ObjectProvider.build_objects_for_path
    return {"objects": []}


def _get_jobs_and_users_for_partition(partition: str) -> List[Tuple[str, str, int, str]]:
    """Return list of (jobid, userid, nodecount, jobstate) for jobs in the given partition.

    Uses a single squeue call to retrieve all fields for efficiency.
    """
    part = partition.lstrip("/")
    try:
        out = subprocess.check_output(["squeue", "-h", "-p", part, "-o", "%i|%u|%D|%T"], text=True)
        pairs: List[Tuple[str, str, int, str]] = []
        for line in out.splitlines():
            entry = line.strip()
            if not entry:
                continue
            # Split exactly into 4 parts: jobid | user | nodecount | state
            parts = entry.split("|", 3)
            if len(parts) != 4:
                continue
            jid = parts[0].strip()
            user = parts[1].strip()
            try:
                nodes = int(parts[2].strip())
            except Exception:
                nodes = 0
            state_raw = parts[3].strip()
            # Normalize to human readable: capitalize only first letter, lower rest
            state = state_raw.capitalize()
            if jid:
                pairs.append((jid, user, nodes, state))
        return pairs
    except Exception:
        return []


def main() -> None:
    parser = argparse.ArgumentParser(description="Slurm Object Provider")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8888, help="Port to bind (default: 8888)")
    args = parser.parse_args()

    provider = SlurmProvider(
        ProviderOptions(
            root_name="Slurm Batch System",
            provider_dir=PROVIDER_DIR,
            resources_dir=PROVIDER_DIR / "Resources",
        )
    )
    provider.serve(args.host, args.port)


if __name__ == "__main__":
    main()


