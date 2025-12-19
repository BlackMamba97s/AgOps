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
        "--pattern",
        type=str,
        help="Optional substring to filter trace names or descriptions",
    )
    return parser.parse_args()


def require(value: str | None, name: str) -> str:
    if value:
        return value
    raise SystemExit(f"Missing required setting: {name}. Set it via --{name} or LANGFUSE_{name.upper()}.")


def fetch_traces(limit: int) -> List[object]:
    """Retrieve traces up to the given limit using the Langfuse SDK."""
    response = client.fetch_traces(limit=limit)
    return list(response.data)


def normalize_text(value: str | None) -> str:
    return value.lower() if isinstance(value, str) else ""


def format_trace(trace: object) -> str:
    data = trace.dict()
    return " | ".join(
        [
            data.get("id", "<id?>"),
            data.get("name", "<name?>") or "<name?>",
            data.get("userId", "<user?>") or "<user?>",
            data.get("timestamp", "<timestamp?>") or "<timestamp?>",
        ]
    )


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

    global client
    client = Langfuse(host=host, public_key=public_key, secret_key=secret_key)

    traces = fetch_traces(limit=args.limit)
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

    print(f"Fetched {len(traces)} traces:\n")
    for trace in traces:
        print(f"- {format_trace(trace)}")

    print_name_frequencies(traces)


if __name__ == "__main__":
    main()
