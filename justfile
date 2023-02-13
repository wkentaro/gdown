version := `python -c "from gdown.__init__ import __version__; print(__version__)"`

default:
  @just --summary --unsorted

publish: clean
  @if [ "$(git rev-parse --abbrev-ref HEAD)" != "main" ]; then exit 1; fi
  @git push origin main
  @python -c 'import github2pypi' &>/dev/null || (echo "\"pip install github2pypi\"?"; exit 1)
  @python -c 'import build' &>/dev/null || (echo "\"pip install build\"?"; exit 1)
  @which twine &>/dev/null || (echo "\"pip install twine\"?"; exit 1)
  @git tag "v{{version}}" && git push origin "v{{version}}"
  python -m build --sdist --wheel .
  twine upload dist/*

clean:
  @find . | grep -E "(__pycache__|\.pyc|\.pyo$)" | xargs rm -rf
  @rm -rf src/*.egg-info/ build/ dist/ .tox/

format:
  isort .
  black .

lint:
  flake8 .
  black --check .
  isort --check .

test:
  @python -m pytest -sxv tests/
