# K8S_ClusterVigil <img src="./src/file/icon.png" align="left" width="45" height="45">

K8S ClusterVigil is an event-aware chatbot capable of answering any questions within the cluster. It interacts with the cluster, reads the event history, and provides possible resolutions to encountered issues. This tool offers real-time surveillance, enabling the detection of errors within the system. It utilizes Large Language Models (LLM) to analyze logs, aiding in the identification and debugging of detected errors. This real-time analysis allows for immediate response to issues as they occur, contributing to the efficient management and optimal functioning of Kubernetes clusters.

## Architecture

<img src="./src/file/diagram.png" align="center">

## Requirements
- Manual login to the cluster
- Installing the dependencies
```
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