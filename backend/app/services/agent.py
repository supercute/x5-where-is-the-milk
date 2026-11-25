from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import models, schemas
from .llm import LLMAnswerer, clean_model_output, get_answerer

PARSE_PROMPT = """Из каждого фрагмента вопроса выдели название одного товара.
Исправь очевидную опечатку, но не подменяй товар другим. Если товара нет, верни пустую строку.
Верни только JSON-массив строк: одна строка на каждый входной фрагмент, в том же порядке.
Пример: ["Куда за яйцами?", "а смтану?", "спасибо"] → ["яйца", "сметана", ""]
"""

QUERY_PARTS = re.compile(r"[,;!?]|\s+и\s+", re.IGNORECASE)
STRONG_MATCH = 0.94
MAX_QUERY_PARTS = 3

ORDINALS = {
    0: "первая",
    1: "вторая",
    2: "третья",
    3: "четвёртая",
    4: "пятая",
    5: "шестая",
    6: "седьмая",
    7: "восьмая",
    8: "девятая",
    9: "десятая",
    10: "одиннадцатая",
    11: "двенадцатая",
    12: "тринадцатая",
    13: "четырнадцатая",
    14: "пятнадцатая",
}

RUSSIAN_SUFFIXES = sorted(
    {
        "ыми",
        "ими",
        "ого",
        "его",
        "ому",
        "ему",
        "ами",
        "ями",
        "ах",
        "ях",
        "ов",
        "ев",
        "ий",
        "ый",
        "ая",
        "ое",
        "ие",
        "ые",
        "ую",
        "ам",
        "ям",
        "ой",
        "ей",
        "у",
        "ю",
        "а",
        "я",
        "ы",
        "и",
        "е",
        "о",
        "й",
    },
    key=len,
    reverse=True,
)

MAP_INTENT_PATTERN = re.compile(
    r"(?<![а-яa-z])(схем\w*|карт(?:а|у|е|ы|ой|ин\w*)|план(?:а|у|е|ом)?|макет\w*)(?![а-яa-z])",
    re.IGNORECASE,
)

# «Где молоко на схеме?» — это вопрос о товаре, а не просьба прислать карту.
PRODUCT_ON_MAP_PATTERN = re.compile(
    r"\bгде\b.*\b(?:на|по)\s+(?:схем|карт|план)",
    re.IGNORECASE,
)


@dataclass
class CategoryMatch:
    category: models.Category
    score: float


def normalize_text(text: str) -> str:
    text = (text or "").lower().replace("ё", "е")
    text = re.sub(r"[^a-zа-я0-9]+", " ", text)
    return " ".join(text.split())


def stem(token: str) -> str:
    if len(token) <= 3:
        return token
    for suffix in RUSSIAN_SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: -len(suffix)]
    return token


def _term_score(term: str, query: str, query_tokens: list[str], query_stems: set[str]) -> float:
    term = normalize_text(term)
    if not term:
        return 0.0
    if f" {term} " in f" {query} ":
        return 1.0

    term_tokens = term.split()
    term_stems = {stem(token) for token in term_tokens}
    if term_stems and term_stems.issubset(query_stems):
        return 0.94

    if len(term_tokens) == 1:
        token_stem = stem(term_tokens[0])
        for query_token in query_tokens:
            query_stem = stem(query_token)
            if (
                len(query_stem) >= 4
                and len(token_stem) >= 4
                and token_stem[0] == query_stem[0]
                and SequenceMatcher(None, token_stem, query_stem).ratio() >= 0.85
            ):
                return 0.82
    return 0.0


def find_matches(text: str, categories: list[models.Category]) -> list[CategoryMatch]:
    query = normalize_text(text)
    if not query:
        return []
    query_tokens = query.split()
    query_stems = {stem(token) for token in query_tokens}

    matches: list[CategoryMatch] = []
    for category in categories:
        terms = [category.name, *(category.aliases or [])]
        score = max(
            (_term_score(term, query, query_tokens, query_stems) for term in terms),
            default=0.0,
        )
        if score > 0:
            matches.append(CategoryMatch(category=category, score=score))

    matches.sort(key=lambda item: (-item.score, item.category.name.casefold()))
    if not matches:
        return []

    best = matches[0].score
    cutoff = best - 0.08
    selected: list[CategoryMatch] = []
    seen: set[int] = set()
    for match in matches:
        if match.score < cutoff or len(selected) >= 3:
            break
        if match.category.id not in seen:
            seen.add(match.category.id)
            selected.append(match)
    return selected


def ordinal(number: int) -> str:
    return ORDINALS.get(number, f"{number + 1}-я")


def build_location(category: models.Category) -> schemas.AgentLocation | None:
    level = category.level
    if level is None:
        return None
    shelf = level.shelf
    if shelf is None:
        return None

    levels = sorted(shelf.levels, key=lambda item: item.position)
    levels_count = max(1, len(levels))
    level_position = level.position
    if levels_count == 1:
        level_phrase = "единственная полка"
    elif level_position == 0:
        level_phrase = "верхняя полка"
    elif level_position == levels_count - 1:
        level_phrase = "нижняя полка"
    else:
        level_phrase = f"{ordinal(level_position)} полка сверху"

    siblings = sorted(level.categories, key=lambda item: (item.position, item.id))
    sibling_count = len(siblings)
    index = next((i for i, item in enumerate(siblings) if item.id == category.id), 0)
    horizontal = ""
    if sibling_count > 1:
        if index == 0:
            horizontal = ", слева"
        elif index == sibling_count - 1:
            horizontal = ", справа"
        else:
            horizontal = ", в центре"

    hint = f", {shelf.location_hint}" if shelf.location_hint else ""
    summary = f"стеллаж «{shelf.name}»{hint}, {level_phrase}{horizontal}"
    return schemas.AgentLocation(
        category_id=category.id,
        category=category.name,
        shelf_id=shelf.id,
        shelf_name=shelf.name,
        location_hint=shelf.location_hint,
        level_position=level_position,
        levels_count=levels_count,
        position=category.position,
        summary=summary,
    )


def fallback_answer(locations: list[schemas.AgentLocation]) -> str:
    return "\n".join(f"{item.category} — {item.summary}." for item in locations)


def _match_extracted_term(term: str, categories: list[models.Category]) -> CategoryMatch | None:
    normalized = normalize_text(term)
    if not normalized:
        return None
    stems = tuple(map(stem, normalized.split()))
    candidates = []
    for category in categories:
        terms = [normalize_text(value) for value in (category.name, *(category.aliases or []))]
        if normalized in terms:
            candidates.append(CategoryMatch(category, 1.0))
        elif any(tuple(map(stem, value.split())) == stems for value in terms):
            candidates.append(CategoryMatch(category, STRONG_MATCH))
    exact = [match for match in candidates if match.score == 1.0]
    best = exact or candidates
    return best[0] if len(best) == 1 else None


async def _resolve_products(
    text: str,
    categories: list[models.Category],
    generator: LLMAnswerer,
    model_ready: bool,
) -> tuple[list[CategoryMatch], int, str | None]:
    # Preserve a direct match for a category whose name itself contains «и».
    query = normalize_text(text)
    whole_query_matches = find_matches(text, categories)
    if any(
        normalize_text(term) == query
        for match in whole_query_matches
        for term in (match.category.name, *(match.category.aliases or []))
    ):
        return whole_query_matches, 0, None

    parts = [part.strip() for part in QUERY_PARTS.split(text) if normalize_text(part)]
    part_matches = [find_matches(part, categories) for part in parts[:MAX_QUERY_PARTS]]
    pending = [
        index for index, matches in enumerate(part_matches)
        if not matches or matches[0].score < STRONG_MATCH
    ]
    used_source: str | None = None
    if model_ready and pending:
        result = await generator.generate(
            PARSE_PROMPT, json.dumps([parts[index] for index in pending], ensure_ascii=False)
        )
        if result is not None:
            try:
                extracted = json.loads(clean_model_output(result.text))
            except ValueError:
                extracted = None
            if isinstance(extracted, list) and len(extracted) == len(pending):
                for index, term in zip(pending, extracted):
                    if not isinstance(term, str) or not term.strip() or len(term) > 120:
                        continue
                    match = _match_extracted_term(term, categories)
                    if match is not None:
                        part_matches[index] = [match]
                        used_source = result.source

    unique: dict[int, CategoryMatch] = {}
    unresolved = max(0, len(parts) - MAX_QUERY_PARTS)
    for matches in part_matches:
        if not matches or (len(matches) > 1 and matches[0].score < STRONG_MATCH):
            unresolved += 1
            continue
        for match in matches:
            unique.setdefault(match.category.id, match)
    return list(unique.values())[:MAX_QUERY_PARTS], unresolved, used_source


def _load_categories(db: Session, store_id: int) -> list[models.Category]:
    return list(
        db.scalars(
            select(models.Category)
            .where(models.Category.store_id == store_id)
            .options(
                selectinload(models.Category.level)
                .selectinload(models.ShelfLevel.shelf)
                .selectinload(models.Shelf.levels),
                selectinload(models.Category.level).selectinload(
                    models.ShelfLevel.categories
                ),
            )
            .order_by(models.Category.name)
        ).all()
    )


def _choose_store(db: Session, store_id: int | None) -> models.Store:
    if store_id is not None:
        store = db.get(models.Store, store_id)
    else:
        store = db.scalar(select(models.Store).order_by(models.Store.id).limit(1))
    if store is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Магазин не найден")
    return store


def is_map_request(text: str) -> bool:
    normalized = normalize_text(text)
    if PRODUCT_ON_MAP_PATTERN.search(normalized):
        return False
    return bool(MAP_INTENT_PATTERN.search(normalized))


async def answer_query(
    db: Session,
    text: str,
    store_id: int | None = None,
) -> schemas.AgentResponse:
    store = _choose_store(db, store_id)
    categories = _load_categories(db, store.id)
    generator = get_answerer()
    model_ready = generator.ready
    model_name = getattr(generator, "model_id", "fallback")
    if not model_ready:
        generator.preload_in_background()
    matches, unresolved, used_source = await _resolve_products(
        text, categories, generator, model_ready
    )

    placed: list[tuple[models.Category, schemas.AgentLocation]] = []
    unplaced: list[models.Category] = []
    for match in matches:
        location = build_location(match.category)
        if location is None:
            unplaced.append(match.category)
        else:
            placed.append((match.category, location))

    if not placed:
        if unplaced:
            names = ", ".join(f"«{item.name}»" for item in unplaced[:3])
            answer = (
                f"{names} есть в каталоге, но пока не размещено на схеме магазина. "
                "Уточните расположение у сотрудника."
            )
        else:
            available = [category.name for category in categories if category.level is not None]
            preview = ", ".join(available[:12])
            answer = (
                "Не нашёл такой товар на схеме. "
                + (f"Например, на полках есть: {preview}." if preview else "Схема пока пустая.")
            )
        return schemas.AgentResponse(
            answer=answer,
            source=used_source or "fallback",
            model=model_name,
            matches=[],
            store_id=store.id,
            store_name=store.name,
        )

    locations = [location for _, location in placed]
    answer = fallback_answer(locations)
    if unplaced:
        names = ", ".join(f"«{item.name}»" for item in unplaced)
        answer += f"\nПока не размещено на схеме: {names}."
    if unresolved:
        answer += "\nНе всё удалось найти. Уточните название оставшихся товаров."

    return schemas.AgentResponse(
        answer=answer,
        source=used_source or "fallback",
        model=model_name,
        matches=locations,
        store_id=store.id,
        store_name=store.name,
    )
