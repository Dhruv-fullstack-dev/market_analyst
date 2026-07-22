VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
RUFF := $(VENV)/bin/ruff
UVICORN := $(VENV)/bin/uvicorn
STREAMLIT := $(VENV)/bin/streamlit

.PHONY: install dev frontend test test-cov lint format docker-build docker-run clean

install:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

dev:
	$(UVICORN) app.main:app --reload --app-dir backend

frontend:
	$(STREAMLIT) run frontend/streamlit_app.py

test:
	$(PYTEST)

test-cov:
	$(PYTEST) --cov=app --cov-report=term-missing

lint:
	$(RUFF) check backend frontend pyproject.toml

format:
	$(RUFF) format backend frontend
	$(RUFF) check --fix backend frontend

docker-build:
	docker build -t market-analyst:latest .

docker-run:
	docker run --rm -p 8000:8000 --env-file .env market-analyst:latest

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf .pytest_cache .coverage htmlcov dump.log*
