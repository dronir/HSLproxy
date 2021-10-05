FROM tiangolo/uvicorn-gunicorn-fastapi:python3.8-slim

RUN pip install poetry

WORKDIR /project
COPY poetry.lock .
COPY pyproject.toml .
RUN poetry config virtualenvs.create false
RUN poetry install --no-root --no-dev
COPY ./hslproxy /app
