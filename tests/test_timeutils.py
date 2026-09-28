"""Tests for :mod:`src.llm_circuit_router.timeutils`."""

from __future__ import annotations

import datetime

from src.llm_circuit_router.timeutils import utc_after_iso, utc_now_iso


def _parse(value: str) -> datetime.datetime:
    """Round-trip one of our ``...Z`` timestamps."""
    assert value.endswith("Z"), value
    return datetime.datetime.fromisoformat(value[:-1] + "+00:00")


def test_utc_now_iso_is_parseable():
    assert _parse(utc_now_iso()).tzinfo is not None


def test_timestamps_carry_a_single_offset_marker():
    stamp = utc_now_iso()

    assert stamp.endswith("Z")
    assert "+00:00" not in stamp


def test_utc_after_iso_returns_the_requested_offset():
    before = datetime.datetime.now(datetime.timezone.utc)

    elapsed_minutes = (_parse(utc_after_iso(15)) - before).total_seconds() / 60

    assert 14 <= elapsed_minutes <= 15.1


def test_utc_after_iso_accepts_fractional_minutes():
    before = datetime.datetime.now(datetime.timezone.utc)

    elapsed_seconds = (_parse(utc_after_iso(0.5)) - before).total_seconds()

    assert 25 <= elapsed_seconds <= 35
