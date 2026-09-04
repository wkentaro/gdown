ifneq ($(OS),Windows_NT)
	SHELL := bash
endif

.PHONY: help setup format lint test vendor release
.DEFAULT_GOAL := help

PYTEST_ARGS ?= --numprocesses=auto

define exec
	@uv run --no-sync python -c "import sys;print('\033[1;36m'+' '.join(sys.argv[1:])+'\033[0m')" $(1)
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
	$(call exec,uv run gruff check $(shell git ls-files "*.py" ":!gdown/_vendor/_ytdlp_cookies.py"))
	$(call exec,uv run ty check --no-progress)
	$(call exec,uv run taplo fmt --check $(shell git ls-files "*.toml"))
	$(call exec,uv run mdformat --check $(shell git ls-files "*.md"))
	$(call exec,uv run yamlfix --check $(shell git ls-files "*.yml" "*.yaml"))
	$(call exec,uv run typos)

vendor:  # Regenerate the vendored yt-dlp cookie module
	$(call exec,uv run python scripts/vendor_ytdlp_cookies.py)

test:  # Run tests
	$(call exec,uv run pytest -v tests/ $(PYTEST_ARGS))

release:  # Prepare a release: make release VERSION=X.Y.Z
	@test -n "$(VERSION)" || { \
		fragments=$$(find changelog.d -maxdepth 1 -type f \( \
			-name "*.added.md" -o -name "*.changed.md" -o \
			-name "*.deprecated.md" -o -name "*.removed.md" -o \
			-name "*.fixed.md" -o -name "*.security.md" \)); \
		latest=$$(git tag --sort=-v:refname | \
			grep -E "^v[0-9]+\.[0-9]+\.[0-9]+$$" | head -1); \
		if test -n "$$fragments" && test -n "$$latest"; then \
			version=$${latest#v}; \
			major=$${version%%.*}; \
			remainder=$${version#*.}; \
			minor=$${remainder%%.*}; \
			patch=$${remainder#*.}; \
			if grep -q '\*\*Breaking:\*\*' $$fragments; then \
				next=$$((major + 1)).0.0; \
			elif find changelog.d -maxdepth 1 -type f \( \
				-name "*.added.md" -o -name "*.changed.md" -o \
				-name "*.deprecated.md" -o -name "*.removed.md" \) | grep -q .; then \
				next=$$major.$$((minor + 1)).0; \
			else \
				next=$$major.$$minor.$$((patch + 1)); \
			fi; \
			echo "suggested: make release VERSION=$$next" >&2; \
		else \
			echo "usage: make release VERSION=X.Y.Z" >&2; \
		fi; \
		echo "recent releases:" >&2; \
		git tag --sort=-v:refname | head -5 | sed "s/^/  /" >&2; \
		exit 1; \
	}
	$(call exec,uv run towncrier build --yes --version $(VERSION))
	$(call exec,uv run mdformat CHANGELOG.md && git add CHANGELOG.md)
	@printf "\n\033[1;32mNext steps\033[0m\n"
	@echo "  git commit -am \"chore: prep $(VERSION) release\""
	@echo "  git tag v$(VERSION)"
	@echo "  git push origin main v$(VERSION)"
