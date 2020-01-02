from pymerkles.core import View, TypeDef, BasicView
from .ssz_typing import (
    bit, boolean, Container, List, Vector,
    byte, uint8, uint16, uint32, uint64, uint128, uint256,
    Bytes32, Bytes48
)


def expect_value_error(fn, msg):
    try:
        fn()
        raise AssertionError(msg)
    except ValueError:
        pass


def test_subclasses():
    for u in [uint8, uint16, uint32, uint64, uint128, uint256]:
        assert issubclass(u, int)
        assert issubclass(u, View)
        assert issubclass(u, BasicView)
        assert isinstance(u, TypeDef)
    assert issubclass(boolean, BasicView)
    assert issubclass(boolean, View)
    assert isinstance(boolean, TypeDef)

    for c in [Container, List, Vector, Bytes32]:
        assert not issubclass(c, View)
        assert not isinstance(c, TypeDef)


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
        expect_value_error(lambda: k(v), "no overflows allowed")

    for k, _ in max.items():
        # this should work
        assert k(0) == 0
        # but we do not allow underflows
        expect_value_error(lambda: k(-1), "no underflows allowed")


def test_container():
    class Foo(Container):
        a: uint8
        b: uint32

    empty = Foo()
    assert empty.a == uint8(0)
    assert empty.b == uint32(0)

    assert issubclass(Foo, Container)
    assert issubclass(Foo, View)

    assert Foo.is_fixed_size()
    x = Foo(a=uint8(123), b=uint32(45))
    assert x.a == 123
    assert x.b == 45
    assert isinstance(x.a, uint8)
    assert isinstance(x.b, uint32)
    assert x.__class__.is_fixed_size()

    class Bar(Container):
        a: uint8
        b: List[uint8, 1024]

    assert not Bar.is_fixed_size()

    y = Bar(a=123, b=List[uint8, 1024](uint8(1), uint8(2)))
    assert y.a == 123
    assert isinstance(y.a, uint8)
    assert len(y.b) == 2
    assert isinstance(y.a, uint8)
    # noinspection PyTypeHints
    assert isinstance(y.b, List[uint8, 1024])
    assert not y.__class__.is_fixed_size()
    assert y.b[0] == 1
    v: List = y.b
    assert v.__class__.elem_type == uint8
    assert v.__class__.length == 1024

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


def test_list():
    typ = List[uint64, 128]
    assert issubclass(typ, List)
    assert issubclass(typ, View)
    assert isinstance(typ, TypeDef)

    assert not typ.is_fixed_byte_length()

    assert len(typ()) == 0  # empty
    assert len(typ(uint64(0))) == 1  # single arg
    assert len(typ(uint64(i) for i in range(10))) == 10  # generator
    assert len(typ(uint64(0), uint64(1), uint64(2))) == 3  # args
    assert isinstance(typ(1, 2, 3, 4, 5)[4], uint64)  # coercion
    assert isinstance(typ(i for i in range(10))[9], uint64)  # coercion in generator

    v = typ(uint64(0))
    v[0] = uint64(123)
    assert v[0] == 123
    assert isinstance(v[0], uint64)

    assert isinstance(v, List)
    # noinspection PyTypeHints
    assert isinstance(v, List[uint64, 128])
    # noinspection PyTypeHints
    assert isinstance(v, typ)
    assert isinstance(v, View)

    assert len(typ([i for i in range(10)])) == 10  # cast py list to SSZ list

    foo = List[uint32, 128](0 for i in range(128))
    foo[0] = 123
    foo[1] = 654
    foo[127] = 222
    assert sum(foo) == 999
    try:
        foo[3] = 2 ** 32  # out of bounds
    except ValueError:
        pass

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


def test_bytesn_subclass():
    assert isinstance(Vector[byte, 32](b'\xab' * 32), Bytes32)
    assert not isinstance(Vector[byte, 32](b'\xab' * 32), Bytes48)
    assert issubclass(Vector[byte, 32](b'\xab' * 32).__class__, Bytes32)
    assert issubclass(Vector[byte, 32], Bytes32)

    class Root(Bytes32):
        pass

    assert isinstance(Root(b'\xab' * 32), Bytes32)
    assert not isinstance(Root(b'\xab' * 32), Bytes48)
    assert issubclass(Root(b'\xab' * 32).__class__, Bytes32)
    assert issubclass(Root, Bytes32)

    assert not issubclass(Bytes48, Bytes32)

    assert len(Bytes32() + Bytes48()) == 80


def test_uint_math():
    assert uint8(0) + uint8(uint32(16)) == uint8(16)  # allow explicit casting to make invalid addition valid

    expect_value_error(lambda: uint8(0) - uint8(1), "no underflows allowed")
    expect_value_error(lambda: uint8(1) + uint8(255), "no overflows allowed")
    expect_value_error(lambda: uint8(0) + 256, "no overflows allowed")
    expect_value_error(lambda: uint8(42) + uint32(123), "no mixed types")
    expect_value_error(lambda: uint32(42) + uint8(123), "no mixed types")

    assert type(uint32(1234) + 56) == uint32
