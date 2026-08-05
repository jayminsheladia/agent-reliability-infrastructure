# Agent Reliability Infrastructure (ARI)

Observability and control-plane layer for multi-agent LLM systems.
Agent frameworks handle orchestration logic — deciding what an agent
does next. ARI handles what happens when that orchestration runs in
production: agents lose context on hand-off, call tools with bad
arguments, loop indefinitely, take unsafe actions with no human check,
and burn budget with no visibility into why.

ARI sits between the orchestrator and the underlying model calls and
addresses four problems:

1. **Curated state hand-off** — agents receive relevant prior state via
   structured + vector retrieval instead of a full-transcript dump.
2. **Human-approval gates** — a config-driven policy engine flags risky
   tool calls and pauses the agent loop pending human approval.
3. **Trace/replay debugging** — every step is written to a structured
   event log, viewable via CLI and a web UI.
4. **Loop and cost-anomaly detection** — repeated tool calls and
   abnormal token spend are flagged automatically.

## Architecture

```
 Multi-agent orchestrator
        │
        ▼
 ┌────────────────────────────────────────┐
 │              ARI control plane          │
 │                                          │
 │  event log ──▶ trace/replay viewer       │
 │  policy engine ──▶ approval queue (Redis)│
 │  state store (Postgres + pgvector)       │
 │    └─▶ curated hand-off retrieval        │
 │  loop / cost anomaly detectors           │
 └────────────────────────────────────────┘
        │
        ▼
      LLM calls
```

## Stack

- Python 3.12, FastAPI
- Postgres (pgvector) — structured event log + state store
- Redis — approval queue
- SQLAlchemy + Alembic
- Plain HTML/HTMX — trace viewer and approval UI
- Docker Compose — local Postgres/Redis

## Status

Day 1: scaffold + core schemas (event log, state store) and policy
config loading. No agent loop or API endpoints beyond `/health` yet —
that starts Day 2.

## Setup

```bash
cp .env.example .env
docker compose up -d
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```
