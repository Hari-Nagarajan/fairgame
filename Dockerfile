FROM python:3.8

WORKDIR /app

COPY Pipfile /app

RUN pip install pipenv && pipenv lock
RUN pipenv install --system --deploy

COPY . /app
