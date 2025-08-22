#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass

from providers.base import ProviderObject


@dataclass
class WPCount(ProviderObject):
    """Represents an account entry for a compute system.

    Emits class_name "WPAccount" per requirement.
    """

    @property
    def class_name(self) -> str:  # noqa: D401
        return "WPAccount"


