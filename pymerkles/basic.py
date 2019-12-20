from pymerkles.core import BasicTypeDef, BasicTypeBase, BasicView


class BoolType(BasicTypeBase, metaclass=BasicTypeDef):
    @classmethod
    def byte_length(mcs) -> int:
        return 1

    def __repr__(self):
        return "Bool"


class boolean(int, BasicView, metaclass=BoolType):

    def __new__(cls, value: int):  # int value, but can be any subclass of int (bool, Bit, Bool, etc...)
        if value < 0 or value > 1:
            raise ValueError(f"value {value} out of bounds for bit")
        return super().__new__(cls, value)

    def __bool__(self):
        return self > 0


class Uint8Type(BasicTypeBase, metaclass=BasicTypeDef):
    @classmethod
    def byte_length(mcs) -> int:
        return 1

    def __repr__(self):
        return "Uint8"


class uint8(int, BasicView, metaclass=Uint8Type):
    pass


class Uint16Type(BasicTypeBase, metaclass=BasicTypeDef):
    @classmethod
    def byte_length(mcs) -> int:
        return 2

    def __repr__(self):
        return "Uint16"


class uint16(int, BasicView, metaclass=Uint16Type):
    pass


class Uint32Type(BasicTypeBase, metaclass=BasicTypeDef):
    @classmethod
    def byte_length(mcs) -> int:
        return 4

    def __repr__(self):
        return "Uint32"


class uint32(int, BasicView, metaclass=Uint32Type):
    pass


class Uint64Type(BasicTypeBase, metaclass=BasicTypeDef):
    @classmethod
    def byte_length(mcs) -> int:
        return 8

    def __repr__(self):
        return "Uint64"


class uint64(int, BasicView, metaclass=Uint64Type):
    pass


class Uint128Type(BasicTypeBase, metaclass=BasicTypeDef):
    @classmethod
    def byte_length(mcs) -> int:
        return 16

    def __repr__(self):
        return "Uint128"


class uint128(int, BasicView, metaclass=Uint128Type):
    pass


class Uint256Type(BasicTypeBase, metaclass=BasicTypeDef):
    @classmethod
    def byte_length(mcs) -> int:
        return 32

    def __repr__(self):
        return "Uint256"


class uint256(int, BasicView, metaclass=Uint256Type):
    pass
