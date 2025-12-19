"""Utility script to inspect Langfuse traces locally.

This script fetches traces from Langfuse using the official SDK and prints
basic information so it is easy to spot recurring patterns (e.g. repeated
trace names or users). Environment variables are supported to keep secrets
out of the command line.

Example usage::

    python -m src.utils.langfuse_traces \
        --host https://langfuse.example.com \
        --public-key YOUR_PUBLIC_KEY \
        --secret-key YOUR_SECRET_KEY \
        --limit 50 --pattern error

The script also computes a frequency table for trace names to help with
pattern recognition.
"""
from __future__ import annotations

import argparse
import os
from collections import Counter
from typing import Iterable, List

from langfuse import Langfuse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch and print Langfuse traces")
    parser.add_argument(
        "--host",
        type=str,
        default=os.getenv("LANGFUSE_HOST"),
        help="Langfuse host URL (overrides LANGFUSE_HOST)",
    )
    parser.add_argument(
        "--public-key",
        type=str,
        default=os.getenv("LANGFUSE_PUBLIC_KEY"),
        help="Langfuse public key (overrides LANGFUSE_PUBLIC_KEY)",
    )
    parser.add_argument(
        "--secret-key",
        type=str,
        default=os.getenv("LANGFUSE_SECRET_KEY"),
        help="Langfuse secret key (overrides LANGFUSE_SECRET_KEY)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of traces to fetch (default: 50)",
    )
    parser.add_argument(
        "--environment",
        type=str,
        help="Filter by Langfuse environment (e.g. production, staging)",
    )
    parser.add_argument(
        "--user-id",
        type=str,
        help="Filter by userId",
    )
    parser.add_argument(
        "--name",
        type=str,
        help="Filter by trace name",
    )
    parser.add_argument(
        "--order-by",
        type=str,
        default="createdAt:desc",
        help="Field and direction, e.g. createdAt:desc (default) or createdAt:asc",
    )
    parser.add_argument(
        "--show-io",
        action="store_true",
        help="Print the input/output payloads when available",
    )
    parser.add_argument(
        "--pattern",
        type=str,
        help="Optional substring to filter trace names or descriptions",
    )
    return parser.parse_args()


def require(value: str | None, name: str) -> str:
    if value:
        return value
    raise SystemExit(f"Missing required setting: {name}. Set it via --{name} or LANGFUSE_{name.upper()}.")


def fetch_traces(
    client: Langfuse,
    *,
    limit: int,
    environment: str | None,
    user_id: str | None,
    name: str | None,
    order_by: str | None,
) -> List[object]:
    """Retrieve traces up to the given limit using the Langfuse SDK."""
    response = client.fetch_traces(
        limit=limit,
        environment=environment,
        user_id=user_id,
        name=name,
        order_by=order_by,
    )
    return list(response.data)


def normalize_text(value: str | None) -> str:
    return value.lower() if isinstance(value, str) else ""


def format_trace(trace: object, *, show_io: bool) -> str:
    data = trace.dict()
    basics = [
        data.get("id", "<id?>"),
        data.get("name", "<name?>") or "<name?>",
        data.get("userId", "<user?>") or "<user?>",
        data.get("environment", "<env?>") or "<env?>",
        data.get("timestamp", data.get("createdAt", "<timestamp?>")) or "<timestamp?>",
    ]

    if not show_io:
        return " | ".join(basics)

    details = []
    input_payload = data.get("input")
    output_payload = data.get("output")
    if input_payload:
        details.append(f"input={input_payload}")
    if output_payload:
        details.append(f"output={output_payload}")

    joined_details = " | ".join(details) if details else "no-io"
    return " | ".join(basics + [joined_details])


def print_name_frequencies(traces: Iterable[object]) -> None:
    counts = Counter()
    for trace in traces:
        trace_name = trace.dict().get("name")
        if trace_name:
            counts[trace_name] += 1
    if not counts:
        print("No trace names found to summarize.")
        return

    print("\nMost common trace names:")
    for name, count in counts.most_common():
        print(f"- {name}: {count}")


def main() -> None:
    args = parse_args()
    host = require(args.host, "host")
    public_key = require(args.public_key, "public-key")
    secret_key = require(args.secret_key, "secret-key")

    client = Langfuse(host=host, public_key=public_key, secret_key=secret_key)

    try:
        traces = fetch_traces(
            client=client,
            limit=args.limit,
            environment=args.environment,
            user_id=args.user_id,
            name=args.name,
            order_by=args.order_by,
        )
    except Exception as exc:  # pragma: no cover - defensive user feedback
        raise SystemExit(f"Failed to fetch traces: {exc}") from exc
    if args.pattern:
        pattern = normalize_text(args.pattern)
        traces = [
            t
            for t in traces
            if pattern in normalize_text(t.dict().get("name"))
            or pattern in normalize_text(t.dict().get("input"))
            or pattern in normalize_text(t.dict().get("output"))
        ]

    if not traces:
        print("No traces found with the given parameters.")
        return

    print(
        f"Fetched {len(traces)} traces"
        f" (order={args.order_by}; environment={args.environment or 'any'}):\n"
    )
    for trace in traces:
        print(f"- {format_trace(trace, show_io=args.show_io)}")

    print_name_frequencies(traces)


if __name__ == "__main__":
    main()
