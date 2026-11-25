from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.services.agent import (
    PARSE_PROMPT,
    find_matches,
    is_map_request,
    normalize_text,
)
from app.services.llm import (
    GenerationResult,
    OpenAICompatibleAnswerer,
    clean_model_output,
)


def first_store_id(client) -> int:
    response = client.get("/api/stores")
    assert response.status_code == 200
    stores = response.json()
    assert stores
    return stores[0]["id"]


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["llm"]["provider"] == "disabled"
    assert payload["llm"]["enabled"] is False


def test_openai_compatible_client_success():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers.get("authorization")
        seen["title"] = request.headers.get("x-title")
        seen["referer"] = request.headers.get("http-referer")
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "  B  "}}]},
        )

    answerer = OpenAICompatibleAnswerer(
        api_key="test-secret",
        base_url="https://router.example/v1",
        model="test/model",
        site_url="https://store.example",
        app_name="test-app",
        enable_thinking=False,
        transport=httpx.MockTransport(handler),
        retry_delay=0,
    )
    result = asyncio.run(answerer.generate("system prompt", "user prompt"))

    assert result is not None
    assert result.text == "B"
    assert result.source == "api"
    assert result.model == "test/model"
    assert seen["url"] == "https://router.example/v1/chat/completions"
    assert seen["authorization"] == "Bearer test-secret"
    assert seen["title"] == "test-app"
    assert seen["referer"] == "https://store.example"
    assert seen["body"]["model"] == "test/model"
    assert seen["body"]["enable_thinking"] is False
    assert seen["body"]["messages"] == [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "user prompt"},
    ]


def test_openai_compatible_client_retries_temporary_error():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url)
        if len(calls) == 1:
            return httpx.Response(429, text="rate limited")
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "A"}}]},
        )

    answerer = OpenAICompatibleAnswerer(
        api_key="test-secret",
        base_url="https://router.example/v1",
        model="test/model",
        transport=httpx.MockTransport(handler),
        retry_delay=0,
    )
    result = asyncio.run(answerer.generate("system", "user"))

    assert result is not None
    assert result.text == "A"
    assert len(calls) == 2
    assert answerer.status["error"] is None


def test_openai_compatible_client_returns_none_on_error_and_cools_down(caplog):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url)
        return httpx.Response(401, json={"error": "private-diagnostic"})

    answerer = OpenAICompatibleAnswerer(
        api_key="bad-key",
        base_url="https://router.example/v1",
        model="test/model",
        transport=httpx.MockTransport(handler),
        retry_delay=0,
        cooldown_seconds=60,
    )
    result = asyncio.run(answerer.generate("system", "user"))
    second = asyncio.run(answerer.generate("system", "user"))

    assert result is None
    assert second is None
    assert len(calls) == 1
    assert answerer.status["error"] == "LLM API HTTP 401"
    assert "private-diagnostic" not in caplog.text
    assert answerer.status["cooldown"] > 0


def test_openai_compatible_client_allows_local_endpoint_without_key():
    answerer = OpenAICompatibleAnswerer(
        api_key="",
        base_url="http://localhost:11434/v1",
        model="local-model",
    )
    assert answerer.configured is True
    assert answerer.ready is True

    remote = OpenAICompatibleAnswerer(
        api_key="",
        base_url="https://router.example/v1",
        model="remote-model",
    )
    assert remote.configured is False
    assert "LLM_API_KEY" in remote.status["error"]
    assert not OpenAICompatibleAnswerer(
        api_key="", base_url="http://localhost.example/v1", model="remote-model",
    ).configured


@pytest.mark.parametrize("body", [[], {"choices": ["bad"]}, {"choices": {"0": {}}}])
def test_malformed_router_response_falls_back(client, monkeypatch, body):
    answerer = OpenAICompatibleAnswerer(
        api_key="test", base_url="https://router.example/v1", model="test/model",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body)),
    )
    monkeypatch.setattr("app.services.agent.get_answerer", lambda: answerer)
    response = client.post("/api/agent/query", json={"text": "Где кефир и смтану?"})
    assert response.status_code == 200
    assert response.json()["source"] == "fallback"
    assert [item["category"] for item in response.json()["matches"]] == ["Кефир", "Сметана"]


def test_router_timeout_includes_retry_delay():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(429)

    answerer = OpenAICompatibleAnswerer(
        api_key="test", base_url="https://router.example/v1", model="test/model",
        timeout=0.05, retry_delay=30, transport=httpx.MockTransport(handler),
    )
    assert asyncio.run(answerer.generate("system", "user")) is None
    assert len(calls) == 1
    assert "Таймаут" in answerer.status["error"]


def test_demo_layout(client):
    store_id = first_store_id(client)
    response = client.get(f"/api/stores/{store_id}/layout")
    assert response.status_code == 200
    layout = response.json()
    assert layout["store"]["name"]
    assert len(layout["shelves"]) >= 5
    assert layout["stats"]["placed"] > 10
    milk = next(category for category in layout["categories"] if category["name"] == "Молоко")
    assert milk["shelf_id"]
    assert milk["level_position"] == 1


def test_agent_finds_milk(client):
    store_id = first_store_id(client)
    response = client.post(
        "/api/agent/query",
        json={"text": "Где молоко?", "store_id": store_id},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] in {"fallback", "qwen", "api"}
    assert "Молоко" in payload["answer"]
    assert "вторая полка сверху" in payload["answer"]
    assert payload["matches"][0]["shelf_name"] == "У входа"


def test_agent_understands_alias_and_multiple_products(client):
    store_id = first_store_id(client)
    response = client.post(
        "/api/agent/query",
        json={"text": "Где молочка и банан?", "store_id": store_id},
    )
    payload = response.json()
    assert len(payload["matches"]) >= 2
    assert "Молоко" in payload["answer"]
    assert "Бананы" in payload["answer"]


def test_agent_does_not_invent_products(client):
    store_id = first_store_id(client)
    response = client.post(
        "/api/agent/query",
        json={"text": "Где ананасы?", "store_id": store_id},
    )
    payload = response.json()
    assert payload["matches"] == []
    assert "Не нашёл" in payload["answer"]


def test_agent_handles_typos_and_reports_missing_products(client):
    result = client.post("/api/agent/query", json={"text": "Где кефир и смтану?"}).json()
    assert [item["category"] for item in result["matches"]] == ["Кефир", "Сметана"]

    result = client.post("/api/agent/query", json={"text": "Где мыло?"}).json()
    assert result["matches"] == []

    result = client.post("/api/agent/query", json={"text": "Где кефир и мыло?"}).json()
    assert [item["category"] for item in result["matches"]] == ["Кефир"]
    assert "Не всё удалось найти" in result["answer"]


def test_qwen_can_parse_but_locations_come_from_db(client, monkeypatch):
    calls = []

    class Model:
        ready = True

        async def generate(self, system_prompt, user_prompt):
            calls.append((system_prompt, user_prompt))
            text = '```json\n["сметана"]\n```'
            return GenerationResult(text=text, source="qwen", model="test")

    monkeypatch.setattr("app.services.agent.get_answerer", Model)
    result = client.post(
        "/api/agent/query", json={"text": "Где кефир и смтану?"}
    ).json()

    assert calls == [(PARSE_PROMPT, '["смтану"]')]
    assert result["source"] == "qwen"
    assert [item["category"] for item in result["matches"]] == ["Кефир", "Сметана"]
    assert result["answer"].splitlines() == [
        *(f"{item['category']} — {item['summary']}." for item in result["matches"]),
    ]


def test_confident_matches_do_not_call_model(client, monkeypatch):
    calls = []

    class Model:
        ready = True

        async def generate(self, system_prompt, user_prompt):
            calls.append(system_prompt)
            return GenerationResult(
                text="Молоко — стеллаж «У входа», шестая полка справа.",
                source="qwen",
                model="test",
            )

    monkeypatch.setattr("app.services.agent.get_answerer", Model)
    result = client.post("/api/agent/query", json={"text": "Где молоко и яйца?"}).json()
    assert calls == []
    assert result["source"] == "fallback"
    assert "вторая полка сверху" in result["answer"]
    assert "шестая полка" not in result["answer"]
    assert "Яйца" in result["answer"]


def test_agent_reports_api_provider_source(client, monkeypatch):
    class ApiModel:
        ready = True
        model_id = "router/model"

        async def generate(self, system_prompt, user_prompt):
            return GenerationResult(
                text='["сметана"]',
                source="api",
                model="router/model",
            )

    monkeypatch.setattr("app.services.agent.get_answerer", lambda: ApiModel())
    result = client.post("/api/agent/query", json={"text": "Где смтану?"}).json()

    assert result["source"] == "api"
    assert result["model"] == "router/model"
    assert result["answer"].startswith("Сметана —")


def test_qwen_cannot_add_a_product_missing_from_catalog(client, monkeypatch):
    class Model:
        ready = True

        async def generate(self, system_prompt, user_prompt):
            assert system_prompt == PARSE_PROMPT
            return GenerationResult(text='["телевизор"]', source="qwen", model="test")

    monkeypatch.setattr("app.services.agent.get_answerer", Model)
    result = client.post("/api/agent/query", json={"text": "Где телевизор?"}).json()
    assert result["matches"] == []
    assert result["source"] == "fallback"


def test_shelf_category_and_reordering_flow(client):
    store_id = first_store_id(client)
    shelf_response = client.post(
        f"/api/stores/{store_id}/shelves",
        json={
            "name": "Тестовый стеллаж",
            "location_hint": "у тестового входа",
            "color": "#4F8EF7",
            "x": 2,
            "y": 2,
            "width": 16,
            "height": 8,
            "levels_count": 3,
        },
    )
    assert shelf_response.status_code == 201
    shelf = shelf_response.json()
    assert shelf["levels_count"] == 3

    first = client.post(
        f"/api/stores/{store_id}/categories",
        json={"name": "Тестовые вафли", "aliases": ["вафельки"], "color": "#F59E0B"},
    ).json()
    second = client.post(
        f"/api/stores/{store_id}/categories",
        json={"name": "Тестовая халва", "aliases": [], "color": "#8B5CF6"},
    ).json()

    level_id = shelf["levels"][1]["id"]
    assert (
        client.put(
            f"/api/categories/{first['id']}/placement",
            json={"shelf_level_id": level_id, "position": 0},
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"/api/categories/{second['id']}/placement",
            json={"shelf_level_id": level_id, "position": 1},
        ).status_code
        == 200
    )

    layout = client.get(f"/api/stores/{store_id}/layout").json()
    updated_shelf = next(item for item in layout["shelves"] if item["id"] == shelf["id"])
    level = updated_shelf["levels"][1]
    assert [item["name"] for item in level["categories"]] == [
        "Тестовые вафли",
        "Тестовая халва",
    ]

    # Move the second category before the first one.
    assert (
        client.put(
            f"/api/categories/{second['id']}/placement",
            json={"shelf_level_id": level_id, "position": 0},
        ).status_code
        == 200
    )
    layout = client.get(f"/api/stores/{store_id}/layout").json()
    level = next(
        level
        for item in layout["shelves"]
        if item["id"] == shelf["id"]
        for level in item["levels"]
        if level["id"] == level_id
    )
    assert [item["name"] for item in level["categories"]] == [
        "Тестовая халва",
        "Тестовые вафли",
    ]

    # Reducing the number of levels returns categories to the palette.
    reduced = client.patch(
        f"/api/shelves/{shelf['id']}", json={"levels_count": 1}
    ).json()
    assert reduced["levels_count"] == 1
    layout = client.get(f"/api/stores/{store_id}/layout").json()
    moved = next(item for item in layout["categories"] if item["id"] == first["id"])
    assert moved["shelf_level_id"] is None

    client.delete(f"/api/categories/{first['id']}")
    client.delete(f"/api/categories/{second['id']}")
    assert client.delete(f"/api/shelves/{shelf['id']}").status_code == 204


def test_reset_to_demo_requires_confirmation(client):
    store_id = first_store_id(client)
    response = client.post(
        f"/api/stores/{store_id}/reset-demo",
        json={"confirm": False},
    )
    assert response.status_code == 400


def test_reset_to_demo_restores_layout(client):
    store_id = first_store_id(client)
    client.patch(f"/api/stores/{store_id}", json={"name": "Изменённый магазин"})
    client.post(
        f"/api/stores/{store_id}/shelves",
        json={
            "name": "Временный стеллаж",
            "x": 4,
            "y": 4,
            "width": 12,
            "height": 8,
            "levels_count": 2,
        },
    )
    client.post(
        f"/api/stores/{store_id}/categories",
        json={"name": "Временная категория", "color": "#4F8EF7"},
    )

    response = client.post(
        f"/api/stores/{store_id}/reset-demo",
        json={"confirm": True},
    )
    assert response.status_code == 200
    layout = response.json()
    assert layout["store"]["name"] == "Пятёрочка на Ленина"
    assert layout["stats"]["shelves"] == 6
    assert layout["stats"]["categories"] == 37
    assert all(shelf["name"] != "Временный стеллаж" for shelf in layout["shelves"])
    assert all(
        category["name"] != "Временная категория"
        for category in layout["categories"]
    )
    milk = next(category for category in layout["categories"] if category["name"] == "Молоко")
    assert milk["shelf_name"] == "У входа"
    assert milk["level_position"] == 1


def test_map_image(client):
    store_id = first_store_id(client)
    response = client.get(f"/api/stores/{store_id}/map.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(response.content) > 10_000


def test_normalizers_and_map_intent():
    assert normalize_text("Где  МОЛОКО?") == "где молоко"
    assert is_map_request("Покажи схему магазина")
    assert is_map_request("пришли карту")
    assert not is_map_request("Где картошка?")
    assert not is_map_request("Где молоко на схеме?")
    assert clean_model_output("**Молоко** — вторая полка") == "Молоко — вторая полка"


def test_matcher_prefers_exact_category():
    from app import models

    categories = [
        models.Category(id=1, store_id=1, name="Молоко", aliases=[]),
        models.Category(id=2, store_id=1, name="Молоко в бутылках", aliases=["бутылочное"]),
    ]
    matches = find_matches("Где молоко?", categories)
    assert matches
    assert matches[0].category.name == "Молоко"
