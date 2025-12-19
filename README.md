# K8S_ClusterVigil <img src="./src/file/icon.png" align="left" width="45" height="45">

K8S ClusterVigil is an event-aware chatbot capable of answering any questions within the cluster. It interacts with the cluster, reads the event history, and provides possible resolutions to encountered issues. This tool offers real-time surveillance, enabling the detection of errors within the system. It utilizes Large Language Models (LLM) to analyze logs, aiding in the identification and debugging of detected errors. This real-time analysis allows for immediate response to issues as they occur, contributing to the efficient management and optimal functioning of Kubernetes clusters.

## Architecture

<img src="./src/file/diagram.png" align="center">

## Requirements
- Manual login to the cluster
- Installing the dependencies
```
# Use the `-r` flag (without it pip will try to install a package literally
# named "requirements.txt" and fail):
pip install -r requirements.txt
```
## Create the vector DB
```
cd src/
python embed_all.py
```

## Run the gui
```
cd src/
chainlit run cl-async.py
```

## Inspect Langfuse traces locally
The repository includes a small CLI helper for listing Langfuse traces and spotting repeated patterns.

1. Install dependencies (the `langfuse` SDK lives in `requirements.txt`):
   ```bash
   pip install -r requirements.txt
   ```
2. Export your Langfuse credentials (you can also pass them via flags):
   ```bash
   export LANGFUSE_HOST="https://your-langfuse-host"
   export LANGFUSE_PUBLIC_KEY="pk_..."
   export LANGFUSE_SECRET_KEY="sk_..."
   ```
3. Run the script from the repo root to fetch and print traces (you can also filter by environment, user, or trace name):
   ```bash
   python -m src.utils.langfuse_traces \
     --limit 20 --pattern error --environment production --show-io \
     --order-by timestamp.desc
   ```
   The `--order-by` flag must follow Langfuse's `[field].[ASC|DESC]` format (for example `timestamp.desc` or `name.ASC`). If you see a 400 error mentioning `orderBy.order`, double-check the casing and separator.

### Quick test
To confirm the script is syntactically valid without hitting Langfuse, run:
```bash
python -m compileall src/utils/langfuse_traces.py
```
