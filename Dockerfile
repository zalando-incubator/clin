ARG python_version="3.9"

FROM python:${python_version}-slim as build

RUN pip install poetry

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN poetry install

COPY . .

ARG clin_version="1.0.dev0"
RUN sed -i "s/\"1.0.dev0\"/\"${clin_version}\"/g" clin/__init__.py \
 && poetry version $clin_version \
 && poetry run black clin --check \
 && poetry run pytest \
 && poetry build

ENTRYPOINT [ "poetry" ]


FROM python:${python_version}-slim as venv
COPY --from=build /app/dist /app/dist
ARG clin_version="1.0.dev0"
ENV PATH="/opt/venv/bin:$PATH"
RUN python -m venv /opt/venv \
 && pip install /app/dist/clin-${clin_version}-py3-none-any.whl


FROM python:${python_version}-slim as cli
COPY --from=venv /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENTRYPOINT [ "clin" ]
CMD [ "--help" ]
