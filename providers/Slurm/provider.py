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

from providers.base import ObjectProvider, ProviderOptions
try:
    # When running as a package/module
    from providers.Slurm.model import WPSlurmPartition, WPSlurmJob, WPSlurmJobGroup  # type: ignore[import-not-found]
except Exception:
    # Fallback for direct script execution
    try:
        from .model import WPSlurmPartition, WPSlurmJob, WPSlurmJobGroup  # type: ignore[no-redef]
    except Exception:
        _dir = Path(__file__).resolve().parent
        if str(_dir) not in sys.path:
            sys.path.insert(0, str(_dir))
        from model import WPSlurmPartition, WPSlurmJob, WPSlurmJobGroup  # type: ignore[no-redef]


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
        part = path_str.lstrip("/")
        # Match e.g. "hopper/<GroupBy:userid>"
        m = re.match(r"^(.*)/<([^:>]+):([^>]+)>$", part)
        prop_name = None
        if m:
            base, command, prop_name = m.groups()
            if command == "GroupBy":
                return _handle_group_by(base, prop_name)
        # Match e.g. "hopper/<Show:userid:value>"
        m = re.match(r"^(.*)/<([^:>]+):([^>]+):([^>]+)>$", part)
        prop_name = None
        if m:
            base, command, prop_name, prop_value = m.groups()
            if command == "Show":
                return _handle_show(base, prop_name, prop_value)

        job_user_pairs = _get_jobs_and_users_for_partition(part)
        icon_name = f"./resources/{JOB_ICON_PATH.name}"
        objects: List[Dict[str, object]] = []
        for jid, user in job_user_pairs:
            obj = WPSlurmJob(
                id=f"/{part}/{jid}",
                title=jid,
                icon=icon_name,
                objects=0,
                jobarray=("_" in jid),
                userid=user,
            )
            objects.append(obj.to_dict())
        return {"objects": objects}

def _handle_show(base: str, prop_name: str, prop_value: str) -> Dict[str, List[Dict]]:
    print(f"Base: {base}, Prop Name: {prop_name}, Prop Value: {prop_value}")
    try:
        job_user_pairs = _get_jobs_and_users_for_partition(base)
        # Create objects of type WPSlurmJob from the return of job_user_pairs
        objects: List[Dict[str, object]] = []
        icon_name = f"./resources/{JOB_ICON_PATH.name}"
        for jid, user in job_user_pairs:
            obj = WPSlurmJob(
                id=f"/{base}/{jid}",
                title=jid,
                icon=icon_name,
                objects=0,
                jobarray=("_" in jid),
                userid=user,
            )
            objects.append(obj.to_dict())
        # Now check if the property extracted as "p" is a valid property of the WPSlurmJob object and if so use it to group the jobs
        if prop_name in WPSlurmJob.__dataclass_fields__:
            # Count occurrences of each property value across the dict objects
            grouped_objects: List[Dict[str, object]] = []
            for o in objects:
                try:
                    val = o.get(prop_name)  # type: ignore[arg-type]
                except Exception:
                    val = None
                if val is None:
                    continue
                if str(val) == prop_value:
                    grouped_objects.append(o)
    except Exception as e:
        print(e)
    return {"objects": grouped_objects}

def _handle_group_by(base: str, prop_name: str) -> Dict[str, List[Dict]]:
    job_user_pairs = _get_jobs_and_users_for_partition(base)
    # Create objects of type WPSlurmJob from the return of job_user_pairs
    objects: List[Dict[str, object]] = []
    icon_name = f"./resources/{JOB_ICON_PATH.name}"
    for jid, user in job_user_pairs:
        obj = WPSlurmJob(
            id=f"/{base}/{jid}",
            title=jid,
            icon=icon_name,
            objects=0,
            jobarray=("_" in jid),
            userid=user,
        )
        objects.append(obj.to_dict())
    # Now check if the property extracted as "p" is a valid property of the WPSlurmJob object and if so use it to group the jobs
    if prop_name in WPSlurmJob.__dataclass_fields__:
        # Count occurrences of each property value across the dict objects
        value_counts: Dict[object, int] = {}
        for o in objects:
            try:
                val = o.get(prop_name)  # type: ignore[arg-type]
            except Exception:
                val = None
            if val is None:
                continue
            value_counts[val] = value_counts.get(val, 0) + 1
        grouped_objects: List[Dict[str, object]] = []
        for value, count in value_counts.items():
            grp = WPSlurmJobGroup(
                id=f"/{base}/<Show:{prop_name}:{value}>",
                title=str(value),
                icon=icon_name,
                objects=int(count),
            )
            grouped_objects.append(grp.to_dict())
        return {"objects": grouped_objects}


def _get_jobs_and_users_for_partition(partition: str) -> List[Tuple[str, str]]:
    """Return list of (jobid, userid) for jobs in the given partition.

    Uses a single squeue call to retrieve both fields for efficiency.
    """
    part = partition.lstrip("/")
    try:
        out = subprocess.check_output(["squeue", "-h", "-p", part, "-o", "%i|%u"], text=True)
        pairs: List[Tuple[str, str]] = []
        for line in out.splitlines():
            entry = line.strip()
            if not entry:
                continue
            jid, sep, user = entry.partition("|")
            jid = jid.strip()
            user = user.strip() if sep else ""
            if jid:
                pairs.append((jid, user))
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


