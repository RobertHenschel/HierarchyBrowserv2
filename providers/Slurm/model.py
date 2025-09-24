from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Dict

from providers.base import ProviderObject


@dataclass
class WPSlurmPartition(ProviderObject):
    """Represents a Slurm partition in the object tree."""

    isdefault: bool = False
    maxtime: Optional[str] = None
    totalnodes: Optional[str] = None
    runningjobs: Optional[str] = None
    pendingjobs: Optional[str] = None
    hasgpus: bool = False
    contextmenu: Optional[List[Dict]] = None

    def _extra_fields(self) -> dict[str, object]:
        extra: dict[str, object] = {}
        extra["isdefault"] = self.isdefault
        if self.maxtime is not None:
            extra["maxtime"] = self.maxtime
        if self.totalnodes is not None:
            extra["totalnodes"] = self.totalnodes
        if self.runningjobs is not None:
            extra["runningjobs"] = self.runningjobs
        if self.pendingjobs is not None:
            extra["pendingjobs"] = self.pendingjobs
        extra["hasgpus"] = self.hasgpus
        if self.contextmenu is not None:
            extra["contextmenu"] = self.contextmenu
        return extra

    @property
    def class_name(self) -> str:  # noqa: D401
        return "WPSlurmPartition"

    @classmethod
    def from_dict(cls, payload: dict) -> "WPSlurmPartition":
        """Build a WPSlurmPartition from a dict produced by to_dict().

        Missing fields are defaulted, and types are normalized defensively.
        """
        icon_value = payload.get("icon")
        return cls(
            id=str(payload.get("id", "/")),
            title=str(payload.get("title", "")),
            icon=(icon_value if isinstance(icon_value, str) else None),
            objects=int(payload.get("objects", 0)),
            isdefault=bool(payload.get("isdefault", False)),
            maxtime=(payload.get("maxtime") if isinstance(payload.get("maxtime"), str) else None),
            totalnodes=(payload.get("totalnodes") if isinstance(payload.get("totalnodes"), str) else None),
            runningjobs=(payload.get("runningjobs") if isinstance(payload.get("runningjobs"), str) else None),
            pendingjobs=(payload.get("pendingjobs") if isinstance(payload.get("pendingjobs"), str) else None),
            hasgpus=bool(payload.get("hasgpus", False)),
            contextmenu=payload.get("contextmenu"),
        )


@dataclass
class WPSlurmJob(ProviderObject):
    """Represents a Slurm job entry."""

    jobarray: bool = False
    userid: Optional[str] = None
    nodecount: int = 0
    jobstate: Optional[str] = None
    partition: Optional[str] = None
    jobname: Optional[str] = None
    cpus: int = 0
    totalmemory: Optional[str] = None
    requestedruntime: Optional[str] = None
    account: Optional[str] = None
    elapsedruntime: Optional[str] = None
    state_reason: Optional[str] = None
    priority: Optional[int] = None
    remainingruntime: Optional[str] = None
    gres: Optional[str] = None
    contextmenu: Optional[List[Dict]] = None

    @property
    def class_name(self) -> str:  # noqa: D401
        return "WPSlurmJob"

    def _extra_fields(self) -> dict[str, object]:
        extra: dict[str, object] = {}
        extra["jobarray"] = bool(self.jobarray)
        if self.userid is not None:
            extra["userid"] = self.userid
        extra["nodecount"] = int(self.nodecount)
        if self.jobstate is not None:
            extra["jobstate"] = self.jobstate
        if self.partition is not None:
            extra["partition"] = self.partition
        if self.jobname is not None:
            extra["jobname"] = self.jobname
        extra["cpus"] = int(self.cpus)
        if self.totalmemory is not None:
            extra["totalmemory"] = self.totalmemory
        if self.requestedruntime is not None:
            extra["requestedruntime"] = self.requestedruntime
        if self.account is not None:
            extra["account"] = self.account
        if self.elapsedruntime is not None:
            extra["elapsedruntime"] = self.elapsedruntime
        if self.state_reason is not None:
            extra["state_reason"] = self.state_reason
        if self.priority is not None:
            extra["priority"] = int(self.priority)
        if self.remainingruntime is not None:
            extra["remainingruntime"] = self.remainingruntime
        if self.gres is not None:
            extra["gres"] = self.gres
        if self.contextmenu is not None:
            extra["contextmenu"] = self.contextmenu
        return extra


