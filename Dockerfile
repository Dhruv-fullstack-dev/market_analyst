FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
COPY backend/app ./backend/app

RUN pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# backend/app/main.py lands in Phase 4; this is the entrypoint once it exists.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "backend"]
