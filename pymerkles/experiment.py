from pymerkles.complex import Container, List, Vector
from pymerkles.basic import uint64, boolean
from pymerkles.bytes32 import Bytes32
from pymerkles.tree import merkle_hash


class Validator(Container):
    pubkey: Bytes32  # TODO basic vec type for bytes48
    withdrawal_credentials: Bytes32  # Commitment to pubkey for withdrawals
    effective_balance: uint64  # Balance at stake
    slashed: boolean
    # Status epochs
    activation_eligibility_epoch: uint64  # When criteria for activation were met
    activation_epoch: uint64
    exit_epoch: uint64
    withdrawable_epoch: uint64  # When validator can withdraw funds



print(Bytes32.default_node())
print(uint64.default_node())
print(Vector[uint64, 5].default_node())
print(List[uint64, 5].default_node())

a = Validator
print(a)
b = a()
print(b)

print(Bytes32)
print(Bytes32())

SimpleVec = Vector[uint64, 512]
print(SimpleVec)
data: Vector = SimpleVec()
print(data)
print(data.get_backing().merkle_root(merkle_hash).hex())
data.set(1, uint64(123))
print(data.get_backing().merkle_root(merkle_hash).hex())
data.set(10, uint64(42))
print(data.get_backing().merkle_root(merkle_hash).hex())
data.set(1, uint64(0))
print(data.get_backing().merkle_root(merkle_hash).hex())
data.set(10, uint64(0))
print(data.get_backing().merkle_root(merkle_hash).hex())

SimpleList = List[uint64, 512]
print(SimpleList)
foo: List = SimpleList()
print(foo)
print(foo.get_backing().merkle_root(merkle_hash).hex())

Registry = List[Validator, 2**40]
print(Registry)
registry = Registry()
print(registry)
print(registry.get_backing().merkle_root(merkle_hash).hex())
print(registry.length())

val1 = Validator()
print(val1)
registry.append(val1)
print(registry)
print(registry.get_backing().merkle_root(merkle_hash).hex())
print(registry.length())

for i in range(1000):
    registry.append(val1)

print(registry)
print(registry.get_backing().merkle_root(merkle_hash).hex())
print(registry.length())

import time

N = 100
x = Validator()
start = time.time()
for i in range(N):
    registry.append(x)
    registry.get_backing().merkle_root(merkle_hash)

end = time.time()
delta = end - start
print(f"ops: {N}, time: {delta} seconds  ms/op: {(delta / N) * 1000}")
