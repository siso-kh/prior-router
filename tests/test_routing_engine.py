"""Tests for :mod:`src.llm_circuit_router.routing_engine`."""

from __future__ import annotations

import json

from src.llm_circuit_router.routing_engine import CircuitRouterSortingEngine


def _model(scores, *, reliability=1.0, quarantined_until=None, vision=0.0):
    benchmarks = {"general": 0.0, "coding": 0.0, "reasoning": 0.0, "vision": vision}
    benchmarks.update(scores)
    return {
        "provider": "openrouter",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": "sk-test",
        "context_length": 4096,
        "reliability": {"score": reliability, "quarantined_until": quarantined_until},
        "benchmarks": benchmarks,
        "composite_routing_scores": dict(benchmarks),
    }


def _write_registry(tmp_path, models):
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(models), encoding="utf-8")
    return str(path)


def test_sorts_by_composite_score_descending(tmp_path):
    path = _write_registry(
        tmp_path,
        {
            "mid": _model({"coding": 50.0}),
            "top": _model({"coding": 90.0}),
            "low": _model({"coding": 10.0}),
        },
    )

    ranked = CircuitRouterSortingEngine(path).get_ranked_models_for_task("coding")

    assert [model["model_name"] for model in ranked] == ["top", "mid", "low"]
    assert ranked[0]["composite_score"] == 90.0


def test_omitted_task_defaults_to_general(tmp_path):
    path = _write_registry(
        tmp_path,
        {
            "gen": _model({"general": 70.0, "coding": 10.0}),
            "coder": _model({"general": 20.0, "coding": 99.0}),
        },
    )

    ranked = CircuitRouterSortingEngine(path).get_ranked_models_for_task(None)

    assert [model["model_name"] for model in ranked] == ["gen", "coder"]


def test_unknown_task_falls_back_to_general(tmp_path, capsys):
    path = _write_registry(tmp_path, {"gen": _model({"general": 70.0})})

    ranked = CircuitRouterSortingEngine(path).get_ranked_models_for_task("astrology")

    assert [model["model_name"] for model in ranked] == ["gen"]
    assert "invalid task" in capsys.readouterr().out.lower()


def test_quarantined_models_are_excluded(tmp_path):
    path = _write_registry(
        tmp_path,
        {
            "available": _model({"general": 10.0}),
            "banned": _model({"general": 99.0}, quarantined_until="2999-01-01T00:00:00Z"),
        },
    )

    ranked = CircuitRouterSortingEngine(path).get_ranked_models_for_task("general")

    assert [model["model_name"] for model in ranked] == ["available"]


def test_vision_task_requires_vision_capability(tmp_path):
    path = _write_registry(
        tmp_path,
        {
            "blind": _model({"general": 90.0}),
            "seer": _model({"general": 40.0}, vision=80.0),
        },
    )

    ranked = CircuitRouterSortingEngine(path).get_ranked_models_for_task("vision")

    assert [model["model_name"] for model in ranked] == ["seer"]


def test_missing_registry_returns_empty_list(tmp_path, capsys):
    engine = CircuitRouterSortingEngine(str(tmp_path / "nope.json"))

    assert engine.get_ranked_models_for_task("general") == []
    assert "missing or" in capsys.readouterr().out


def test_payload_exposes_expected_fields(tmp_path):
    path = _write_registry(
        tmp_path, {"m": _model({"general": 42.0}, reliability=0.5)}
    )

    [entry] = CircuitRouterSortingEngine(path).get_ranked_models_for_task("general")

    assert entry["composite_score"] == 42.0
    assert entry["benchmark_base"] == 42.0
    assert entry["reliability_score"] == 0.5
    assert entry["provider"] == "openrouter"
