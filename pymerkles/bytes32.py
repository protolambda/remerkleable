from pymerkles.tree import Node, RootNode, Root
from pymerkles.core import View, ViewHook, TypeDef, zero_node, FixedByteLengthTypeHelper, FixedByteLengthViewHelper
from typing import Optional, Any


class Bytes32TypeHelper(FixedByteLengthTypeHelper, TypeDef):
    @classmethod
    def type_byte_length(mcs) -> int:
        return 32

    @classmethod
    def decode_bytes(mcs, bytez: bytes) -> "View":
        return Bytes32(bytez)

    @classmethod
    def coerce_view(mcs, v: Any) -> View:
        return Bytes32(v)

    @classmethod
    def default_node(mcs) -> Node:
        return zero_node(0)

    @classmethod
    def view_from_backing(mcs, node: Node, hook: Optional["ViewHook"] = None) -> "View":
        if isinstance(node, RootNode):
            return Bytes32(node.root)
        else:
            raise Exception("cannot create root view from composite node!")

    def __repr__(self):
        return "Bytes32"


class Bytes32(bytes, FixedByteLengthViewHelper, View, metaclass=Bytes32TypeHelper):
    def __new__(cls, *args, **kwargs):
        if len(args) == 0:
            return super().__new__(cls, b"\x00" * 32, **kwargs)
        else:
            if len(args) == 1:
                val = args[0]
                if isinstance(val, str):
                    if val[:2] == '0x':
                        val = val[2:]
                    val = bytes.fromhex(val)
                args = [val]
            out = super().__new__(cls, *args, **kwargs)
            if len(out) != 32:
                raise Exception(f"Bytes32 must be exactly 32 bytes, not {len(out)}")
            return out

    def get_backing(self) -> Node:
        return RootNode(Root(self))

    def set_backing(self, value):
        raise Exception("cannot change the backing of a root view")

    def __repr__(self):
        return "0x" + self.hex()

    def __str__(self):
        return "0x" + self.hex()

    def encode_bytes(self) -> bytes:
        return self
