"""Tests for :mod:`src.llm_circuit_router.discovery` (no real network calls)."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from src.llm_circuit_router.discovery import ModelDiscoveryEngine


class FakeResponse:
    def __init__(self, payload: Any, status_code: int = 200, text: str = "") -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = text

    def json(self) -> Any:
        return self._payload


class FakeClient:
    """Minimal stand-in for ``httpx.AsyncClient`` that records requested URLs."""

    def __init__(self, response: FakeResponse) -> None:
        self._response = response
        self.requested_urls: List[str] = []

    async def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.requested_urls.append(url)
        return self._response


def test_openrouter_driver_keeps_only_free_models():
    payload: Dict[str, Any] = {
        "data": [
            {
                "id": "vendor/free-model:free",
                "pricing": {"prompt": "0", "completion": "0"},
                "context_length": 100,
            },
            {
                "id": "vendor/paid-model",
                "pricing": {"prompt": "0.5", "completion": "1"},
                "context_length": 200,
            },
        ]
    }
    client = FakeClient(FakeResponse(payload))

    models = asyncio.run(
        ModelDiscoveryEngine([])._discover_openrouter(
            client, "https://openrouter.ai/api/v1", "sk-test", {}
        )
    )

    assert [model["model_name"] for model in models] == ["vendor/free-model:free"]
    assert models[0]["provider"] == "openrouter"
    assert models[0]["api_key"] == "sk-test"


def test_openrouter_driver_returns_empty_on_error_status():
    client = FakeClient(FakeResponse({}, status_code=500, text="boom"))

    models = asyncio.run(
        ModelDiscoveryEngine([])._discover_openrouter(
            client, "https://openrouter.ai/api/v1", "sk-test", {}
        )
    )

    assert models == []


def test_bynara_driver_detects_free_suffix_and_skips_paid():
    payload: Dict[str, Any] = {
        "data": [
            {"id": "vendor/thing-free", "context_length": 10},
            {
                "id": "vendor/paid",
                "pricing": {"prompt": "1", "completion": "1"},
                "context_length": 20,
            },
        ]
    }
    client = FakeClient(FakeResponse(payload))

    models = asyncio.run(
        ModelDiscoveryEngine([])._discover_bynara(
            client, "https://router.bynara.id/v1", "nar-test", {}
        )
    )

    assert [model["model_name"] for model in models] == ["vendor/thing-free"]
    assert models[0]["base_url"] == "https://router.bynara.id/v1"
    assert client.requested_urls == ["https://router.bynara.id/v1/models"]


def test_all_free_models_skips_invalid_credentials_without_requesting():
    engine = ModelDiscoveryEngine(
        [{"provider": "openrouter", "api_key": "", "base_url": ""}]
    )

    assert asyncio.run(engine.get_all_free_models()) == []
