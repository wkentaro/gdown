set shell := ["bash", "-eu", "-o", "pipefail", "-c"]
set script-interpreter := ["bash", "-eu", "-o", "pipefail"]
set positional-arguments
set default-list
set minimum-version := "1.58.0"

num_processes := env("NUM_PROCESSES", "auto")

# Setup the development environment
setup:
    uv sync

# Format code
format:
    uv run ruff format
    uv run ruff check --fix
    git ls-files "*.toml" | xargs uv run taplo fmt
    git ls-files "*.md" | xargs uv run mdformat
    git ls-files "*.yml" "*.yaml" | xargs uv run yamlfix

# Lint code
lint:
    uv run ruff format --check
    uv run ruff check
    git ls-files "*.py" ":!gdown/_vendor/**" | xargs uv run gruff check
    uv run ty check --no-progress
    git ls-files "*.toml" | xargs uv run taplo fmt --check
    git ls-files "*.md" | xargs uv run mdformat --check
    git ls-files "*.yml" "*.yaml" | xargs uv run yamlfix --check
    uv run typos

# Regenerate the vendored yt-dlp cookie module
vendor:
    uv run python scripts/vendor_ytdlp_cookies.py

# Run tests
test *args:
    uv run pytest -v tests/ --numprocesses={{ quote(num_processes) }} "$@"

# Prepare a release
[script]
release version="":
    version="$1"
    if test -z "$version"; then
        fragments=$(find changelog.d -maxdepth 1 -type f \( -name "*.added.md" -o -name "*.changed.md" -o -name "*.deprecated.md" -o -name "*.removed.md" -o -name "*.fixed.md" -o -name "*.security.md" \))
        latest=$(git tag --sort=-v:refname |
            grep -E "^v[0-9]+\.[0-9]+\.[0-9]+$" | head -1)
        if test -n "$fragments" && test -n "$latest"; then
            version=${latest#v}
            major=${version%%.*}
            remainder=${version#*.}
            minor=${remainder%%.*}
            patch=${remainder#*.}
            if grep -q '\*\*Breaking:\*\*' $fragments; then
                next=$((major + 1)).0.0
            elif find changelog.d -maxdepth 1 -type f \( -name "*.added.md" -o -name "*.changed.md" -o -name "*.deprecated.md" -o -name "*.removed.md" \) | grep -q .; then
                next=$major.$((minor + 1)).0
            else
                next=$major.$minor.$((patch + 1))
            fi
            echo "suggested: just release $next" >&2
        else
            echo "usage: just release X.Y.Z" >&2
        fi
        echo "recent releases:" >&2
        git tag --sort=-v:refname | head -5 | sed "s/^/  /" >&2
        exit 1
    fi
    uv run towncrier build --yes --version "$version"
    uv run mdformat CHANGELOG.md
    git add CHANGELOG.md
    printf "\n\033[1;32mNext steps\033[0m\n"
    echo "  git commit -am \"chore: prep $version release\""
    echo "  git tag v$version"
    echo "  git push origin main v$version"
