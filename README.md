# Self-Healing Enterprise Agent

An enterprise-grade boilerplate for a **self-correcting (self-healing) AI agent**.
The agent generates tool-call JSON payloads, validates them with strict Pydantic v2
guardrails, and — on failure — feeds the exact validation errors back to the LLM
in an in-flight reflection loop (up to `MAX_SELF_HEALING_RETRIES`), auto-correcting
its payload instead of crashing with a 500 error.

It also ships a **two-layer guardrail system** (syntactic Pydantic validation +
factual/semantic validation via an MCP-style tool server) and a **pluggable cloud
adapter** so the same core can target MOCK, AWS, OCI, GCP or Azure backends.

## Table of contents

- [Features](#features)
- [Architecture](#architecture)
- [How it works](#how-it-works)
- [Project structure](#project-structure)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [API reference](#api-reference)
- [Mock mode](#mock-mode)
- [Guardrails](#guardrails)
- [Extending the boilerplate](#extending-the-boilerplate)
- [Testing](#testing)
- [Docker](#docker)
- [Troubleshooting](#troubleshooting)

## Features

- **Self-healing loop** — Try → Validate → Catch → Reflect → Retry, with the exact
  Pydantic error messages injected back into the conversation.
- **Strict Pydantic v2 guardrails** — `extra="forbid"`, field/model validators,
  regex patterns, cross-field consistency checks.
- **Layered validation** — syntactic (Pydantic) + factual/semantic (MCP validators).
- **Universal LLM client** — OpenAI-compatible API with built-in **Mock mode**
  (zero API key required) for demos and tests.
- **Pluggable cloud adapters** — Mock included; commented templates for AWS, OCI,
  GCP and Azure.
- **MCP integration** — in-memory server for zero-setup, plus an optional
  SDK-backed client (`mcp` package) for real MCP servers over stdio.
- **FastAPI + OpenAPI** — auto-generated docs at `/docs`.
- **Structured JSON logging**.
- **Docker & docker-compose** ready.
- **Pytest suite** covering the healing loop and guardrails.

## Architecture

```mermaid
graph TD
    U[User] --> F[FastAPI /api/v1/agent/execute]
    F --> E[SelfHealingAgentEngine]
    E --> L[LLM Client (Mock / OpenAI / LiteLLM)]
    L --> E
    E --> P[Pydantic v2 Guardrail]
    P -->|Valid| G[ValidatorPipeline (MCP/factual)]
    G -->|Valid| A[Cloud Adapter]
    P -->|ValidationError| R[Reflection Prompt]
    G -->|FactualValidationError| R
    R --> L
    A --> R2[Execution Result]
    R2 --> F
```

## How it works

1. The engine builds a system + user prompt containing the goal, tool name and the
   target Pydantic schema.
2. The LLM returns a raw JSON string.
3. The payload is parsed and validated against the Pydantic schema (Layer 1).
4. On success, the `ValidatorPipeline` runs Layer-2 factual validators (e.g. vendor
   existence via MCP).
5. If any validation fails, the errors are formatted (`field 'x': msg (received: ...)`) 
   and appended to the conversation as a correction prompt.
6. The LLM is asked again; up to `MAX_SELF_HEALING_RETRIES` retries are allowed.
7. Once valid, the payload is dispatched to the cloud adapter, which runs the
   business logic (`app/tools/enterprise_tools.py`) and returns an execution result.

## Project structure

```
.
├── app/
│   ├── adapters/
│   │   ├── base.py                 # BaseCloudAdapter contract
│   │   └── cloud_adapter.py        # Mock + AWS/OCI/GCP/AZURE templates
│   ├── core/
│   │   ├── llm_client.py           # Universal LLM wrapper (Mock mode)
│   │   └── self_healing_engine.py  # Try → Validate → Catch → Reflect → Retry
│   ├── guardrails/
│   │   ├── base_validator.py       # BaseValidator plugin interface
│   │   ├── default_validators.py   # Default MCP server + pipelines
│   │   ├── exceptions.py           # FactualValidationError
│   │   ├── mcp_client.py           # InMemory + SDK MCP clients
│   │   ├── mcp_validator.py        # MCP-backed factual validator
│   │   └── pipeline.py             # ValidatorPipeline
│   ├── schemas/
│   │   ├── agent_response.py       # API response wrappers
│   │   └── enterprise_payloads.py  # Pydantic v2 guardrails
│   ├── tools/
│   │   └── enterprise_tools.py     # Business logic dispatched after validation
│   ├── config.py                   # Central settings (env-driven)
│   └── main.py                     # FastAPI entrypoint
├── tests/
│   ├── test_guardrails.py
│   └── test_self_healing.py
├── .env.example
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Quick start

### Local (Python)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

Open http://localhost:8000/docs

### Docker

```bash
docker compose up --build
```

The service listens on http://localhost:8000.

## Configuration

Settings are loaded from environment variables / `.env` (see `.env.example`).

| Variable | Default | Description |
|---|---|---|
| `CLOUD_PROVIDER` | `MOCK` | Cloud backend: `MOCK`, `AWS`, `OCI`, `GCP`, `AZURE` |
| `MAX_SELF_HEALING_RETRIES` | `3` | Self-healing retry budget (0–10) |
| `LLM_MODEL_NAME` | `gpt-4o-mini` | Model name for the remote LLM |
| `LLM_API_KEY` | `mock` | API key; `mock`/empty enables Mock mode |
| `LLM_BASE_URL` | (unset) | Optional base URL (LiteLLM / custom endpoints) |
| `LLM_TEMPERATURE` | `0.0` | Sampling temperature (0.0–2.0) |

Edit `app/config.py` for structural changes (defaults, validation ranges).

## API reference

### `GET /health`

Returns service health and active backend info.

```json
{
  "status": "ok",
  "cloud_provider": "MOCK",
  "llm_mode": "mock"
}
```

### `POST /api/v1/agent/execute`

Executes an enterprise tool through the self-healing agent.

**Request body**

```json
{
  "user_goal": "Create a purchase order for 2 units",
  "tool_name": "create_purchase_order"
}
```

- `user_goal` (string, required, min length 3) — natural language instruction.
- `tool_name` (string, default `create_purchase_order`) — target tool. Available:
  `create_purchase_order`, `update_inventory`.

**Response body** (`AgentExecutionResponse`)

```json
{
  "success": true,
  "tool_name": "create_purchase_order",
  "attempts": 2,
  "max_retries": 3,
  "correction_history": [
    {
      "attempt_number": 1,
      "raw_payload": { "vendor_code": "VEN-12", "...": "..." },
      "validation_errors": [
        { "loc": ["vendor_code"], "msg": "vendor_code must match pattern VEN-XXXX (e.g. VEN-1234)", "type": "value_error", "input": "VEN-12" }
      ],
      "succeeded": false
    },
    { "attempt_number": 2, "raw_payload": { "...": "..." }, "validation_errors": null, "succeeded": true }
  ],
  "final_payload": { "order_id": "...", "amount": 100.0, "currency": "USD", "vendor_code": "VEN-1234", "items": [ { "sku": "ABC-123", "quantity": 2, "unit_price": 50.0 } ], "priority": "high", "requested_by": "procurement-bot" },
  "execution_result": { "status": "success", "provider": "MOCK", "record_id": "...", "message": "Purchase order ... dispatched to mock ERP", "stored_count": 1, "business_result": { "erp_reference": "ERP-PO-...", "status": "dispatched" } },
  "error": null,
  "completed_at": "2026-01-01T00:00:00"
}
```

Interactive docs: http://localhost:8000/docs (Swagger) and `/redoc`.

## Mock mode (zero setup)

With `LLM_API_KEY=mock` (default) the built-in Mock LLM deliberately returns an
invalid payload on attempt 1 (bad `vendor_code`: `VEN-12`) and a corrected one on
attempt 2 (`VEN-1234`), demonstrating the full self-healing loop without any API key.

To use a real LLM, set `LLM_API_KEY` (and optionally `LLM_BASE_URL`) to an
OpenAI-compatible endpoint. The client sends `response_format: { type: json_object }`.

## Guardrails

Two layers protect the system before any cloud call:

### Layer 1 — Pydantic v2 (syntactic)

Defined in `app/schemas/enterprise_payloads.py`. `CreatePurchaseOrderSchema` and
`UpdateInventorySchema` use `extra="forbid"`, typed fields, regex validators,
range checks and a model-level consistency check (amount == sum of items).

### Layer 2 — Factual / semantic (MCP validators)

`app/guardrails` provides a plugin system:

- `BaseValidator` — async interface; raise `FactualValidationError` on failure.
- `ValidatorPipeline` — registry for field-scoped and global validators; collects
  all errors before raising.
- `MCPValidator` — delegates fact-checking to an MCP tool server.
- `MCPClient` — transport-agnostic interface with two implementations:
  - `InMemoryMCPClient` / `InMemoryMCPServer` — zero-setup (used by default).
  - `SDKMCPClient` — backed by the official `mcp` package (stdio transport).

Default pipelines (see `app/guardrails/default_validators.py`):

- `create_purchase_order` → validates `vendor_code` via `validate_vendor` MCP tool.
- `update_inventory` → validates `warehouse_id` via `validate_warehouse` MCP tool.

## Extending the boilerplate

### Add a new tool / schema

1. Add a Pydantic model in `app/schemas/enterprise_payloads.py`.
2. Register it in `TOOL_SCHEMAS`.
3. Add business logic in `app/tools/enterprise_tools.py` and register in
   `TOOL_DISPATCHERS`.
4. (Optional) Register factual validators in `get_default_pipeline`.

### Add a cloud adapter

1. Implement `BaseCloudAdapter` in `app/adapters/cloud_adapter.py` (see the
   commented AWS/OCI templates).
2. Wire it in `get_cloud_adapter()` for your `CLOUD_PROVIDER` value.
3. Set `CLOUD_PROVIDER` in `.env`.

### Add a factual validator

Implement `BaseValidator` and register it on a `ValidatorPipeline`, or add a new
MCP tool to the in-memory server in `default_validators.py`. For a real backend,
swap the client for `SDKMCPClient(command=..., args=[...])`.

### Use a real MCP server

```python
from app.guardrails.mcp_client import SDKMCPClient
client = SDKMCPClient(command="npx", args=["-y", "@modelcontextprotocol/server-..."])
```

Requires the optional `mcp` package (uncomment in `requirements.txt`).

## Testing

```bash
pytest -q
```

The suite covers:

- Self-healing succeeds on the 2nd attempt and records validation errors.
- No HTTP 500 on initial failure; graceful handling.
- `max_retries=0` fails gracefully.
- Final payload validates against the schema.
- Guardrail pipeline raises on invalid values and passes on valid ones.
- MCP validator uses the provided client.
- Default vendor validation pipeline.

## Docker

```bash
# Build and run
docker compose up --build

# Or manually
docker build -t self-healing-agent .
docker run -p 8000:8000 --env-file .env self-healing-agent
```

## Troubleshooting

- **`NotImplementedError: AWS/OCI/GCP/AZURE adapter not implemented`** — implement
  the adapter template in `app/adapters/cloud_adapter.py` and wire it in
  `get_cloud_adapter()`.
- **`RuntimeError: openai package is required`** — install `openai` (already in
  `requirements.txt`) or use Mock mode (`LLM_API_KEY=mock`).
- **`RuntimeError: mcp package is required`** — uncomment `mcp` in
  `requirements.txt` and reinstall, or use the in-memory client.
- **`KeyError: Unknown tool schema`** — the `tool_name` is not registered in
  `TOOL_SCHEMAS`; add the schema and restart.
- **Validation keeps failing / retries exhausted** — inspect `correction_history`
  in the response for the exact field errors; tune the prompt or schema.
- **Port 8000 in use** — change the port in the uvicorn command / compose file.

## License

No license file is included in this repository. Add one (e.g. MIT, Apache-2.0)
before distributing.
