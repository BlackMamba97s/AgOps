# LLM-as-a-Judge per trace Langfuse

Questo modulo introduce un LLM-as-a-judge che analizza i file esportati da `langfuse_trace_browser_complex.py` e valuta il comportamento dell'agente con metriche di pattern evaluation.

## Cosa fa

- Legge export JSON/JSONL con campi `trace`, `observations`, `stepSequence`.
- Costruisce un **riassunto compatto** della trace (input/output, step principali, tool usage stimato).
- Usa un **modello LLM** (default: `gpt-4o-mini`) per assegnare un punteggio e commenti sulle metriche chiave.
- Salva il risultato in un JSON pronto per dashboard o analisi automatica.

## Come funziona

1. Carica i record esportati da `langfuse_trace_browser_complex.py`.
2. Crea un summary con:
   - ID trace, nome, timestamp
   - input/output (troncati per evitare prompt troppo lunghi)
   - numero di osservazioni e stima tool usage
   - stepSequence (max 50)
3. Chiede al modello di giudizio di produrre un JSON con:
   - `overall_score` (0-100)
   - metriche (1-5) con razionale
   - `pattern_flags`, `strengths`, `weaknesses`, `recommendations`

## Metriche utilizzate

- **task_success (1-5)**: l'output risponde davvero all'input?
- **tool_use (1-5)**: strumenti usati in modo coerente con il task?
- **clarity (1-5)**: chiarezza e struttura della risposta finale.
- **efficiency (1-5)**: numero di step/tool proporzionati al problema.
- **risk (1-5)**: rischio di allucinazioni/contraddizioni (1 = alto rischio, 5 = basso rischio).

> Nota: la stima tool usage è **euristica** (basata su nomi delle osservazioni/metadati). Se vuoi precisione massima, includi osservazioni con `--fetch-observations` e `--observation-io` nel browser complesso.

## Casi d'uso

- **Regression testing**: confrontare il comportamento tra versioni dell'agente.
- **Quality gate**: bloccare il deploy se `overall_score` o `task_success` scendono sotto una soglia.
- **Pattern analysis**: capire se l'agente usa troppi tool o risponde senza usare fonti.
- **Debug**: evidenziare incoerenze tra input/output e strumenti invocati.

## Esempi di utilizzo

### Eseguire il judge su un export JSON

```bash
python test_pattern_recognition/langfuse_trace_judge.py \
  --input langfuse_export.json \
  --out langfuse_trace_judge_results.json \
  --model gpt-4o-mini
```

### Eseguire su JSONL con più trace

```bash
python test_pattern_recognition/langfuse_trace_judge.py \
  --input langfuse_export_20240601T120000Z.jsonl \
  --out results.json \
  --max-traces 25
```

## Esempi di pattern (best/worst case)

### Best case (risultato atteso)

- **Input**: domanda specifica e contestualizzata.
- **Trace**: tool chiamato una sola volta, output coerente con il tool.
- **Output**: risposta sintetica, strutturata, senza contraddizioni.

> Expected judge: task_success=5, tool_use=5, clarity=4-5, efficiency=4-5, risk=5.

### Worst case (risultato critico)

- **Input**: domanda tecnica.
- **Trace**: nessun tool usato o tool invocato ma output non usa i risultati.
- **Output**: risposta generica, errata o contraddittoria.

> Expected judge: task_success=1-2, tool_use=1-2, clarity=2, efficiency=1-2, risk=1-2.

## Variabili d'ambiente richieste

- `OPENAI_API_KEY` (obbligatoria)
- `OPENAI_BASE_URL` (opzionale, solo se usi endpoint custom)

## Output

Il file di output contiene un array di oggetti:

```json
[
  {
    "trace_id": "...",
    "summary": { "...": "..." },
    "evaluation": {
      "overall_score": 82,
      "metrics": { "task_success": { "score": 4, "rationale": "..." } },
      "pattern_flags": ["tool_used_consistently"],
      "strengths": ["risposta precisa"],
      "weaknesses": [],
      "recommendations": ["aggiungere citazioni" ]
    }
  }
]
```
