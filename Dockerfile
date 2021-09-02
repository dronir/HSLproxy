FROM tiangolo/uvicorn-gunicorn-fastapi:python3.8-slim

COPY ./app /app
COPY Pipfile Pipfile
COPY Pipfile.lock Pipfile.lock

RUN pip install --upgrade pip
RUN pip install pipenv 

RUN pipenv install --system --deploy
