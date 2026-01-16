"""
LLM-as-a-judge for Langfuse trace exports produced by langfuse_trace_browser_complex.py.

It reads JSON/JSONL records with fields:
- trace
- observations
- stepSequence

For each trace, it builds a compact summary and asks a judge model to score
behavioral patterns (tool usage, task success, clarity, efficiency, risk).
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List

from openai import AzureOpenAI, OpenAI


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
        description="Evaluate Langfuse trace exports with an LLM-as-a-judge.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", default="langfuse_export.json", help="Path to JSON/JSONL export file")
    parser.add_argument("--out", default="langfuse_trace_judge_results.json", help="Output JSON file")
    parser.add_argument("--model", default="gpt-4o-mini", help="Judge model to use")
    parser.add_argument("--max-traces", type=int, default=50, help="Maximum number of traces to score")
    parser.add_argument(
        "--truncate-chars",
        type=int,
        default=4000,
        help="Max characters per large text field (input/output) sent to the judge",
    )
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


def is_tool_observation(obs: Dict[str, Any]) -> bool:
    name = (obs.get("name") or "").lower()
    obs_type = (obs.get("type") or "").lower()
    meta = obs.get("metadata") or {}
    meta_text = json.dumps(meta, ensure_ascii=False).lower()
    tool_keywords = ["tool", "function", "call", "invoke", "kubernetessme", "retriever"]
    return any(k in name for k in tool_keywords) or any(k in obs_type for k in tool_keywords) or any(
        k in meta_text for k in tool_keywords
    )


def build_summary(record: Dict[str, Any], max_chars: int) -> Dict[str, Any]:
    trace = record.get("trace", {}) or {}
    observations = record.get("observations", []) or []
    step_sequence = record.get("stepSequence", []) or []

    tool_obs = [o for o in observations if is_tool_observation(o)]

    summary = {
        "trace_id": trace.get("id"),
        "trace_name": trace.get("name"),
        "environment": trace.get("environment"),
        "user_id": trace.get("userId"),
        "timestamp": trace.get("timestamp"),
        "input": truncate_text(trace.get("input"), max_chars),
        "output": truncate_text(trace.get("output"), max_chars),
        "observation_count": len(observations),
        "tool_observation_count": len(tool_obs),
        "observation_names": [o.get("name") for o in observations[:25]],
        "step_sequence": step_sequence[:50],
        "warnings": record.get("warnings"),
    }

    return summary


def build_prompt(summary: Dict[str, Any]) -> List[Dict[str, str]]:
    system = (
        "Sei un LLM-as-a-judge che valuta il comportamento di un agente da trace Langfuse. "
        "Analizza il pattern di azioni (tool usage, coerenza, completezza, efficienza) e "
        "restituisci un JSON con metriche strutturate. Non inventare dettagli non presenti."
    )

    rubric = (
        "Rubrica (1-5):\n"
        "- task_success: l'output risponde correttamente all'input.\n"
        "- tool_use: uso adeguato degli strumenti quando necessario e coerente con il pattern.\n"
        "- clarity: chiarezza e struttura della risposta finale.\n"
        "- efficiency: numero di step/tool proporzionati al task.\n"
        "- risk: rischio di allucinazioni o contraddizioni (1=alto rischio, 5=basso rischio).\n"
        "Fornisci anche: overall_score (0-100), pattern_flags (lista stringhe), "
        "strengths (lista), weaknesses (lista), recommendations (lista)."
    )

    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    user = (
        f"Trace summary:\n{payload}\n\n"
        "Valuta e rispondi SOLO con un JSON valido seguendo lo schema:\n"
        "{\n"
        "  \"trace_id\": string,\n"
        "  \"overall_score\": number,\n"
        "  \"metrics\": {\n"
        "    \"task_success\": {\"score\": 1-5, \"rationale\": string},\n"
        "    \"tool_use\": {\"score\": 1-5, \"rationale\": string},\n"
        "    \"clarity\": {\"score\": 1-5, \"rationale\": string},\n"
        "    \"efficiency\": {\"score\": 1-5, \"rationale\": string},\n"
        "    \"risk\": {\"score\": 1-5, \"rationale\": string}\n"
        "  },\n"
        "  \"pattern_flags\": [string],\n"
        "  \"strengths\": [string],\n"
        "  \"weaknesses\": [string],\n"
        "  \"recommendations\": [string]\n"
        "}\n"
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": rubric},
        {"role": "user", "content": user},
    ]


def judge_trace(client: OpenAI, model: str, summary: Dict[str, Any]) -> Dict[str, Any]:
    messages = build_prompt(summary)
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content or "{}"
    result = json.loads(content)
    result.setdefault("trace_id", summary.get("trace_id"))
    return result


def build_client() -> OpenAI:
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        return OpenAI(
            api_key=openai_key,
            base_url=os.getenv("OPENAI_BASE_URL"),
        )

    azure_key = os.getenv("AZURE_API_KEY_GPT4")
    azure_endpoint = os.getenv("AZURE_ENDPOINT")
    azure_version = os.getenv("AZURE_GPT_VERSION")
    azure_deployment = os.getenv("AZURE_GPT_4_MODEL")

    if azure_key and azure_endpoint and azure_version and azure_deployment:
        return AzureOpenAI(
            api_key=azure_key,
            azure_endpoint=azure_endpoint,
            api_version=azure_version,
            azure_deployment=azure_deployment,
        )

    raise SystemExit(
        "Missing API configuration. Set OPENAI_API_KEY (optional OPENAI_BASE_URL) "
        "or Azure envs: AZURE_API_KEY_GPT4, AZURE_ENDPOINT, AZURE_GPT_VERSION, AZURE_GPT_4_MODEL."
    )


def main() -> None:
    args = parse_args()

    load_env_file()

    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    records = load_records(input_path)
    if not records:
        raise SystemExit("No records found in input file.")

    client = build_client()

    results = []
    for record in records[: args.max_traces]:
        summary = build_summary(record, args.truncate_chars)
        evaluation = judge_trace(client, args.model, summary)
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
