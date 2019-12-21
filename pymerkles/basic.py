from typing import cast
from pymerkles.core import BasicTypeDef, BasicTypeBase, BasicView


class BoolTypeDef(BasicTypeDef):
    def byte_length(self) -> int:
        return 1


class BoolType(BasicTypeBase, metaclass=BoolTypeDef):
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


class UintTypeDef(BasicTypeDef):
    @classmethod
    def byte_length(mcs) -> int:
        raise NotImplementedError


class UintTypeBase(BasicTypeBase, metaclass=UintTypeDef):
    def __repr__(self):
        return "Uint"


class uint(int, BasicView, metaclass=UintTypeBase):
    def as_bytes(self) -> bytes:
        return self.to_bytes(length=self.__class__.byte_length(), byteorder='little')


class Uint8TypeDef(UintTypeDef):
    @classmethod
    def byte_length(mcs) -> int:
        return 1

    @classmethod
    def from_bytes(mcs, bytez: bytes) -> BasicView:
        return uint8(int.from_bytes(bytez, byteorder='little'))


class Uint8Type(UintTypeBase, metaclass=Uint8TypeDef):
    def __repr__(self):
        return "uint8"


class uint8(uint, metaclass=Uint8Type):
    pass


class Uint16TypeDef(UintTypeDef):
    @classmethod
    def byte_length(mcs) -> int:
        return 2

    @classmethod
    def from_bytes(mcs, bytez: bytes) -> BasicView:
        return uint16(int.from_bytes(bytez, byteorder='little'))


class Uint16Type(UintTypeBase, metaclass=Uint16TypeDef):
    def __repr__(self):
        return "uint16"


class uint16(uint, metaclass=Uint16Type):
    pass


class Uint32TypeDef(UintTypeDef):
    @classmethod
    def byte_length(mcs) -> int:
        return 4

    @classmethod
    def from_bytes(mcs, bytez: bytes) -> BasicView:
        return uint32(int.from_bytes(bytez, byteorder='little'))


class Uint32Type(UintTypeBase, metaclass=Uint32TypeDef):
    def __repr__(self):
        return "uint32"


class uint32(uint, metaclass=Uint32Type):
    pass


class Uint64TypeDef(UintTypeDef):
    @classmethod
    def byte_length(mcs) -> int:
        return 8

    @classmethod
    def from_bytes(mcs, bytez: bytes) -> BasicView:
        return uint64(int.from_bytes(bytez, byteorder='little'))


class Uint64Type(UintTypeBase, metaclass=Uint64TypeDef):
    
    def __repr__(self):
        return "uint64"


class uint64(uint, metaclass=Uint64Type):
    pass


class Uint128TypeDef(UintTypeDef):
    @classmethod
    def byte_length(mcs) -> int:
        return 16

    @classmethod
    def from_bytes(mcs, bytez: bytes) -> BasicView:
        return uint128(int.from_bytes(bytez, byteorder='little'))


class Uint128Type(UintTypeBase, metaclass=Uint128TypeDef):

    def __repr__(self):
        return "uint128"


class uint128(uint, metaclass=Uint128Type):
    pass


class Uint256TypeDef(UintTypeDef):
    @classmethod
    def byte_length(mcs) -> int:
        return 32

    @classmethod
    def from_bytes(mcs, bytez: bytes) -> BasicView:
        return uint256(int.from_bytes(bytez, byteorder='little'))


class Uint256Type(UintTypeBase, metaclass=Uint256TypeDef):
    def __repr__(self):
        return "uint256"


class uint256(uint, metaclass=Uint256Type):
    pass
