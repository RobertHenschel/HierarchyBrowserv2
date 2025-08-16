from dataclasses import dataclass
from providers.base import ProviderObject


@dataclass
class WPLmodSearchHandle(ProviderObject):
    id: str
    search_string: str
    recursive: bool = True

    @property
    def class_name(self) -> str:
        return "WPLmodSearchHandle"

@dataclass
class WPLmodSearchProgress(ProviderObject):
    id: str
    state: str  # 'ongoing' or 'done'

    @property
    def class_name(self) -> str:
        return "WPLmodSearchProgress"
