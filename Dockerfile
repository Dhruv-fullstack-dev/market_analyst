FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
COPY backend/app ./backend/app

RUN pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Shell form so $PORT expands at container start - most PaaS hosts (Render, Railway, Heroku-
# style buildpacks, Cloud Run) inject their own port and require the process to bind to it.
# Falls back to 8000 for local `docker run`/`make docker-run`.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --app-dir backend
