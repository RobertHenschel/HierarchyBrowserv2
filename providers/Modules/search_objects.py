from dataclasses import dataclass, field
from typing import Optional
from providers.base import ProviderObject


@dataclass
class WPLmodSearchHandle(ProviderObject):
    id: str
    title: str
    search_string: str = ""
    recursive: bool = True
    icon: Optional[str] = None
    objects: int = 0

    @property
    def class_name(self) -> str:
        return "WPLmodSearchHandle"

@dataclass
class WPLmodSearchProgress(ProviderObject):
    id: str
    title: str
    state: str = "ongoing"  # 'ongoing' or 'done'
    icon: Optional[str] = None
    objects: int = 0

    @property
    def class_name(self) -> str:
        return "WPLmodSearchProgress"
