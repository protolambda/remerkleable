from pymerkles.complex import Container, List, Vector
from pymerkles.basic import uint64, boolean
from pymerkles.bytes_vector import ByteVector
from pymerkles.tree import merkle_hash

Bytes32 = ByteVector[32]
Bytes48 = ByteVector[48]


class Validator(Container):
    pubkey: Bytes48
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
print(b.pubkey)

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

print(data)
data[1] = 456
print(data)
print(data[1])

for i, v in enumerate(data):
    print(f"{i}: {v}")
    if i > 3:
        break

print(data[:3])

SimpleList = List[uint64, 512]
print(SimpleList)
foo: List = SimpleList()
print(foo)
print(foo.get_backing().merkle_root(merkle_hash).hex())

print(foo)
foo.append(uint64(1001))
foo.append(uint64(1002))
print(foo)
foo[1] = 456
print(foo)
print(foo[1])

for i, v in enumerate(foo):
    print(f"{i}: {v}")
    if i > 3:
        break

print(foo[1:])

small_vec = Vector[uint64, 8](1, 2, 3, 4, 5, 6, 7, 8)
print("small vec: ", small_vec)

small_list = List[uint64, 8](1, 2, 3)
print("small list: ", small_list)
small_full_list = List[uint64, 8](1, 2, 3, 4, 5, 6, 7, 8)
print("small full list: ", small_full_list)

Registry = List[Validator, 2**40]
print(Registry)
registry = Registry()
print(registry)
print(registry.get_backing().merkle_root(merkle_hash).hex())
print(registry.length())

val1 = Validator()
print(val1)


def do_append():
    print("appending!")
    registry.append(val1)
    print(registry)
    print(registry.get_backing().merkle_root(merkle_hash).hex())
    print(registry.length())


def do_pop():
    print("popping!")
    registry.pop()
    print(registry)
    print(registry.get_backing().merkle_root(merkle_hash).hex())
    print(registry.length())


do_append()
do_pop()
do_append()
do_append()
do_pop()
do_pop()
do_append()
do_append()
do_append()
do_append()
do_pop()
do_append()
do_pop()
do_pop()
do_pop()

print("----")

for i in range(20):
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

print(" --- balances test --- ")
Balances = List[uint64, 2**40]
print(Balances)
balances = Balances()
print(balances)
print(balances.get_backing().merkle_root(merkle_hash).hex())
print(balances.length())

def do_append():
    print("appending!")
    balances.append(uint64(123))
    print(balances)
    print(balances.get_backing().merkle_root(merkle_hash).hex())
    print(balances.length())


def do_pop():
    print("popping!")
    balances.pop()
    print(balances)
    print(balances.get_backing().merkle_root(merkle_hash).hex())
    print(balances.length())


do_append()
do_pop()
do_append()
do_append()
do_pop()
do_pop()
do_append()
do_append()
do_append()
do_append()
do_pop()
do_append()
do_pop()
do_pop()
do_pop()