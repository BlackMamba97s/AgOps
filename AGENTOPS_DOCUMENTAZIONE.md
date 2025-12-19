# Documentazione dettagliata AgentOps / ClusterVigil

Questo documento descrive l'architettura osservabile nel repository `AgOps`, articolata in due sezioni distinte:

1. **ClusterVigil (applicazione principale)**: chatbot event-aware per Kubernetes, con API FastAPI e interfaccia Chainlit.
2. **agentops_library-main (libreria separata)**: raccolta di script e pipeline CI/CD per generare RAG e pubblicare microservizi.

Ogni sezione riporta flussi, componenti e possibili modalità di integrazione tra i due mondi.

## 1) ClusterVigil

### Obiettivo e interfacce
- Espone un'API FastAPI per ricevere richieste (`/call_clustervigil`) e inoltrarle a un agente LangChain; monta anche Chainlit su `/home` per l'uso interattivo, eseguendo Uvicorn su `0.0.0.0:8000`.【F:src/main.py†L1-L47】
- La UI Chainlit (`src/cl-async.py`) gestisce sessioni utente, streaming degli step dell'agente e tracciamento su Langfuse tramite `CallbackHandler` configurato via variabili d'ambiente.【F:src/cl-async.py†L1-L43】【F:src/cl-async.py†L23-L74】

### Pipeline conversazionale
- **Agente**: `KubeVigilAgent` costruisce un agente LangChain con strumenti e prompt dedicati, memorizza la conversazione (finestra di 5 messaggi) e offre metodi sincroni/asincroni per streaming dei risultati.【F:src/agents/KubeVigiliAgent/agent.py†L1-L54】
- **LLM**: creato da `llm.llm_creator.create_new_llm()` (non mostrato qui), fornito al costruttore `create_openai_tools_agent` insieme al prompt `prompt3.py` e agli strumenti caricati.【F:src/agents/KubeVigiliAgent/agent.py†L15-L26】
- **Strumenti**: `KubernetesSmeTool` espone un retriever LangChain che interroga un archivio vettoriale con documentazione Kubernetes generale (non dati di cluster). Il retriever usa la classe `KubernetesSme`, che a sua volta deriva da `ChromaSme` per accedere a un indice Chroma persistente.【F:src/tools/kubernetes_sme/tool.py†L1-L17】【F:src/embedding/sme/kubernetes_sme.py†L1-L10】
- **Base conoscenze**: `ChromaSme` istanzia il vettorial store Chroma usando embeddings Azure OpenAI e path configurati tramite variabili d'ambiente (`VECTORIAL_DB_PATH`, `AZURE_*`). Include helper per caricare web, sitemap e markdown in batch, gestendo rate-limit OpenAI e persistenza su disco.【F:src/embedding/chroma.py†L1-L59】【F:src/embedding/chroma.py†L61-L89】
- **Tracing**: sia API che UI configurano Langfuse per tracciare ogni richiesta; l'handler viene passato nel `RunnableConfig` dell'agente per includere metadati richieste.【F:src/main.py†L1-L44】【F:src/cl-async.py†L9-L42】

### Flusso di esecuzione (API)
1. FastAPI riceve `ClusterVigilRequest` contenente input e `request_name` opzionale.【F:src/main.py†L21-L38】
2. Instanzia `KubeVigilAgent` e costruisce `input_dict` con il prompt utente.
3. Chiama `agent.istream(...)` per ottenere risultati streaming; concatena i chunk con campo `output` e restituisce risposta JSON, gestendo eccezioni con HTTP 500.【F:src/main.py†L38-L47】

### Flusso di esecuzione (Chainlit)
1. `@cl.on_chat_start` crea e memorizza un `KubeVigilAgent` per la sessione utente.【F:src/cl-async.py†L19-L34】
2. `@cl.on_message` invoca `agent.get_agent().astream(...)` e gestisce streaming a tre livelli: azioni degli strumenti, osservazioni/risultati degli step, output finale, inviandoli come step Chainlit nidificati.【F:src/cl-async.py†L35-L74】

### Ipotesi operative
- Il tool `KubernetesSme` fornisce solo documentazione “static” (no interrogazione cluster). Altri tool o prompt (non mostrati) potrebbero aggiungere accessi runtime al cluster.
- Il caricamento degli embeddings dipende da variabili d’ambiente Azure e dal percorso `VECTORIAL_DB_PATH`; in assenza di questi valori, l’istanza di `ChromaSme` potrebbe fallire in fase di import.
- La memoria finestrata (k=5) implica che il contesto recente guida l’agente; per sessioni lunghe conviene un riepilogo periodico per evitare perdita di informazioni meno recenti.

## 2) agentops_library-main (libreria separata)

### Scopo e struttura
Libreria staccata (probabilmente clonata da un repository interno) che raccoglie script di automazione CI/CD e provisioning RAG. Non viene importata dal codice ClusterVigil, ma può fungere da toolbox DevOps.

- **Script Groovy (cartella `vars/`)**: funzioni condivise Jenkins per pipeline CI/CD Python/RAG. Esempi: `CI_Python.groovy` clona il repo `agentops_library`, costruisce e pubblica immagini container; `CI_RAG.groovy`, `createRAG.groovy` e `evaluation.groovy` orchestrano pipeline di generazione e valutazione RAG; `CD_Python_*` gestiscono deploy e rollback con immagini `registry.liquid-reply.net/agentops/...`.【F:agentops_library-main/vars/CI_Python.groovy†L86-L168】【F:agentops_library-main/vars/CI_RAG.groovy†L95-L117】【F:agentops_library-main/vars/CD_Python_prod.groovy†L300-L332】
- **Job Kubernetes (manifests/)**: template YAML per PVC (`pvc-prompt.yaml`, `pvc-rag.yaml`) e Job batch (`job-azure-prompt.yaml`, `job-azure-rag.yaml`) utili a generare prompt ed embeddings in ambienti Azure/Kubernetes.【F:agentops_library-main/manifests/job-azure-rag.yaml†L1-L42】【F:agentops_library-main/manifests/pvc-prompt.yaml†L1-L20】
- **Utility Python**: `RAG/file2chroma.py` converte directory di JSON embedding in collezioni Chroma, verificando duplicati ed eseguendo ingest con progress bar e gestione errori; `resources/configRepo.py` probabilmente gestisce configurazioni repository (placeholder), mentre `scripts/get_new_version.py` e `get_old_version.py` calcolano versioni per pipeline (non mostrati qui).【F:agentops_library-main/RAG/file2chroma.py†L1-L49】
- **Valutazione**: `evaluation/test.py` e `debug.py` (non analizzati in dettaglio) suggeriscono workflow di scoring RAG dentro Jenkins.

### Possibili integrazioni con ClusterVigil
- **Condivisione di pipeline**: le pipeline CI/CD Groovy fanno riferimento a immagini `agentops/<MICROSERVICE_NAME>` e a un repository `agentops_library`; potrebbero essere riusate per build/deploy di ClusterVigil se si allineano nomi e registry.
- **Ingestione RAG**: lo script `file2chroma.py` può popolare il DB vettoriale usato da `ChromaSme`, facilitando la creazione dell’indice `k8sindex` con dataset esterni.
- **Kubernetes manifests**: i Job e le PVC possono essere adattati per eseguire batch di embedding o prompt-tuning per ClusterVigil su cluster Kubernetes.

### Evidenza di uso diretto
Non risultano import o riferimenti alla cartella `agentops_library-main` nel codice di ClusterVigil; le uniche occorrenze `agentops` sono interne ai file Groovy della libreria stessa. È quindi plausibile che la libreria serva come toolkit DevOps separato o come submodule portato localmente, più che come dipendenza runtime.【F:agentops_library-main/vars/CI_Python.groovy†L86-L168】【F:src/main.py†L1-L47】

## Sintesi
- **ClusterVigil** fornisce un agente conversazionale basato su LangChain e Chainlit, con recupero documentale via Chroma e tracing Langfuse.
- **agentops_library-main** offre pipeline Jenkins, manifest Kubernetes e utility Python per costruire, distribuire e generare dataset RAG.
- Al momento non esiste un collegamento diretto nel codice, ma la libreria può diventare parte del ciclo di build/deploy o del popolamento del database vettoriale richiesto da ClusterVigil.
