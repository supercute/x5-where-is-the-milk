"""Smoke-test the configured LLM provider.

Works for both an OpenAI-compatible router and the optional local Qwen model.

Usage:
    cd backend
    python -m app.warmup
"""

from __future__ import annotations

import asyncio
import json

from .services.agent import PARSE_PROMPT, normalize_text, stem
from .services.llm import get_answerer


async def _main() -> None:
    answerer = get_answerer()
    status = answerer.status
    print(
        f"Провайдер: {status.get('provider')}; "
        f"модель: {status.get('model')}; готов: {answerer.ready}"
    )
    if not answerer.configured:
        print(f"LLM не настроен: {status.get('error')}")
        print("Проверьте LLM_PROVIDER, LLM_BASE_URL, LLM_API_KEY и LLM_MODEL в .env.")
        raise SystemExit(1)

    result = await answerer.generate(
        PARSE_PROMPT,
        '["Где молоко?"]',
    )
    if result is None:
        print("Запрос к модели завершился ошибкой. Подробности в логах.")
        raise SystemExit(1)
    try:
        terms = json.loads(result.text)
    except ValueError:
        terms = None
    if (
        not isinstance(terms, list)
        or len(terms) != 1
        or not isinstance(terms[0], str)
        or stem(normalize_text(terms[0])) != "молок"
    ):
        print("Модель ответила, но не вернула ожидаемый JSON с названием товара.")
        raise SystemExit(1)
    print(f"Ответ модели ({result.source}, {result.model}): {result.text}")


if __name__ == "__main__":
    asyncio.run(_main())
