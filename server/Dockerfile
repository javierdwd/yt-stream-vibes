FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl unzip ca-certificates proxychains4 \
    && rm -rf /var/lib/apt/lists/*

# yt-dlp YouTube extractor needs a JS runtime (same as local: Deno).
ENV DENO_INSTALL=/usr/local
RUN curl -fsSL https://deno.land/install.sh | sh \
    && ln -sf /usr/local/bin/deno /usr/bin/deno

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY src ./src

RUN mkdir -p /data/cache

ENV PATH="/app/.venv/bin:/usr/local/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/data/cache/huggingface \
    XDG_CACHE_HOME=/data/cache

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
