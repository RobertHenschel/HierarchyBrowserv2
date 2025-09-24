#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import re
import getpass
from collections import Counter
import json

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
PERSON_ICON_PATH = PROVIDER_DIR / "Resources" / "IDCard.png"
MY_JOB_ICON_PATH = PROVIDER_DIR / "Resources" / "Job_IDCard.png"
# Use a python package to get the user id
MY_USER_ID = getpass.getuser().strip()


def _rot13(text: str) -> str:
    """Apply ROT13 transformation to text."""
    result = []
    for char in text:
        if char.isalpha():
            base = ord('A') if char.isupper() else ord('a')
            result.append(chr((ord(char) - base + 13) % 26 + base))
        else:
            result.append(char)
    return ''.join(result)

def _get_default_partition() -> str:
    try:
        out = subprocess.check_output(["sinfo", "-h", "-o", "%P"], text=True)
        lines = out.splitlines()
        for line in lines:
            if line.strip().endswith("*"):
                return line.strip().rstrip("*")
        return ""
    except Exception:
        return ""

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

class SlurmProvider(ObjectProvider):
    def __init__(self, options: ProviderOptions, scramble_users: bool = False):
        super().__init__(options)
        self.scramble_users = scramble_users

    def get_root_objects_payload(self) -> Dict[str, List[Dict]]:
        partitions = _get_slurm_partitions()
        default_partition = _get_default_partition()
        partition_name = f"./resources/{PARTITION_ICON_PATH.name}"
        group_name = f"./resources/{PERSON_ICON_PATH.name}"
        objects: List[Dict[str, object]] = []
        for part in partitions:
            try:
                job_count = len(_get_jobs_for_partition(part, self.scramble_users))
            except Exception:
                job_count = 0
            config = subprocess.check_output(["scontrol", "show", "partition", part])
            try:
                max_time = None
                total_nodes = None
                has_gpus = False
                for line in config.decode().splitlines():
                    if "MaxTime=" in line:
                        max_time_part = line.split("MaxTime=")[1].split()[0]
                        max_time = max_time_part
                    if "TotalNodes=" in line:
                        total_nodes_part = line.split("TotalNodes=")[1].split()[0]
                        total_nodes = total_nodes_part
                    if "gres" in line.lower():
                        has_gpus = True
            except Exception:
                pass
            try:
                jobs = subprocess.check_output(["squeue", "-p", part, "-o", "\"%.8u %.10T\""])
                running_jobs = 0
                pending_jobs = 0
                for line in jobs.splitlines():
                    if line.strip():
                        #if line contains "RUNNING" then running_jobs += 1
                        if b"RUNNING" in line:
                            running_jobs += 1
                        else:
                            pending_jobs += 1
                pending_jobs -= 1 # because of header line
            except Exception:
                pass
            obj = WPSlurmPartition(
                id=f"/{part}",
                title=part,
                icon=partition_name,
                objects=int(job_count),
                isdefault=part == default_partition,
                maxtime=max_time,
                totalnodes=total_nodes,
                runningjobs=running_jobs,
                pendingjobs=pending_jobs,
                hasgpus=has_gpus
            )
            objects.append(obj.to_dict())
        
        obj = WPGroup(
            id=f"/<ShowMy:{MY_USER_ID}>",
            title="My Jobs",
            icon=group_name,
            objects=int(_get_my_jobs_count()),
        )
        objects.append(obj.to_dict())
        return {"objects": objects}

    def get_my(self) -> Dict[str, List[Dict]]:
        """Return only jobs for the current user using squeue --me."""
        objects: List[Dict[str, object]] = []
        try:
            # Use squeue --me to get only current user's jobs
            fmt = "%i|%u|%D|%T|%P|%j|%C|%m|%l|%a|%M|%r|%Q|%b"
            out = subprocess.check_output(["squeue", "-h", "--me", "-o", fmt], text=True)
            
            for line in out.splitlines():
                entry = line.strip()
                if not entry:
                    continue
                # Split into expected parts per fmt
                parts = entry.split("|", 13)
                if len(parts) != 14:
                    continue
                jid = parts[0].strip()
                user = parts[1].strip()
                try:
                    nodes = int(parts[2].strip())
                except Exception:
                    nodes = 0
                state_raw = parts[3].strip()
                partition_name = parts[4].strip()
                jobname = parts[5].strip()
                cpus_str = parts[6].strip()
                mem_str = parts[7].strip()
                timelimit_str = parts[8].strip()
                account_str = parts[9].strip()
                elapsed_str = parts[10].strip()
                state_reason_str = parts[11].strip()
                priority_str = parts[12].strip()
                gres_str = parts[13].strip()
                
                if not jid:
                    continue
                    
                job_obj = _create_slurm_job_object(
                    jid, user, nodes, state_raw, partition_name, jobname,
                    cpus_str, mem_str, timelimit_str, account_str, elapsed_str,
                    state_reason_str, priority_str, gres_str, self.scramble_users
                )
                job_obj.contextmenu = [
                    {"title": "Show Resource Usage", "action": "terminal", "command": "./show_job_usage.py " + jid + "; exit"}
                ]
                objects.append(job_obj.to_dict())
        except Exception as e:
            import traceback
            traceback.print_exc()   
            print(f"Error in get_my: {e}", flush=True)
        return {"objects": objects}

    def get_objects_for_path(self, path_str: str) -> Dict[str, List[Dict]]:
        if path_str.strip() == "/" or path_str.strip() == "":
            return self.get_root_objects_payload()
        if path_str.startswith("/<ShowMy:"):
            return self.get_my()


        def list_for_base(base: str) -> List[ProviderObject]:
            # Always extract the partition as the first segment, ignoring any command tokens
            segments = base.strip("/").split("/")
            part = segments[0] if segments else ""
            if part == "":
                dictt = self.get_root_objects_payload()
                objs = dictt.get("objects", []) if isinstance(dictt, dict) else []
                typed: List[ProviderObject] = []
                for od in objs:
                    try:
                        if not isinstance(od, dict):
                            continue
                        if od.get("class") != "WPSlurmPartition":
                            continue
                        typed.append(WPSlurmPartition.from_dict(od))
                    except Exception:
                        continue
                return typed
            return _get_jobs_for_partition(part, self.scramble_users)

        return self.build_objects_for_path(
            path_str,
            list_for_base,
            group_icon_filename=f"./resources/Group.png",
        )

def _create_slurm_job_object(
    jid: str, user: str, nodes: int, state_raw: str, partition_name: str, 
    jobname: str, cpus_str: str, mem_str: str, timelimit_str: str, 
    account_str: str, elapsed_str: str, state_reason_str: str, 
    priority_str: str, gres_str: str, scramble_users: bool = False
) -> WPSlurmJob:
    """Create a WPSlurmJob object from squeue output fields."""
    if scramble_users:
        user = _rot13(user)
        my_user_id = _rot13(MY_USER_ID)
    else:
        my_user_id = MY_USER_ID
    
    # Normalize state to human readable: capitalize only first letter, lower rest
    state = state_raw.capitalize()
    
    job_id = f"/{partition_name}/{jid}"
    if job_id.startswith("//"):
        job_id = job_id[1:]
    
    # Compute remaining runtime from timelimit - elapsed
    remaining = None
    try:
        def _to_seconds(s: str) -> int:
            if not s:
                return 0
            if "-" in s:
                days_part, time_part = s.split("-", 1)
                days = int(days_part)
            else:
                days = 0
                time_part = s
            bits = time_part.split(":")
            bits = [int(x) if x.isdigit() else 0 for x in bits]
            while len(bits) < 3:
                bits.insert(0, 0)
            hh, mm, ss = bits[-3], bits[-2], bits[-1]
            return days * 86400 + hh * 3600 + mm * 60 + ss
        tl = _to_seconds(timelimit_str)
        el = _to_seconds(elapsed_str)
        rem = max(0, tl - el)
        d, rem2 = divmod(rem, 86400)
        h, rem3 = divmod(rem2, 3600)
        m, s = divmod(rem3, 60)
        if d > 0:
            remaining = f"{d}-{h:02d}:{m:02d}:{s:02d}"
        else:
            remaining = f"{h:02d}:{m:02d}:{s:02d}"
    except Exception:
        remaining = None
    
    # Choose icon based on ownership
    if user == my_user_id:
        icon_name = f"./resources/{MY_JOB_ICON_PATH.name}"
    else:
        icon_name = f"./resources/{JOB_ICON_PATH.name}"
    
    return WPSlurmJob(
        id=job_id,
        title=jid,
        icon=icon_name,
        objects=0,
        jobarray=("_" in jid),
        userid=user,
        nodecount=int(nodes),
        jobstate=state,
        partition=partition_name,
        jobname=jobname,
        cpus=(int(cpus_str) if cpus_str.isdigit() else 0),
        totalmemory=mem_str if mem_str else None,
        requestedruntime=timelimit_str if timelimit_str else None,
        account=account_str if account_str else None,
        elapsedruntime=elapsed_str if elapsed_str else None,
        state_reason=state_reason_str if state_reason_str else None,
        priority=(int(priority_str) if priority_str.isdigit() else None),
        remainingruntime=remaining,
        gres=gres_str if gres_str else None,
    )


def _get_jobs_for_partition(partition: str, scramble_users: bool = False) -> List[ProviderObject]:
    """Return typed WPSlurmJob objects for jobs in the given partition.

    Uses a single squeue call to retrieve all fields for efficiency.
    """
    part = partition.lstrip("/")
    icon_name = f"./resources/{JOB_ICON_PATH.name}"
    try:
        out = ""
        # %M: elapsed time, %l: time limit, %C: total CPUs, %m: requested memory, %a: account, %r: state reason, %Q: priority, %b: gres
        # Note: %m units depend on site config; %M/%l format like days-hours:minutes:seconds when applicable
        fmt = "%i|%u|%D|%T|%P|%j|%C|%m|%l|%a|%M|%r|%Q|%b"
        if part == "":
            out = subprocess.check_output(["squeue", "-h", "-o", fmt], text=True)
        else:
            out = subprocess.check_output(["squeue", "-h", "-p", part, "-o", fmt], text=True)
        typed: List[ProviderObject] = []
        for line in out.splitlines():
            entry = line.strip()
            if not entry:
                continue
            # Split into expected parts per fmt
            parts = entry.split("|", 13)
            if len(parts) != 14:
                continue
            jid = parts[0].strip()
            user = parts[1].strip()
            try:
                nodes = int(parts[2].strip())
            except Exception:
                nodes = 0
            state_raw = parts[3].strip()
            partition_name = parts[4].strip()
            jobname = parts[5].strip()
            cpus_str = parts[6].strip()
            mem_str = parts[7].strip()
            timelimit_str = parts[8].strip()
            account_str = parts[9].strip()
            elapsed_str = parts[10].strip()
            state_reason_str = parts[11].strip()
            priority_str = parts[12].strip()
            gres_str = parts[13].strip()
            
            if not jid:
                continue
                
            job_obj = _create_slurm_job_object(
                jid, user, nodes, state_raw, partition_name, jobname,
                cpus_str, mem_str, timelimit_str, account_str, elapsed_str,
                state_reason_str, priority_str, gres_str, scramble_users
            )
            typed.append(job_obj)
        return typed
    except Exception as e:
        import traceback
        traceback.print_exc()   
        print(f"Error: {e}", flush=True)
        return []


def main() -> None:
    parser = argparse.ArgumentParser(description="Slurm Object Provider")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8888, help="Port to bind (default: 8888)")
    parser.add_argument("--scrambleUsers", action="store_true", help="Apply ROT13 transformation to user names")
    args = parser.parse_args()

    provider = SlurmProvider(
        ProviderOptions(
            root_name="Slurm Batch System",
            provider_dir=PROVIDER_DIR,
            resources_dir=PROVIDER_DIR / "Resources",
            customize_icons="Job.png",  # e.g., "Partition.png;Job.png" (semicolon-separated)
        ),
        scramble_users=args.scrambleUsers
    )
    provider.serve(args.host, args.port)


if __name__ == "__main__":
    main()


