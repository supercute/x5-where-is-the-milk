from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatAction
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import select

from .config import QWEN_PRELOAD, TELEGRAM_BOT_TOKEN
from .database import SessionLocal, init_db
from .models import Store
from .seed import seed_demo_data
from .services.agent import answer_query, is_map_request
from .services.layout import build_layout
from .services.llm import get_answerer
from .services.map_image import render_store_map

logger = logging.getLogger(__name__)
dp = Dispatcher()


def _map_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗺 Показать схему магазина", callback_data="map:show")]
        ]
    )


def _first_store():
    with SessionLocal() as db:
        return db.scalar(select(Store).order_by(Store.id).limit(1))


def _load_store_and_map() -> tuple[str, bytes] | None:
    with SessionLocal() as db:
        store = db.scalar(select(Store).order_by(Store.id).limit(1))
        if store is None:
            return None
        layout = build_layout(db, store.id)
        return layout.store.name, render_store_map(layout)


async def _send_map(message: Message) -> None:
    await message.bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_PHOTO)
    try:
        payload = await asyncio.to_thread(_load_store_and_map)
    except Exception:
        logger.exception("Не удалось подготовить схему")
        await message.answer("Не получилось подготовить схему. Попробуйте чуть позже.")
        return
    if payload is None:
        await message.answer(
            "Магазин ещё не настроен. Попросите администратора заполнить схему."
        )
        return
    store_name, image = payload
    await message.answer_photo(
        BufferedInputFile(image, filename="store-map.png"),
        caption=(
            f"Схема магазина «{store_name}».\n\n"
            "Спросите меня, где лежит товар, например: «Где молоко?»"
        ),
    )


@dp.message(CommandStart())
async def start(message: Message) -> None:
    name = "вашем магазине"
    try:
        store = await asyncio.to_thread(_first_store)
        if store is not None:
            name = f"магазине «{store.name}»"
    except Exception:
        logger.exception("Не удалось получить магазин")
    await message.answer(
        f"Здравствуйте! Я помогу найти товар в {name}.\n\n"
        "Напишите, что ищете, — например: «Где молоко?» или «Куда за яйцами?».\n\n"
        "Или откройте схему магазина кнопкой ниже.",
        reply_markup=_map_keyboard(),
    )


@dp.message(Command("map"))
async def map_command(message: Message) -> None:
    await _send_map(message)


@dp.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        "Я знаю схему торгового зала и подскажу, на каком стеллаже и какой полке искать товар.\n\n"
        "Примеры:\n"
        "• Где молоко?\n"
        "• Где бананы?\n"
        "• Покажи схему магазина\n\n"
        "Команда /map — прислать картинку со схемой.",
        reply_markup=_map_keyboard(),
    )


@dp.callback_query(F.data == "map:show")
async def map_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message is not None:
        await _send_map(callback.message)


@dp.message(F.text & ~F.text.startswith("/"))
async def handle_text(message: Message) -> None:
    text = (message.text or "").strip()
    if not text:
        return

    if is_map_request(text):
        await _send_map(message)
        return

    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    try:
        with SessionLocal() as db:
            response = await answer_query(db, text)
        await message.answer(response.answer)
    except Exception:
        logger.exception("Ошибка ответа агента")
        await message.answer(
            "Не получилось найти товар. Попробуйте переформулировать вопрос "
            "или попросите схему командой /map."
        )


async def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN не задан. Добавьте токен в .env и запустите снова."
        )
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    init_db()
    with SessionLocal() as db:
        seed_demo_data(db)
    if QWEN_PRELOAD:
        get_answerer().preload_in_background()

    bot = Bot(
        token=TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=None),
    )
    logger.info("Telegram-бот запускается (long polling)")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен")
