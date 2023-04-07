FROM python:3.10.10

COPY ./pip.conf /root/.pip/

RUN pip install poetry

WORKDIR /home/app/

COPY ./pyproject.toml ./
COPY ./poetry.lock ./

RUN poetry install --no-root

COPY ./ ./

WORKDIR /home/app/nkgame/
