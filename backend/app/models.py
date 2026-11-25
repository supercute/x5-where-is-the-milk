from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), default="Мой магазин")
    address: Mapped[str] = mapped_column(String(300), default="")
    map_width: Mapped[float] = mapped_column(Float, default=100.0)
    map_height: Mapped[float] = mapped_column(Float, default=64.0)
    entrance_x: Mapped[float] = mapped_column(Float, default=50.0)
    entrance_y: Mapped[float] = mapped_column(Float, default=60.0)
    entrance_label: Mapped[str] = mapped_column(String(80), default="Вход")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    shelves: Mapped[list["Shelf"]] = relationship(
        back_populates="store",
        cascade="all, delete-orphan",
        order_by="Shelf.sort_order, Shelf.id",
    )
    categories: Mapped[list["Category"]] = relationship(
        back_populates="store",
        cascade="all, delete-orphan",
        order_by="Category.name",
    )


class Shelf(Base):
    __tablename__ = "shelves"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120), default="Стеллаж")
    location_hint: Mapped[str] = mapped_column(String(300), default="")
    color: Mapped[str] = mapped_column(String(20), default="#4F8EF7")
    x: Mapped[float] = mapped_column(Float, default=10.0)
    y: Mapped[float] = mapped_column(Float, default=10.0)
    width: Mapped[float] = mapped_column(Float, default=22.0)
    height: Mapped[float] = mapped_column(Float, default=10.0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    store: Mapped[Store] = relationship(back_populates="shelves")
    levels: Mapped[list["ShelfLevel"]] = relationship(
        back_populates="shelf",
        cascade="all, delete-orphan",
        order_by="ShelfLevel.position",
    )

    @property
    def levels_count(self) -> int:
        return len(self.levels)


class ShelfLevel(Base):
    __tablename__ = "shelf_levels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shelf_id: Mapped[int] = mapped_column(
        ForeignKey("shelves.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0)

    shelf: Mapped[Shelf] = relationship(back_populates="levels")
    categories: Mapped[list["Category"]] = relationship(
        back_populates="level",
        order_by="Category.position, Category.id",
    )


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list)
    color: Mapped[str] = mapped_column(String(20), default="#34C759")
    shelf_level_id: Mapped[int | None] = mapped_column(
        ForeignKey("shelf_levels.id", ondelete="SET NULL"), nullable=True, index=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0)

    store: Mapped[Store] = relationship(back_populates="categories")
    level: Mapped[ShelfLevel | None] = relationship(back_populates="categories")
