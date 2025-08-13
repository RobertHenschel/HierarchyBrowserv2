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
    @property
    def class_name(self) -> str:  # noqa: D401
        return "WPLmodSoftware"


