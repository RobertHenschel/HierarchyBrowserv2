from __future__ import annotations

from dataclasses import dataclass

from providers.base import ProviderObject


@dataclass
class WPDirectory(ProviderObject):
    @property
    def class_name(self) -> str:  # noqa: D401
        return "WPDirectory"


@dataclass
class WPFile(ProviderObject):
    @property
    def class_name(self) -> str:  # noqa: D401
        return "WPFile"


