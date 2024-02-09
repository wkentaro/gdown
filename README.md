<div align="center">
  <h1>gdown</h1>
  <p><b>Google Drive Public File Downloader when Curl/Wget Fails</b></p>
  <img src="https://github.com/wkentaro/gdown/raw/main/.readme/cli.png" width="80%">
  <img src="https://github.com/wkentaro/gdown/raw/main/.readme/python.png" width="80%">
  <br>
  <br>
</div>


*Gdown* downloads a public file/folder from Google Drive.

*Gdown* provides what curl/wget doesn't for Google Drive:
- **Skip the security notice** allowing you to download large files (curl/wget fails);
- **Recursive download** of files in a folder (maximum 50 files per folder);
- **Specify download file format** for Google Slides/Sheet/Docs like PDF/XML/CSV.


## Installation

<a href="https://pypi.org/project/gdown"><img src="https://img.shields.io/pypi/pyversions/gdown.svg"></a>
<a href="https://pypi.python.org/pypi/gdown"><img src="https://img.shields.io/pypi/v/gdown.svg"></a>

```bash
pip install gdown

# to upgrade
pip install --upgrade gdown
```


## Usage

### via Command Line

```bash
$ gdown --help
usage: gdown [-h] [-V] [-O OUTPUT] [-q] [--fuzzy] [--id] [--proxy PROXY]
             [--speed SPEED] [--no-cookies] [--no-check-certificate]
             [--continue] [--folder] [--remaining-ok]
             url_or_id
...

$ # a large file (~500MB)
$ gdown https://drive.google.com/uc?id=1l_5RK28JRL19wpT22B-DY9We3TVXnnQQ
$ md5sum fcn8s_from_caffe.npz
256c2a8235c1c65e62e48d3284fbd384

$ # same as the above but with the file ID
$ gdown 1l_5RK28JRL19wpT22B-DY9We3TVXnnQQ

$ # a small file
$ gdown https://drive.google.com/uc?id=0B9P1L--7Wd2vU3VUVlFnbTgtS2c
$ cat spam.txt
spam

$ # download with fuzzy extraction of a file ID
$ gdown --fuzzy 'https://drive.google.com/file/d/0B9P1L--7Wd2vU3VUVlFnbTgtS2c/view?usp=sharing&resourcekey=0-WWs_XOSctfaY_0-sJBKRSQ'
$ cat spam.txt
spam

$ # --fuzzy option also works with Microsoft Powerpoint files
$ gdown --fuzzy "https://docs.google.com/presentation/d/15umvZKlsJ3094HNg5S4vJsIhxcFlyTeK/edit?usp=sharing&ouid=117512221203072002113&rtpof=true&sd=true"

$ # a folder
$ gdown https://drive.google.com/drive/folders/15uNXeRBIhVvZJIhL4yTw4IsStMhUaaxl -O /tmp/folder --folder

$ # as an alternative to curl/wget
$ gdown https://httpbin.org/ip -O ip.json
$ cat ip.json
{
  "origin": "126.169.213.247"
}

$ # write stdout and pipe to extract
$ gdown https://github.com/wkentaro/gdown/archive/refs/tags/v4.0.0.tar.gz -O - --quiet | tar zxvf -
$ ls gdown-4.0.0/
gdown  github2pypi  LICENSE  MANIFEST.in  pyproject.toml  README.md  setup.cfg  setup.py  tests
```

### via Python

```python
import gdown

# a file
url = "https://drive.google.com/uc?id=1l_5RK28JRL19wpT22B-DY9We3TVXnnQQ"
output = "fcn8s_from_caffe.npz"
gdown.download(url, output)

# same as the above, but with the file ID
id = "0B9P1L--7Wd2vNm9zMTJWOGxobkU"
gdown.download(id=id, output=output)

# same as the above, and you can copy-and-paste a URL from Google Drive with fuzzy=True
url = "https://drive.google.com/file/d/0B9P1L--7Wd2vNm9zMTJWOGxobkU/view?usp=sharing"
gdown.download(url=url, output=output, fuzzy=True)

# Cached download with identity check via MD5 (or SHA1, SHA256, etc).
# Pass postprocess function e.g., extracting compressed file.
md5 = "md5:fa837a88f0c40c513d975104edf3da17"
gdown.cached_download(url, output, hash=hash, postprocess=gdown.extractall)

# a folder
url = "https://drive.google.com/drive/folders/15uNXeRBIhVvZJIhL4yTw4IsStMhUaaxl"
gdown.download_folder(url)

# same as the above, but with the folder ID
id = "15uNXeRBIhVvZJIhL4yTw4IsStMhUaaxl"
gdown.download_folder(id=id)
```


## FAQ

### I get a 'Permission Denied' error.

Have you made sure you set the file permission to 'Anyone with Link'?

### I set the permission 'Anyone with Link', but I still can't download.

Google restricts access to a file when the download is concentrated.
If you can still access to the file from your browser, downloading cookies file might
help. Follow this step: 1) download cookies.txt using browser extensions like
([Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc));
2) mv the `cookies.txt` to `~/.cache/gdown/cookies.txt`; 3) run download again.
If you're using `gdown>=5.0.0`, it should be able to use the cookies same as your browser.


## License

MIT
