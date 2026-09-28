"""Scenario tests for the failover :class:`ReboundSession`."""

from __future__ import annotations

import datetime
import json
from typing import Dict, Iterable, Tuple

import pytest

from src.llm_circuit_router.rebound import (
    CRITICAL_QUARANTINE_MINUTES,
    REPEATED_QUARANTINE_MINUTES,
    ReboundSession,
)
from src.llm_circuit_router.storage import load_json, save_json

REGISTRY_FILE_NAME = "registry.json"
LEDGER_FILE_NAME = "ledger.json"
FAR_FUTURE = "2999-01-01T00:00:00Z"


def _parse(value: str) -> datetime.datetime:
    """Parse one of our ``...Z`` timestamps into an aware datetime."""
    assert value.endswith("Z"), value
    return datetime.datetime.fromisoformat(value[:-1] + "+00:00")


def _registry_entry(
    score: float,
    *,
    task: str = "general",
    api_key: str = "sk-test",
    provider: str = "openrouter",
    quarantined_until=None,
) -> Dict:
    scores = {"general": 0.0, "coding": 0.0, "reasoning": 0.0, "vision": 0.0}
    scores[task] = score
    return {
        "provider": provider,
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": api_key,
        "context_length": 4096,
        "reliability": {"score": 1.0, "quarantined_until": quarantined_until},
        "benchmarks": dict(scores),
        "composite_routing_scores": dict(scores),
    }


def _ledger_record(*, success: int = 5, failure: int = 0, consecutive: int = 0) -> Dict:
    total = success + failure
    return {
        "success_count": success,
        "failure_count": failure,
        "consecutive_failures": consecutive,
        "reliability_score": round(success / total, 3) if total else 1.0,
        "quarantined_until": None,
        "last_tested": None,
    }


def _write(tmp_path, registry: Dict, slugs: Iterable[str] = ()) -> Tuple[str, str]:
    registry_path = tmp_path / REGISTRY_FILE_NAME
    registry_path.write_text(json.dumps(registry), encoding="utf-8")

    ledger_path = tmp_path / LEDGER_FILE_NAME
    save_json(
        ledger_path,
        {slug: _ledger_record() for slug in (slugs or registry)},
    )
    return str(registry_path), str(ledger_path)


def _session(tmp_path, slugs=("a", "b", "c"), *, task="general", **kwargs):
    registry = {
        slug: _registry_entry(100.0 - index, task=task, **kwargs)
        for index, slug in enumerate(slugs)
    }
    registry_path, ledger_path = _write(tmp_path, registry, slugs)
    session = ReboundSession(
        task_type=task,
        registry_filepath=registry_path,
        ledger_filepath=ledger_path,
    )
    return session, ledger_path


# ── ordering / session state ──────────────────────────────────────────────────


def test_session_starts_on_the_top_ranked_model(tmp_path):
    session, _ = _session(tmp_path)

    assert session.get_current_model_config()["model"] == "a"


def test_config_is_langchain_ready(tmp_path):
    session, _ = _session(tmp_path)

    config = session.get_current_model_config()

    assert set(config) == {"model", "api_key", "base_url"}
    assert config["base_url"] == "https://openrouter.ai/api/v1"


def test_raw_info_exposes_full_metadata(tmp_path):
    session, _ = _session(tmp_path)

    info = session.get_current_raw_info()

    assert info["provider"] == "openrouter"
    assert info["context_length"] == 4096
    assert info["composite_score"] == 100.0
    assert info["benchmark_base"] == 100.0


def test_task_type_controls_the_ranking(tmp_path):
    registry = {
        "generalist": _registry_entry(10.0, task="general"),
        "coder": _registry_entry(80.0, task="coding"),
    }
    registry_path, ledger_path = _write(tmp_path, registry)

    coding = ReboundSession(
        task_type="coding",
        registry_filepath=registry_path,
        ledger_filepath=ledger_path,
    )
    general = ReboundSession(
        task_type="general",
        registry_filepath=registry_path,
        ledger_filepath=ledger_path,
    )

    assert coding.get_current_model_config()["model"] == "coder"
    assert general.get_current_model_config()["model"] == "generalist"


# ── stepping through the stack ────────────────────────────────────────────────


def test_rebound_advances_one_step(tmp_path):
    session, _ = _session(tmp_path)

    assert session.rebound(RuntimeError("connection reset"))["model"] == "b"


def test_rebound_walks_the_whole_stack_in_order(tmp_path):
    session, _ = _session(tmp_path)

    visited = [session.get_current_model_config()["model"]]
    while (following := session.rebound(RuntimeError("boom"))) is not None:
        visited.append(following["model"])

    assert visited == ["a", "b", "c"]


def test_rebound_penalises_every_attempted_model(tmp_path):
    session, ledger_path = _session(tmp_path)

    while session.rebound(RuntimeError("boom")) is not None:
        pass

    ledger = load_json(ledger_path)
    assert all(ledger[slug]["failure_count"] == 1 for slug in ("a", "b", "c"))


def test_exhausting_the_stack_returns_none(tmp_path):
    session, _ = _session(tmp_path, slugs=("only",))

    assert session.rebound(RuntimeError("first")) is None
    assert session.rebound(RuntimeError("second")) is None
    assert session.get_current_model_config() is None
    assert session.get_current_raw_info() is None


def test_all_quarantined_models_yield_an_empty_stack(tmp_path):
    session, _ = _session(
        tmp_path, slugs=("a", "b"), quarantined_until=FAR_FUTURE
    )

    assert session.model_stack == []
    assert session.get_current_model_config() is None
    assert session.rebound(RuntimeError("boom")) is None


# ── ledger penalties ─────────────────────────────────────────────────────────


def test_rebound_records_the_failure(tmp_path):
    session, ledger_path = _session(tmp_path)

    session.rebound(RuntimeError("boom"))

    record = load_json(ledger_path)["a"]
    assert record["failure_count"] == 1
    assert record["consecutive_failures"] == 1
    assert record["reliability_score"] == round(5 / 6, 3)


def test_reliability_score_is_recomputed_from_counts(tmp_path):
    session, ledger_path = _session(tmp_path)
    ledger = load_json(ledger_path)
    ledger["a"].update(success_count=0, failure_count=3, consecutive_failures=0)
    save_json(ledger_path, ledger)

    session.rebound(RuntimeError("boom"))

    assert load_json(ledger_path)["a"]["reliability_score"] == 0.0


def test_each_model_is_penalised_independently(tmp_path):
    session, ledger_path = _session(tmp_path)

    session.rebound(RuntimeError("402 insufficient balance"))
    session.rebound(RuntimeError("502 bad gateway"))

    ledger = load_json(ledger_path)
    assert ledger["a"]["quarantined_until"] is not None
    assert ledger["b"]["quarantined_until"] is None
    assert ledger["b"]["failure_count"] == 1


def test_transient_failure_below_threshold_does_not_quarantine(tmp_path):
    session, ledger_path = _session(tmp_path)

    session.rebound(RuntimeError("connection reset by peer"))

    assert load_json(ledger_path)["a"]["quarantined_until"] is None


def test_three_consecutive_failures_trip_the_circuit(tmp_path):
    session, ledger_path = _session(tmp_path)
    ledger = load_json(ledger_path)
    ledger["a"]["consecutive_failures"] = 2
    ledger["a"]["failure_count"] = 2
    save_json(ledger_path, ledger)

    session.rebound(RuntimeError("transient timeout"))

    record = load_json(ledger_path)["a"]
    assert record["consecutive_failures"] == 3
    assert record["quarantined_until"] is not None


@pytest.mark.parametrize(
    "message",
    [
        "insufficient credits",
        "Insufficient Balance",
        "HTTP 402 Payment Required",
        "subscription expired",
        "CREDIT limit reached",
    ],
)
def test_critical_terms_match_case_insensitively(tmp_path, message):
    session, ledger_path = _session(tmp_path)

    session.rebound(RuntimeError(message))

    assert load_json(ledger_path)["a"]["quarantined_until"] is not None


# ── quarantine windows ───────────────────────────────────────────────────────


def test_credit_error_quarantines_for_about_an_hour(tmp_path):
    session, ledger_path = _session(tmp_path)
    before = datetime.datetime.now(datetime.timezone.utc)

    session.rebound(RuntimeError("402 insufficient balance"))

    expiry = _parse(load_json(ledger_path)["a"]["quarantined_until"])
    elapsed_minutes = (expiry - before).total_seconds() / 60
    assert CRITICAL_QUARANTINE_MINUTES - 1 <= elapsed_minutes <= CRITICAL_QUARANTINE_MINUTES + 1


def test_repeated_failure_quarantines_for_fifteen_minutes(tmp_path):
    session, ledger_path = _session(tmp_path)
    ledger = load_json(ledger_path)
    ledger["a"]["consecutive_failures"] = 2
    ledger["a"]["failure_count"] = 2
    save_json(ledger_path, ledger)
    before = datetime.datetime.now(datetime.timezone.utc)

    session.rebound(RuntimeError("transient timeout"))

    record = load_json(ledger_path)["a"]
    expiry = _parse(record["quarantined_until"])
    elapsed_minutes = (expiry - before).total_seconds() / 60
    assert REPEATED_QUARANTINE_MINUTES - 1 <= elapsed_minutes <= REPEATED_QUARANTINE_MINUTES + 1


# ── degraded / missing state ─────────────────────────────────────────────────


def test_missing_ledger_file_is_tolerated(tmp_path):
    registry = {
        "a": _registry_entry(50.0),
        "b": _registry_entry(40.0),
    }
    registry_path, _ = _write(tmp_path, registry)
    session = ReboundSession(
        task_type="general",
        registry_filepath=registry_path,
        ledger_filepath=str(tmp_path / "absent.json"),
    )

    assert session.rebound(RuntimeError("boom"))["model"] == "b"


def test_model_missing_from_ledger_is_skipped(tmp_path):
    registry = {"a": _registry_entry(50.0)}
    registry_path, ledger_path = _write(tmp_path, registry)
    save_json(ledger_path, {"someone-else": _ledger_record()})
    session = ReboundSession(
        task_type="general",
        registry_filepath=registry_path,
        ledger_filepath=ledger_path,
    )

    assert session.rebound(RuntimeError("boom")) is None
    assert "someone-else" in load_json(ledger_path)


def test_missing_registry_yields_an_empty_stack(tmp_path):
    session = ReboundSession(
        task_type="general",
        registry_filepath=str(tmp_path / "nope.json"),
        ledger_filepath=str(tmp_path / "ledger.json"),
    )

    assert session.model_stack == []
    assert session.rebound(RuntimeError("boom")) is None


def test_very_long_error_messages_are_truncated(tmp_path, capsys):
    session, _ = _session(tmp_path)

    session.rebound(RuntimeError("x" * 5000))

    out = capsys.readouterr().out
    assert "failed:" in out
    assert "x" * 70 not in out
