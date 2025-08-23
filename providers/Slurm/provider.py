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
GROUP_ICON_PATH = PROVIDER_DIR / "Resources" / "IDCard.png"


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

def _get_my_jobs_count() -> int:
    try:
        out = subprocess.check_output(["squeue", "-h", "--me", "-o", "%i"], text=True)
        return len(out.splitlines())
    except Exception:
        return 0

def _get_my_userid() -> str:
    try:
        out = subprocess.check_output(["whoami"], text=True)
        return out.strip()
    except Exception:
        return ""

class SlurmProvider(ObjectProvider):
    def get_root_objects_payload(self) -> Dict[str, List[Dict]]:
        partitions = _get_slurm_partitions()
        partition_name = f"./resources/{PARTITION_ICON_PATH.name}"
        group_name = f"./resources/{GROUP_ICON_PATH.name}"
        objects: List[Dict[str, object]] = []
        for part in partitions:
            try:
                job_count = len(_get_jobs_for_partition(part))
            except Exception:
                job_count = 0
            obj = WPSlurmPartition(
                id=f"/{part}",
                title=part,
                icon=partition_name,
                objects=int(job_count),
            )
            objects.append(obj.to_dict())
        
        obj = WPGroup(
            id=f"/<Show:userid:{_get_my_userid()}>",
            title="My Jobs",
            icon=group_name,
            objects=int(_get_my_jobs_count()),
        )
        objects.append(obj.to_dict())
        return {"objects": objects}

    def get_objects_for_path(self, path_str: str) -> Dict[str, List[Dict]]:
        if path_str.strip() == "/" or path_str.strip() == "":
            return self.get_root_objects_payload()


        def list_for_base(base: str) -> List[ProviderObject]:
            # Always extract the partition as the first segment, ignoring any command tokens
            segments = base.strip("/").split("/")
            part = segments[0] if segments else ""
            return _get_jobs_for_partition(part)

        return self.build_objects_for_path(
            path_str,
            list_for_base,
            group_icon_filename=f"./resources/Group.png",
        )

def _get_jobs_for_partition(partition: str) -> List[ProviderObject]:
    """Return typed WPSlurmJob objects for jobs in the given partition.

    Uses a single squeue call to retrieve all fields for efficiency.
    """
    part = partition.lstrip("/")
    icon_name = f"./resources/{JOB_ICON_PATH.name}"
    try:
        out = ""
        if part == "":
            out = subprocess.check_output(["squeue", "-h", "-o", "%i|%u|%D|%T|%P"], text=True)
        else:
            out = subprocess.check_output(["squeue", "-h", "-p", part, "-o", "%i|%u|%D|%T|%P"], text=True)
        typed: List[ProviderObject] = []
        for line in out.splitlines():
            entry = line.strip()
            if not entry:
                continue
            # Split exactly into 4 parts: jobid | user | nodecount | state | partition
            parts = entry.split("|", 4)
            if len(parts) != 5:
                continue
            jid = parts[0].strip()
            user = parts[1].strip()
            try:
                nodes = int(parts[2].strip())
            except Exception:
                nodes = 0
            state_raw = parts[3].strip()
            partition_name = parts[4].strip()
            # Normalize to human readable: capitalize only first letter, lower rest
            state = state_raw.capitalize()
            if not jid:
                continue
            job_id = f"/{partition_name}/{jid}"
            if job_id.startswith("//"):
                job_id = job_id[1:]
            typed.append(
                WPSlurmJob(
                    id=job_id,
                    title=jid,
                    icon=icon_name,
                    objects=0,
                    jobarray=("_" in jid),
                    userid=user,
                    nodecount=int(nodes),
                    jobstate=state,
                    partition=partition_name,
                )
            )
        return typed
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


