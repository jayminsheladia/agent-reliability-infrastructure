import argparse
import sys
import uuid

from app.db import SessionLocal
from app.trace.service import get_trace


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
        print(
            f"[{step.step_index}] {step.agent_id}"
            f"  ({step.tokens_used} tokens, {step.latency_ms}ms, {step.timestamp})"
        )
        print(f"    in:  {step.input_preview}")
        print(f"    out: {step.output_preview}")
        print()

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="ari")
    subparsers = parser.add_subparsers(dest="command", required=True)

    trace_parser = subparsers.add_parser("trace", help="Show the ordered event trace for a run")
    trace_parser.add_argument("run_id", help="The run_id (UUID) to trace")

    args = parser.parse_args()

    if args.command == "trace":
        return cmd_trace(args.run_id)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
