"""Quick Langfuse trace browser with metadata filtering.

This is an alternate helper that mirrors the logic used in
``agentops_library-main/evaluation/test_old.py`` to list traces via the
`langfuse.api.trace.list` endpoint and then filter client-side by metadata,
pattern, or environment. It intentionally lives alongside ``langfuse_traces.py``
so you can try whichever script works best in your environment.
"""
from __future__ import annotations

import argparse
import json
import os
import textwrap
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List

from langfuse import Langfuse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="List Langfuse traces and filter by metadata, pattern, or user",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--host", default=os.getenv("LANGFUSE_HOST"), help="Langfuse host URL")
    parser.add_argument(
        "--public-key",
        default=os.getenv("LANGFUSE_PUBLIC_KEY"),
        help="Langfuse public key (overrides LANGFUSE_PUBLIC_KEY)",
    )
    parser.add_argument(
        "--secret-key",
        default=os.getenv("LANGFUSE_SECRET_KEY"),
        help="Langfuse secret key (overrides LANGFUSE_SECRET_KEY)",
    )
    parser.add_argument("--limit", type=int, default=50, help="Number of raw traces to fetch")
    parser.add_argument("--environment", help="Filter by environment (exact match)")
    parser.add_argument("--user-id", help="Filter by userId (exact match)")
    parser.add_argument("--name", help="Filter by trace name (exact match)")
    parser.add_argument(
        "--pattern",
        help="Case-insensitive substring to search in name/input/output/metadata",
    )
    parser.add_argument("--metadata-key", help="Metadata key to match (exact)")
    parser.add_argument(
        "--metadata-value",
        help="Metadata value to match (exact). Use with --metadata-key.",
    )
    parser.add_argument(
        "--since-hours",
        type=float,
        default=None,
        help="Only show traces newer than N hours ago (client-side filter)",
    )
    parser.add_argument(
        "--show-metadata",
        action="store_true",
        help="Print the metadata dictionary for each trace",
    )
    parser.add_argument(
        "--show-io",
        action="store_true",
        help="Print the input/output payloads when available",
    )
    return parser.parse_args()


def require(value: str | None, flag: str) -> str:
    if value:
        return value
    raise SystemExit(f"Missing required setting: {flag} (set via --{flag} or LANGFUSE_{flag.upper()})")


def fetch_raw_traces(client: Langfuse, *, limit: int) -> List[Any]:
    """Fetch raw traces using the SDK's list endpoint used in evaluation scripts."""
    response = client.api.trace.list(limit=limit)
    return list(response.data)


def parse_timestamp(data: Dict[str, Any]) -> datetime | None:
    raw = data.get("timestamp") or data.get("createdAt")
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw
    try:
        # fromisoformat does not support a trailing Z, so normalize it first.
        sanitized = raw.replace("Z", "+00:00")
        return datetime.fromisoformat(sanitized)
    except Exception:
        return None


def matches_filters(
    trace_dict: Dict[str, Any],
    *,
    environment: str | None,
    user_id: str | None,
    name: str | None,
    pattern: str | None,
    metadata_key: str | None,
    metadata_value: str | None,
    since_hours: float | None,
) -> bool:
    metadata = trace_dict.get("metadata") or {}
    if environment and trace_dict.get("environment") != environment:
        return False
    if user_id and trace_dict.get("userId") != user_id:
        return False
    if name and trace_dict.get("name") != name:
        return False

    if metadata_key:
        if metadata_key not in metadata:
            return False
        if metadata_value is not None and str(metadata.get(metadata_key)) != metadata_value:
            return False

    if since_hours is not None:
        ts = parse_timestamp(trace_dict)
        if not ts:
            return False
        cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
        if ts.replace(tzinfo=timezone.utc) < cutoff:
            return False

    if pattern:
        needle = pattern.lower()
        haystacks = [
            str(trace_dict.get("name", "")),
            str(trace_dict.get("input", "")),
            str(trace_dict.get("output", "")),
            str(metadata),
        ]
        if not any(needle in value.lower() for value in haystacks):
            return False

    return True


def summarize_traces(traces: Iterable[Any]) -> None:
    print("\nField coverage (non-empty counts):")
    counters = {"name": 0, "userId": 0, "environment": 0, "metadata": 0}
    total = 0
    for trace in traces:
        total += 1
        data = trace.dict()
        for key in counters:
            if data.get(key):
                counters[key] += 1
    if total == 0:
        print("  no traces to summarize")
        return
    for key, count in counters.items():
        print(f"  {key}: {count}/{total}")


def print_trace(trace: Any, *, show_metadata: bool, show_io: bool) -> None:
    data = trace.dict()
    ts = parse_timestamp(data)
    ts_display = ts.isoformat() if ts else "<timestamp?>"
    divider = "=" * 80
    meta = data.get("metadata") or {}

    print(divider)
    print(f"id:          {data.get('id', '<id?>')}")
    print(f"name:        {data.get('name', '<name?>')}")
    print(f"environment: {data.get('environment', '<env?>')}")
    print(f"userId:      {data.get('userId', '<user?>')}")
    print(f"timestamp:   {ts_display}")
    if data.get("durationMs") is not None:
        print(f"durationMs:  {data['durationMs']}")
    if data.get("sessionId"):
        print(f"sessionId:   {data['sessionId']}")
    if data.get("release"):
        print(f"release:     {data['release']}")

    if show_metadata:
        print("metadata:")
        if meta:
            print(textwrap.indent(json.dumps(meta, indent=2, ensure_ascii=False), prefix="  "))
        else:
            print("  <empty>")

    if show_io and (data.get("input") is not None or data.get("output") is not None):
        print("io:")
        if data.get("input") is not None:
            input_block = json.dumps(data.get("input"), indent=2, ensure_ascii=False)
            print(textwrap.indent(f"input:\n{input_block}", prefix="  "))
        if data.get("output") is not None:
            output_block = json.dumps(data.get("output"), indent=2, ensure_ascii=False)
            print(textwrap.indent(f"output:\n{output_block}", prefix="  "))

    known_keys = {
        "id",
        "name",
        "environment",
        "userId",
        "timestamp",
        "createdAt",
        "durationMs",
        "sessionId",
        "release",
        "metadata",
        "input",
        "output",
    }
    extra_keys = {k: v for k, v in data.items() if k not in known_keys and v is not None}
    if extra_keys:
        print("other fields:")
        print(textwrap.indent(json.dumps(extra_keys, indent=2, ensure_ascii=False), prefix="  "))


def main() -> None:
    args = parse_args()
    host = require(args.host, "host")
    public_key = require(args.public_key, "public-key")
    secret_key = require(args.secret_key, "secret-key")

    client = Langfuse(host=host, public_key=public_key, secret_key=secret_key)

    try:
        raw_traces = fetch_raw_traces(client, limit=args.limit)
    except Exception as exc:  # pragma: no cover - defensive user feedback
        raise SystemExit(f"Failed to fetch traces: {exc}") from exc

    print(f"Fetched {len(raw_traces)} traces from the API (limit={args.limit}).")

    filtered = [
        t
        for t in raw_traces
        if matches_filters(
            t.dict(),
            environment=args.environment,
            user_id=args.user_id,
            name=args.name,
            pattern=args.pattern,
            metadata_key=args.metadata_key,
            metadata_value=args.metadata_value,
            since_hours=args.since_hours,
        )
    ]

    if not filtered:
        print("No traces matched after client-side filters.")
        print(
            "Filters -> "
            f"environment={args.environment or 'any'}, "
            f"user-id={args.user_id or 'any'}, "
            f"name={args.name or 'any'}, "
            f"pattern={args.pattern or 'none'}, "
            f"metadata={args.metadata_key or 'none'}={args.metadata_value or 'any'}, "
            f"since-hours={args.since_hours or 'none'}."
        )
        print(
            "Tips: drop filters, reduce --since-hours, or reuse the metadata key/value "
            "shown in Langfuse (e.g. request_name)."
        )
        return

    print(f"\nShowing {len(filtered)} trace(s) after filters:")
    for idx, trace in enumerate(filtered, start=1):
        print(f"\nTrace {idx}/{len(filtered)}:")
        print_trace(trace, show_metadata=args.show_metadata, show_io=args.show_io)

    summarize_traces(filtered)


if __name__ == "__main__":
    main()
