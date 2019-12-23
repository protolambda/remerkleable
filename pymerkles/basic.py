from typing import Any
from pymerkles.core import BasicTypeDef, BasicView, View


class BoolType(BasicTypeDef):
    @classmethod
    def coerce_view(mcs, v: Any) -> View:
        return boolean(v)

    @classmethod
    def byte_length(mcs) -> int:
        return 1

    @classmethod
    def from_bytes(mcs, bytez: bytes) -> BasicView:
        return boolean(bytez != b"\x00")

    def __repr__(self):
        return "boolean"


class boolean(int, BasicView, metaclass=BoolType):

    def as_bytes(self) -> bytes:
        return b"\x01" if self else b"\x00"

    def __new__(cls, value: int):  # int value, but can be any subclass of int (bool, Bit, Bool, etc...)
        if value < 0 or value > 1:
            raise ValueError(f"value {value} out of bounds for bit")
        return super().__new__(cls, value)

    def __bool__(self):
        return self > 0


class UintTypeBase(BasicTypeDef):
    @classmethod
    def byte_length(mcs) -> int:
        raise NotImplementedError

    def __repr__(self):
        return "Uint"


class uint(int, BasicView, metaclass=UintTypeBase):
    @classmethod
    def coerce_view(cls, v: Any) -> View:
        return cls(v)

    def as_bytes(self) -> bytes:
        return self.to_bytes(length=self.__class__.byte_length(), byteorder='little')


class Uint8Type(UintTypeBase):
    @classmethod
    def byte_length(mcs) -> int:
        return 1

    @classmethod
    def from_bytes(mcs, bytez: bytes) -> BasicView:
        return uint8(int.from_bytes(bytez, byteorder='little'))

    def __repr__(self):
        return "uint8"


class uint8(uint, metaclass=Uint8Type):
    pass


class Uint16Type(UintTypeBase):
    @classmethod
    def byte_length(mcs) -> int:
        return 2

    @classmethod
    def from_bytes(mcs, bytez: bytes) -> BasicView:
        return uint16(int.from_bytes(bytez, byteorder='little'))

    def __repr__(self):
        return "uint16"


class uint16(uint, metaclass=Uint16Type):
    pass


class Uint32Type(UintTypeBase):
    @classmethod
    def byte_length(mcs) -> int:
        return 4

    @classmethod
    def from_bytes(mcs, bytez: bytes) -> BasicView:
        return uint32(int.from_bytes(bytez, byteorder='little'))

    def __repr__(self):
        return "uint32"


class uint32(uint, metaclass=Uint32Type):
    pass


class Uint64Type(UintTypeBase):
    @classmethod
    def byte_length(mcs) -> int:
        return 8

    @classmethod
    def from_bytes(mcs, bytez: bytes) -> BasicView:
        return uint64(int.from_bytes(bytez, byteorder='little'))
    
    def __repr__(self):
        return "uint64"


class uint64(uint, metaclass=Uint64Type):
    pass


class Uint128Type(UintTypeBase):
    @classmethod
    def byte_length(mcs) -> int:
        return 16

    @classmethod
    def from_bytes(mcs, bytez: bytes) -> BasicView:
        return uint128(int.from_bytes(bytez, byteorder='little'))

    def __repr__(self):
        return "uint128"


class uint128(uint, metaclass=Uint128Type):
    pass


class Uint256Type(UintTypeBase):
    @classmethod
    def byte_length(mcs) -> int:
        return 32

    @classmethod
    def from_bytes(mcs, bytez: bytes) -> BasicView:
        return uint256(int.from_bytes(bytez, byteorder='little'))

    def __repr__(self):
        return "uint256"


class uint256(uint, metaclass=Uint256Type):
    pass
