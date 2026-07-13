FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies in a cached layer before copying source
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# Copy application source
COPY . .

# Frontend (Next.js) on 3000, backend (FastAPI/WebSocket) on 8001
EXPOSE 3000 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/ping')"

CMD ["uv", "run", "reflex", "run", "--env", "prod"]
