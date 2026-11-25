from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import models, schemas


def get_store_or_404(db: Session, store_id: int) -> models.Store:
    store = db.get(models.Store, store_id)
    if store is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Магазин не найден")
    return store


def get_shelf_or_404(db: Session, shelf_id: int) -> models.Shelf:
    shelf = db.get(models.Shelf, shelf_id)
    if shelf is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Стеллаж не найден")
    return shelf


def get_category_or_404(db: Session, category_id: int) -> models.Category:
    category = db.get(models.Category, category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Категория не найдена")
    return category


def store_to_out(store: models.Store) -> schemas.StoreOut:
    return schemas.StoreOut(
        id=store.id,
        name=store.name,
        address=store.address,
        map_width=store.map_width,
        map_height=store.map_height,
        entrance_x=store.entrance_x,
        entrance_y=store.entrance_y,
        entrance_label=store.entrance_label,
        created_at=store.created_at,
    )


def category_to_out(category: models.Category) -> schemas.CategoryOut:
    level = category.level
    shelf = level.shelf if level is not None else None
    return schemas.CategoryOut(
        id=category.id,
        store_id=category.store_id,
        name=category.name,
        aliases=list(category.aliases or []),
        color=category.color,
        shelf_level_id=category.shelf_level_id,
        shelf_id=shelf.id if shelf is not None else None,
        shelf_name=shelf.name if shelf is not None else None,
        level_position=level.position if level is not None else None,
        position=category.position,
    )


def shelf_to_out(shelf: models.Shelf) -> schemas.ShelfOut:
    levels = [
        schemas.ShelfLevelOut(
            id=level.id,
            position=level.position,
            categories=[
                schemas.CategoryBrief(
                    id=category.id,
                    name=category.name,
                    color=category.color,
                    position=category.position,
                )
                for category in sorted(level.categories, key=lambda item: (item.position, item.id))
            ],
        )
        for level in sorted(shelf.levels, key=lambda item: item.position)
    ]
    return schemas.ShelfOut(
        id=shelf.id,
        store_id=shelf.store_id,
        name=shelf.name,
        location_hint=shelf.location_hint,
        color=shelf.color,
        x=shelf.x,
        y=shelf.y,
        width=shelf.width,
        height=shelf.height,
        sort_order=shelf.sort_order,
        levels_count=len(levels),
        levels=levels,
    )


def build_layout(db: Session, store_id: int) -> schemas.LayoutOut:
    store = db.scalar(
        select(models.Store)
        .where(models.Store.id == store_id)
        .options(
            selectinload(models.Store.shelves)
            .selectinload(models.Shelf.levels)
            .selectinload(models.ShelfLevel.categories)
        )
    )
    if store is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Магазин не найден")

    categories = db.scalars(
        select(models.Category)
        .where(models.Category.store_id == store_id)
        .options(
            selectinload(models.Category.level).selectinload(models.ShelfLevel.shelf)
        )
        .order_by(models.Category.name)
    ).all()

    shelves = [
        shelf_to_out(shelf)
        for shelf in sorted(store.shelves, key=lambda item: (item.sort_order, item.id))
    ]
    category_items = [category_to_out(category) for category in categories]
    return schemas.LayoutOut(
        store=store_to_out(store),
        shelves=shelves,
        categories=category_items,
        stats=schemas.LayoutStats(
            shelves=len(shelves),
            categories=len(category_items),
            placed=sum(1 for category in category_items if category.shelf_level_id is not None),
        ),
    )


def set_levels_count(db: Session, shelf: models.Shelf, count: int) -> None:
    levels = sorted(shelf.levels, key=lambda item: item.position)
    current = len(levels)

    if count < current:
        removed = levels[count:]
        for level in removed:
            for category in list(level.categories):
                category.shelf_level_id = None
                category.position = 0
            db.delete(level)
        db.flush()
        levels = levels[:count]
    elif count > current:
        for position in range(current, count):
            level = models.ShelfLevel(shelf_id=shelf.id, position=position)
            db.add(level)
            levels.append(level)
        db.flush()

    for position, level in enumerate(sorted(levels, key=lambda item: item.position)):
        level.position = position
    db.flush()


def _renumber_level(db: Session, level_id: int) -> None:
    db.flush()
    categories = db.scalars(
        select(models.Category)
        .where(models.Category.shelf_level_id == level_id)
        .order_by(models.Category.position, models.Category.id)
    ).all()
    for position, category in enumerate(categories):
        category.position = position
    db.flush()


def place_category(
    db: Session,
    category: models.Category,
    target_level_id: int | None,
    position: int | None = None,
) -> models.Category:
    old_level_id = category.shelf_level_id
    target_level = None

    if target_level_id is not None:
        target_level = db.get(models.ShelfLevel, target_level_id)
        if target_level is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Полка не найдена")
        target_shelf = db.get(models.Shelf, target_level.shelf_id)
        if target_shelf is None or target_shelf.store_id != category.store_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Полка принадлежит другому магазину",
            )

    if old_level_id is not None:
        category.shelf_level_id = None
        category.position = 0
        db.flush()
        _renumber_level(db, old_level_id)

    if target_level is not None:
        siblings = db.scalars(
            select(models.Category)
            .where(
                models.Category.shelf_level_id == target_level.id,
                models.Category.id != category.id,
            )
            .order_by(models.Category.position, models.Category.id)
        ).all()
        insertion = len(siblings) if position is None else max(0, min(position, len(siblings)))
        category.shelf_level_id = target_level.id
        category.position = insertion
        db.flush()
        for index, sibling in enumerate(siblings):
            sibling.position = index if index < insertion else index + 1
        db.flush()
        _renumber_level(db, target_level.id)

    db.commit()
    db.refresh(category)
    return category
