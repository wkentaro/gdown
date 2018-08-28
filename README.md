# gdown

[![PyPi Version](https://img.shields.io/pypi/v/gdown.svg)](https://pypi.python.org/pypi/gdown)
[![Travis Status](https://travis-ci.org/wkentaro/gdown.svg?branch=master)](https://travis-ci.org/wkentaro/gdown)

Download a large file from Google Drive.  
If you use curl/wget, it fails with a large file because of
the security warning from Google Drive.


## Installation

```bash
pip install gdown
```


## Usage

### From Command Line

```bash
$ # gdown [-h] [-V] [-O OUTPUT] [-q] [--id] url_or_id

$ # a large file (~400MB)
$ gdown https://drive.google.com/uc?id=0B_NiLAzvehC9R2stRmQyM3ZiVjQ
$ # gdown --id 0B_NiLAzvehC9R2stRmQyM3ZiVjQ
$ md5sum pose_estimation_2d_chainermodel.pkl
587933c2c0adf335ebed0486c183541f

$ # a small file
$ gdown https://drive.google.com/uc?id=0B9P1L--7Wd2vU3VUVlFnbTgtS2c
$ cat spam.txt
spam

$ # as an alternative to curl/wget
$ gdown https://httpbin.org/ip -O ip.json
$ cat ip.json
{
  "origin": "126.169.213.247"
}

$ # write stdout and pipe to extract
$ gdown https://drive.google.com/uc?id=0B9P1L--7Wd2vNm9zMTJWOGxobkU -O - --quiet | tar zxvf -
$ ls 20150428_collected_images/
```

### From Python

```python
import gdown

url = 'https://drive.google.com/uc?id=0B9P1L--7Wd2vU3VUVlFnbTgtS2c'
output = 'spam.txt'
gdown.download(url, output, quiet=False)
```


## License

See [LICENSE](LICENSE).
