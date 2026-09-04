import hashlib
import re
from typing import Final

from .exceptions import HashMismatchError


def parse_filehash(*, hash: str) -> tuple[str, str]:
    # The shake_* variants are extendable-output functions whose hexdigest()
    # takes a mandatory length, so they have no fixed digest to compare against.
    supported_algorithms = sorted(
        hashlib.algorithms_guaranteed - {"shake_128", "shake_256"}
    )

    algorithm, separator, hash_value = hash.partition(":")
    if not separator:
        raise ValueError(
            f"Invalid hash: {hash}. "
            "Hash must be in the format of {algorithm}:{hash_value}."
        )

    if algorithm not in supported_algorithms:
        raise ValueError(
            f"Unsupported hash algorithm: {algorithm}. "
            f"Supported algorithms: {', '.join(supported_algorithms)}"
        )

    # hexdigest() is lower case, so a hash pasted from a tool that prints upper
    # case hex names the same file.
    hash_value = hash_value.lower()
    if not re.fullmatch("[0-9a-f]+", hash_value):
        raise ValueError(f"Invalid hash: {hash}. Hash value must be hexadecimal.")

    # blake2b and blake2s can produce a shorter digest, but only the default
    # length is computed here, so a shorter one could never match.
    digest_size = hashlib.new(algorithm).digest_size
    if len(hash_value) != digest_size * 2:
        raise ValueError(
            f"Invalid hash: {hash}. "
            f"{algorithm} hash values are {digest_size * 2} characters long."
        )

    return algorithm, hash_value


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
        raise HashMismatchError(
            f"File hash doesn't match:\nactual: {hash_actual}\nexpected: {hash}"
        )
