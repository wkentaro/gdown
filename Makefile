ifneq ($(OS),Windows_NT)
	SHELL := bash
endif

.PHONY: help setup format lint test
.DEFAULT_GOAL := help

PYTEST_ARGS ?= --numprocesses=auto

define exec
	@uv run --no-sync python -c "print('\033[1;36m$(1)\033[0m')"
	@$(1)
endef

help:
	@uv run --no-sync python -c "import re; lines=open('Makefile').read().splitlines(); print('\033[1;32mAvailable targets:\033[0m'); [print(f'  \033[1;36m{m.group(1):<20s}\033[0m {m.group(2)}') for l in lines if (m:=re.match(r'^([a-zA-Z_-]+):.*?# (.+)$$',l))]"

setup:  # Setup the development environment
	$(call exec,uv sync)

format:  # Format code
	$(call exec,uv run ruff format)
	$(call exec,uv run ruff check --fix)
	$(call exec,uv run taplo fmt $(shell git ls-files "*.toml"))
	$(call exec,uv run mdformat $(shell git ls-files "*.md"))
	$(call exec,uv run yamlfix $(shell git ls-files "*.yml" "*.yaml"))

lint:  # Lint code
	$(call exec,uv run ruff format --check)
	$(call exec,uv run ruff check)
	$(call exec,uv run ty check --no-progress)
	$(call exec,uv run taplo fmt --check $(shell git ls-files "*.toml"))
	$(call exec,uv run mdformat --check $(shell git ls-files "*.md"))
	$(call exec,uv run yamlfix --check $(shell git ls-files "*.yml" "*.yaml"))
	$(call exec,uv run typos)

test:  # Run tests
	$(call exec,uv run pytest -v tests/ $(PYTEST_ARGS))
