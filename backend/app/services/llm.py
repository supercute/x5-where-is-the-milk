from __future__ import annotations

import asyncio
import logging
import re
import threading
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx

from ..config import (
    LLM_API_KEY,
    LLM_APP_NAME,
    LLM_BASE_URL,
    LLM_ENABLE_THINKING,
    LLM_FAILURE_COOLDOWN,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_PROVIDER,
    LLM_SITE_URL,
    LLM_TEMPERATURE,
    LLM_TIMEOUT,
    QWEN_CACHE_DIR,
    QWEN_DEVICE,
    QWEN_ENABLED,
    QWEN_MAX_NEW_TOKENS,
    QWEN_MODEL_ID,
)

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


@dataclass
class GenerationResult:
    text: str
    source: str
    model: str


class OpenAICompatibleAnswerer:
    """Client for any OpenAI-compatible chat completions router.

    Works with OpenRouter, an internal gateway, vLLM, Ollama's OpenAI endpoint,
    or another provider exposing POST /chat/completions.
    """

    def __init__(
        self,
        *,
        api_key: str = LLM_API_KEY,
        base_url: str = LLM_BASE_URL,
        model: str = LLM_MODEL,
        timeout: float = LLM_TIMEOUT,
        max_tokens: int = LLM_MAX_TOKENS,
        temperature: float = LLM_TEMPERATURE,
        site_url: str = LLM_SITE_URL,
        app_name: str = LLM_APP_NAME,
        enable_thinking: bool | None = LLM_ENABLE_THINKING,
        transport: httpx.AsyncBaseTransport | None = None,
        retry_delay: float = 0.4,
        cooldown_seconds: float = LLM_FAILURE_COOLDOWN,
    ) -> None:
        self.api_key = api_key.strip()
        self.base_url = base_url.strip().rstrip("/")
        self.model = model.strip()
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.site_url = site_url.strip()
        self.app_name = app_name.strip()
        self.enable_thinking = enable_thinking
        self._transport = transport
        self._retry_delay = retry_delay
        self._cooldown_seconds = max(0.0, cooldown_seconds)
        self._blocked_until = 0.0
        self._last_error: str | None = None

    @property
    def model_id(self) -> str:
        return self.model

    @property
    def source(self) -> str:
        return "api"

    @property
    def _configuration_error(self) -> str | None:
        if not self.base_url:
            return "LLM_BASE_URL не задан"
        if not self.model:
            return "LLM_MODEL не задан"
        try:
            url = urlsplit(self.base_url)
            port = url.port
            if (
                url.scheme not in {"http", "https"}
                or not url.hostname
                or url.username is not None
                or "?" in self.base_url
                or "#" in self.base_url
                or port == 0
                or any(char.isspace() for char in self.base_url)
            ):
                return "Некорректный LLM_BASE_URL"
        except ValueError:
            return "Некорректный LLM_BASE_URL"
        if not self.api_key and url.hostname not in {
            "localhost", "127.0.0.1", "::1", "0.0.0.0", "host.docker.internal",
        }:
            return "LLM_API_KEY не задан"
        return None

    @property
    def configured(self) -> bool:
        return self._configuration_error is None

    @property
    def ready(self) -> bool:
        return self.configured and time.monotonic() >= self._blocked_until

    @property
    def loading(self) -> bool:
        return False

    @property
    def status(self) -> dict[str, Any]:
        return {
            "provider": "openai",
            "enabled": self.configured,
            "model": self.model,
            "ready": self.ready,
            "loaded": False,
            "loading": False,
            "cooldown": round(max(0.0, self._blocked_until - time.monotonic()), 1),
            "error": self._last_error or self._configuration_error,
        }

    def preload_in_background(self) -> None:
        # API mode is stateless: nothing to load into memory.
        return

    @property
    def _endpoint(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        if self.app_name:
            headers["X-Title"] = self.app_name
        return headers

    @staticmethod
    def _extract_content(data: object) -> str:
        if not isinstance(data, dict) or data.get("error"):
            return ""
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            return ""
        first = choices[0]
        message = first.get("message")
        content = message.get("content") if isinstance(message, dict) else None

        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
            return "".join(parts)
        if isinstance(first.get("text"), str):
            return first["text"]
        return ""

    def _fail(self, message: str) -> None:
        self._last_error = message
        self._blocked_until = time.monotonic() + self._cooldown_seconds
        logger.warning("%s", message)

    async def generate(
        self, system_prompt: str, user_prompt: str
    ) -> GenerationResult | None:
        if not self.ready:
            return None

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        if self.enable_thinking is not None:
            payload["enable_thinking"] = self.enable_thinking

        try:
            async with asyncio.timeout(self.timeout):
                return await self._complete(payload)
        except (TimeoutError, httpx.TimeoutException):
            self._fail(f"Таймаут LLM API ({self.timeout:g} с)")
        except (httpx.HTTPError, httpx.InvalidURL, ValueError):
            self._fail("Ошибка подключения или настроек LLM API")
        return None

    async def _complete(self, payload: dict[str, Any]) -> GenerationResult | None:
        async with httpx.AsyncClient(
            timeout=self.timeout,
            transport=self._transport,
        ) as client:
            for attempt in range(2):
                response = await client.post(
                    self._endpoint,
                    headers=self._headers(),
                    json=payload,
                )

                if response.status_code in RETRYABLE_STATUS_CODES and attempt == 0:
                    logger.warning(
                        "LLM API временно вернул HTTP %s, повторяю запрос",
                        response.status_code,
                    )
                    await asyncio.sleep(self._retry_delay)
                    continue

                if not response.is_success:
                    self._fail(f"LLM API HTTP {response.status_code}")
                    return None

                try:
                    data = response.json()
                except ValueError:
                    self._fail("LLM API вернул не JSON")
                    return None

                text = clean_model_output(self._extract_content(data))
                if not text:
                    self._fail("LLM API вернул пустой или некорректный ответ")
                    return None

                self._last_error = None
                self._blocked_until = 0.0
                return GenerationResult(
                    text=text,
                    source=self.source,
                    model=self.model,
                )

        return None


class QwenAnswerer:
    """Lazy, CPU-friendly wrapper around a small Qwen instruct model."""

    def __init__(self) -> None:
        self._model: Any = None
        self._tokenizer: Any = None
        self._lock = threading.Lock()
        self._load_attempted = False
        self._loading = False
        self._preload_thread: threading.Thread | None = None
        self._load_error: str | None = None

    @property
    def model_id(self) -> str:
        return QWEN_MODEL_ID

    @property
    def source(self) -> str:
        return "qwen"

    @property
    def configured(self) -> bool:
        return QWEN_ENABLED not in {"0", "false", "off", "no"}

    @property
    def ready(self) -> bool:
        return self._model is not None and self._tokenizer is not None

    @property
    def loading(self) -> bool:
        return self._loading

    @property
    def status(self) -> dict[str, Any]:
        return {
            "provider": "qwen",
            "enabled": self.configured,
            "model": self.model_id,
            "loaded": self.ready,
            "loading": self._loading,
            "error": self._load_error,
        }

    def preload_in_background(self) -> None:
        """Start loading without blocking an API or bot request."""
        if not self.configured or self.ready or self._load_attempted:
            return
        if self._preload_thread is not None and self._preload_thread.is_alive():
            return
        self._preload_thread = threading.Thread(
            target=self._preload_worker,
            name="qwen-preload",
            daemon=True,
        )
        self._preload_thread.start()

    def _preload_worker(self) -> None:
        try:
            with self._lock:
                self._load_sync()
        except Exception:
            # The error is already exposed through status and logged.
            pass

    def _load_sync(self) -> None:
        if self.ready:
            return
        if self._load_attempted and self._load_error:
            raise RuntimeError(self._load_error)
        self._load_attempted = True
        self._loading = True

        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except Exception as exc:  # pragma: no cover - optional heavy dependencies
            self._loading = False
            self._load_error = (
                "Qwen не загружен: установите requirements-llm.txt "
                f"({type(exc).__name__}: {exc})"
            )
            logger.warning(self._load_error)
            raise RuntimeError(self._load_error) from exc

        try:
            if QWEN_DEVICE == "cpu":
                device = "cpu"
            elif QWEN_DEVICE == "mps":
                device = "mps"
            elif QWEN_DEVICE == "cuda":
                device = "cuda"
            elif torch.cuda.is_available():
                device = "cuda"
            elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"

            dtype = torch.float16 if device in {"cuda", "mps"} else torch.float32

            logger.info("Загружаю %s на %s…", self.model_id, device)
            tokenizer = AutoTokenizer.from_pretrained(
                self.model_id,
                cache_dir=QWEN_CACHE_DIR,
            )
            model = AutoModelForCausalLM.from_pretrained(
                self.model_id,
                cache_dir=QWEN_CACHE_DIR,
                torch_dtype=dtype,
                low_cpu_mem_usage=True,
            )
            model.to(device)
            model.eval()
            self._tokenizer = tokenizer
            self._model = model
            self._loading = False
            logger.info("Модель %s готова", self.model_id)
        except Exception as exc:  # pragma: no cover - depends on model/runtime
            self._loading = False
            self._model = None
            self._tokenizer = None
            self._load_error = f"Qwen не загружен: {type(exc).__name__}: {exc}"
            logger.exception("Ошибка загрузки Qwen")
            raise RuntimeError(self._load_error) from exc

    def _generate_sync(self, system_prompt: str, user_prompt: str) -> str:
        with self._lock:
            self._load_sync()
            import torch

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            try:
                rendered = self._tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                    enable_thinking=False,
                )
            except TypeError:
                rendered = self._tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                )

            inputs = self._tokenizer([rendered], return_tensors="pt")
            device = next(self._model.parameters()).device
            inputs = {key: value.to(device) for key, value in inputs.items()}
            with torch.inference_mode():
                output = self._model.generate(
                    **inputs,
                    max_new_tokens=QWEN_MAX_NEW_TOKENS,
                    do_sample=False,
                    repetition_penalty=1.05,
                    pad_token_id=self._tokenizer.eos_token_id,
                )
            new_tokens = output[0][inputs["input_ids"].shape[-1] :]
            return self._tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

    async def generate(
        self, system_prompt: str, user_prompt: str
    ) -> GenerationResult | None:
        if not self.configured:
            return None
        try:
            text = await asyncio.wait_for(
                asyncio.to_thread(self._generate_sync, system_prompt, user_prompt),
                timeout=180,
            )
        except Exception as exc:  # pragma: no cover - optional model path
            logger.warning("Qwen недоступен, использую fallback: %s", exc)
            return None

        text = clean_model_output(text)
        if not text:
            return None
        return GenerationResult(text=text, source=self.source, model=self.model_id)


class DisabledAnswerer:
    """Explicitly disabled LLM: the bot uses deterministic DB answers only."""

    model_id = "disabled"
    source = "fallback"
    configured = False
    ready = False
    loading = False

    @property
    def status(self) -> dict[str, Any]:
        return {
            "provider": "disabled",
            "enabled": False,
            "model": self.model_id,
            "loaded": False,
            "loading": False,
            "error": "LLM отключён через LLM_PROVIDER=disabled",
        }

    def preload_in_background(self) -> None:
        return

    async def generate(
        self, system_prompt: str, user_prompt: str
    ) -> GenerationResult | None:
        return None


def clean_model_output(text: str) -> str:
    if not text:
        return ""
    text = text.replace("<|im_end|>", "").replace("<|endoftext|>", "")
    if "<｜end▁of▁thinking｜>" in text:
        text = text.split("<｜end▁of▁thinking｜>")[-1]
    text = re.sub(
        r"<think(?:ing)?>.*?<｜end▁of▁thinking｜>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    text = re.sub(r"</?think(?:ing)?>", "", text, flags=re.IGNORECASE)
    text = re.sub(
        r"^```(?:text|json)?\s*|\s*```$",
        "",
        text.strip(),
        flags=re.IGNORECASE,
    )
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > 700:
        text = text[:700].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
    return text


LLMAnswerer = QwenAnswerer | OpenAICompatibleAnswerer | DisabledAnswerer


def _build_answerer() -> LLMAnswerer:
    provider = LLM_PROVIDER
    if provider == "auto":
        api_answerer = OpenAICompatibleAnswerer()
        if api_answerer.configured:
            return api_answerer
        elif QWEN_ENABLED not in {"0", "false", "off", "no"}:
            provider = "qwen"
        else:
            provider = "disabled"

    if provider in {"openai", "api", "openrouter", "router"}:
        return OpenAICompatibleAnswerer()
    if provider in {"qwen", "local"}:
        return QwenAnswerer()
    if provider in {"disabled", "none", "off", "0"}:
        return DisabledAnswerer()

    logger.warning("Неизвестный LLM_PROVIDER=%s, LLM отключён", provider)
    return DisabledAnswerer()


_answerer: LLMAnswerer = _build_answerer()


def get_answerer() -> LLMAnswerer:
    return _answerer
