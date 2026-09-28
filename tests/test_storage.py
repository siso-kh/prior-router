"""Tests for :mod:`src.llm_circuit_router.storage`."""

from __future__ import annotations

from src.llm_circuit_router import storage


def test_save_then_load_round_trips(tmp_path):
    target = tmp_path / "nested" / "data.json"
    payload = {"a": 1, "nested": {"b": [1, 2, 3]}}

    storage.save_json(target, payload)

    assert storage.load_json(target) == payload


def test_save_creates_missing_parent_directories(tmp_path):
    target = tmp_path / "deep" / "deeper" / "data.json"

    storage.save_json(target, {"ok": True})

    assert target.exists()


def test_load_missing_file_returns_empty_dict(tmp_path):
    assert storage.load_json(tmp_path / "absent.json") == {}


def test_load_malformed_file_returns_default(tmp_path):
    target = tmp_path / "broken.json"
    target.write_text("{not valid json", encoding="utf-8")

    assert storage.load_json(target, default={"fallback": True}) == {"fallback": True}


def test_load_non_object_json_returns_default(tmp_path):
    target = tmp_path / "list.json"
    target.write_text("[1, 2, 3]", encoding="utf-8")

    assert storage.load_json(target) == {}


def test_save_writes_utf8_without_escaping(tmp_path):
    target = tmp_path / "unicode.json"

    storage.save_json(target, {"emoji": "🎬"})

    assert "🎬" in target.read_text(encoding="utf-8")
