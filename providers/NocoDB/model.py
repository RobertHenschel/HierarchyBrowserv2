from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Dict

from providers.base import ProviderObject


@dataclass
class WPNocoTable(ProviderObject):
    """Represents a NocoDB table in the object tree."""

    base_id: Optional[str] = None
    table_type: Optional[str] = None
    column_count: Optional[int] = None
    record_count: Optional[int] = None
    contextmenu: Optional[List[Dict]] = None

    def _extra_fields(self) -> dict[str, object]:
        extra: dict[str, object] = {}
        if self.base_id is not None:
            extra["base_id"] = self.base_id
        if self.table_type is not None:
            extra["table_type"] = self.table_type
        if self.column_count is not None:
            extra["column_count"] = self.column_count
        if self.record_count is not None:
            extra["record_count"] = self.record_count
        if self.contextmenu is not None:
            extra["contextmenu"] = self.contextmenu
        return extra

    @property
    def class_name(self) -> str:  # noqa: D401
        return "WPNocoTable"

    @classmethod
    def from_dict(cls, payload: dict) -> "WPNocoTable":
        """Build a WPNocoTable from a dict produced by to_dict()."""
        icon_value = payload.get("icon")
        return cls(
            id=str(payload.get("id", "/")),
            title=str(payload.get("title", "")),
            icon=(icon_value if isinstance(icon_value, str) else None),
            objects=int(payload.get("objects", 0)),
            base_id=(payload.get("base_id") if isinstance(payload.get("base_id"), str) else None),
            table_type=(payload.get("table_type") if isinstance(payload.get("table_type"), str) else None),
            column_count=(int(payload.get("column_count")) if payload.get("column_count") is not None else None),
            record_count=(int(payload.get("record_count")) if payload.get("record_count") is not None else None),
            contextmenu=payload.get("contextmenu"),
        )


@dataclass
class WPNocoRecord(ProviderObject):
    """Represents a NocoDB record/entry."""

    url: Optional[str] = None
    status: Optional[str] = None
    branch: Optional[str] = None
    image_title: Optional[str] = None
    image_description: Optional[str] = None
    credit: Optional[str] = None
    date_created: Optional[str] = None
    instrument: Optional[str] = None
    facility: Optional[str] = None
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    file_size: Optional[int] = None
    contextmenu: Optional[List[Dict]] = None

    @property
    def class_name(self) -> str:  # noqa: D401
        return "WPNocoRecord"

    def _extra_fields(self) -> dict[str, object]:
        extra: dict[str, object] = {}
        if self.url is not None:
            extra["url"] = self.url
        if self.status is not None:
            extra["status"] = self.status
        if self.branch is not None:
            extra["branch"] = self.branch
        if self.image_title is not None:
            extra["image_title"] = self.image_title
        if self.image_description is not None:
            extra["image_description"] = self.image_description
        if self.credit is not None:
            extra["credit"] = self.credit
        if self.date_created is not None:
            extra["date_created"] = self.date_created
        if self.instrument is not None:
            extra["instrument"] = self.instrument
        if self.facility is not None:
            extra["facility"] = self.facility
        if self.image_width is not None:
            extra["image_width"] = int(self.image_width)
        if self.image_height is not None:
            extra["image_height"] = int(self.image_height)
        if self.file_size is not None:
            extra["file_size"] = int(self.file_size)
        if self.contextmenu is not None:
            extra["contextmenu"] = self.contextmenu
        return extra

