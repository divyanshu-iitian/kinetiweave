FROM node:22-bookworm-slim AS studio
WORKDIR /workspace/apps/studio
COPY apps/studio/package*.json ./
RUN npm ci
COPY apps/studio/ ./
RUN npm run build

FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    KINETIWEAVE_HOST=0.0.0.0 \
    KINETIWEAVE_PORT=7860 \
    KINETIWEAVE_DATA_DIR=/data \
    KINETIWEAVE_STUDIO_DIST=/app/apps/studio/dist
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
COPY --from=studio /workspace/apps/studio/dist ./apps/studio/dist
RUN python -m pip install --no-cache-dir ".[rl]"
RUN mkdir -p /data && chmod 777 /data
EXPOSE 7860
CMD ["kinetiweave", "serve", "--host", "0.0.0.0", "--port", "7860"]
