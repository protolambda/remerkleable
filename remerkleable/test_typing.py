# flake8:noqa F401  Ignore unused imports. Tests are a work in progress.

import pytest  # type: ignore

from typing import Optional, Type
from random import Random

from remerkleable.complex import Container, Vector, List
from remerkleable.basic import boolean, bit, uint, byte, uint8, uint16, uint32, uint64, uint128, uint256,\
    OperationNotSupported
from remerkleable.bitfields import Bitvector, Bitlist
from remerkleable.byte_arrays import ByteVector, Bytes1, Bytes4, Bytes8, Bytes32, Bytes48, Bytes96
from remerkleable.core import BasicView, View
from remerkleable.progressive import ProgressiveList
from remerkleable.stable_container import Profile, StableContainer
from remerkleable.union import Union
from remerkleable.tree import get_depth, merkle_hash, LEFT_GINDEX, RIGHT_GINDEX


def expect_op_error(fn, msg):
    try:
        fn()
        raise AssertionError(msg)
    except (ValueError, OperationNotSupported, AttributeError) as e:
        pass


def test_subclasses():
    for u in [uint8, uint16, uint32, uint64, uint128, uint256]:
        assert issubclass(u, int)
        assert issubclass(u, View)
        assert issubclass(u, BasicView)
    assert issubclass(boolean, BasicView)
    assert issubclass(boolean, View)

    for c in [Container, List, Vector, ProgressiveList, Bytes32]:
        assert issubclass(c, View)


def test_basic_instances():
    for u in [uint8, byte, uint16, uint32, uint64, uint128, uint256]:
        v = u(123)
        assert isinstance(v, int)
        assert isinstance(v, BasicView)
        assert isinstance(v, View)

    assert isinstance(boolean(True), BasicView)
    assert isinstance(boolean(False), BasicView)
    assert isinstance(bit(True), boolean)
    assert isinstance(bit(False), boolean)


def test_basic_value_bounds():
    max = {
        boolean: 2 ** 1,
        bit: 2 ** 1,
        uint8: 2 ** (8 * 1),
        byte: 2 ** (8 * 1),
        uint16: 2 ** (8 * 2),
        uint32: 2 ** (8 * 4),
        uint64: 2 ** (8 * 8),
        uint128: 2 ** (8 * 16),
        uint256: 2 ** (8 * 32),
    }
    for k, v in max.items():
        # this should work
        assert k(v - 1) == v - 1
        # but we do not allow overflows
        expect_op_error(lambda: k(v), f"no overflows allowed: type: {k}, value: {v}")

    for k, _ in max.items():
        # this should work
        assert k(0) == 0
        # but we do not allow underflows
        expect_op_error(lambda: k(-1), "no underflows allowed")

    for k, v in max.items():
        if v == 2:
            continue  # skip bool/bit
        half = v // 2
        # this should work
        assert k(half) + k(half-1) == v - 1
        # but 2x half == max, so this should fail
        expect_op_error(lambda: k(half) + k(half), f"no __add__ overflows allowed: type: {k}, value: {half}")
        # this should work
        assert k(half) - k(half) == 0
        assert k(half-1) - k(half-1) == 0
        # but underflow should not
        expect_op_error(lambda: k(half - 1) - k(half), f"no __sub__ underflows allowed: type: {k}, value: {half}")

    for k, v in max.items():
        if v == 2:
            continue  # skip bool/bit
        assert k(v-1) * k(1) == v-1
        assert k(v // 3) * 2 == (v // 3) * 2
        assert k((v // 2) - 1) * 2 == ((v // 2) - 1) * 2
        # but 2x max-1 should fail
        expect_op_error(lambda: k(v - 1) * 2, f"no __mul__ overflows allowed: type: {k}")
        # and 2x half too
        expect_op_error(lambda: k(v // 2) * 2, f"no __mul__ overflows allowed: type: {k}")
        expect_op_error(lambda: k(v // 2) // 0.5, f"no __floordiv__ with float overflows allowed: type: {k}")
        expect_op_error(lambda: k(v - 1) / 2.0, f"no __truediv__ allowed: type: {k}")


def test_container():
    class Foo(Container):
        a: uint8
        b: uint32

    empty = Foo()
    assert empty.a == uint8(0)
    assert empty.b == uint32(0)

    assert issubclass(Foo, Container)
    assert issubclass(Foo, View)

    assert Foo.is_fixed_byte_length()
    x = Foo(a=uint8(123), b=uint32(45))
    assert x.a == 123
    assert x.b == 45
    assert isinstance(x.a, uint8)
    assert isinstance(x.b, uint32)
    assert x.__class__.is_fixed_byte_length()

    class Bar(Container):
        a: uint8
        b: List[uint8, 1024]

    assert not Bar.is_fixed_byte_length()

    y = Bar(a=123, b=List[uint8, 1024](uint8(1), uint8(2)))
    assert y.a == 123
    assert isinstance(y.a, uint8)
    assert len(y.b) == 2
    assert isinstance(y.a, uint8)
    assert not y.__class__.is_fixed_byte_length()
    assert y.b[0] == 1
    v: List = y.b
    assert v.__class__.element_cls() == uint8
    assert v.__class__.limit() == 1024

    field_values = list(y)
    assert field_values == [y.a, y.b]

    f_a, f_b = y
    assert f_a == y.a
    assert f_b == y.b

    y.a = 42
    try:
        y.a = 256  # out of bounds
        assert False
    except ValueError:
        pass

    try:
        y.a = uint16(255)  # within bounds, wrong type
        assert False
    except ValueError:
        pass

    try:
        y.not_here = 5
        assert False
    except AttributeError:
        pass

    try:
        Foo(wrong_field_name=100)
        assert False
    except AttributeError:
        pass


def test_container_unpack():
    class Foo(Container):
        a: uint64
        b: uint8
        c: Vector[uint16, 123]

    foo = Foo(b=42)
    a, b, c = foo
    assert b == 42


@pytest.mark.parametrize("typ", [List[uint64, 128], ProgressiveList[uint64]])
def test_list_1(typ: Type[View]):
    base_typ = List if typ.type_repr().startswith("List") else ProgressiveList
    assert issubclass(typ, base_typ)
    assert issubclass(typ, View)
    assert not issubclass(int, View)

    assert not typ.is_fixed_byte_length()

    assert len(typ()) == 0  # empty
    assert len(typ(uint64(0))) == 1  # single arg
    assert len(typ(uint64(i) for i in range(10))) == 10  # generator
    assert len(typ(uint64(0), uint64(1), uint64(2))) == 3  # args
    assert isinstance(typ(1, 2, 3, 4, 5)[4], uint64)  # coercion
    assert isinstance(typ(i for i in range(10))[9], uint64)  # coercion in generator

    v = typ(uint64(2), uint64(1))
    v[0] = uint64(123)
    assert v[0] == 123
    assert isinstance(v[0], uint64)

    assert isinstance(v, base_typ)
    assert isinstance(v, View)

    assert len(typ([i for i in range(10)])) == 10  # cast py list to SSZ list


@pytest.mark.parametrize("typ", [List[uint32, 128], ProgressiveList[uint32]])
def test_list_2(typ: Type[View]):
    foo = typ(0 for i in range(128))
    foo[0] = 123
    foo[1] = 654
    foo[127] = 222
    assert sum(foo) == 999
    try:
        foo[3] = 2 ** 32  # out of bounds
    except ValueError:
        pass

    assert foo.encode_bytes().hex() == (
        "7b0000008e020000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000"
        "00000000000000000000000000000000000000000000000000000000de000000"
    )
    assert foo.hash_tree_root() == typ.decode_bytes(foo.encode_bytes()).hash_tree_root()

    for i in range(128):
        foo.pop()
        assert len(foo) == 128 - 1 - i
        assert foo.hash_tree_root() == typ.decode_bytes(foo.encode_bytes()).hash_tree_root()

        if i == 64:
            assert foo.encode_bytes().hex() == (
                "7b0000008e020000000000000000000000000000000000000000000000000000"
                "0000000000000000000000000000000000000000000000000000000000000000"
                "0000000000000000000000000000000000000000000000000000000000000000"
                "0000000000000000000000000000000000000000000000000000000000000000"
                "0000000000000000000000000000000000000000000000000000000000000000"
                "0000000000000000000000000000000000000000000000000000000000000000"
                "0000000000000000000000000000000000000000000000000000000000000000"
                "00000000000000000000000000000000000000000000000000000000"
            )

    assert foo.encode_bytes().hex() == ""

    for i in range(128):
        foo.append(uint32(i))
        assert len(foo) == i + 1
        assert foo[i] == i
        assert foo.hash_tree_root() == typ.decode_bytes(foo.encode_bytes()).hash_tree_root()

    try:
        foo[3] = uint64(2 ** 32 - 1)  # within bounds, wrong type
        assert False
    except ValueError:
        pass

    try:
        foo[128] = 100
        assert False
    except IndexError:
        pass

    try:
        foo[-1] = 100  # valid in normal python lists
        assert False
    except IndexError:
        pass

    try:
        foo[128] = 100  # out of bounds
        assert False
    except IndexError:
        pass

    assert foo.encode_bytes().hex() == (
        "0000000001000000020000000300000004000000050000000600000007000000"
        "08000000090000000a0000000b0000000c0000000d0000000e0000000f000000"
        "1000000011000000120000001300000014000000150000001600000017000000"
        "18000000190000001a0000001b0000001c0000001d0000001e0000001f000000"
        "2000000021000000220000002300000024000000250000002600000027000000"
        "28000000290000002a0000002b0000002c0000002d0000002e0000002f000000"
        "3000000031000000320000003300000034000000350000003600000037000000"
        "38000000390000003a0000003b0000003c0000003d0000003e0000003f000000"
        "4000000041000000420000004300000044000000450000004600000047000000"
        "48000000490000004a0000004b0000004c0000004d0000004e0000004f000000"
        "5000000051000000520000005300000054000000550000005600000057000000"
        "58000000590000005a0000005b0000005c0000005d0000005e0000005f000000"
        "6000000061000000620000006300000064000000650000006600000067000000"
        "68000000690000006a0000006b0000006c0000006d0000006e0000006f000000"
        "7000000071000000720000007300000074000000750000007600000077000000"
        "78000000790000007a0000007b0000007c0000007d0000007e0000007f000000"
    )
    assert foo.hash_tree_root() == typ.decode_bytes(foo.encode_bytes()).hash_tree_root()


def test_bytesn_subclass():
    class Root(Bytes32):
        pass

    # mypy does not like instance checks with parametrized generics, but they work, python can do everything
    assert isinstance(Root(b'\xab' * 32), Bytes32)  # type: ignore
    assert not isinstance(Root(b'\xab' * 32), Bytes48)  # type: ignore
    assert issubclass(Root(b'\xab' * 32).__class__, Bytes32)  # type: ignore
    assert issubclass(Root, Bytes32)  # type: ignore

    assert not issubclass(Bytes48, Bytes32)  # type: ignore

    assert len(Bytes32() + Bytes48()) == 80


def test_uint_math():
    assert uint8(0) + uint8(uint32(16)) == uint8(16)  # allow explicit casting to make invalid addition valid

    expect_op_error(lambda: uint8(0) - uint8(1), "no underflows allowed")
    expect_op_error(lambda: uint8(1) + uint8(255), "no overflows allowed")
    expect_op_error(lambda: uint8(0) + 256, "no overflows allowed")
    expect_op_error(lambda: uint8(42) + uint32(123), "no mixed types")
    expect_op_error(lambda: uint32(42) + uint8(123), "no mixed types")

    assert type(uint32(1234) + 56) == uint32


def test_container_depth():
    class SingleField(Container):
        foo: uint32

    assert SingleField.tree_depth() == 0

    class TwoField(Container):
        foo: uint32
        bar: uint64

    assert TwoField.tree_depth() == 1

    class ThreeField(Container):
        foo: uint32
        bar: uint64
        quix: uint8

    assert ThreeField.tree_depth() == 2

    class FourField(Container):
        foo: uint32
        bar: uint64
        quix: uint8
        more: uint32

    assert FourField.tree_depth() == 2

    class FiveField(Container):
        foo: uint32
        bar: uint64
        quix: uint8
        more: uint32
        fiv: uint8

    assert FiveField.tree_depth() == 3


@pytest.mark.parametrize("count, depth", [
    (0, 0), (1, 0), (2, 1), (3, 2), (4, 2), (5, 3), (6, 3), (7, 3), (8, 3), (9, 4)])
def test_tree_depth(count: int, depth: int):
    assert get_depth(count) == depth


def test_paths():
    class FourField(Container):
        foo: uint32
        bar: uint64
        quix: uint8
        more: uint32

    assert (FourField / 'foo').navigate_type() == uint32
    assert (FourField / 'bar').navigate_type() == uint64
    assert (FourField / 'foo').gindex() == 0b100
    assert (FourField / 'bar').gindex() == 0b101

    class Wrapper(Container):
        a: uint32
        b: FourField

    assert (Wrapper / 'a').navigate_type() == uint32
    assert (Wrapper / 'b').navigate_type() == FourField
    assert (Wrapper / 'b' / 'quix').navigate_type() == uint8

    assert (Wrapper / 'a').gindex() == 0b10
    assert (Wrapper / 'b' / 'more').gindex() == 0b1111

    assert ((Wrapper / 'b') / (FourField / 'quix')).gindex() == ((Wrapper / 'b') / 'quix').gindex()

    w = Wrapper(b=FourField(quix=42))
    assert (Wrapper / 'b' / 'quix').navigate_view(w) == 42

    assert (List[uint32, 123] / 0).navigate_type() == uint32
    assert (List[uint32, 123] / "__len__").navigate_type() == uint256
    try:
        (List[uint32, 123] / 123).navigate_type()
        assert False
    except KeyError:
        pass

    assert (Bitlist[123] / 0).navigate_type() == boolean
    assert (Bitlist[123] / "__len__").navigate_type() == uint256
    try:
        (Bitlist[123] / 123).navigate_type()
        assert False
    except KeyError:
        pass

    class StableFields(StableContainer[8]):
        foo: Optional[uint32]
        bar: Optional[uint64]
        quix: Optional[uint64]
        more: Optional[uint32]

    class FooFields(Profile[StableFields]):
        foo: uint32
        more: Optional[uint32]

    class BarFields(Profile[StableFields]):
        bar: uint64
        quix: uint64
        more: Optional[uint32]

    assert issubclass((StableFields / '__active_fields__').navigate_type(), Bitvector)
    assert (StableFields / '__active_fields__').navigate_type().vector_length() == 8
    assert (StableFields / '__active_fields__').gindex() == 0b11
    assert (StableFields / 'foo').navigate_type() == Optional[uint32]
    assert (StableFields / 'foo').gindex() == 0b10000
    assert (StableFields / 'bar').navigate_type() == Optional[uint64]
    assert (StableFields / 'bar').gindex() == 0b10001
    assert (StableFields / 'quix').navigate_type() == Optional[uint64]
    assert (StableFields / 'quix').gindex() == 0b10010
    assert (StableFields / 'more').navigate_type() == Optional[uint32]
    assert (StableFields / 'more').gindex() == 0b10011

    assert issubclass((FooFields / '__active_fields__').navigate_type(), Bitvector)
    assert (FooFields / '__active_fields__').navigate_type().vector_length() == 8
    assert (FooFields / '__active_fields__').gindex() == 0b11
    assert (FooFields / 'foo').navigate_type() == uint32
    assert (FooFields / 'foo').gindex() == 0b10000
    assert (FooFields / 'more').navigate_type() == Optional[uint32]
    assert (FooFields / 'more').gindex() == 0b10011
    try:
        (FooFields / 'bar').navigate_type()
        assert False
    except KeyError:
        pass

    assert issubclass((BarFields / '__active_fields__').navigate_type(), Bitvector)
    assert (BarFields / '__active_fields__').navigate_type().vector_length() == 8
    assert (BarFields / '__active_fields__').gindex() == 0b11
    assert (BarFields / 'bar').navigate_type() == uint64
    assert (BarFields / 'bar').gindex() == 0b10001
    assert (BarFields / 'more').navigate_type() == Optional[uint32]
    assert (BarFields / 'more').gindex() == 0b10011
    try:
        (BarFields / 'foo').navigate_type()
        assert False
    except KeyError:
        pass


def test_bitvector():
    for size in [1, 2, 3, 4, 5, 6, 7, 8, 9, 15, 16, 17, 31, 32, 33, 63, 64, 65, 511, 512, 513, 1023, 1024, 1025]:
        for i in range(size):
            b = Bitvector[size]()
            b[i] = True
            assert bool(b[i]) == True, "set %d / %d" % (i, size)

        for i in range(size):
            b = Bitvector[size](True for i in range(size))
            b[i] = False
            assert bool(b[i]) == False, "unset %d / %d" % (i, size)


def test_bitvector_iter():
    rng = Random(123)
    for size in [1, 2, 3, 4, 5, 6, 7, 8, 9, 15, 16, 17, 31, 32, 33, 63, 64, 65, 511, 512, 513, 1023, 1024, 1025]:
        # get a somewhat random bitvector
        bools = list(rng.randint(0, 1) == 1 for i in range(size))
        b = Bitvector[size](*bools)
        # Test iterator
        for i, bit in enumerate(b):
            assert bool(bit) == bools[i]


def test_bitlist():
    for size in [1, 2, 3, 4, 5, 6, 7, 8, 9, 15, 16, 17, 31, 32, 33, 63, 64, 65, 511, 512, 513, 1023, 1024, 1025]:
        for i in range(size):
            b = Bitlist[size](False for i in range(size))
            b[i] = True
            assert bool(b[i]) == True, "set %d / %d" % (i, size)

        for i in range(size):
            b = Bitlist[size](True for i in range(size))
            b[i] = False
            assert bool(b[i]) == False, "unset %d / %d" % (i, size)


def test_bitlist_iter():
    rng = Random(123)
    for limit in [1, 2, 3, 4, 5, 6, 7, 8, 9, 15, 16, 17, 31, 32, 33, 63, 64, 65, 511, 512, 513, 1023, 1024, 1025]:
        for length in [0, 1, limit // 2, limit]:
            # get a somewhat random bitvector
            bools = list(rng.randint(0, 1) == 1 for i in range(length))
            b = Bitlist[limit](*bools)
            # Test iterator
            for i, bit in enumerate(b):
                assert bool(bit) == bools[i]


def test_bitlist_access():
    bf = Bitlist[200](i % 2 == 1 for i in range(200))
    assert bf[int(123)]
    assert bf[uint64(123)]
    assert not bf[uint64(124)]
    assert not bf[uint8(42)]
    assert bf[uint8(43)]

    assert bf[len(bf)-1]
    bf.pop()
    assert not bf[len(bf)-1]
    bf.pop()
    assert bf[len(bf)-1]
    bf.append(True)
    assert bf[len(bf)-1]


def test_container_inheritance():
    class Foo(Container):
        a: uint64
        b: uint32

    class Bar(Foo):
        c: uint8

    assert Foo.fields() == {'a': uint64, 'b': uint32}
    assert Bar.fields() == {'a': uint64, 'b': uint32, 'c': uint8}
    assert Foo._field_indices == {'a': 0, 'b': 1}
    assert Bar._field_indices == {'a': 0, 'b': 1, 'c': 2}

    foo = Foo(a=0xaabbccdd11223344, b=0x55667788)
    assert foo.encode_bytes().hex() == "44332211ddccbbaa88776655"  # little endian!
    bar = Bar(c=0x99)
    assert bar.encode_bytes().hex() == "00000000000000000000000099"  # inits missing fields still
    bar2 = Bar(a=0xaabbccdd11223344, b=0x55667788, c=0x99)
    assert bar2.encode_bytes().hex() == "44332211ddccbbaa8877665599"

    class ChocoBar(Bar):
        aa: uint64

    assert ChocoBar.fields() == {'a': uint64, 'b': uint32, 'c': uint8, 'aa': uint64}
    assert ChocoBar._field_indices == {'a': 0, 'b': 1, 'c': 2, 'aa': 3}
    cb = ChocoBar(a=0xaabbccdd11223344, b=0x55667788, c=0xaf, aa=0x0102030405060708)
    assert cb.encode_bytes().hex() == "44332211ddccbbaa88776655af0807060504030201"

    # multiple inheritance

    class Mixin(Foo):
        m: uint8

    foo_mix = Mixin(a=0xaabbccdd11223344, b=0x55667788, m=0x99)
    assert foo_mix.encode_bytes().hex() == "44332211ddccbbaa8877665599"

    class Combined(Bar, Mixin):
        ...

    assert Combined.fields() == {'a': uint64, 'b': uint32, 'c': uint8, 'm': uint8}
    assert Combined._field_indices == {'a': 0, 'b': 1, 'c': 2, 'm': 3}

    combi = Combined(a=0xaabbccdd11223344, b=0x55667788, c=0x99, m=0x42)
    assert combi.encode_bytes().hex() == "44332211ddccbbaa887766559942"

    class Switcheroo(Mixin, Bar):
        ...

    assert Switcheroo.fields() == {'a': uint64, 'b': uint32, 'm': uint8, 'c': uint8}
    assert Switcheroo._field_indices == {'a': 0, 'b': 1, 'm': 2, 'c': 3}

    combi_switch = Switcheroo(a=0xaabbccdd11223344, b=0x55667788, c=0x99, m=0x42)
    assert combi_switch.encode_bytes().hex() == "44332211ddccbbaa887766554299"
    # fields are switched, while being different, hash tree roots should be different then
    assert combi.hash_tree_root() != combi_switch.hash_tree_root()

    class Duplicates(ChocoBar, Mixin, Foo):
        ...

    assert Duplicates.fields() == {'a': uint64, 'b': uint32, 'c': uint8, 'aa': uint64, 'm': uint8}
    assert Duplicates._field_indices == {'a': 0, 'b': 1, 'c': 2, 'aa': 3, 'm': 4}

    # overriding with different type
    class FancyChocoBar(ChocoBar):
        aa: uint128  # type: ignore

    assert FancyChocoBar.fields() == {'a': uint64, 'b': uint32, 'c': uint8, 'aa': uint128}
    assert FancyChocoBar._field_indices == {'a': 0, 'b': 1, 'c': 2, 'aa': 3}

    fcb = FancyChocoBar(a=0xaabbccdd11223344, b=0x55667788, c=0xaf, aa=0x0102030405060708a1a2a3a4a5a6a7a8)
    assert fcb.encode_bytes().hex() == "44332211ddccbbaa88776655afa8a7a6a5a4a3a2a10807060504030201"

    # overriding and extending
    class ExtendedFancyChocoBar(ChocoBar):
        more: uint16
        aa: uint128  # type: ignore

    # overriden field must stay in place
    assert ExtendedFancyChocoBar.fields() == {'a': uint64, 'b': uint32, 'c': uint8, 'aa': uint128, 'more': uint16}
    assert ExtendedFancyChocoBar._field_indices == {'a': 0, 'b': 1, 'c': 2, 'aa': 3, 'more': 4}

    efcb = ExtendedFancyChocoBar(a=0xaabbccdd11223344, b=0x55667788, c=0xaf,
                                 aa=0x0102030405060708a1a2a3a4a5a6a7a8, more=0xe1e2)
    assert efcb.encode_bytes().hex() == "44332211ddccbbaa88776655afa8a7a6a5a4a3a2a10807060504030201e2e1"


def test_union():
    # test default node
    foo = Union[uint32, uint16]()
    # 0 selector, 0 value
    zero_hash = b"\x00" * 32
    assert foo.hash_tree_root() == merkle_hash(zero_hash, zero_hash)
    assert foo.value() == uint32(0)
    assert foo.selector() == 0
    assert foo.selected_type() == uint32

    foo1 = Union[uint32, uint16](selector=1)
    assert foo1.value() == uint16(0)
    assert foo1.selector() == 1
    assert foo1.selected_type() == uint16

    # overriding and extending
    class Example(Container):
        more: uint16
        aa: uint128

    foo2 = Union[Example, uint64, uint16, uint128]()
    # 0 selector, default value
    assert foo2.hash_tree_root() == merkle_hash(merkle_hash(zero_hash, zero_hash), zero_hash)

    # change the selected value
    foo2.change(2, uint16(3))

    assert foo2.hash_tree_root() == merkle_hash(uint16(3).hash_tree_root(), uint256(2).hash_tree_root())
    assert foo2.value() == uint16(3)
    assert foo2.selector() == 2
    assert foo2.selected_type() == uint16

    # Only one non-none option
    foo = Union[uint32]()
    assert foo.options() == [uint32]

    # Max options (128)
    max_opts = [uint32] + ([uint16] * 126) + [uint8]
    bar = Union.__class_getitem__(tuple(max_opts))
    assert bar.options() == list(max_opts)

    # No union with too many options
    try:
        bar = Union.__class_getitem__((uint16,) * 129)
        assert False
    except TypeError:
        pass

    # No union with just a None option
    try:
        bar = Union[None]
        assert False
    except TypeError:
        pass

    # None type must always be the first option
    try:
        bar = Union[uint32, None]
        assert False
    except TypeError:
        pass

    # No more None types
    try:
        bar = Union[None, uint16, None]
        assert False
    except TypeError:
        pass

    data = {'selector': 2, 'value': '0x0123'}
    data_typ = Union[uint32, uint8, uint64]
    quix = data_typ.from_obj(data)
    assert quix.value() == 0x2301
    assert quix.selector() == 2

    data_back = quix.to_obj()
    assert data_back['selector'] == 2
    assert data_back['value'] == 0x2301
    assert len(data_back) == 2

    assert Union[None, uint64]().to_obj()['value'] is None

    gindex_test_typ = Union[None, uint16, uint64]
    assert gindex_test_typ.key_to_static_gindex('__selector__') == RIGHT_GINDEX
    assert gindex_test_typ.key_to_static_gindex(0) == LEFT_GINDEX
    assert gindex_test_typ.key_to_static_gindex(1) == LEFT_GINDEX
