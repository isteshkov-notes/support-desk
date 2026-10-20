FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.14 /uv /uvx /bin/
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev
COPY . .
RUN uv sync --locked --no-dev --no-editable
CMD ["/app/.venv/bin/uvicorn", "supportdesk.main:app", "--host", "0.0.0.0", "--port", "8000"]