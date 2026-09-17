import os

from pip_api._call import call
from pip_api.exceptions import InvalidArguments


def hash(filename: os.PathLike, algorithm: str = "sha256") -> str:
    """
    Hash the given filename.
    """

    if algorithm not in ["sha256", "sha384", "sha512"]:
        raise InvalidArguments("Algorithm {} not supported".format(algorithm))

    result = call("hash", "--algorithm", algorithm, filename)

    # result is of the form:
    # <filename>:\n--hash=<algorithm>:<hash>\n
    return result.strip().split(":")[-1]
