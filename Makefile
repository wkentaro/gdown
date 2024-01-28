all:
	@echo '## Make commands ##'
	@echo
	@$(MAKE) -pRrq -f $(lastword $(MAKEFILE_LIST)) : 2>/dev/null | awk -v RS= -F: '/^# File/,/^# Finished Make data base/ {if ($$1 !~ "^[#.]") {print $$1}}' | sort | egrep -v -e '^[^[:alnum:]]' -e '^$@$$' | xargs

lint:
	mypy --package gdown
	ruff format --check
	ruff check

format:
	ruff format
	ruff check --fix

test:
	python -m pytest -n auto -v tests

clean:
	rm -rf build dist *.egg-info

build: clean
	python -m build --sdist --wheel

upload: build
	python -m twine upload dist/gdown-*

publish: build upload
