"""Tests for :mod:`src.llm_circuit_router.benchmarks_fetcher`."""

from __future__ import annotations

import asyncio
import json

from src.llm_circuit_router.benchmarks_fetcher import LiveBenchmarkFetcher


def test_normalize_score_scales_fractions_to_percentages():
    fetcher = LiveBenchmarkFetcher()

    assert fetcher._normalize_score(0.614) == 61.4
    assert fetcher._normalize_score(57.6) == 57.6
    assert fetcher._normalize_score(1.0) == 100.0


def test_normalize_score_handles_unusable_values():
    fetcher = LiveBenchmarkFetcher()

    assert fetcher._normalize_score(None) == 0.0
    assert fetcher._normalize_score("not-a-number") == 0.0
    assert fetcher._normalize_score(0.0) == 0.0


def test_normalize_score_applies_multiplier_and_caps_at_100():
    fetcher = LiveBenchmarkFetcher()

    assert fetcher._normalize_score(30.0, multiplier=2.0) == 60.0
    assert fetcher._normalize_score(80.0, multiplier=2.0) == 100.0


def test_classify_prefers_livecodebench_for_coding():
    fetcher = LiveBenchmarkFetcher()
    scores = fetcher._classify_single_model(
        {
            "slug": "claude-opus-5-5",
            "name": "Claude Opus 5.5",
            "evaluations": {
                "artificial_analysis_intelligence_index": 57.6,
                "livecodebench": 0.55,
                "hle": 0.614,
            },
        }
    )

    assert scores["general"] == 57.6
    assert scores["coding"] == 55.0
    assert scores["reasoning"] == 61.4
    assert scores["vision"] == 0.0


def test_classify_falls_back_to_the_intelligence_proxy():
    fetcher = LiveBenchmarkFetcher()
    scores = fetcher._classify_single_model(
        {"slug": "plain-model", "name": "Plain Model", "evaluations": {}}
    )

    assert scores["general"] == 60.0
    assert scores["coding"] == 57.0
    assert scores["reasoning"] == 57.0


def test_classify_infers_vision_from_the_identifier():
    fetcher = LiveBenchmarkFetcher()
    scores = fetcher._classify_single_model(
        {
            "slug": "vendor/vision-model",
            "name": "Vision Model",
            "evaluations": {"artificial_analysis_intelligence_index": 60.0},
        }
    )

    assert scores["vision"] == 75.0


def test_fetch_live_matrix_reads_a_local_snapshot(tmp_path):
    snapshot = tmp_path / "raw.json"
    snapshot.write_text(
        json.dumps(
            {
                "data": [
                    {
                        "slug": "claude-opus-5-5",
                        "name": "Claude Opus 5.5",
                        "evaluations": {"artificial_analysis_intelligence_index": 57.6},
                        "pricing": {"price_1m_input_tokens": 4},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    matrix = asyncio.run(LiveBenchmarkFetcher().fetch_live_matrix(str(snapshot)))

    assert set(matrix) == {"claude-opus-5-5"}
    assert matrix["claude-opus-5-5"]["name"] == "Claude Opus 5.5"
    assert matrix["claude-opus-5-5"]["scores"]["general"] == 57.6


def test_fetch_live_matrix_tolerates_a_missing_file():
    matrix = asyncio.run(LiveBenchmarkFetcher().fetch_live_matrix("does-not-exist.json"))

    assert matrix == {}
