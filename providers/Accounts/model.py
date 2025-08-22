from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

from providers.base import ProviderObject


@dataclass
class WPAccount(ProviderObject):
    """Represents an account entry for a compute system.

    Emits class_name "WPAccount" per requirement.
    """

    @property
    def class_name(self) -> str:  # noqa: D401
        return "WPAccount"
    
    # Optional ownership metadata for directories
    type: Optional[str] = None

    def _extra_fields(self) -> dict[str, object]:
        extra: dict[str, object] = {}
        if self.type is not None:
            extra["type"] = self.type
        return extra