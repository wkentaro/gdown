import pytest

from gdown._filehash import parse_filehash


def test_parse_filehash_lower_cases_the_hash_value() -> None:
    algorithm, hash_value = parse_filehash(hash="md5:8D777F385D3DFEC8815D20F7496026DC")

    assert algorithm == "md5"
    assert hash_value == "8d777f385d3dfec8815d20f7496026dc"


def test_parse_filehash_accepts_a_full_length_blake2_digest() -> None:
    hash_value = "0" * 128

    assert parse_filehash(hash=f"blake2b:{hash_value}") == ("blake2b", hash_value)


@pytest.mark.parametrize(
    ("hash", "message"),
    [
        ("md5", "Hash must be in the format"),
        ("MD5:8d777f385d3dfec8815d20f7496026dc", "Unsupported hash algorithm"),
        # shake_* is in hashlib.algorithms_guaranteed but has no fixed digest.
        ("shake_128:00", "Unsupported hash algorithm"),
        ("crc32:00000000", "Unsupported hash algorithm"),
        ("md5:zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz", "must be hexadecimal"),
        ("md5:8d777f385d3dfec8815d20f749602", "characters long"),
        # blake2b takes a shorter digest, but only its default length is computed.
        ("blake2b:0123456789abcdef", "characters long"),
    ],
)
def test_parse_filehash_rejects_bad_hash(*, hash: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_filehash(hash=hash)
