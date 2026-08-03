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
	@echo "up: conteinerização chega na SPEC-016 — alvo reservado, sem efeito ainda"

down:
	@echo "down: conteinerização chega na SPEC-016 — alvo reservado, sem efeito ainda"
