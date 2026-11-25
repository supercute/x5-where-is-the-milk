from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

HEX_COLOR = r"^#[0-9a-fA-F]{6}$"


def _clean_aliases(value: list[str] | str | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [part.strip() for part in value.replace(";", ",").split(",")]
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        cleaned = " ".join(str(item).split()).strip()
        if cleaned and cleaned.casefold() not in seen:
            seen.add(cleaned.casefold())
            result.append(cleaned[:120])
    return result


class StoreOut(BaseModel):
    id: int
    name: str
    address: str
    map_width: float
    map_height: float
    entrance_x: float
    entrance_y: float
    entrance_label: str
    created_at: datetime | None = None


class StoreCreate(BaseModel):
    name: str = Field(default="Мой магазин", min_length=1, max_length=200)
    address: str = Field(default="", max_length=300)
    map_width: float = Field(default=100, gt=10, le=1000)
    map_height: float = Field(default=64, gt=10, le=1000)
    entrance_x: float = Field(default=50, ge=0, le=1000)
    entrance_y: float = Field(default=60, ge=0, le=1000)
    entrance_label: str = Field(default="Вход", max_length=80)


class StoreUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    address: str | None = Field(default=None, max_length=300)
    map_width: float | None = Field(default=None, gt=10, le=1000)
    map_height: float | None = Field(default=None, gt=10, le=1000)
    entrance_x: float | None = Field(default=None, ge=0, le=1000)
    entrance_y: float | None = Field(default=None, ge=0, le=1000)
    entrance_label: str | None = Field(default=None, max_length=80)


class CategoryBrief(BaseModel):
    id: int
    name: str
    color: str
    position: int


class ShelfLevelOut(BaseModel):
    id: int
    position: int
    categories: list[CategoryBrief] = Field(default_factory=list)


class ShelfOut(BaseModel):
    id: int
    store_id: int
    name: str
    location_hint: str
    color: str
    x: float
    y: float
    width: float
    height: float
    sort_order: int
    levels_count: int
    levels: list[ShelfLevelOut] = Field(default_factory=list)


class CategoryOut(BaseModel):
    id: int
    store_id: int
    name: str
    aliases: list[str] = Field(default_factory=list)
    color: str
    shelf_level_id: int | None = None
    shelf_id: int | None = None
    shelf_name: str | None = None
    level_position: int | None = None
    position: int = 0


class LayoutStats(BaseModel):
    shelves: int
    categories: int
    placed: int


class LayoutOut(BaseModel):
    store: StoreOut
    shelves: list[ShelfOut]
    categories: list[CategoryOut]
    stats: LayoutStats


class ShelfCreate(BaseModel):
    name: str = Field(default="Новый стеллаж", min_length=1, max_length=120)
    location_hint: str = Field(default="", max_length=300)
    color: str = Field(default="#4F8EF7", pattern=HEX_COLOR)
    x: float = Field(default=10, ge=0, le=1000)
    y: float = Field(default=10, ge=0, le=1000)
    width: float = Field(default=22, gt=1, le=1000)
    height: float = Field(default=10, gt=1, le=1000)
    levels_count: int = Field(default=4, ge=1, le=15)


class ShelfUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    location_hint: str | None = Field(default=None, max_length=300)
    color: str | None = Field(default=None, pattern=HEX_COLOR)
    x: float | None = Field(default=None, ge=0, le=1000)
    y: float | None = Field(default=None, ge=0, le=1000)
    width: float | None = Field(default=None, gt=1, le=1000)
    height: float | None = Field(default=None, gt=1, le=1000)
    levels_count: int | None = Field(default=None, ge=1, le=15)
    sort_order: int | None = None


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    aliases: list[str] = Field(default_factory=list)
    color: str = Field(default="#34C759", pattern=HEX_COLOR)

    @field_validator("aliases", mode="before")
    @classmethod
    def normalize_aliases(cls, value):
        return _clean_aliases(value)


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    aliases: list[str] | None = None
    color: str | None = Field(default=None, pattern=HEX_COLOR)

    @field_validator("aliases", mode="before")
    @classmethod
    def normalize_aliases(cls, value):
        return _clean_aliases(value)


class CategoryPlacement(BaseModel):
    shelf_level_id: int | None = None
    position: int | None = Field(default=None, ge=0)


class ResetDemoRequest(BaseModel):
    confirm: bool = False


class AgentQuery(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    store_id: int | None = None


class AgentLocation(BaseModel):
    category_id: int
    category: str
    shelf_id: int
    shelf_name: str
    location_hint: str
    level_position: int
    levels_count: int
    position: int
    summary: str


class AgentResponse(BaseModel):
    answer: str
    source: Literal["api", "qwen", "fallback"]
    model: str
    matches: list[AgentLocation] = Field(default_factory=list)
    store_id: int
    store_name: str
