"""UTC timestamp helpers shared across the pipeline.

Timestamps are always rendered as ``YYYY-MM-DDTHH:MM:SSZ`` — a single, explicit
UTC offset marker that ``datetime.fromisoformat`` can round-trip once the ``Z``
is normalised to ``+00:00``.
"""

from __future__ import annotations

import datetime


def utc_now_iso() -> str:
    """Return the current UTC time in ISO-8601 form."""
    return _format(datetime.datetime.now(datetime.timezone.utc))


def utc_after_iso(minutes: float) -> str:
    """Return the UTC timestamp ``minutes`` minutes from now."""
    moment = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        minutes=minutes
    )
    return _format(moment)


def _format(moment: datetime.datetime) -> str:
    return moment.isoformat(timespec="seconds").replace("+00:00", "Z")
