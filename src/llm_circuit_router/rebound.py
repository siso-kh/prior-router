"""Stateful failover session that penalises failing models and steps down the stack."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.llm_circuit_router.routing_engine import CircuitRouterSortingEngine
from src.llm_circuit_router.security import redact_secrets
from src.llm_circuit_router.storage import (
    FINAL_REGISTRY_FILE,
    LEDGER_FILE,
    load_json,
    save_json,
)
from src.llm_circuit_router.timeutils import utc_after_iso, utc_now_iso

# Errors that indicate a billing/account problem rather than a transient glitch.
CRITICAL_ERROR_TERMS: tuple[str, ...] = (
    "credit",
    "balance",
    "402",
    "insufficient",
    "subscription",
)
CRITICAL_QUARANTINE_MINUTES = 60
REPEATED_FAILURE_THRESHOLD = 3
REPEATED_QUARANTINE_MINUTES = 15

# Provider error messages are echoed (redacted) to the console, truncated here.
ERROR_PREVIEW_CHARS = 60


class ReboundSession:
    """Walks a ranked model stack, penalising each model that fails.

    On construction the session snapshots the current fallback order for a
    task. Each call to :meth:`rebound` records the failure in the reliability
    ledger and advances to the next candidate.
    """

    def __init__(
        self,
        task_type: Optional[str] = None,
        registry_filepath: str = FINAL_REGISTRY_FILE,
        ledger_filepath: str = LEDGER_FILE,
    ) -> None:
        self.registry_filepath = registry_filepath
        self.ledger_filepath = ledger_filepath
        self.task_type = task_type

        self.sorter = CircuitRouterSortingEngine(registry_filepath=registry_filepath)
        self.model_stack: List[Dict[str, Any]] = self.sorter.get_ranked_models_for_task(
            task_type=task_type
        )
        self.current_index = 0
        print(
            f"🎬 [Rebound Session] Spawned. Initialized {len(self.model_stack)} "
            "compatible fallback routes."
        )

    def get_current_model_config(self) -> Optional[Dict[str, Any]]:
        """Return the active model as a LangChain-ready config dict, or ``None``."""
        current = self.get_current_raw_info()
        if current is None:
            return None
        return {
            "model": current["model_name"],
            "api_key": current["api_key"],
            "base_url": current["base_url"],
        }

    def get_current_raw_info(self) -> Optional[Dict[str, Any]]:
        """Return the full metadata block of the active candidate, or ``None``."""
        if self.current_index >= len(self.model_stack):
            return None
        return self.model_stack[self.current_index]

    def rebound(self, exception_error: Exception) -> Optional[Dict[str, Any]]:
        """Penalise the active model, then return the next candidate's config.

        Returns ``None`` once the stack is exhausted.
        """
        active_model = self.get_current_raw_info()
        if active_model is None:
            print("❌ [Rebound] Reached the bottom of the list. No options left.")
            return None

        slug = active_model["model_name"]
        raw_error = str(exception_error)

        # Provider errors sometimes echo the credential back at us; the log line
        # is redacted (and the credential passed explicitly) before printing.
        safe_error = redact_secrets(raw_error, extra=[active_model.get("api_key")])
        print(
            f"⚠️ [Rebound] Model '{slug}' failed: "
            f"{safe_error[:ERROR_PREVIEW_CHARS]}..."
        )

        self._penalize_model_in_ledger(slug, raw_error)

        self.current_index += 1
        next_model = self.get_current_model_config()
        if next_model is not None:
            print(
                f"🔄 [Rebound] Falling back to rank #{self.current_index + 1}: "
                f"{next_model['model']}"
            )
        return next_model

    def _penalize_model_in_ledger(self, slug: str, error_msg: str) -> None:
        """Record a failure for ``slug`` and quarantine it when warranted."""
        ledger = load_json(self.ledger_filepath)
        if not ledger:
            return

        record = ledger.get(slug)
        if record is None:
            print(f"⚠️ [Ledger] No ledger record for '{slug}'; skipping penalty.")
            return

        record["failure_count"] += 1
        record["consecutive_failures"] += 1

        lowered = error_msg.lower()
        if any(term in lowered for term in CRITICAL_ERROR_TERMS):
            quarantine_minutes = CRITICAL_QUARANTINE_MINUTES
        elif record["consecutive_failures"] >= REPEATED_FAILURE_THRESHOLD:
            quarantine_minutes = REPEATED_QUARANTINE_MINUTES
        else:
            quarantine_minutes = 0

        if quarantine_minutes:
            record["quarantined_until"] = utc_after_iso(quarantine_minutes)

        total = record["success_count"] + record["failure_count"]
        record["reliability_score"] = round(record["success_count"] / total, 3)
        record["last_tested"] = utc_now_iso()

        save_json(self.ledger_filepath, ledger)
        print(f"📉 [Ledger Updated] Deducted reliability points for {slug}.")
