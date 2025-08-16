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
    
    def _extra_fields(self) -> dict:
        return {
            "search_string": self.search_string,
            "recursive": self.recursive
        }

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
    
    def _extra_fields(self) -> dict:
        return {"state": self.state}
