from __future__ import annotations

from dataclasses import dataclass

from providers.base import ProviderObject


@dataclass
class WPLmodDependency(ProviderObject):
    @property
    def class_name(self) -> str:  # noqa: D401
        return "WPLmodDependency"


@dataclass
class WPLmodSoftware(ProviderObject):
    loaded: bool = False
    details: str = ""

    @property
    def class_name(self) -> str:  # noqa: D401
        return "WPLmodSoftware"

    def _extra_fields(self) -> dict[str, object]:
        extra: dict[str, object] = {}
        extra["loaded"] = bool(self.loaded)
        extra["details"] = str(self.details)
        return extra


