"""
Langfuse trace browser + exporter (trace + observations).

Features:
- Fetch traces (Langfuse SDK: client.api.trace.list)
- Client-side filters: environment, userId, name, metadata key/value, since-hours, pattern
- Optional fetch of observations by IDs listed in trace.observations
- Optional sorting of observations by time
- Export to JSON (pretty) or JSONL
- Console printing remains available (show-metadata/show-io/show-observations)

Notes:
- JSON export is hardened: any datetime (and other non-JSON types) are serialized safely.
- Observation fetching is implemented defensively to tolerate SDK method name variations.
"""

from __future__ import annotations

import argparse
import json
import os
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from langfuse import Langfuse


# ---------------------------
# JSON serialization hardening
# ---------------------------

def _json_default(obj: Any) -> Any:
    """Fallback serializer for json.dumps(default=...)."""
    if isinstance(obj, datetime):
        dt = obj if obj.tzinfo else obj.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    return str(obj)


# ---------------------------
# CLI
# ---------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="List Langfuse traces and optionally fetch observations; export to JSON/JSONL.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Connection
    p.add_argument("--host", default=os.getenv("LANGFUSE_HOST"), help="Langfuse host URL")
    p.add_argument("--public-key", default=os.getenv("LANGFUSE_PUBLIC_KEY"), help="Langfuse public key")
    p.add_argument("--secret-key", default=os.getenv("LANGFUSE_SECRET_KEY"), help="Langfuse secret key")

    # Trace fetch
    p.add_argument("--limit", type=int, default=50, help="Number of traces to fetch from API (raw)")

    # Client-side filters
    p.add_argument("--environment", help="Filter by trace environment (exact match)")
    p.add_argument("--user-id", help="Filter by trace userId (exact match)")
    p.add_argument("--name", help="Filter by trace name (exact match)")
    p.add_argument("--pattern", help="Case-insensitive substring search in trace name/input/output/metadata")
    p.add_argument("--metadata-key", help="Trace metadata key to match (exact)")
    p.add_argument("--metadata-value", help="Trace metadata value to match (exact). Use with --metadata-key.")
    p.add_argument("--since-hours", type=float, default=None, help="Only keep traces newer than N hours ago (UTC)")

    # Console verbosity
    p.add_argument("--show-metadata", action="store_true", help="Print trace metadata to console")
    p.add_argument("--show-io", action="store_true", help="Print trace input/output to console")

    # Observations (extended)
    p.add_argument("--fetch-observations", action="store_true", help="Fetch observations listed in trace.observations")
    p.add_argument("--max-observations", type=int, default=500, help="Safety cap per trace when fetching observations")
    p.add_argument("--sort-observations", action="store_true", help="Sort observations by timestamp/startTime/createdAt")
    p.add_argument("--show-observations", action="store_true", help="Print a compact list of observations to console")
    p.add_argument(
        "--observation-io",
        action="store_true",
        help="Include observation input/output in export (very verbose)",
    )

    # Export
    p.add_argument("--format", choices=["json", "jsonl"], default="json", help="Export format")
    p.add_argument("--out", default=None, help="Output file path. If omitted, a timestamped file is created.")

    return p.parse_args()


def require(value: Optional[str], flag_name: str) -> str:
    if value:
        return value
    env_hint = f"LANGFUSE_{flag_name.replace('-', '_').upper()}"
    raise SystemExit(f"Missing required setting: {flag_name} (pass via --{flag_name} or {env_hint})")


# ---------------------------
# Time helpers
# ---------------------------

def _to_iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    if isinstance(value, str):
        return value.replace("Z", "+00:00")
    return str(value)


def parse_timestamp(d: Dict[str, Any]) -> Optional[datetime]:
    raw = d.get("timestamp") or d.get("startTime") or d.get("createdAt") or d.get("updatedAt")
    if raw is None:
        return None

    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)

    if isinstance(raw, str):
        try:
            s = raw.replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None

    return None


# ---------------------------
# Trace fetch + filtering
# ---------------------------

def fetch_raw_traces(client: Langfuse, *, limit: int) -> List[Any]:
    resp = client.api.trace.list(limit=limit)
    return list(resp.data)


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
    meta = trace_dict.get("metadata") or {}

    if environment and trace_dict.get("environment") != environment:
        return False
    if user_id and trace_dict.get("userId") != user_id:
        return False
    if name and trace_dict.get("name") != name:
        return False

    if metadata_key:
        if metadata_key not in meta:
            return False
        if metadata_value is not None and str(meta.get(metadata_key)) != metadata_value:
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
        hay = [
            str(trace_dict.get("name", "")),
            str(trace_dict.get("input", "")),
            str(trace_dict.get("output", "")),
            str(meta),
        ]
        if not any(needle in s.lower() for s in hay):
            return False

    return True


# ---------------------------
# Observations fetch (robust to SDK variations)
# ---------------------------

def _resolve_callable(obj: Any, dotted: str) -> Optional[Any]:
    cur = obj
    for part in dotted.split("."):
        if not hasattr(cur, part):
            return None
        cur = getattr(cur, part)
    return cur if callable(cur) else None


def _call_obs_get(fn: Any, obs_id: str) -> Any:
    # Try common signatures
    try:
        return fn(id=obs_id)
    except TypeError:
        pass

    for key in ("observation_id", "observationId", "observationID"):
        try:
            return fn(**{key: obs_id})
        except TypeError:
            continue

    return fn(obs_id)  # last resort positional


def fetch_observation(client: Langfuse, obs_id: str) -> Tuple[bool, Optional[Any], Optional[str]]:
    candidates = [
        "api.observation.get",
        "api.observations.get",
        "api.observation.retrieve",
        "api.observations.retrieve",
    ]

    last_err: Optional[str] = None
    for cand in candidates:
        fn = _resolve_callable(client, cand)
        if not fn:
            continue
        try:
            obj = _call_obs_get(fn, obs_id)
            return True, obj, None
        except Exception as e:
            last_err = f"{cand} failed: {e}"

    if last_err:
        return False, None, last_err
    return False, None, "No compatible observation getter found on this SDK instance."


def normalize_observation(obs_obj: Any, *, include_io: bool) -> Dict[str, Any]:
    if isinstance(obs_obj, dict):
        d = obs_obj
    else:
        d = obs_obj.dict() if hasattr(obs_obj, "dict") else dict(obs_obj)

    out: Dict[str, Any] = {
        "id": d.get("id"),
        "type": d.get("type"),
        "name": d.get("name"),
        "status": d.get("status"),
        "level": d.get("level"),
        "traceId": d.get("traceId"),
        "parentObservationId": d.get("parentObservationId"),
        "startTime": _to_iso(d.get("startTime") or d.get("timestamp") or d.get("createdAt")),
        "endTime": _to_iso(d.get("endTime")),
        "durationMs": d.get("durationMs") or d.get("latencyMs") or d.get("latency"),
        "metadata": d.get("metadata") or {},
    }

    if include_io:
        if "input" in d:
            out["input"] = d.get("input")
        if "output" in d:
            out["output"] = d.get("output")

    known = set(out.keys()) | {"input", "output"}
    raw_extra = {k: v for k, v in d.items() if k not in known and v is not None}
    if raw_extra:
        out["raw"] = raw_extra

    return out


def sort_observations(obs_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def keyfn(o: Dict[str, Any]) -> Tuple[int, str]:
        s = o.get("startTime") or ""
        return (0 if s else 1, s)

    return sorted(obs_list, key=keyfn)


# ---------------------------
# Console printing
# ---------------------------

def print_trace(trace: Any, *, show_metadata: bool, show_io: bool) -> None:
    d = trace.dict()
    meta = d.get("metadata") or {}
    ts = parse_timestamp(d)
    ts_s = ts.isoformat() if ts else "<timestamp?>"

    divider = "=" * 80
    print(divider)
    print(f"id:          {d.get('id', '<id?>')}")
    print(f"name:        {d.get('name', '<name?>')}")
    print(f"environment: {d.get('environment', '<env?>')}")
    print(f"userId:      {d.get('userId', '<user?>')}")
    print(f"timestamp:   {ts_s}")

    if show_metadata:
        print("metadata:")
        if meta:
            print(textwrap.indent(json.dumps(meta, indent=2, ensure_ascii=False, default=_json_default), prefix="  "))
        else:
            print("  <empty>")

    if show_io and (d.get("input") is not None or d.get("output") is not None):
        print("io:")
        if d.get("input") is not None:
            print(
                textwrap.indent(
                    "input:\n" + json.dumps(d.get("input"), indent=2, ensure_ascii=False, default=_json_default),
                    prefix="  ",
                )
            )
        if d.get("output") is not None:
            print(
                textwrap.indent(
                    "output:\n" + json.dumps(d.get("output"), indent=2, ensure_ascii=False, default=_json_default),
                    prefix="  ",
                )
            )


def print_observations_compact(obs_norm: List[Dict[str, Any]]) -> None:
    for i, o in enumerate(obs_norm, start=1):
        print(
            f"  [{i:02d}] "
            f"id={o.get('id')} | type={o.get('type')} | name={o.get('name')} | "
            f"time={o.get('startTime')} | status={o.get('status')}"
        )


# ---------------------------
# Export
# ---------------------------

def default_out_path(fmt: str) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(f"langfuse_export_{ts}.{fmt}")


def export_records(path: Path, fmt: str, records: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "json":
        path.write_text(
            json.dumps(records, indent=2, ensure_ascii=False, default=_json_default),
            encoding="utf-8",
        )
        return

    # jsonl
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False, default=_json_default))
            f.write("\n")


# ---------------------------
# Main
# ---------------------------

def main() -> None:
    args = parse_args()

    host = require(args.host, "host")
    public_key = require(args.public_key, "public-key")
    secret_key = require(args.secret_key, "secret-key")

    client = Langfuse(host=host, public_key=public_key, secret_key=secret_key)

    raw_traces = fetch_raw_traces(client, limit=args.limit)
    print(f"Fetched {len(raw_traces)} traces from API (limit={args.limit}).")

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
        return

    print(f"Showing {len(filtered)} trace(s) after filters.\n")

    records: List[Dict[str, Any]] = []

    for idx, trace in enumerate(filtered, start=1):
        trace_dict = trace.dict()

        print(f"Trace {idx}/{len(filtered)}:")
        print_trace(trace, show_metadata=args.show_metadata, show_io=args.show_io)

        obs_norm: List[Dict[str, Any]] = []
        warnings: Dict[str, Any] = {}

        if args.fetch_observations:
            obs_ids = trace_dict.get("observations") or []
            if not isinstance(obs_ids, list):
                obs_ids = []

            if len(obs_ids) > args.max_observations:
                warnings["observationsTruncated"] = {
                    "originalCount": len(obs_ids),
                    "keptCount": args.max_observations,
                }
                obs_ids = obs_ids[: args.max_observations]

            obs_errors: List[Dict[str, str]] = []
            for obs_id in obs_ids:
                ok, obj, err = fetch_observation(client, str(obs_id))
                if not ok or obj is None:
                    obs_errors.append({"id": str(obs_id), "error": err or "unknown"})
                    continue
                obs_norm.append(normalize_observation(obj, include_io=args.observation_io))

            if obs_errors:
                warnings["observationsFetch"] = {
                    "failed": len(obs_errors),
                    "errors": obs_errors[:20],
                    "note": "Showing first 20 errors only.",
                }

            if args.sort_observations:
                obs_norm = sort_observations(obs_norm)

            if args.show_observations:
                print("observations (compact):")
                print_observations_compact(obs_norm)

        step_seq: List[Dict[str, Any]] = []
        if obs_norm:
            for i, o in enumerate(obs_norm, start=1):
                step_seq.append(
                    {
                        "index": i,
                        "id": o.get("id"),
                        "type": o.get("type"),
                        "name": o.get("name"),
                        "time": o.get("startTime"),
                        "status": o.get("status"),
                        "level": o.get("level"),
                        "durationMs": o.get("durationMs"),
                        "parentObservationId": o.get("parentObservationId"),
                    }
                )

        rec: Dict[str, Any] = {
            "trace": trace_dict,
            "observations": obs_norm if args.fetch_observations else [],
            "stepSequence": step_seq,
        }
        if warnings:
            rec["warnings"] = warnings

        records.append(rec)
        print("")

    out_path = Path(args.out) if args.out else default_out_path(args.format)
    export_records(out_path, args.format, records)
    print(f"Export written to: {out_path}")


if __name__ == "__main__":
    main()
