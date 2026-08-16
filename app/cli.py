import argparse
import sys
import uuid

from app.agent_loop import run_pipeline
from app.db import SessionLocal
from app.trace.service import get_trace

DEFAULT_TOPIC = "the benefits of local-first software"


def cmd_trace(run_id_str: str) -> int:
    try:
        run_id = uuid.UUID(run_id_str)
    except ValueError:
        print(f"Invalid run_id: {run_id_str!r} is not a valid UUID", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        steps = get_trace(db, run_id)
    finally:
        db.close()

    if not steps:
        print(f"No events found for run_id {run_id}")
        return 1

    print(f"Trace for run {run_id} ({len(steps)} step{'s' if len(steps) != 1 else ''})\n")
    for step in steps:
        flag = f"  !!! {step.event_type.upper()} !!!" if step.event_type != "step" else ""
        print(
            f"[{step.step_index}] {step.agent_id}"
            f"  ({step.tokens_used} tokens, {step.latency_ms}ms, {step.timestamp}){flag}"
        )
        print(f"    in:  {step.input_preview}")
        print(f"    out: {step.output_preview}")
        if step.context_used:
            print(f"    context_used: {step.context_used}")
        print()

    return 0


def cmd_demo(mode: str, topic: str | None, mock: bool) -> int:
    run_id = run_pipeline(topic or DEFAULT_TOPIC, mode=mode, mock_llm=mock)
    print(f"\nrun_id={run_id}")
    print(f"View the trace:  python -m app.cli trace {run_id}")
    print(f"Or in a browser: http://localhost:8000/trace/{run_id}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="ari")
    subparsers = parser.add_subparsers(dest="command", required=True)

    trace_parser = subparsers.add_parser("trace", help="Show the ordered event trace for a run")
    trace_parser.add_argument("run_id", help="The run_id (UUID) to trace")

    demo_parser = subparsers.add_parser("demo", help="Run a demo pipeline exercising ARI's features")
    demo_parser.add_argument(
        "mode",
        choices=["success", "loop", "cost"],
        help="success: full run, hits the approval gate twice, completes cleanly. "
        "loop: repeats a tool call past the threshold and gets auto-killed. "
        "cost: a deliberately 'expensive' step trips the cost-anomaly flag.",
    )
    demo_parser.add_argument("topic", nargs="?", default=None, help="Optional topic for the researcher step")
    demo_parser.add_argument(
        "--mock",
        action="store_true",
        help="Use a free, mocked LLM instead of the real Anthropic API (no ANTHROPIC_API_KEY needed)",
    )

    args = parser.parse_args()

    if args.command == "trace":
        return cmd_trace(args.run_id)
    if args.command == "demo":
        return cmd_demo(args.mode, args.topic, args.mock)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
