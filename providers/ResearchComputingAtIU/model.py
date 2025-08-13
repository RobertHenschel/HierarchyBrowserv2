from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

from providers.base import ProviderObject


@dataclass
class WPObject(ProviderObject):
    """Generic research computing object with passthrough extras."""

    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def class_name(self) -> str:  # noqa: D401
        return "WPObject"

    def _extra_fields(self) -> dict[str, object]:
        # Pass through any additional fields that are not core
        return dict(self.extra)


