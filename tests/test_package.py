"""Tests for configuration loading and the package's public surface."""

from __future__ import annotations

import pytest

import src.llm_circuit_router as pkg
from src.llm_circuit_router.config import Settings


def test_settings_accept_explicit_values():
    settings = Settings(
        NARA_API_KEY="nara",
        NARA_BASE_URL="https://router.bynara.id/v1",
        OPENROUTER_API_KEY="or",
        OPENROUTER_BASE_URL="https://openrouter.ai/api/v1",
        BENCHMARK_API_KEY="bench",
    )

    assert settings.OPENROUTER_API_KEY == "or"
    assert settings.NARA_BASE_URL == "https://router.bynara.id/v1"
    assert settings.BENCHMARK_API_KEY == "bench"


def test_package_exposes_a_version():
    assert pkg.__version__ == "0.1.0"


def test_public_symbols_resolve_lazily():
    assert pkg.CircuitRouterSortingEngine.__name__ == "CircuitRouterSortingEngine"
    assert pkg.get_settings.__name__ == "get_settings"


def test_unknown_attribute_raises_attribute_error():
    with pytest.raises(AttributeError):
        pkg.not_a_real_symbol


def test_dir_lists_the_public_api():
    assert "ReboundSession" in dir(pkg)
    assert "ModelDiscoveryEngine" in dir(pkg)
