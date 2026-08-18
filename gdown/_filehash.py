import hashlib
from typing import Final


def compute_filehash(*, path: str, algorithm: str) -> str:
    BLOCKSIZE: Final = 65536

    if algorithm not in hashlib.algorithms_guaranteed:
        raise ValueError(
            f"Unsupported hash algorithm: {algorithm}. "
            f"Supported algorithms: {hashlib.algorithms_guaranteed}"
        )

    algorithm_instance = getattr(hashlib, algorithm)()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(BLOCKSIZE), b""):
            algorithm_instance.update(block)
    return f"{algorithm}:{algorithm_instance.hexdigest()}"


def assert_filehash(*, path: str, hash: str) -> None:
    if ":" not in hash:
        raise ValueError(
            f"Invalid hash: {hash}. "
            "Hash must be in the format of {algorithm}:{hash_value}."
        )
    algorithm = hash.split(":")[0]

    hash_actual = compute_filehash(path=path, algorithm=algorithm)

    if hash_actual != hash:
        raise AssertionError(
            f"File hash doesn't match:\nactual: {hash_actual}\nexpected: {hash}"
        )
