from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from providers.base import ProviderObject


@dataclass
class WPDirectory(ProviderObject):
    @property
    def class_name(self) -> str:  # noqa: D401
        return "WPDirectory"

    # Optional ownership metadata for directories
    owner: Optional[str] = None
    group: Optional[str] = None

    def _extra_fields(self) -> dict[str, object]:
        extra: dict[str, object] = {}
        if self.owner is not None:
            extra["owner"] = self.owner
        if self.group is not None:
            extra["group"] = self.group
        return extra


@dataclass
class WPFile(ProviderObject):
    @property
    def class_name(self) -> str:  # noqa: D401
        return "WPFile"

    # Optional ownership metadata
    owner: Optional[str] = None
    group: Optional[str] = None

    def _extra_fields(self) -> dict[str, object]:
        extra: dict[str, object] = {}
        if self.owner is not None:
            extra["owner"] = self.owner
        if self.group is not None:
            extra["group"] = self.group
        return extra


