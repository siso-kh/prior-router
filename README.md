# LLM Circuit Router

Route every request across a pool of **free** LLM endpoints — ranked by measured
quality and real-world reliability — with automatic circuit-breaker failover.

Instead of hardcoding a model, you ask the router for the best available model
for a task (`general`, `coding`, `reasoning`, or `vision`). It ranks every
discovered free model by a composite score, then walks down that ranking until
one succeeds. Models that misbehave are penalised and temporarily quarantined.

---

## How it works

The project is a pipeline. Each stage reads one JSON artifact and writes the
next, so any stage can be re-run independently.

```
                  ┌─────────────────────┐
                  │  run_discovery.py   │  OpenRouter + Bynara /models
                  └──────────┬──────────┘
                             │ free ($0) endpoints only
                             ▼
                        pending.json
                             │
        ┌────────────────────┴────────────────────┐
        ▼                                         ▼
┌───────────────────────┐              ┌─────────────────────────┐
│ fetch_raw_benchmarks  │  AA API →    │  run_health_check.py    │
│ compile_capabilities  │              │  live "ONLINE" probes   │
└──────────┬────────────┘              └────────────┬────────────┘
           │ model_capabilities.json                │ reliability_ledger.json
           └──────────────────┬─────────────────────┘
                              ▼
                ┌──────────────────────────────┐
                │  generate_final_registry.py  │  composite = quality × reliability
                └───────────────┬──────────────┘
                                ▼
                       final_model_registry.json
                                │
              ┌─────────────────┴──────────────────┐
              ▼                                    ▼
   CircuitRouterSortingEngine               ReboundSession
   ranked lineup per task                   failover at call time
```

### Core concepts

| Concept | Meaning |
| --- | --- |
| **Composite routing score** | `benchmark score × reliability score`, computed per task domain. Ranking is by this value. |
| **Reliability ledger** | A rolling success/failure record per model, persisted in `reliability_ledger.json`. |
| **Circuit breaker** | After 3 consecutive failures, a model is quarantined for 15 minutes and its composite score collapses to `0`. |
| **Rebound** | At call time, a failed model is penalised in the ledger and the session advances to the next candidate. |
| **Capability scoring** | Raw Artificial Analysis benchmarks are normalised to 0–100 scores for `general` / `coding` / `reasoning` / `vision`. |

---

## Project layout

```
src/llm_circuit_router/
├── config.py                    # env-backed settings (loaded lazily)
├── storage.py                   # shared JSON load/save + canonical artifact paths
├── console.py                   # UTF-8 console setup for the CLI scripts
├── discovery.py                 # per-provider "free model" discovery drivers
├── benchmarks_fetcher.py        # benchmark → 0-100 capability scoring
├── routing_engine.py            # CircuitRouterSortingEngine (ranked lineups)
├── rebound.py                   # ReboundSession (failover + ledger penalties)
├── run_discovery.py             # stage 1 — discover free models
├── fetch_raw_benchmarks.py      # stage 2a — download the raw benchmark snapshot
├── compile_capabilities.py      # stage 2b — compile the capability matrix
├── run_health_check.py          # stage 3 — probe liveness, update the ledger
├── generate_final_registry.py   # stage 4 — build the final routing registry
└── demo_*.py                    # runnable examples (sorting, failover, scoring)
tests/                           # pytest suite (no network, no live credentials)
```

---

## Setup

Requires **Python 3.10+**.

```bash
python -m venv venv
source venv/Scripts/activate      # Windows (Git Bash)
# source venv/bin/activate        # macOS / Linux

pip install -r requirements.txt
```

Create a `.env` from the template and fill in your keys:

```bash
cp .env.example .env
```

| Variable | Purpose |
| --- | --- |
| `OPENROUTER_API_KEY` / `OPENROUTER_BASE_URL` | OpenRouter discovery + inference |
| `NARA_API_KEY` / `NARA_BASE_URL` | Bynara / NaraRouter discovery + inference |
| `BENCHMARK_API_KEY` | Artificial Analysis benchmark snapshot |

---

## Usage

### Run the pipeline

Run each stage from the repository root. Every stage is a module entrypoint:

```bash
# 1. Discover free models across all configured providers → pending.json
python -m src.llm_circuit_router.run_discovery

# 2a. Download the raw benchmark snapshot → artificial_analysis_models.json
python -m src.llm_circuit_router.fetch_raw_benchmarks

# 2b. Compile it into capability scores → model_capabilities.json
python -m src.llm_circuit_router.compile_capabilities

# 3. Probe every candidate and update the ledger → reliability_ledger.json
python -m src.llm_circuit_router.run_health_check
# ...or re-check models already in the ledger:
python -m src.llm_circuit_router.run_health_check --sweep

# 4. Build the final routing registry → final_model_registry.json
python -m src.llm_circuit_router.generate_final_registry
```

### Use the router as a library

**Rank models for a task:**

```python
from src.llm_circuit_router import CircuitRouterSortingEngine

engine = CircuitRouterSortingEngine()          # reads final_model_registry.json
for model in engine.get_ranked_models_for_task("coding"):
    print(model["model_name"], model["composite_score"])
```

**Fail over automatically at call time:**

```python
from src.llm_circuit_router import ReboundSession

session = ReboundSession(task_type="reasoning")
while (config := session.get_current_model_config()) is not None:
    try:
        call_model(config)                     # your provider call
        break
    except Exception as error:
        session.rebound(error)                 # penalise + step down
```

### Runnable demos

```bash
python -m src.llm_circuit_router.demo_sorting             # print ranked lineups
python -m src.llm_circuit_router.demo_capabilities_scoring  # score a mock model
python -m src.llm_circuit_router.demo_rebound_chatbot     # self-healing chatbot loop
```

---

## Generated artifacts

All of these are gitignored — they are rebuilt by the pipeline and may embed
provider API keys.

| File | Written by | Contents |
| --- | --- | --- |
| `pending.json` | `run_discovery` | Discovered free models awaiting testing |
| `artificial_analysis_models.json` | `fetch_raw_benchmarks` | Raw benchmark snapshot |
| `model_capabilities.json` | `compile_capabilities` | Per-model 0–100 capability scores |
| `reliability_ledger.json` | `run_health_check`, `rebound` | Success/failure history + quarantine state |
| `final_model_registry.json` | `generate_final_registry` | The merged registry the router reads |

---

## Development

```bash
pip install -e ".[dev]"
pytest
```

The test suite makes **no network calls** and needs **no live credentials** —
HTTP and LLM interactions are exercised through fakes, and the settings object
is constructed explicitly per test.

| Test module | Covers |
| --- | --- |
| `test_rebound.py` | Failover scenarios: ordering, mid-stack hops, per-model penalties, quarantine windows, exhausted/degraded state |
| `test_security.py` | Credential leak audit (see below) |
| `test_routing_engine.py` | Ranking, task defaults, quarantine and vision filtering |
| `test_benchmarks_fetcher.py` | Benchmark normalisation and capability classification |
| `test_discovery.py` | Provider drivers against a fake HTTP client |
| `test_storage.py` / `test_timeutils.py` / `test_package.py` | Persistence, timestamps, public API |

### Credential leak audit

`tests/test_security.py` measures whether the credentials in `.env` can escape,
by checking that:

- `.env` and every generated `*.json` artifact are gitignored, and `.env` is not tracked.
- No tracked file contains a credential-shaped string
  (`find_secrets` scans `git ls-files`).
- `repr()`/`str()` of `Settings` mask secret fields.
- `ReboundSession` redacts credentials before logging provider errors, even when a
  provider echoes the key back inside its error message.
- `.env.example` ships with no values.

---

## Security notes

- `.env` and every `*.json` artifact are gitignored. The compiled artifacts
  store credentials alongside model metadata, so treat them as secrets.
- If you have previously committed any of those files, rotate the affected
  provider keys.
- Settings mask secret fields in `repr()`/`str()`, so a stray `print(settings)`
  or a traceback will not expose a key.
- Model API keys are redacted from failover logs via
  `security.redact_secrets`, which masks known credential prefixes plus the
  active model's own key.
