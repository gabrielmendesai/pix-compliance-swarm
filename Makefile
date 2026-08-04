.PHONY: install run test lint up down

install:
	python -m venv .venv
	.venv/bin/pip install -e ".[dev]" || .venv/Scripts/pip install -e ".[dev]"

run:
	python -m pix_compliance.agents.orchestrator_agent

test:
	pytest

lint:
	ruff check .

up:
	docker compose up -d

down:
	docker compose down
