<div align="center">
<h1>gdown</h1>

[![PyPI](https://img.shields.io/pypi/v/gdown.svg)](https://pypi.org/project/gdown/)
[![Python](https://img.shields.io/pypi/pyversions/gdown.svg)](https://pypi.org/project/gdown/)
[![Build](https://github.com/wkentaro/gdown/actions/workflows/test.yml/badge.svg)](https://github.com/wkentaro/gdown/actions/workflows/test.yml)
[![License](https://img.shields.io/pypi/l/gdown.svg)](https://pypi.org/project/gdown/)

Google Drive public file/folder downloader when curl/wget fails.

<img src="https://github.com/wkentaro/gdown/raw/main/assets/cli.png" width="80%">
<img src="https://github.com/wkentaro/gdown/raw/main/assets/python.png" width="80%">
</div>

## Why?

Downloading public files from Google Drive with curl or wget doesn't work —
Google serves a confirmation page for large files, and the URL formats are a mess.

gdown gets around that:

- Skips the virus-scan confirmation page so large downloads actually finish
- Downloads folders recursively
- Exports Google Docs/Sheets/Slides as PDF, DOCX, CSV, etc.
- Resumes partial downloads with `--continue`
- Also works with plain HTTP/HTTPS URLs as a curl/wget replacement

## Install

Requires Python 3.10 or later.

```bash
pip install gdown
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv tool install gdown
```

## Quick start

```bash
# Just paste a Google Drive URL
gdown https://drive.google.com/uc?id=1l_5RK28JRL19wpT22B-DY9We3TVXnnQQ

# Or copy-paste a share link directly
gdown 'https://drive.google.com/file/d/0B9P1L--7Wd2vU3VUVlFnbTgtS2c/view?usp=sharing'
```

## Usage

### CLI

#### Files

```bash
# Download by URL
gdown https://drive.google.com/uc?id=1l_5RK28JRL19wpT22B-DY9We3TVXnnQQ

# Download by file ID
gdown 1l_5RK28JRL19wpT22B-DY9We3TVXnnQQ

# Download from a share link
gdown 'https://drive.google.com/file/d/0B9P1L--7Wd2vU3VUVlFnbTgtS2c/view?usp=sharing'

# Save to a specific path
gdown https://drive.google.com/uc?id=0B9P1L--7Wd2vU3VUVlFnbTgtS2c -O /tmp/spam.txt

# Resolve the filename (with its real extension) without downloading
gdown https://drive.google.com/uc?id=0B9P1L--7Wd2vU3VUVlFnbTgtS2c --json
```

The `--json` output is an array of `{url, path}` entries, where `path` is the
filename Google Drive reports. This lets you choose a name while keeping the
original extension:

```bash
url="https://drive.google.com/uc?id=0B9P1L--7Wd2vU3VUVlFnbTgtS2c"
filename=$(gdown "$url" --json | jq -r '.[0].path')
gdown "$url" -O "my_name.${filename##*.}"
```

#### Folders

```bash
# Download an entire folder
gdown https://drive.google.com/drive/folders/15uNXeRBIhVvZJIhL4yTw4IsStMhUaaxl -O /tmp/folder --folder

# List folder contents as a JSON array (each entry has url and path)
gdown https://drive.google.com/drive/folders/15uNXeRBIhVvZJIhL4yTw4IsStMhUaaxl --folder --json

# Filter by path and download matches
gdown https://drive.google.com/drive/folders/15uNXeRBIhVvZJIhL4yTw4IsStMhUaaxl --folder --json \
  | jq -r '.[] | select(.path | test("shad")) | .url' \
  | xargs -n1 gdown
```

#### Google Docs, Sheets, Slides

```bash
# Download a Google Slides file (default: pptx)
gdown "https://docs.google.com/presentation/d/15umvZKlsJ3094HNg5S4vJsIhxcFlyTeK/edit?usp=sharing"

# Export as PDF instead
gdown "https://docs.google.com/presentation/d/15umvZKlsJ3094HNg5S4vJsIhxcFlyTeK/edit" --format pdf
```

Default export formats: Docs → `docx`, Sheets → `xlsx`, Slides → `pptx`.

#### Resume, speed limit, proxy

```bash
# Resume a partially downloaded file
gdown https://drive.google.com/uc?id=1l_5RK28JRL19wpT22B-DY9We3TVXnnQQ --continue

# Limit download speed
gdown https://drive.google.com/uc?id=1l_5RK28JRL19wpT22B-DY9We3TVXnnQQ --speed 10MB

# Download via proxy
gdown https://drive.google.com/uc?id=1l_5RK28JRL19wpT22B-DY9We3TVXnnQQ --proxy http://proxy:8080
```

#### Other options

```bash
# Skip TLS certificate verification
gdown https://drive.google.com/uc?id=1l_5RK28JRL19wpT22B-DY9We3TVXnnQQ --no-check-certificate

# Don't use cookies from ~/.cache/gdown/cookies.txt
gdown https://drive.google.com/uc?id=1l_5RK28JRL19wpT22B-DY9We3TVXnnQQ --no-cookies

# Use a custom User-Agent
gdown https://drive.google.com/uc?id=1l_5RK28JRL19wpT22B-DY9We3TVXnnQQ --user-agent "MyApp/1.0"
```

#### Pipe to stdout

```bash
gdown https://github.com/wkentaro/gdown/archive/refs/tags/v4.0.0.tar.gz -O - --quiet | tar zxvf -
```

#### Any URL

gdown also works with regular URLs, not just Google Drive:

```bash
gdown https://httpbin.org/ip -O ip.json
```

> [!NOTE]
> For Google Drive URLs, gdown automatically extracts the file ID and downloads
> the actual file. Use curl or wget to download the raw HTML page instead.

### Python

```python
import gdown

# Download a file
url = "https://drive.google.com/uc?id=1l_5RK28JRL19wpT22B-DY9We3TVXnnQQ"
gdown.download(url=url, output="fcn8s_from_caffe.npz")

# Download by file ID
gdown.download(id="0B9P1L--7Wd2vNm9zMTJWOGxobkU", output="output.npz")

# Download from a share link
url = "https://drive.google.com/file/d/0B9P1L--7Wd2vNm9zMTJWOGxobkU/view?usp=sharing"
gdown.download(url=url, output="output.npz")

# Download with hash verification and caching
gdown.cached_download(
    url=url,
    path="output.npz",
    hash="md5:fa837a88f0c40c513d975104edf3da17",
    postprocess=gdown.extractall,
)

# Track download progress
def on_progress(bytes_so_far: int, bytes_total: int | None) -> None:
    if bytes_total is not None:
        print(f"\r{bytes_so_far / bytes_total * 100:.1f}%", end="")

gdown.download(url=url, output="output.npz", quiet=True, progress=on_progress)

# Download a folder
url = "https://drive.google.com/drive/folders/15uNXeRBIhVvZJIhL4yTw4IsStMhUaaxl"
gdown.download_folder(url=url)

# Download a folder by ID
gdown.download_folder(id="15uNXeRBIhVvZJIhL4yTw4IsStMhUaaxl")
```

## FAQ

### "Permission Denied" error

Make sure the file sharing is set to "Anyone with the link".

### Download still fails even with "Anyone with the link"

Google throttles downloads when too many people access the same file.
If you can still open the file in your browser, try exporting cookies:

1. Install a browser extension like [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
1. Export `cookies.txt` and move it to `~/.cache/gdown/cookies.txt`
1. Run the download again

Once the file is in place, gdown loads it automatically (no extra flags needed).

### Download stops after ~1 hour

Google Drive terminates connections after approximately 1 hour for large files.
Use `--continue` to resume, and retry until the download completes:

```bash
gdown --continue https://drive.google.com/uc?id=<file_id>
```

### Can I use gdown for non-Google-Drive URLs?

Yes. It works with any public HTTP/HTTPS URL.

## Contributing

```bash
git clone https://github.com/wkentaro/gdown.git
cd gdown
make setup   # install dependencies
make test    # run tests
make lint    # run linters
```

## License

MIT ([LICENSE](https://github.com/wkentaro/gdown/blob/main/LICENSE))
