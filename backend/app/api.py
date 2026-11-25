from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models, schemas
from .database import get_db
from .seed import reset_demo_data
from .services.agent import answer_query
from .services.layout import (
    build_layout,
    category_to_out,
    get_category_or_404,
    get_shelf_or_404,
    get_store_or_404,
    place_category,
    set_levels_count,
    shelf_to_out,
    store_to_out,
)
from .services.llm import get_answerer
from .services.map_image import render_store_map

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "where-is-the-milk",
        "llm": get_answerer().status,
    }


@router.get("/stores", response_model=list[schemas.StoreOut])
def list_stores(db: Session = Depends(get_db)):
    stores = db.scalars(select(models.Store).order_by(models.Store.id)).all()
    return [store_to_out(store) for store in stores]


@router.post("/stores", response_model=schemas.StoreOut, status_code=status.HTTP_201_CREATED)
def create_store(payload: schemas.StoreCreate, db: Session = Depends(get_db)):
    store = models.Store(**payload.model_dump())
    db.add(store)
    db.commit()
    db.refresh(store)
    return store_to_out(store)


@router.get("/stores/{store_id}", response_model=schemas.StoreOut)
def get_store(store_id: int, db: Session = Depends(get_db)):
    return store_to_out(get_store_or_404(db, store_id))


@router.patch("/stores/{store_id}", response_model=schemas.StoreOut)
def update_store(
    store_id: int, payload: schemas.StoreUpdate, db: Session = Depends(get_db)
):
    store = get_store_or_404(db, store_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(store, field, value)
    db.commit()
    db.refresh(store)
    return store_to_out(store)


@router.delete("/stores/{store_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_store(store_id: int, db: Session = Depends(get_db)):
    store = get_store_or_404(db, store_id)
    db.delete(store)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/stores/{store_id}/layout", response_model=schemas.LayoutOut)
def get_layout(store_id: int, db: Session = Depends(get_db)):
    return build_layout(db, store_id)


@router.post("/stores/{store_id}/reset-demo", response_model=schemas.LayoutOut)
def reset_store_to_demo(
    store_id: int,
    payload: schemas.ResetDemoRequest,
    db: Session = Depends(get_db),
):
    if not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Сброс не подтверждён",
        )
    store = get_store_or_404(db, store_id)
    reset_demo_data(db, store)
    return build_layout(db, store.id)


@router.post(
    "/stores/{store_id}/shelves",
    response_model=schemas.ShelfOut,
    status_code=status.HTTP_201_CREATED,
)
def create_shelf(
    store_id: int, payload: schemas.ShelfCreate, db: Session = Depends(get_db)
):
    store = get_store_or_404(db, store_id)
    max_order = db.scalar(
        select(func.max(models.Shelf.sort_order)).where(
            models.Shelf.store_id == store_id
        )
    )
    payload_data = payload.model_dump()
    levels_count = payload_data.pop("levels_count")
    payload_data["x"] = max(0, min(payload_data["x"], store.map_width - 2))
    payload_data["y"] = max(0, min(payload_data["y"], store.map_height - 2))
    shelf = models.Shelf(
        store_id=store_id,
        sort_order=(max_order + 1) if max_order is not None else 0,
        **payload_data,
    )
    db.add(shelf)
    db.flush()
    set_levels_count(db, shelf, levels_count)
    db.commit()
    db.refresh(shelf)
    return shelf_to_out(shelf)


@router.patch("/shelves/{shelf_id}", response_model=schemas.ShelfOut)
def update_shelf(
    shelf_id: int, payload: schemas.ShelfUpdate, db: Session = Depends(get_db)
):
    shelf = get_shelf_or_404(db, shelf_id)
    data = payload.model_dump(exclude_unset=True)
    levels_count = data.pop("levels_count", None)
    for field, value in data.items():
        setattr(shelf, field, value)
    if levels_count is not None:
        set_levels_count(db, shelf, levels_count)
    db.commit()
    db.refresh(shelf)
    return shelf_to_out(shelf)


@router.delete("/shelves/{shelf_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shelf(shelf_id: int, db: Session = Depends(get_db)):
    shelf = get_shelf_or_404(db, shelf_id)
    for level in list(shelf.levels):
        for category in list(level.categories):
            category.shelf_level_id = None
            category.position = 0
    db.flush()
    db.delete(shelf)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/stores/{store_id}/categories",
    response_model=schemas.CategoryOut,
    status_code=status.HTTP_201_CREATED,
)
def create_category(
    store_id: int, payload: schemas.CategoryCreate, db: Session = Depends(get_db)
):
    get_store_or_404(db, store_id)
    category = models.Category(store_id=store_id, **payload.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category_to_out(category)


@router.patch("/categories/{category_id}", response_model=schemas.CategoryOut)
def update_category(
    category_id: int, payload: schemas.CategoryUpdate, db: Session = Depends(get_db)
):
    category = get_category_or_404(db, category_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    db.commit()
    db.refresh(category)
    return category_to_out(category)


@router.put("/categories/{category_id}/placement", response_model=schemas.CategoryOut)
def set_category_placement(
    category_id: int,
    payload: schemas.CategoryPlacement,
    db: Session = Depends(get_db),
):
    category = get_category_or_404(db, category_id)
    category = place_category(
        db,
        category,
        target_level_id=payload.shelf_level_id,
        position=payload.position,
    )
    return category_to_out(category)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, db: Session = Depends(get_db)):
    category = get_category_or_404(db, category_id)
    db.delete(category)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/stores/{store_id}/map.png")
def store_map(store_id: int, db: Session = Depends(get_db)):
    layout = build_layout(db, store_id)
    image = render_store_map(layout)
    return Response(
        content=image,
        media_type="image/png",
        headers={
            "Cache-Control": "no-store, max-age=0",
            "Content-Disposition": 'inline; filename="store-map.png"',
        },
    )


@router.post("/agent/query", response_model=schemas.AgentResponse)
async def agent_query(payload: schemas.AgentQuery, db: Session = Depends(get_db)):
    return await answer_query(db, payload.text, payload.store_id)
