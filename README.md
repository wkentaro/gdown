# gdown

[![PyPi Version](https://img.shields.io/pypi/v/gdown.svg)](https://pypi.python.org/pypi/gdown)
[![Travis Status](https://travis-ci.org/wkentaro/gdown.svg?branch=master)](https://travis-ci.org/wkentaro/gdown)

Download a large file from Google Drive.

If you use curl/wget, it fails with a large file because of
the security warning from Google Drive. This python package solves that.


## Installation

```bash
pip install gdown
```


## Usage

```bash
$ # gdown URL [-O FILENAME]

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
% cat ip
{
  "origin": "126.169.213.247"
}
```

And with the `-s` flag, UNIX pipes are now also possible:

```
$ time gdown https://drive.google.com/uc?id=1cKq-rgSNCYPCUJ38pCi_xy6_PJH-FZWD -s | tar xvfz -
real    18m19.087s
user    1m1.682s
sys    1m25.540s

$ du -hs data/
9.5G    data/
```


## License

See [LICENSE](LICENSE).
