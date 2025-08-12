#!/usr/bin/env python3
import argparse
import subprocess
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
                job_count = len(_get_jobs_for_partition(part))
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
        job_ids = _get_jobs_for_partition(part)
        icon_name = f"./resources/{JOB_ICON_PATH.name}"
        objects: List[Dict[str, object]] = []
        for jid in job_ids:
            objects.append(
                {
                    "class": "WPSlurmJob",
                    "id": f"/{part}/{jid}",
                    "icon": icon_name,
                    "title": jid,
                    "objects": 0,
                }
            )
        return {"objects": objects}


def _get_jobs_for_partition(partition: str) -> List[str]:
    part = partition.lstrip("/")
    # Try squeue first for job IDs in this partition
    try:
        out = subprocess.check_output(["squeue", "-h", "-p", part, "-o", "%i"], text=True)
        jobs = [line.strip() for line in out.splitlines() if line.strip()]
        return jobs
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


