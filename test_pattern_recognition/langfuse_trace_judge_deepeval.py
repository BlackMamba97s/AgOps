"""
DeepEval-based LLM-as-a-judge for Langfuse trace exports.

It reads JSON/JSONL records with fields:
- trace
- observations
- stepSequence

For each trace, it builds a compact summary focused on observations and scores
behavioral patterns using DeepEval's GEval.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from deepeval.metrics import GEval
from deepeval.models import AzureOpenAIModel
from deepeval.test_case import LLMTestCase, LLMTestCaseParams


def load_env_file() -> None:
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent / ".env",
        Path(__file__).resolve().parent / ".env",
    ]

    for path in candidates:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if key and key not in os.environ:
                os.environ[key] = value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate Langfuse trace exports with DeepEval (LLM-as-a-judge).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", default="langfuse_export.json", help="Path to JSON/JSONL export file")
    parser.add_argument("--out", default="langfuse_trace_judge_deepeval.json", help="Output JSON file")
    parser.add_argument("--max-traces", type=int, default=50, help="Maximum number of traces to score")
    parser.add_argument(
        "--truncate-chars",
        type=int,
        default=4000,
        help="Max characters per large text field (input/output) sent to the judge",
    )
    parser.add_argument(
        "--max-observations",
        type=int,
        default=60,
        help="Maximum number of observations to include per trace summary",
    )
    parser.add_argument("--threshold", type=float, default=0.7, help="Passing threshold for the GEval metric")
    return parser.parse_args()


def load_records(path: Path) -> List[Dict[str, Any]]:
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []

    if path.suffix.lower() == ".jsonl":
        records = []
        for line in raw.splitlines():
            if not line.strip():
                continue
            records.append(json.loads(line))
        return records

    data = json.loads(raw)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "records" in data and isinstance(data["records"], list):
        return data["records"]
    return [data]


def truncate_text(value: Any, max_chars: int) -> str:
    if value is None:
        return ""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 40] + " ...[truncated]..."


def normalize_observation(obs: Dict[str, Any], max_chars: int) -> Dict[str, Any]:
    return {
        "id": obs.get("id"),
        "name": obs.get("name"),
        "type": obs.get("type"),
        "level": obs.get("level"),
        "status_message": obs.get("statusMessage"),
        "input": truncate_text(obs.get("input"), max_chars),
        "output": truncate_text(obs.get("output"), max_chars),
        "metadata": obs.get("metadata"),
        "start_time": obs.get("startTime"),
        "end_time": obs.get("endTime"),
        "parent_observation_id": obs.get("parentObservationId"),
    }


def build_summary(record: Dict[str, Any], max_chars: int, max_observations: int) -> Dict[str, Any]:
    trace = record.get("trace", {}) or {}
    observations = record.get("observations", []) or []
    step_sequence = record.get("stepSequence", []) or []

    normalized_observations = [
        normalize_observation(obs, max_chars) for obs in observations[:max_observations]
    ]

    summary = {
        "trace_id": trace.get("id"),
        "trace_name": trace.get("name"),
        "environment": trace.get("environment"),
        "user_id": trace.get("userId"),
        "timestamp": trace.get("timestamp"),
        "input": truncate_text(trace.get("input"), max_chars),
        "output": truncate_text(trace.get("output"), max_chars),
        "observation_count": len(observations),
        "observations": normalized_observations,
        "step_sequence": step_sequence[:50],
        "warnings": record.get("warnings"),
    }

    return summary


def build_model() -> AzureOpenAIModel:
    azure_key = os.getenv("AZURE_API_KEY_GPT4")
    azure_endpoint = os.getenv("AZURE_ENDPOINT")
    azure_version = os.getenv("AZURE_GPT_VERSION")
    azure_deployment = os.getenv("AZURE_GPT_4_MODEL")
    azure_model_name = os.getenv("AZURE_GPT_4_NAME", "gpt-4o")

    if not all([azure_key, azure_endpoint, azure_version, azure_deployment]):
        raise SystemExit(
            "Missing Azure configuration. Set AZURE_API_KEY_GPT4, AZURE_ENDPOINT, "
            "AZURE_GPT_VERSION, AZURE_GPT_4_MODEL."
        )

    return AzureOpenAIModel(
        model_name=azure_model_name,
        deployment_name=azure_deployment,
        azure_openai_api_key=azure_key,
        openai_api_version=azure_version,
        azure_endpoint=azure_endpoint,
        temperature=0,
    )


def build_metric(model: AzureOpenAIModel, threshold: float) -> GEval:
    return GEval(
        name="PatternRecognition",
        criteria=(
            "Valuta se il pattern nelle osservazioni della trace indica un comportamento coerente, "
            "corretto ed efficiente. Considera uso di tool, successi/fallimenti, chiarezza, "
            "completezza e rischio di allucinazioni."
        ),
        evaluation_steps=[
            "Rivedi l'input/output della trace e le osservazioni disponibili.",
            "Verifica coerenza tra input, tool usage e output finale.",
            "Individua pattern positivi/negativi (es. tool overuse, passi mancanti).",
            "Assegna un punteggio più alto quando il pattern è consistente e sicuro.",
        ],
        evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
        model=model,
        threshold=threshold,
    )


def evaluate_trace(summary: Dict[str, Any], model: AzureOpenAIModel, threshold: float) -> Dict[str, Any]:
    summary_payload = json.dumps(summary, ensure_ascii=False, indent=2)
    test_case = LLMTestCase(
        input=summary.get("trace_id") or "",
        actual_output=summary_payload,
        expected_output="",
    )

    metric = build_metric(model, threshold)
    metric.measure(test_case)

    return {
        "score": metric.score,
        "reason": metric.reason,
        "threshold": metric.threshold,
        "passed": metric.score is not None and metric.score >= metric.threshold,
    }


def main() -> None:
    os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")

    args = parse_args()
    load_env_file()

    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    records = load_records(input_path)
    if not records:
        raise SystemExit("No records found in input file.")

    model = build_model()

    results = []
    for record in records[: args.max_traces]:
        summary = build_summary(record, args.truncate_chars, args.max_observations)
        evaluation = evaluate_trace(summary, model, args.threshold)
        results.append(
            {
                "trace_id": summary.get("trace_id"),
                "summary": summary,
                "evaluation": evaluation,
            }
        )

    out_path = Path(args.out)
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(results)} evaluations to {out_path}")


if __name__ == "__main__":
    main()
