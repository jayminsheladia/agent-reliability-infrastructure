# ARI — Architecture

This is the "read before an interview" doc — the design decisions
behind each piece, one level deeper than the README's map of "where
does X live."

## 1. The event log — `emit_event()`

Everything in ARI reads from one table, `event_log` (`app/models/event.py`).
One row per agent step:

```python
def emit_event(
    *,
    run_id: uuid.UUID,
    agent_id: str,
    step_index: int,
    input_state: dict,
    output_state: dict,
    tool_calls: list[dict],
    tokens_used: int,
    latency_ms: int,
    parent_step_id: uuid.UUID | None,
    event_type: str = "step",
) -> uuid.UUID:
```

Design choices that matter:

- **Opens its own DB session and commits immediately.** A step's trace
  is durable the moment it completes, independent of whatever the
  caller does next — if the process crashes on the following line, the
  event you just wrote is already safe in Postgres.
- **`input_state` / `output_state` are JSONB, not plain strings**, with
  a `{"text": "..."}` convention (see `app/state_text.py::extract_text`,
  shared by embedding, trace display, and retrieval so all three agree
  on "what does this state mean as text"). JSONB leaves room for
  structured fields (`context_used`, detector `details`) without a
  schema change.
- **`parent_step_id` chains events**, but ordering in the trace viewer
  is by `(step_index, timestamp)`, not the parent chain — `step_index`
  is the simple, always-correct ordering for this project's strictly
  sequential pipeline; the parent chain exists for causal linkage
  (e.g. "which step did this anomaly marker attach to") more than
  ordering.
- **`event_type` defaults to `"step"`**; detector markers
  (`"loop_detected"`, `"cost_anomaly"`) are the only other values.
  Markers **reuse their triggering step's own `step_index`** rather
  than claiming a new one — this avoids index collisions with whatever
  step runs next (this matters for cost anomalies specifically, since
  flag-only means the run keeps going and would otherwise clash with
  the marker's borrowed index). The `(step_index, timestamp)` ordering
  is what makes a marker reliably sort right after the step that
  caused it.
- **On write, `output_state` is embedded** (`app/embeddings.py`) and
  stored in a pgvector column — this is what makes retrieval (§3)
  possible without a separate batch/backfill step.

## 2. Human-approval gates

**Policy config** (`policies/example.yaml`, loaded by `app/policy.py`):

```yaml
rules:
  - tool_name: send_email
    condition: null
    requires_approval: true

  - tool_name: execute_action
    condition: "amount > 100"
    requires_approval: true
```

`evaluate_policy(tool_name, arguments)` checks rules in order; the
first rule matching `tool_name` whose `condition` (if any) evaluates
true against `arguments` wins. **No matching rule → no approval
required** — this is a fail-open, allowlist-of-restrictions design,
not a default-deny gate (explicit tradeoff, confirmed during Day 4:
simpler for a demo, but a production version handling arbitrary new
tools might want fail-closed instead).

Conditions are evaluated with `eval(condition, {"__builtins__": {}}, arguments)`.
This is safe *only* because conditions come from this project's own
trusted YAML file, never from external/attacker input — `arguments`
(the tool call's own arguments) is the only untrusted-ish data, and it
only ever appears as `eval`'s locals dict, not as code. This was a
deliberate choice over hand-rolling a comparison-expression parser for
a "keep it simple" MVP; it would need to change before conditions
could ever come from a source you don't fully trust.

**Approval queue** (`app/approvals/queue.py`, Redis): a `PendingApproval`
record (`id`, `run_id`, `step_index`, `agent_id`, `tool_name`,
`arguments`, `status`, `created_at`) stored as a JSON string at
`approval:{id}`, with a Redis set (`approvals:pending`) tracking which
are still open.

**Pause/resume** (`app/approvals/gate.py::propose_and_run_tool_call`):
when a call requires approval, the agent loop process itself blocks —
`wait_for_resolution()` polls Redis every 1s (configurable,
`POLL_INTERVAL_SECONDS`) for up to 300s (`APPROVAL_TIMEOUT_SECONDS`)
until the status flips from `"pending"`. The FastAPI process's
`/approvals/{id}/approve` endpoint is what flips it — coordination is
entirely through Redis, no message broker or task queue.

**Why blocking/poll instead of a worker queue:** the agent loop process
*is* the worker. Redis is already the shared state between it and the
API process, so there's no separate coordination layer to build.
**Tradeoff:** this ties up one OS process per in-flight run for as long
as it's paused, and a dead process means a stuck run — a production
system with many concurrent gated runs surviving process restarts
would swap this for a durable task queue. That's a rewrite of the
*executor*, not the approval data model above, so this schema doesn't
paint anyone into a corner.

## 3. Curated retrieval (`app/retrieval.py`)

`get_relevant_context(db, run_id, requesting_agent_id, requesting_step_index, query_or_need, k)`
returns the top-k prior events in this run most relevant to what the
requesting agent needs, scored as:

```
score = cosine_similarity(query_embedding, event_embedding) * exp(-decay_rate * steps_ago)
```

- `decay_rate` defaults to 0.15 — chosen so a step 5 turns ago is
  discounted to roughly half its raw similarity score
  (`exp(-0.15 * 5) ≈ 0.47`), old enough to matter but not enough to
  swamp a strong similarity match.
- Only looks backward (`step_index < requesting_step_index`) and only
  at `event_type = "step"` rows — anomaly markers aren't prior agent
  output and were explicitly excluded after Day 6 testing showed them
  leaking into a step's `context_used` (they share their triggering
  step's `step_index`, so without the `event_type` filter they'd be
  eligible candidates).
- **"What an agent needs" is a free-text string**, not a taxonomy —
  each `LLM_STEPS` entry in `agent_loop.py` declares a `need` like
  `"the draft content and any research findings related to it"`. This
  is deliberately the simplest thing that works: it gets embedded and
  compared the same way step outputs are, no separate schema for
  "kinds of need."
- Embeddings use a local `sentence-transformers` model
  (`all-MiniLM-L6-v2`, 384 dims) rather than a paid API — Anthropic
  doesn't serve embeddings, and a demo-scale retrieval problem (a
  handful of candidates per run) doesn't need a stronger model. This
  also means embedding has zero marginal cost and no extra API key.

## 4. Anomaly detection (`app/anomaly/`)

Two independent, separately-testable modules, both invoked inline
after every `emit_event()` call in `agent_loop.py` — not an offline
batch job, so a runaway run is caught *while it's still running*.

### Loop detection (`loop_detector.py`)

Tracks `(agent_id, tool_name, args_hash)` triples. `args_hash` is
`sha256(json.dumps(arguments, sort_keys=True))` — stable regardless of
dict key order. `check_for_loop()` re-derives the occurrence count from
`event_log` on every call (no separate counter store), by scanning that
run's step events for tool calls matching the same triple. Past
`threshold` (default 3, i.e. the 4th occurrence trips it), the run is
**killed**: a marker is written and `RunKilledError` propagates up to
`run_pipeline()`, which catches it once and returns — no further steps
run.

*Known limitation, not hit by any tool in this project:* if a tool's
arguments ever embedded a non-deterministic value (a timestamp, a
request ID), every "repeat" would hash differently and silently defeat
this. Worth a mitigation (e.g. an argument-normalization step before
hashing) before a tool like that is ever added.

### Cost-anomaly detection (`cost_detector.py`)

Two independent triggers, both **flag-only** (never kill — an
expensive run can still be legitimate, so halting it unilaterally is a
human's call, not the system's):

- **Hard threshold**: cumulative `tokens_used` across the run's `"step"`
  events exceeds a fixed configurable limit (`COST_HARD_THRESHOLD_TOKENS`,
  default 5000).
- **Per-agent z-score**: `check_agent_zscore()` compares the current
  step's `tokens_used` against that *specific agent's* historical
  average, using **all past runs** (not a rolling window — simplest
  option, and at this project's scale there's no meaningful difference
  from "last N runs"). Excludes the current run (comparing a value
  against a baseline that includes itself is meaningless) and marker
  rows (`tokens_used=0`, which would corrupt the baseline). Requires
  at least 3 historical samples before activating at all — with fewer,
  there's no meaningful baseline, so only the hard threshold still
  applies. Sample standard deviation (`statistics.stdev`, not
  population), guarded against division by zero when a history has no
  variance.

Both write a marker (`event_type="cost_anomaly"`) via the same
`app/anomaly/markers.py::write_anomaly_marker` helper the loop detector
uses — shared *plumbing* ("how do we record that a detector fired"),
not shared *detection logic*, so each detector stays independently
readable and testable.

## Capturing screenshots

For the README's screenshot section — run these against a live server:

```bash
docker compose up -d
source .venv/bin/activate
uvicorn app.main:app --reload &
```

1. **Trace viewer, full run**: `python -m app.cli demo success --mock`,
   approve both pending actions via the UI (step 2 below) as they come
   up, then open `http://localhost:8000/trace/<run_id>` and screenshot
   the full table (shows `context_used` links and both approved tool
   calls).
2. **Approval UI, pending action**: while `demo success` is running and
   paused (its terminal prints `... requires approval -> pending`),
   open `http://localhost:8000/approvals/ui` *before* clicking approve
   — screenshot the pending row with its Approve/Reject buttons.
3. **Loop-killed run**: `python -m app.cli demo loop --mock`, then open
   the trace viewer for the printed `run_id` — screenshot the row with
   the red `LOOP_DETECTED` flag.
