from typing import Any, TypeVar, Type
from abc import abstractmethod
from remerkleable.core import BasicTypeHelperDef, BasicView, View

V = TypeVar('V', bound=View)


class BoolType(BasicTypeHelperDef):
    @classmethod
    def coerce_view(mcs: Type[Type[V]], v: Any) -> V:
        return boolean(v)

    @classmethod
    def type_byte_length(mcs) -> int:
        return 1

    @classmethod
    def decode_bytes(mcs: Type[Type[V]], bytez: bytes) -> V:
        return boolean(bytez != b"\x00")

    def __repr__(self):
        return "boolean"


class boolean(int, BasicView, metaclass=BoolType):

    def encode_bytes(self) -> bytes:
        return b"\x01" if self else b"\x00"

    def __new__(cls, value: int):  # int value, but can be any subclass of int (bool, Bit, Bool, etc...)
        if value < 0 or value > 1:
            raise ValueError(f"value {value} out of bounds for bit")
        return super().__new__(cls, value)

    def __bool__(self):
        return self > 0


class UintTypeBase(BasicTypeHelperDef):
    @classmethod
    @abstractmethod
    def type_byte_length(mcs) -> int:
        raise NotImplementedError

    def __repr__(self):
        return "Uint"


class uint(int, BasicView, metaclass=UintTypeBase):
    def __new__(cls, value: int):
        if value < 0:
            raise ValueError(f"unsigned type {cls} must not be negative")
        byte_len = cls.__class__.type_byte_length()
        if value.bit_length() > (byte_len << 3):
            raise ValueError(f"value out of bounds for {cls}")
        return super().__new__(cls, value)

    def __add__(self, other):
        return self.__class__(super().__add__(self.__class__.coerce_view(other)))

    def __sub__(self, other):
        return self.__class__(super().__sub__(self.__class__.coerce_view(other)))

    @classmethod
    def coerce_view(cls: Type[V], v: Any) -> V:
        if isinstance(v, uint) and cls.type_byte_length() != v.__class__.type_byte_length():
            raise ValueError("value must have equal byte length to coerce it")
        if isinstance(v, bytes):
            return cls.decode_bytes(v)
        return cls(v)

    def encode_bytes(self) -> bytes:
        return self.to_bytes(length=self.__class__.type_byte_length(), byteorder='little')


class Uint8Type(UintTypeBase):
    @classmethod
    def type_byte_length(mcs) -> int:
        return 1

    @classmethod
    def decode_bytes(mcs: Type[Type[V]], bytez: bytes) -> V:
        return uint8(int.from_bytes(bytez, byteorder='little'))

    def __repr__(self):
        return "uint8"


class uint8(uint, metaclass=Uint8Type):
    pass


class Uint16Type(UintTypeBase):
    @classmethod
    def type_byte_length(mcs) -> int:
        return 2

    @classmethod
    def decode_bytes(mcs: Type[Type[V]], bytez: bytes) -> V:
        return uint16(int.from_bytes(bytez, byteorder='little'))

    def __repr__(self):
        return "uint16"


class uint16(uint, metaclass=Uint16Type):
    pass


class Uint32Type(UintTypeBase):
    @classmethod
    def type_byte_length(mcs) -> int:
        return 4

    @classmethod
    def decode_bytes(mcs: Type[Type[V]], bytez: bytes) -> V:
        return uint32(int.from_bytes(bytez, byteorder='little'))

    def __repr__(self):
        return "uint32"


class uint32(uint, metaclass=Uint32Type):
    pass


class Uint64Type(UintTypeBase):
    @classmethod
    def type_byte_length(mcs) -> int:
        return 8

    @classmethod
    def decode_bytes(mcs: Type[Type[V]], bytez: bytes) -> V:
        return uint64(int.from_bytes(bytez, byteorder='little'))
    
    def __repr__(self):
        return "uint64"


class uint64(uint, metaclass=Uint64Type):
    pass


class Uint128Type(UintTypeBase):
    @classmethod
    def type_byte_length(mcs) -> int:
        return 16

    @classmethod
    def decode_bytes(mcs: Type[Type[V]], bytez: bytes) -> V:
        return uint128(int.from_bytes(bytez, byteorder='little'))

    def __repr__(self):
        return "uint128"


class uint128(uint, metaclass=Uint128Type):
    pass


class Uint256Type(UintTypeBase):
    @classmethod
    def type_byte_length(mcs) -> int:
        return 32

    @classmethod
    def decode_bytes(mcs: Type[Type[V]], bytez: bytes) -> V:
        return uint256(int.from_bytes(bytez, byteorder='little'))

    def __repr__(self):
        return "uint256"


class uint256(uint, metaclass=Uint256Type):
    pass


class bit(boolean):
    pass

class byte(uint8):
    pass
