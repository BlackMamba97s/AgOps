## DeepEval Trace Judge (Pattern Recognition)

Questo modulo valuta trace Langfuse tramite DeepEval con un approccio LLM-as-a-judge.
L'input al giudice è il *summary* della trace (input/output, osservazioni normalizzate, step sequence),
così da poter giudicare i pattern di comportamento osservabili.

### Metriche disponibili

Ogni trace riceve **sottopunteggi** separati (con motivazione) più un **overall_score** che è la media
dei sottopunteggi disponibili.

1. **ToolUsage**
   - **Cosa valuta**: uso corretto e pertinente dei tool rispetto al task.
   - **Criteri**:
     - tool usati quando servono, senza overuse o invocazioni inutili
     - tool output rilevanti per l'output finale

2. **StepsEfficiency**
   - **Cosa valuta**: efficienza del numero di step e della sequenza.
   - **Criteri**:
     - assenza di passaggi ridondanti
     - sequenza proporzionata alla complessità del task

3. **Coherence**
   - **Cosa valuta**: coerenza tra input, osservazioni e output finale.
   - **Criteri**:
     - output supportato dalle osservazioni
     - assenza di contraddizioni o allucinazioni

4. **OverallPattern**
   - **Cosa valuta**: sintesi complessiva del pattern, combinando tool usage, efficienza e coerenza.
   - **Criteri**:
     - pattern stabile e coerente
     - risposta finale chiara e supportata

### Output atteso

Il file di output contiene un oggetto per trace con:
- `subscores`: punteggi e motivazioni per ogni metrica
- `overall_score`: media dei sottopunteggi disponibili
- `overall_reason`: descrizione sintetica del calcolo

### Esempio di esecuzione

```bash
python test_pattern_recognition/langfuse_trace_judge_deepeval.py \
  --input langfuse_export.json \
  --out langfuse_trace_judge_deepeval.json
```
