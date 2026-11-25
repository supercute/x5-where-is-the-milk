from __future__ import annotations

import io
import math
import os
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .. import schemas
from ..config import FRONTEND_DIST, PROJECT_ROOT

WIDTH = 1600
MARGIN = 64
BACKGROUND = "#F3F0E8"
SURFACE = "#FFFEFA"
INK = "#1E241E"
MUTED = "#6B7369"
CARD = "#FBF9F3"
LINE = "#DEDBD0"
ACCENT = "#2D6A45"

FONT_CANDIDATES_REGULAR = [
    os.getenv("MAP_FONT_REGULAR", ""),
    str(FRONTEND_DIST / "fonts/golos-text-400.ttf"),
    str(PROJECT_ROOT / "frontend/public/fonts/golos-text-400.ttf"),
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
]
FONT_CANDIDATES_BOLD = [
    os.getenv("MAP_FONT_BOLD", ""),
    str(FRONTEND_DIST / "fonts/golos-text-600.ttf"),
    str(PROJECT_ROOT / "frontend/public/fonts/golos-text-600.ttf"),
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
]


def _hex(value: str, fallback: str = "#647467") -> tuple[int, int, int]:
    value = (value or fallback).lstrip("#")
    if len(value) != 6:
        value = fallback.lstrip("#")
    try:
        return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return (100, 116, 103)


def _mix(color: str, target: str, ratio: float) -> tuple[int, int, int]:
    source_rgb = _hex(color)
    target_rgb = _hex(target)
    return tuple(
        round(source + (target - source) * ratio)
        for source, target in zip(source_rgb, target_rgb)
    )  # type: ignore[return-value]


def _text_color(background: tuple[int, int, int]) -> str:
    luminance = (
        0.2126 * background[0] + 0.7152 * background[1] + 0.0722 * background[2]
    )
    return "#17251A" if luminance > 150 else "#FFFFFF"


@lru_cache(maxsize=128)
def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = FONT_CANDIDATES_BOLD if bold else FONT_CANDIDATES_REGULAR
    for path in candidates:
        if not path:
            continue
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _text_width(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def _fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font,
    max_width: int,
) -> str:
    if _text_width(draw, text, font) <= max_width:
        return text
    ellipsis = "…"
    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        candidate = text[:middle].rstrip() + ellipsis
        if _text_width(draw, candidate, font) <= max_width:
            low = middle
        else:
            high = middle - 1
    return (text[:low].rstrip() + ellipsis) if low else ellipsis


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if _text_width(draw, candidate, font) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def _draw_chip(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    color: str,
    font,
    max_width: int,
) -> int:
    text = _fit_text(draw, text, font, max_width - 24)
    width = min(max_width, _text_width(draw, text, font) + 20)
    height = 26
    fill = _mix(color, SURFACE, 0.9)
    outline = _mix(color, INK, 0.18)
    draw.rounded_rectangle(
        (x, y, x + width, y + height),
        radius=4,
        fill=fill,
        outline=outline,
        width=1,
    )
    draw.text((x + 9, y + 5), text, font=font, fill=INK)
    return width


def _draw_map(canvas: Image.Image, store: schemas.StoreOut, shelves: list[schemas.ShelfOut]) -> int:
    map_top = 156
    map_height = 520
    card_box = (MARGIN, map_top, WIDTH - MARGIN, map_top + map_height)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(card_box, radius=16, fill=CARD, outline=LINE, width=1)

    label_font = _font(14)
    draw.text(
        (MARGIN + 24, map_top + 22),
        "План сверху",
        font=label_font,
        fill=MUTED,
    )

    available = (
        MARGIN + 38,
        map_top + 58,
        WIDTH - MARGIN - 38,
        map_top + map_height - 38,
    )
    map_width = max(store.map_width, 1)
    map_height_units = max(store.map_height, 1)
    scale = min(
        (available[2] - available[0]) / map_width,
        (available[3] - available[1]) / map_height_units,
    )
    floor_width = map_width * scale
    floor_height = map_height_units * scale
    offset_x = available[0] + ((available[2] - available[0]) - floor_width) / 2
    offset_y = available[1] + ((available[3] - available[1]) - floor_height) / 2

    floor_box = (
        round(offset_x),
        round(offset_y),
        round(offset_x + floor_width),
        round(offset_y + floor_height),
    )
    draw.rounded_rectangle(floor_box, radius=12, fill=SURFACE, outline=LINE, width=1)

    # Light guidance grid, one cell per 10 map units.
    step_x = 10
    step_y = 10
    for gx in range(step_x, int(map_width), step_x):
        px = round(offset_x + gx * scale)
        draw.line((px, floor_box[1] + 10, px, floor_box[3] - 10), fill="#E9E5DB", width=1)
    for gy in range(step_y, int(map_height_units), step_y):
        py = round(offset_y + gy * scale)
        draw.line((floor_box[0] + 10, py, floor_box[2] - 10, py), fill="#E9E5DB", width=1)

    # Entrance marker.
    entrance_x = offset_x + store.entrance_x * scale
    entrance_y = offset_y + store.entrance_y * scale
    entrance_y = min(max(entrance_y, floor_box[1] + 18), floor_box[3] - 18)
    entrance_x = min(max(entrance_x, floor_box[0] + 38), floor_box[2] - 38)
    marker_r = 9
    draw.ellipse(
        (
            entrance_x - marker_r,
            entrance_y - marker_r,
            entrance_x + marker_r,
            entrance_y + marker_r,
        ),
        fill=ACCENT,
        outline=SURFACE,
        width=2,
    )
    entrance_font = _font(13)
    label = store.entrance_label or "Вход"
    label_width = _text_width(draw, label, entrance_font)
    label_x = min(max(entrance_x - label_width / 2, floor_box[0] + 10), floor_box[2] - label_width - 10)
    draw.text((label_x, entrance_y + 16), label, font=entrance_font, fill=MUTED)

    shelf_font = _font(16, bold=True)
    shelf_meta_font = _font(11)
    external_labels: list[tuple[int, int, int, int, str, tuple[int, int, int]]] = []
    for shelf in shelves:
        left = round(offset_x + shelf.x * scale)
        top = round(offset_y + shelf.y * scale)
        right = round(offset_x + (shelf.x + shelf.width) * scale)
        bottom = round(offset_y + (shelf.y + shelf.height) * scale)
        left, right = min(left, right), max(left, right)
        top, bottom = min(top, bottom), max(top, bottom)
        left = max(left, floor_box[0] + 2)
        top = max(top, floor_box[1] + 2)
        right = min(right, floor_box[2] - 2)
        bottom = min(bottom, floor_box[3] - 2)
        if right - left < 12 or bottom - top < 12:
            continue

        fill = _mix(shelf.color, SURFACE, 0.12)
        outline = _mix(shelf.color, INK, 0.28)
        draw.rounded_rectangle(
            (left, top, right, bottom),
            radius=moderate_radius(right - left, bottom - top),
            fill=fill,
            outline=outline,
            width=1,
        )

        inner_width = right - left - 18
        if inner_width <= 12:
            continue
        text_color = _text_color(fill)
        meta = f"{shelf.levels_count} полок"
        meta_display = _fit_text(draw, meta, shelf_meta_font, inner_width)

        if inner_width < 92 or _text_width(draw, shelf.name, shelf_font) > inner_width:
            external_labels.append((left, top, right, bottom, shelf.name, outline))
            if bottom - top >= 34:
                meta_width = _text_width(draw, meta_display, shelf_meta_font)
                draw.text(
                    (
                        left + (right - left - meta_width) / 2,
                        top + (bottom - top - 13) / 2,
                    ),
                    meta_display,
                    font=shelf_meta_font,
                    fill=text_color,
                )
            continue

        name_lines = _wrap(draw, shelf.name, shelf_font, inner_width)
        if len(name_lines) > 2:
            name_lines = [
                name_lines[0],
                _fit_text(draw, " ".join(name_lines[1:]), shelf_font, inner_width),
            ]
        content_height = len(name_lines) * 19 + 15
        text_y = top + max(8, (bottom - top - content_height) // 2)
        for line_index, line in enumerate(name_lines):
            draw.text(
                (left + 9, text_y + line_index * 19),
                line,
                font=shelf_font,
                fill=text_color,
            )
        if bottom - top >= 46:
            draw.text(
                (left + 9, text_y + len(name_lines) * 19 + 1),
                meta_display,
                font=shelf_meta_font,
                fill=text_color,
            )

    external_font = _font(12, bold=True)
    for left, top, right, bottom, name, outline in external_labels:
        text = _fit_text(draw, name, external_font, 180)
        text_width = _text_width(draw, text, external_font)
        badge_width = text_width + 18
        center = (left + right) / 2
        badge_left = min(
            max(center - badge_width / 2, floor_box[0] + 4),
            floor_box[2] - badge_width - 4,
        )
        badge_top = top - 26
        if badge_top < floor_box[1] + 4:
            badge_top = bottom + 5
        draw.line(
            (center, min(badge_top + 20, top), center, max(badge_top, top)),
            fill=outline,
            width=1,
        )
        draw.rounded_rectangle(
            (badge_left, badge_top, badge_left + badge_width, badge_top + 20),
            radius=4,
            fill=CARD,
            outline=outline,
            width=1,
        )
        draw.text(
            (badge_left + 9, badge_top + 3),
            text,
            font=external_font,
            fill=INK,
        )

    return map_top + map_height


def moderate_radius(width: int, height: int) -> int:
    return max(6, min(14, width // 8, height // 3))


def _draw_legend(
    canvas: Image.Image,
    top: int,
    shelves: list[schemas.ShelfOut],
) -> int:
    draw = ImageDraw.Draw(canvas)
    title_font = _font(28)
    subtitle_font = _font(15)
    draw.text((MARGIN, top + 10), "Что где лежит", font=title_font, fill=INK)
    draw.text(
        (MARGIN, top + 52),
        "Полки в карточках показаны сверху вниз, как в редакторе.",
        font=subtitle_font,
        fill=MUTED,
    )

    content_top = top + 96
    if not shelves:
        draw.rounded_rectangle(
            (MARGIN, content_top, WIDTH - MARGIN, content_top + 160),
            radius=12,
            fill=CARD,
            outline=LINE,
            width=1,
        )
        empty_font = _font(20, bold=True)
        draw.text(
            (MARGIN + 32, content_top + 54),
            "Стеллажи ещё не добавлены",
            font=empty_font,
            fill=INK,
        )
        draw.text(
            (MARGIN + 32, content_top + 90),
            "Администратор может создать схему в веб-редакторе.",
            font=subtitle_font,
            fill=MUTED,
        )
        return content_top + 190

    gap = 16
    columns = 2
    card_width = (WIDTH - MARGIN * 2 - gap * (columns - 1)) // columns
    max_levels = max((max(1, len(shelf.levels)) for shelf in shelves), default=1)
    card_height = 82 + max_levels * 32
    rows = math.ceil(len(shelves) / columns)
    total_height = rows * card_height + (rows - 1) * gap

    card_font = _font(19, bold=True)
    hint_font = _font(13)
    count_font = _font(12)
    level_font = _font(11)
    chip_font = _font(12)

    for index, shelf in enumerate(shelves):
        column = index % columns
        row = index // columns
        left = MARGIN + column * (card_width + gap)
        top_y = content_top + row * (card_height + gap)
        right = left + card_width
        bottom = top_y + card_height

        draw.rounded_rectangle(
            (left, top_y, right, bottom),
            radius=12,
            fill=CARD,
            outline=LINE,
            width=1,
        )
        draw.rounded_rectangle(
            (left, top_y + 18, left + 3, top_y + 58),
            radius=1,
            fill=shelf.color,
        )
        name = _fit_text(draw, shelf.name, card_font, card_width - 160)
        draw.text((left + 24, top_y + 20), name, font=card_font, fill=INK)
        hint = _fit_text(draw, shelf.location_hint, hint_font, card_width - 60)
        draw.text((left + 24, top_y + 50), hint, font=hint_font, fill=MUTED)

        badge_text = f"{shelf.levels_count} полок"
        badge_width = _text_width(draw, badge_text, count_font)
        draw.text(
            (right - badge_width - 18, top_y + 26),
            badge_text,
            font=count_font,
            fill=MUTED,
        )

        levels = sorted(shelf.levels, key=lambda item: item.position)
        for level in levels:
            row_y = top_y + 78 + level.position * 32
            if row_y + 28 > bottom - 8:
                break
            draw.rounded_rectangle(
                (left + 22, row_y, left + 44, row_y + 24),
                radius=4,
                fill=SURFACE,
                outline=LINE,
                width=1,
            )
            number = str(level.position + 1)
            number_width = _text_width(draw, number, level_font)
            draw.text(
                (left + 33 - number_width / 2, row_y + 7),
                number,
                font=level_font,
                fill=MUTED,
            )

            chip_x = left + 54
            chip_limit = right - 18
            categories = sorted(level.categories, key=lambda item: item.position)
            if not categories:
                draw.text(
                    (chip_x, row_y + 4),
                    "нет товаров",
                    font=chip_font,
                    fill="#A0ADA2",
                )
                continue
            for category_index, category in enumerate(categories):
                remaining = len(categories) - category_index
                reserve = 54 if remaining > 1 else 0
                max_chip_width = chip_limit - chip_x - reserve
                if max_chip_width < 70:
                    more_text = f"+{remaining}"
                    more_width = _text_width(draw, more_text, chip_font) + 18
                    draw.rounded_rectangle(
                        (chip_x, row_y, chip_x + more_width, row_y + 24),
                        radius=4,
                        fill=SURFACE,
                    )
                    draw.text(
                        (chip_x + 9, row_y + 5),
                        more_text,
                        font=chip_font,
                        fill=MUTED,
                    )
                    break
                used = _draw_chip(
                    draw,
                    chip_x,
                    row_y - 1,
                    category.name,
                    category.color,
                    chip_font,
                    max_chip_width,
                )
                chip_x += used + 4

    return content_top + total_height


def render_store_map(layout: schemas.LayoutOut) -> bytes:
    store = layout.store
    shelves = layout.shelves

    map_bottom = 156 + 520
    max_levels = max((max(1, len(shelf.levels)) for shelf in shelves), default=1)
    rows = math.ceil(max(1, len(shelves)) / 2)
    card_height = 82 + max_levels * 32
    legend_bottom = map_bottom + 52 + 96 + rows * card_height + max(0, rows - 1) * 16
    height = max(900, legend_bottom + 96)

    canvas = Image.new("RGB", (WIDTH, height), BACKGROUND)
    draw = ImageDraw.Draw(canvas)

    # Header
    kicker_font = _font(14)
    title_font = _font(40, bold=True)
    address_font = _font(18)
    draw.text((MARGIN, 44), "Схема магазина · AI-навигация", font=kicker_font, fill=MUTED)
    draw.text((MARGIN, 70), store.name, font=title_font, fill=INK)
    if store.address:
        draw.text((MARGIN, 122), store.address, font=address_font, fill=MUTED)

    badge = "Поиск товаров"
    badge_font = _font(13)
    badge_width = _text_width(draw, badge, badge_font)
    badge_left = WIDTH - MARGIN - badge_width
    draw.ellipse((badge_left - 14, 61, badge_left - 6, 69), fill=ACCENT)
    draw.text((badge_left, 52), badge, font=badge_font, fill=MUTED)

    _draw_map(canvas, store, shelves)
    legend_bottom = _draw_legend(canvas, map_bottom + 36, shelves)

    footer_font = _font(11)
    draw.text(
        (MARGIN, height - 48),
        "Схема создана администратором магазина. Расположение стеллажей условное.",
        font=footer_font,
        fill=MUTED,
    )
    draw.text(
        (WIDTH - MARGIN - 84, height - 48),
        "where is the milk?",
        font=footer_font,
        fill=MUTED,
    )

    output = io.BytesIO()
    canvas.save(output, format="PNG", optimize=True)
    return output.getvalue()
