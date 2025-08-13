from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from providers.base import ProviderObject


@dataclass
class WPSlurmPartition(ProviderObject):
    """Represents a Slurm partition in the object tree."""

    @property
    def class_name(self) -> str:  # noqa: D401
        return "WPSlurmPartition"


@dataclass
class WPSlurmJob(ProviderObject):
    """Represents a Slurm job entry."""

    jobarray: bool = False
    userid: Optional[str] = None
    nodecount: int = 0
    jobstate: Optional[str] = None

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
        return extra


@dataclass
class WPSlurmJobGroup(ProviderObject):
    @property
    def class_name(self) -> str:  # noqa: D401
        return "WPGroup"


