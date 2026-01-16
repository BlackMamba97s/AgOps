# RUNBOOK — Langfuse Trace Browser & Export (Trace + Observations)

## 1) Obiettivo
Questo runbook descrive come usare `src/utils/langfuse_trace_browser.py` per:
- elencare trace da Langfuse
- applicare filtri client-side
- (opzionale ma raccomandato) recuperare le observations (spans / generations / events)
- esportare tutto in un file (JSON o JSONL) utile per analisi e pattern recognition

---

## 2) Quando usarlo (casi tipici)
Usalo quando devi:
- ricostruire la “timeline” di un agent (RAG / tool calls / LLM generations)
- trovare pattern di comportamento (sequenze step, retry loops, tool specifici)
- individuare errori o anomalie (status/level/exception fields nelle observations)
- produrre un export condivisibile con un collega (file leggibile)

---

## 3) Prerequisiti
- Python 3.9+ (consigliato 3.10+)
- `langfuse` Python SDK installato e funzionante
- accesso rete all’host Langfuse (es. `https://langfuse.liquid-reply.net`)
- credenziali valide (public/secret key)

---

## 4) Setup credenziali (consigliato via ENV)
Non passare la secret key in chiaro in CLI (history/log).

### 4.1 Windows CMD
```bat
set LANGFUSE_HOST=https://<HOST_LANGFUSE> (Liquid reply)
set LANGFUSE_PUBLIC_KEY=pk-lf-...
set LANGFUSE_SECRET_KEY=sk-lf-...
```

### 4.2 PowerShell
```powershell
$env:LANGFUSE_HOST="https://<HOST_LANGFUSE>"
$env:LANGFUSE_PUBLIC_KEY="pk-lf-..."
$env:LANGFUSE_SECRET_KEY="sk-lf-..."
```

### 4.3 Verifica rapida che le env siano settate
CMD:
```bat
echo %LANGFUSE_HOST%
echo %LANGFUSE_PUBLIC_KEY%
```

PowerShell:
```powershell
$env:LANGFUSE_HOST
$env:LANGFUSE_PUBLIC_KEY
```

---

## 5) Comandi rapidi (copy/paste)

### 5.1 Smoke test (trace-only, minimo)
Verifica che credenziali e host funzionino e che arrivino trace.
```bat
python -m src.utils.langfuse_trace_browser --limit 10
```

### 5.2 Export “standard” per pattern recognition (trace + observations)
Comando consigliato nel 90% dei casi:
```bat
python -m src.utils.langfuse_trace_browser --limit 50 --fetch-observations --sort-observations --out langfuse_export.json
```

### 5.3 Export esteso (include I/O delle observations)
Attenzione: file grande e potenzialmente contenente dati sensibili (prompt/tool results).
```bat
python -m src.utils.langfuse_trace_browser --limit 50 --fetch-observations --sort-observations --observation-io --out langfuse_export_full.json
```

### 5.4 JSONL (1 trace per riga) per volumi più grandi
```bat
python -m src.utils.langfuse_trace_browser --limit 200 --fetch-observations --sort-observations --format jsonl --out langfuse_export.jsonl
```

### 5.5 Ultime 24 ore (time window)
```bat
python -m src.utils.langfuse_trace_browser --limit 200 --since-hours 24 --fetch-observations --sort-observations --out last24h.json
```

### 5.6 Ultimi 90 giorni (utile se “vedo solo fino a novembre”)
```bat
python -m src.utils.langfuse_trace_browser --limit 200 --since-hours 2160 --fetch-observations --sort-observations --out last90d.json
```

---

## 6) Filtri (come usarli bene)

### 6.1 Filtra per environment (match esatto)
```bat
python -m src.utils.langfuse_trace_browser --limit 200 --environment default --fetch-observations --sort-observations --out env_default.json
```

### 6.2 Filtra per name della trace (match esatto)
```bat
python -m src.utils.langfuse_trace_browser --limit 200 --name root-agent-span --fetch-observations --sort-observations --out root_agent.json
```

### 6.3 Filtra per metadata (key/value match esatto)
Esempio tipico: `request_name`
```bat
python -m src.utils.langfuse_trace_browser --limit 200 --metadata-key request_name --metadata-value "correctness_test_..." --fetch-observations --sort-observations --out by_request_name.json
```

### 6.4 Pattern search (substring, case-insensitive)
Cerca dentro:
- name/input/output/metadata della trace
- metadata delle observations (e, se `--observation-io`, anche input/output delle observations)
```bat
python -m src.utils.langfuse_trace_browser --limit 200 --pattern error --fetch-observations --sort-observations --out pattern_error.json
```

Nota:
- `pattern=error` NON equivale a “trace con status error”; è una ricerca testuale.
- Per error detection affidabile conviene cercare su campi strutturati (status/level) nelle observations, se presenti.

---

## 7) Output: cosa aspettarsi

### 7.1 Console
A seconda dei flag:
- stampa un blocco per ogni trace (id, name, env, timestamp, ecc.)
- opzionalmente metadata (`--show-metadata`)
- opzionalmente trace input/output (`--show-io`)
- opzionalmente observations in forma compatta (`--show-observations`)

### 7.2 File export (JSON / JSONL)
Per ogni trace esporta un record con:
- `trace`: campi principali
- `observations`: lista normalizzata (se `--fetch-observations`)
- `stepSequence`: timeline snella (type/name/time/status) per pattern recognition
- `warnings` (se qualche fetch observation fallisce)

Suggerimento operativo:
- per analisi rapida, parti sempre da `stepSequence` (è più stabile e leggero).

---

## 8) Playbook: Pattern recognition (procedura consigliata)

### Step 1 — Genera export con observations ordinate
```bat
python -m src.utils.langfuse_trace_browser --limit 200 --since-hours 2160 --fetch-observations --sort-observations --out export.json
```

### Step 2 — Analizza `stepSequence`
Esempi di pattern comuni:
- `RETRIEVAL -> RERANK -> GENERATION -> VALIDATION`
- tool call ripetute (retry loop)
- step mancanti (es. manca retrieval o manca validation)
- anomalia di durata (step troppo lunghi / troppo corti)

### Step 3 — Se serve dettaglio, apri `observations`
- controlla `metadata`, `status`, `level`
- rigenera con `--observation-io` solo quando necessario

---

## 9) Troubleshooting

### 9.1 Errore: `401 Unauthorized` / `Invalid credentials`
Cause tipiche:
- host sbagliato
- public/secret key sbagliate
- stai leggendo un progetto diverso da quello che scrive le trace

Azioni:
1) verifica env:
   - `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`
2) verifica in UI Langfuse che le chiavi siano del progetto corretto
3) se in metadata compare un `scope.attributes.public_key` diverso, potresti essere su progetto differente o credenziali non allineate

---

### 9.2 “No traces matched after filters”
Cause tipiche:
- `--since-hours` troppo stretto
- `--metadata-value` non identico al valore in Langfuse
- `--pattern` troppo specifico

Azioni:
1) prova senza filtri:
```bat
python -m src.utils.langfuse_trace_browser --limit 20
```
2) aggiungi filtri uno alla volta.

---

### 9.3 Observations non recuperate (warnings in export)
Se nel file export compare `warnings.observationsFetch`, significa che:
- la versione dell’SDK non espone il metodo previsto (`api.observation.get`, ecc.)
- oppure alcune observations falliscono individualmente

Azioni:
1) esegui con `--show-observations` per capire se è totale o parziale
2) controlla la versione `langfuse` installata
3) aggiornare la lista di metodi candidati in `fetch_observation(...)` nello script

---

### 9.4 File export enorme / troppo verboso
Cause tipiche:
- `--observation-io` include payload grandi (prompt, tool results, documenti RAG)

Azioni:
- rigenera senza `--observation-io`
- riduci `--limit`
- riduci `--max-observations`

---

## 10) Best practices operative
- usare sempre env var per le chiavi
- evitare export con I/O se non necessario (privacy/volume)
- per pattern recognition iniziare da `stepSequence`
- se “le trace finiscono a una certa data”, verificare:
  - se il sistema sta ancora scrivendo su Langfuse
  - se le chiavi/progetto usati in scrittura sono gli stessi della lettura

---

## 11) FAQ

### D: Dove sono gli “step di ragionamento” dell’agent?
R: Di norma nelle **observations** (spans/generations/events), non nella trace root.
Usa `--fetch-observations`.

### D: Perché `--pattern error` non trova nulla anche se vedo errori in UI?
R: `pattern` è ricerca testuale. Gli errori possono essere in campi strutturati (`status`, `level`) o in fields non inclusi nel testo cercato.
Soluzione: esportare observations e cercare su `status/level` o su metadata.

### D: Posso usare questo in CI?
R: Sì, ma attenzione a:
- non loggare la secret key
- non esportare I/O sensibile
- gestire correttamente retention e accesso ai file export
