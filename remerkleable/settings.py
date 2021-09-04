from typing import Literal, Union as PyUnion, NewType, Callable, List as PyList
from hashlib import sha256

# To override the endianness
ENDIANNESS: PyUnion[Literal['little'], Literal['big']] = 'little'

# To override the hash function & zero-hashes

Root = NewType("Root", bytes)

MerkleFn = Callable[[Root, Root], Root]

ZERO_ROOT: Root = Root(b'\x00' * 32)


def merkle_hash(left: Root, right: Root) -> Root:
    return Root(sha256(left + right).digest())


# hashes of hashes of zeroes etc.
zero_hashes: PyList[Root] = [ZERO_ROOT]


def init_zero_hashes(n=255):
    global zero_hashes
    zero_hashes = [ZERO_ROOT]
    for i in range(n):
        zero_hashes.append(merkle_hash(zero_hashes[i], zero_hashes[i]))


init_zero_hashes()
