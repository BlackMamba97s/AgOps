ARG IMAGE_TAG="3.11.9-bullseye"
FROM python:${IMAGE_TAG} AS builder

ARG GIT_USER
ARG GIT_PASS
ARG POETRY_REPOS_JSON
ARG POETRY_REPOS_USER
ARG POETRY_REPOS_PASSWORD

RUN git config --global url."https://${GIT_USER}:${GIT_PASS}@gitlab.liquid-reply.net".insteadOf "https://gitlab.liquid-reply.net"

WORKDIR /app/src

RUN apt update && apt install -y curl vim && \
    curl -sSL https://install.python-poetry.org | python3 - && \
    ln -s /root/.local/bin/poetry /usr/local/bin/poetry

COPY pyproject.toml poetry.lock* ./
COPY configRepo.py ./
RUN python3 configRepo.py

ENV POETRY_VIRTUALENVS_CREATE=false

RUN poetry install --no-root --no-interaction