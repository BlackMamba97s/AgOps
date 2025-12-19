ARG IMAGE_TAG="3.11.9-bullseye"
FROM docker.io/python:${IMAGE_TAG}

ARG MICROSERVICE_NAME
ARG MICROSERVICE_VERSION

# LABELS
LABEL category="devops-image"
LABEL name=${MICROSERVICE_NAME}
LABEL author="Devops Group"
LABEL description="Microservice ${MICROSERVICE_NAME} image"
LABEL versione=${MICROSERVICE_VERSION}

WORKDIR /app/src

RUN apt update && apt install -y vim

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY requirements_container.txt .
RUN pip install --no-cache-dir -r requirements_container.txt


RUN cp /usr/local/lib/python3.11/site-packages/chromadb/__init__.py /usr/local/lib/python3.11/site-packages/chromadb/__init__copy.py && \
    echo "__import__('pysqlite3')\nimport sys\nsys.modules['sqlite3'] = sys.modules.pop('pysqlite3')\n" > /usr/local/lib/python3.11/site-packages/chromadb/__init__.py && \
    cat /usr/local/lib/python3.11/site-packages/chromadb/__init__copy.py >> /usr/local/lib/python3.11/site-packages/chromadb/__init__.py && \
    rm /usr/local/lib/python3.11/site-packages/chromadb/__init__copy.py

COPY src/ .


ENV OTEL_TRACES_EXPORTER=none
ENV OTEL_EXPORTER_OTLP_ENDPOINT=""
ENV LANGFUSE_PUBLIC_KEY=""
ENV LANGFUSE_SECRET_KEY=""
ENV LANGFUSE_HOST=""
ENV DISABLE_OTEL=true 

ENTRYPOINT [ "python" ]

CMD ["./main.py"]
