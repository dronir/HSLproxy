FROM tiangolo/uvicorn-gunicorn-fastapi:python3.8-slim

COPY ./app /app
COPY Pipfile Pipfile

RUN pip install pipenv 

RUN pipenv lock
RUN pipenv install --system

