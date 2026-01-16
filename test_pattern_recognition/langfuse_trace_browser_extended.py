"""Quick Langfuse trace browser + observation exporter with metadata filtering.

Estende il browser:
- lista trace via langfuse.api.trace.list
- filtri client-side (environment/user/name/metadata/pattern/since-hours)
- fetch delle observations (spans/generations/events) collegate alla trace
- export su file (JSON pretty o JSONL)

Compatibilità:
- prova più metodi del client SDK per scaricare observations, perché i nomi possono
  cambiare tra versioni (observation.get vs observations.get, ecc.).
"""

from __future__ import annotations

import argparse
import json
import os
import textwrap
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from langfuse import Langfuse


# ----------------------------
# Args
# ----------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="List Langfuse traces, fetch observations, filter client-side, export to file.",
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
        help="Case-insensitive substring to search in name/input/output/metadata (+ observation fields if enabled)",
    )

    parser.add_argument("--metadata-key", help="Metadata key to match (exact)")
    parser.add_argument("--metadata-value", help="Metadata value to match (exact). Use with --metadata-key.")
    parser.add_argument(
        "--since-hours",
        type=float,
        default=None,
        help="Only show traces newer than N hours ago (client-side filter)",
    )

    # Printing options
    parser.add_argument("--show-metadata", action="store_true", help="Print trace metadata dictionary")
    parser.add_argument("--show-io", action="store_true", help="Print trace input/output when available")

    # Observation fetching / printing
    parser.add_argument(
        "--fetch-observations",
        action="store_true",
        help="Fetch and include observations for each trace (recommended for pattern recognition)",
    )
    parser.add_argument(
        "--max-observations",
        type=int,
        default=200,
        help="Safety cap: max observations to fetch per trace",
    )
    parser.add_argument(
        "--show-observations",
        action="store_true",
        help="Print observations for each trace to console (can be verbose)",
    )
    parser.add_argument(
        "--observation-io",
        action="store_true",
        help="Include observation input/output in export/print when available",
    )

    # Export
    parser.add_argument(
        "--out",
        default=None,
        help="Output file path. Default: ./langfuse_export_<UTCtimestamp>.json",
    )
    parser.add_argument(
        "--format",
        choices=["json", "jsonl"],
        default="json",
        help="Export format: json (pretty array) or jsonl (one trace per line)",
    )

    # Behavior
    parser.add_argument(
        "--sort-observations",
        action="store_true",
        help="Sort observations by timestamp (recommended). If false, keeps API order.",
    )

    return parser.parse_args()


def require(value: Optional[str], flag: str) -> str:
    if value:
        return value
    raise SystemExit(f"Missing required setting: {flag} (set via --{flag} or LANGFUSE_{flag.upper().replace('-', '_')})")


# ----------------------------
# Helpers: datetime normalization
# ----------------------------

def _to_iso(dt: Union[datetime, str, None]) -> Optional[str]:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        # Ensure timezone; if missing assume UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    if isinstance(dt, str):
        # Normalize "Z" to +00:00 for fromisoformat compatibility
        s = dt.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(s)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.isoformat()
        except Exception:
            return dt  # fallback: keep raw string
    return str(dt)


def parse_timestamp(data: Dict[str, Any]) -> Optional[datetime]:
    raw = data.get("timestamp") or data.get("createdAt") or data.get("startTime")
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    if isinstance(raw, str):
        try:
            sanitized = raw.replace("Z", "+00:00")
            dt = datetime.fromisoformat(sanitized)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    return None


# ----------------------------
# Fetch traces + filters
# ----------------------------

def fetch_raw_traces(client: Langfuse, *, limit: int) -> List[Any]:
    response = client.api.trace.list(limit=limit)
    return list(response.data)


def matches_filters(
    trace_dict: Dict[str, Any],
    *,
    environment: Optional[str],
    user_id: Optional[str],
    name: Optional[str],
    pattern: Optional[str],
    metadata_key: Optional[str],
    metadata_value: Optional[str],
    since_hours: Optional[float],
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
        if ts < cutoff:
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


# ----------------------------
# Observation fetching (robust across SDK versions)
# ----------------------------

@dataclass
class ObservationFetchResult:
    ok: bool
    data: Optional[Dict[str, Any]]
    error: Optional[str]


def _try_get_attr(obj: Any, path: str) -> Any:
    """Resolve dotted attribute path, return None if not found."""
    cur = obj
    for part in path.split("."):
        if not hasattr(cur, part):
            return None
        cur = getattr(cur, part)
    return cur


def fetch_observation(client: Langfuse, observation_id: str) -> ObservationFetchResult:
    """
    Try multiple SDK method names because they vary across versions.
    Expected: returns an object with .data or itself having .dict()
    """
    candidates: List[Tuple[str, Dict[str, Any]]] = [
        ("api.observation.get", {"id": observation_id}),
        ("api.observations.get", {"id": observation_id}),
        ("api.observation.retrieve", {"id": observation_id}),
        ("api.observations.retrieve", {"id": observation_id}),
    ]

    last_error: Optional[str] = None

    for method_path, kwargs in candidates:
        method = _try_get_attr(client, method_path)
        if method is None:
            continue
        try:
            resp = method(**kwargs)
            # Many SDK endpoints wrap in an object with .data
            if hasattr(resp, "data"):
                payload = resp.data
            else:
                payload = resp
            if hasattr(payload, "dict"):
                return ObservationFetchResult(ok=True, data=payload.dict(), error=None)
            if isinstance(payload, dict):
                return ObservationFetchResult(ok=True, data=payload, error=None)
            # Fallback: serialize best-effort
            return ObservationFetchResult(ok=True, data={"_raw": str(payload)}, error=None)
        except Exception as exc:
            last_error = f"{method_path} failed: {exc}"

    return ObservationFetchResult(
        ok=False,
        data=None,
        error=last_error or "No compatible observation.get method found in this SDK version.",
    )


def normalize_observation(obs: Dict[str, Any], *, include_io: bool) -> Dict[str, Any]:
    """
    Produce a normalized observation dict for export/pattern recognition,
    keeping also raw fields (non-null) under 'raw' for completeness.
    """
    # Common fields (best-effort across versions)
    obs_id = obs.get("id")
    obs_type = obs.get("type") or obs.get("observationType") or obs.get("kind")
    name = obs.get("name")
    level = obs.get("level")  # might exist
    status = obs.get("status")  # might exist
    start = obs.get("startTime") or obs.get("timestamp") or obs.get("createdAt")
    end = obs.get("endTime") or obs.get("updatedAt")

    meta = obs.get("metadata") or {}
    out: Dict[str, Any] = {
        "id": obs_id,
        "type": obs_type,
        "name": name,
        "level": level,
        "status": status,
        "startTime": _to_iso(start),
        "endTime": _to_iso(end),
        "durationMs": obs.get("durationMs"),
        "traceId": obs.get("traceId"),
        "parentObservationId": obs.get("parentObservationId") or obs.get("parentId"),
        "metadata": meta if meta else {},
    }

    # Optionally include I/O (can be large)
    if include_io:
        if "input" in obs:
            out["input"] = obs.get("input")
        if "output" in obs:
            out["output"] = obs.get("output")

    # Keep any additional non-null fields in raw for completeness
    known = set(out.keys()) | {"input", "output"}
    raw_extra = {k: v for k, v in obs.items() if k not in known and v is not None}
    if raw_extra:
        out["raw"] = raw_extra

    return out


def sort_observations(observations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def key_fn(o: Dict[str, Any]) -> Tuple[int, str]:
        # prefer startTime, fallback to endTime, fallback to empty
        st = o.get("startTime") or ""
        return (0 if st else 1, st)
    return sorted(observations, key=key_fn)


def pattern_match_in_observations(observations: List[Dict[str, Any]], pattern: str) -> bool:
    needle = pattern.lower()
    for o in observations:
        hay = " ".join(
            [
                str(o.get("type", "")),
                str(o.get("name", "")),
                str(o.get("status", "")),
                str(o.get("level", "")),
                str(o.get("metadata", "")),
                str(o.get("input", "")),
                str(o.get("output", "")),
                str(o.get("raw", "")),
            ]
        ).lower()
        if needle in hay:
            return True
    return False


# ----------------------------
# Printing
# ----------------------------

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


def print_observations(observations: List[Dict[str, Any]]) -> None:
    if not observations:
        print("observations: <none>")
        return
    print("observations:")
    for o in observations:
        line = f"- {o.get('startTime') or ''} | {o.get('type') or ''} | {o.get('name') or ''}"
        if o.get("status"):
            line += f" | status={o.get('status')}"
        if o.get("level"):
            line += f" | level={o.get('level')}"
        print(line)


# ----------------------------
# Export
# ----------------------------

def default_out_path(fmt: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ext = "jsonl" if fmt == "jsonl" else "json"
    return f"langfuse_export_{ts}.{ext}"


def export_records(path: str, fmt: str, records: List[Dict[str, Any]]) -> None:
    if fmt == "json":
        with open(path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
    else:  # jsonl
        with open(path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")


# ----------------------------
# Summaries
# ----------------------------

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


# ----------------------------
# Main
# ----------------------------

def main() -> None:
    args = parse_args()
    host = require(args.host, "host")
    public_key = require(args.public_key, "public-key")
    secret_key = require(args.secret_key, "secret-key")

    client = Langfuse(host=host, public_key=public_key, secret_key=secret_key)

    try:
        raw_traces = fetch_raw_traces(client, limit=args.limit)
    except Exception as exc:
        raise SystemExit(f"Failed to fetch traces: {exc}") from exc

    print(f"Fetched {len(raw_traces)} traces from the API (limit={args.limit}).")

    # First pass filter on trace-level fields
    trace_filtered = [
        t
        for t in raw_traces
        if matches_filters(
            t.dict(),
            environment=args.environment,
            user_id=args.user_id,
            name=args.name,
            pattern=args.pattern,  # trace-level pattern only (obs pattern handled later)
            metadata_key=args.metadata_key,
            metadata_value=args.metadata_value,
            since_hours=args.since_hours,
        )
    ]

    if not trace_filtered:
        print("No traces matched after client-side trace filters.")
        print(
            "Filters -> "
            f"environment={args.environment or 'any'}, "
            f"user-id={args.user_id or 'any'}, "
            f"name={args.name or 'any'}, "
            f"pattern={args.pattern or 'none'}, "
            f"metadata={args.metadata_key or 'none'}={args.metadata_value or 'any'}, "
            f"since-hours={args.since_hours or 'none'}."
        )
        return

    export_records_list: List[Dict[str, Any]] = []

    # For each trace, optionally fetch observations
    for idx, trace in enumerate(trace_filtered, start=1):
        tdata = trace.dict()

        # Console print
        print(f"\nTrace {idx}/{len(trace_filtered)}:")
        print_trace(trace, show_metadata=args.show_metadata, show_io=args.show_io)

        observations_norm: List[Dict[str, Any]] = []
        obs_fetch_error: Optional[str] = None

        if args.fetch_observations:
            obs_ids = tdata.get("observations") or []
            if isinstance(obs_ids, list):
                obs_ids = obs_ids[: max(0, args.max_observations)]
            else:
                obs_ids = []

            for obs_id in obs_ids:
                res = fetch_observation(client, str(obs_id))
                if not res.ok:
                    obs_fetch_error = res.error
                    # Non bloccare tutto: continua, ma segnala
                    continue
                observations_norm.append(normalize_observation(res.data or {}, include_io=args.observation_io))

            if args.sort_observations:
                observations_norm = sort_observations(observations_norm)

            # If a pattern is requested, allow it to match observations too
            if args.pattern and observations_norm:
                # If the trace already matched at trace-level we keep it.
                # But if it didn't match at trace-level, it would have been filtered out above.
                # If you want "pattern applies to trace OR observations", set --fetch-observations and remove trace-level pattern filter.
                pass

            if args.show_observations:
                print_observations(observations_norm)
                if obs_fetch_error:
                    print(f"observations warning: {obs_fetch_error}")

        # Build record for export
        record: Dict[str, Any] = {
            "trace": {
                "id": tdata.get("id"),
                "name": tdata.get("name"),
                "environment": tdata.get("environment"),
                "userId": tdata.get("userId"),
                "timestamp": _to_iso(tdata.get("timestamp") or tdata.get("createdAt")),
                "durationMs": tdata.get("durationMs"),
                "sessionId": tdata.get("sessionId"),
                "release": tdata.get("release"),
                "metadata": tdata.get("metadata") or {},
                # keep a few useful fields if present
                "tags": tdata.get("tags"),
                "public": tdata.get("public"),
                "latency": tdata.get("latency"),
                "totalCost": tdata.get("totalCost"),
                "projectId": tdata.get("projectId"),
                "updatedAt": tdata.get("updatedAt"),
                "htmlPath": tdata.get("htmlPath"),
            },
            "observations": observations_norm,
        }

        # A small derived feature for pattern recognition:
        # "stepSequence": list of dicts with type+name in chronological order
        record["stepSequence"] = [
            {
                "startTime": o.get("startTime"),
                "type": o.get("type"),
                "name": o.get("name"),
                "status": o.get("status"),
                "level": o.get("level"),
                "durationMs": o.get("durationMs"),
            }
            for o in observations_norm
        ]

        if obs_fetch_error:
            record["warnings"] = {"observationsFetch": obs_fetch_error}

        export_records_list.append(record)

    # Export
    out_path = args.out or default_out_path(args.format)
    export_records(out_path, args.format, export_records_list)
    print(f"\nExport written to: {out_path}")

    summarize_traces(trace_filtered)


if __name__ == "__main__":
    main()
