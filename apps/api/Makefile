.PHONY: setup dev build test lint clean

VENV    := .venv
PIP     := $(VENV)/bin/pip
UVICORN := $(VENV)/bin/uvicorn
PYTEST  := $(VENV)/bin/pytest
RUFF    := $(VENV)/bin/ruff
SECRETS := ~/.secrets/kanban-treemap.env

$(VENV)/bin/activate: pyproject.toml
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"
	touch $(VENV)/bin/activate

setup: $(VENV)/bin/activate

dev: $(VENV)/bin/activate
	dotenvx run -f $(SECRETS) -- sh -c 'PORT=$${PORT_API} $(UVICORN) kanban_treemap.main:app --reload --port $${PORT_API}'

build: $(VENV)/bin/activate
	uv build

test: $(VENV)/bin/activate
	$(PYTEST) -q

lint: $(VENV)/bin/activate
	$(RUFF) check src/ tests/

clean:
	rm -rf $(VENV) .pytest_cache dist src/kanban_treemap/static
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
