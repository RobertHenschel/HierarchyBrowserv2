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
            objects.append(
                {
                    "class": "WPSlurmPartition",
                    "id": f"/{part}",
                    "icon": icon_name,
                    "title": part,
                    "objects": int(job_count),
                }
            )
        return {"objects": objects}

    def get_objects_for_path(self, path_str: str) -> Dict[str, List[Dict]]:
        if path_str.strip() == "/" or path_str.strip() == "":
            return self.get_root_objects_payload()
        part = path_str.lstrip("/")
        # Match e.g. "hopper/<GroupBy:userid>"
        m = re.match(r"^(.*)/<([^:>]+):([^>]+)>$", part)
        property = None
        if m:
            base, command, property = m.groups()
            if command == "GroupBy":
                job_user_pairs = _get_jobs_and_users_for_partition(base)
                icon_name = f"./resources/{JOB_ICON_PATH.name}"
                objects: List[Dict[str, object]] = []
                user_counts = Counter(user for _, user in job_user_pairs)
                for user in user_counts:
                    objects.append(
                        {
                            "class": "WPSlurmJobGroup",
                            "id": f"/{base}/{user}",
                            "icon": icon_name,
                            "title": user,
                            "objects": user_counts[user],
                        })
                return {"objects": objects}


        job_user_pairs = _get_jobs_and_users_for_partition(part)
        icon_name = f"./resources/{JOB_ICON_PATH.name}"
        objects: List[Dict[str, object]] = []
        for jid, user in job_user_pairs:
            objects.append(
                {
                    "class": "WPSlurmJob",
                    "id": f"/{part}/{jid}",
                    "icon": icon_name,
                    "title": jid,
                    "jobarray": ("_" in jid),
                    "userid": user,
                    "objects": 0,
                }
            )
        return {"objects": objects}





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


