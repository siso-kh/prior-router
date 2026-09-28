"""Security tests.

These measure whether the credentials the pipeline depends on can leak — via
version control, log output, error messages, or a rendered settings object.

Credential-shaped strings are built at runtime from fragments so that this
module never contains a literal that the tracked-file audit below would flag
against itself.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from src.llm_circuit_router.config import Settings
from src.llm_circuit_router.rebound import ReboundSession
from src.llm_circuit_router.security import REDACTED, find_secrets, redact_secrets
from src.llm_circuit_router.storage import (
    CAPABILITIES_FILE,
    FINAL_REGISTRY_FILE,
    LEDGER_FILE,
    PENDING_FILE,
    RAW_BENCHMARKS_FILE,
    save_json,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

GENERATED_ARTIFACTS = (
    PENDING_FILE,
    LEDGER_FILE,
    CAPABILITIES_FILE,
    RAW_BENCHMARKS_FILE,
    FINAL_REGISTRY_FILE,
)

requires_git = pytest.mark.skipif(
    shutil.which("git") is None, reason="git is not available"
)


def _credential(prefix: str = "sk-", length: int = 32) -> str:
    """Build a credential-shaped string at runtime, from fragments."""
    return prefix + ("A1b2" * length)[:length]


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True)


# ── redaction primitives ─────────────────────────────────────────────────────


def test_redact_masks_a_prefixed_credential():
    cred = _credential()

    redacted = redact_secrets(f"auth failed for {cred}")

    assert cred not in redacted
    assert REDACTED in redacted


def test_redact_masks_an_openrouter_style_credential():
    cred = _credential("sk-or-v1-")

    assert cred not in redact_secrets(f"401 for {cred}")


def test_redact_masks_bearer_tokens():
    token = _credential("", 32)

    assert token not in redact_secrets("Authorization: Bearer " + token)


def test_redact_keeps_the_field_name_but_masks_the_value():
    value = _credential("", 24)

    redacted = redact_secrets('{"api_key": "' + value + '"}')

    assert "api_key" in redacted
    assert value not in redacted


def test_redact_masks_an_explicitly_supplied_value_of_unknown_shape():
    cred = _credential("custom-")

    assert cred not in redact_secrets(f"boom {cred}", extra=[cred])


def test_redact_is_a_no_op_for_placeholders():
    assert redact_secrets("nothing sensitive", extra=[None, "", "***"]) == (
        "nothing sensitive"
    )


def test_find_secrets_detects_a_planted_credential():
    cred = _credential()

    assert cred in find_secrets(f"leaked: {cred}")


def test_find_secrets_is_quiet_on_ordinary_text():
    assert find_secrets("model xyz failed with a connection timeout") == []


# ── settings rendering ───────────────────────────────────────────────────────


def _settings_with(cred: str) -> Settings:
    return Settings(
        NARA_API_KEY=cred,
        NARA_BASE_URL="https://router.bynara.id/v1",
        OPENROUTER_API_KEY=cred,
        OPENROUTER_BASE_URL="https://openrouter.ai/api/v1",
        BENCHMARK_API_KEY=cred,
    )


def test_settings_repr_masks_secrets():
    cred = _credential()

    assert cred not in repr(_settings_with(cred))


def test_settings_str_masks_secrets():
    cred = _credential()

    assert cred not in str(_settings_with(cred))


def test_settings_interpolation_masks_secrets():
    cred = _credential()

    assert cred not in f"config={_settings_with(cred)}"


def test_settings_repr_keeps_non_secret_fields_for_debugging():
    rendered = repr(_settings_with(_credential()))

    assert "router.bynara.id" in rendered
    assert REDACTED in rendered


# ── rebound log output ───────────────────────────────────────────────────────


def _registry_and_ledger(tmp_path, cred: str):
    registry = {
        "m": {
            "provider": "openrouter",
            "base_url": "https://openrouter.ai/api/v1",
            "api_key": cred,
            "context_length": 1024,
            "reliability": {"score": 1.0, "quarantined_until": None},
            "benchmarks": {
                "general": 10.0,
                "coding": 0.0,
                "reasoning": 0.0,
                "vision": 0.0,
            },
            "composite_routing_scores": {
                "general": 10.0,
                "coding": 0.0,
                "reasoning": 0.0,
                "vision": 0.0,
            },
        }
    }
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps(registry), encoding="utf-8")

    ledger_path = tmp_path / "ledger.json"
    save_json(
        ledger_path,
        {
            "m": {
                "success_count": 1,
                "failure_count": 0,
                "consecutive_failures": 0,
                "reliability_score": 1.0,
                "quarantined_until": None,
                "last_tested": None,
            }
        },
    )
    return str(registry_path), str(ledger_path)


def test_rebound_logs_never_echo_provider_credentials(tmp_path, capsys):
    cred = _credential("sk-or-v1-")
    registry_path, ledger_path = _registry_and_ledger(tmp_path, cred)
    session = ReboundSession(
        task_type="general",
        registry_filepath=registry_path,
        ledger_filepath=ledger_path,
    )

    session.rebound(RuntimeError("401 invalid api key: " + cred))

    out = capsys.readouterr().out
    assert cred not in out
    assert REDACTED in out


def test_rebound_never_writes_credentials_into_the_ledger(tmp_path):
    cred = _credential("sk-or-v1-")
    registry_path, ledger_path = _registry_and_ledger(tmp_path, cred)
    session = ReboundSession(
        task_type="general",
        registry_filepath=registry_path,
        ledger_filepath=ledger_path,
    )

    session.rebound(RuntimeError("401 invalid api key: " + cred))

    assert cred not in Path(ledger_path).read_text(encoding="utf-8")


# ── version-control hygiene ──────────────────────────────────────────────────


@requires_git
def test_env_file_is_gitignored():
    assert _git("check-ignore", "-q", ".env").returncode == 0


@requires_git
@pytest.mark.parametrize("artifact", GENERATED_ARTIFACTS)
def test_generated_artifacts_are_gitignored(artifact):
    assert _git("check-ignore", "-q", artifact).returncode == 0


@requires_git
def test_env_file_is_not_tracked():
    assert ".env" not in _git("ls-files").stdout.splitlines()


@requires_git
def test_no_tracked_file_contains_a_credential():
    offenders = []
    for relative in _git("ls-files").stdout.splitlines():
        path = REPO_ROOT / relative
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if find_secrets(text):
            offenders.append(relative)

    assert offenders == []


# ── env template ─────────────────────────────────────────────────────────────


def test_env_example_is_not_gitignored():
    if shutil.which("git") is None:
        pytest.skip("git is not available")
    assert _git("check-ignore", "-q", ".env.example").returncode != 0


def test_env_example_ships_without_secret_values():
    lines = (REPO_ROOT / ".env.example").read_text(encoding="utf-8").splitlines()

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, separator, value = stripped.partition("=")
        assert separator == "=", stripped
        if "BASE_URL" in key.upper():
            continue
        assert value == "", f"{key} must not ship with a value"


def test_env_example_contains_no_credentials():
    text = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")

    assert find_secrets(text) == []
