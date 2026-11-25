from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models


DEMO_SHELVES = [
    {
        "name": "У входа",
        "location_hint": "сразу справа от входа",
        "color": "#58C7F3",
        "x": 10,
        "y": 43,
        "width": 26,
        "height": 10,
        "levels": [
            [("Яйца", ["яйцо"], "#F5B84C")],
            [
                ("Молоко", ["молочка", "молочные продукты"], "#58C7F3"),
                ("Кефир", ["кисломолочные продукты"], "#7DD3FC"),
                ("Сыр", ["сыры"], "#FCD34D"),
            ],
            [("Масло", ["сливочное масло"], "#FDE68A"), ("Йогурты", ["йогурт"], "#F9A8D4")],
            [("Творог", [], "#C4B5FD")],
            [("Сметана", [], "#FBCFE8")],
            [("Молоко в бутылках", ["бутылочное молоко"], "#93C5FD")],
        ],
    },
    {
        "name": "Фрукты и овощи",
        "location_hint": "в центре зала",
        "color": "#F59E0B",
        "x": 44,
        "y": 40,
        "width": 18,
        "height": 14,
        "levels": [
            [("Бананы", ["банан"], "#FACC15"), ("Яблоки", ["яблоко"], "#EF4444")],
            [("Овощи", ["овощи свежие"], "#84CC16"), ("Помидоры", ["томаты"], "#DC2626")],
            [("Зелень", ["укроп", "петрушка"], "#22C55E")],
            [("Ягоды", ["клубника"], "#F472B6")],
            [("Цитрусовые", ["апельсины", "лимоны"], "#FB923C")],
        ],
    },
    {
        "name": "Бакалея",
        "location_hint": "в дальнем правом углу",
        "color": "#8B5CF6",
        "x": 78,
        "y": 10,
        "width": 12,
        "height": 38,
        "levels": [
            [("Чай", [], "#10B981"), ("Кофе", ["кофейные напитки"], "#92400E")],
            [("Макароны", ["паста"], "#FBBF24"), ("Рис", [], "#F3F4F6")],
            [("Крупы", ["гречка", "овсянка"], "#D97706")],
            [("Сахар", [], "#F9FAFB"), ("Соль", [], "#E5E7EB")],
            [("Мука", [], "#FEF3C7")],
            [("Консервы", ["консервация"], "#65A30D")],
        ],
    },
    {
        "name": "Напитки",
        "location_hint": "слева от входа, вдоль стены",
        "color": "#0EA5E9",
        "x": 8,
        "y": 10,
        "width": 26,
        "height": 10,
        "levels": [
            [("Вода", ["питьевая вода"], "#38BDF8")],
            [("Соки", ["сок"], "#FB7185")],
            [("Газировка", ["лимонад"], "#A78BFA")],
            [("Квас", [], "#B45309")],
        ],
    },
    {
        "name": "Хлеб и выпечка",
        "location_hint": "прямо от входа",
        "color": "#D97706",
        "x": 40,
        "y": 10,
        "width": 24,
        "height": 10,
        "levels": [
            [("Хлеб", ["хлебобулочные изделия"], "#D97706")],
            [("Булочки", ["выпечка"], "#F59E0B")],
            [("Печенье", ["печенье к чаю"], "#FCD34D")],
        ],
    },
    {
        "name": "Заморозка",
        "location_hint": "справа в центре зала",
        "color": "#14B8A6",
        "x": 66,
        "y": 40,
        "width": 10,
        "height": 14,
        "levels": [
            [("Пельмени", ["замороженные полуфабрикаты"], "#14B8A6")],
            [("Мороженое", ["мороженное"], "#60A5FA")],
        ],
    },
]


def _clear_store_layout(db: Session, store: models.Store) -> None:
    for category in list(store.categories):
        db.delete(category)
    for shelf in list(store.shelves):
        db.delete(shelf)
    db.flush()


def _populate_demo_store(db: Session, store: models.Store) -> None:
    store.name = "Пятёрочка на Ленина"
    store.address = "ул. Ленина, 42"
    store.map_width = 100
    store.map_height = 64
    store.entrance_x = 50
    store.entrance_y = 60
    store.entrance_label = "Вход"
    db.flush()

    for sort_order, shelf_data in enumerate(DEMO_SHELVES):
        shelf = models.Shelf(
            store_id=store.id,
            name=shelf_data["name"],
            location_hint=shelf_data["location_hint"],
            color=shelf_data["color"],
            x=shelf_data["x"],
            y=shelf_data["y"],
            width=shelf_data["width"],
            height=shelf_data["height"],
            sort_order=sort_order,
        )
        db.add(shelf)
        db.flush()

        for level_position, categories in enumerate(shelf_data["levels"]):
            level = models.ShelfLevel(shelf_id=shelf.id, position=level_position)
            db.add(level)
            db.flush()
            for category_position, (name, aliases, color) in enumerate(categories):
                db.add(
                    models.Category(
                        store_id=store.id,
                        name=name,
                        aliases=aliases,
                        color=color,
                        shelf_level_id=level.id,
                        position=category_position,
                    )
                )

    # Несколько категорий ещё не расставлены — их видно в палитре администратора.
    for name, aliases, color in [
        ("Пицца", ["замороженная пицца"], "#EF4444"),
        ("Суши", [], "#F97316"),
        ("Шоколад", ["сладости"], "#78350F"),
    ]:
        db.add(models.Category(store_id=store.id, name=name, aliases=aliases, color=color))


def seed_demo_data(db: Session) -> None:
    if db.scalar(select(func.count(models.Store.id))) > 0:
        return

    store = models.Store()
    db.add(store)
    db.flush()
    _populate_demo_store(db, store)
    db.commit()


def reset_demo_data(db: Session, store: models.Store) -> None:
    _clear_store_layout(db, store)
    _populate_demo_store(db, store)
    db.commit()
    db.expire_all()
