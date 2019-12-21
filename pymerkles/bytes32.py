from pymerkles.tree import Node, RootNode, Root
from pymerkles.core import View, ViewHook, TypeDef, TypeBase, zero_node
from typing import Optional


class Bytes32TypeDef(TypeDef):
    @classmethod
    def default_node(mcs) -> Node:
        return zero_node(0)


class Bytes32Type(TypeBase, metaclass=Bytes32TypeDef):

    def view_from_backing(cls, node: Node, hook: Optional["ViewHook"]) -> "View":
        if isinstance(node, RootNode):
            return Bytes32(node.root)
        else:
            raise Exception("cannot create root view from composite node!")

    def __repr__(self):
        return "Bytes32"


class Bytes32(bytes, View, metaclass=Bytes32Type):
    def __new__(cls, *args, **kwargs):
        if len(args) == 0:
            return super().__new__(cls, b"\x00" * 32, **kwargs)

    def get_backing(self) -> Node:
        return RootNode(Root(self))

    def set_backing(self, value):
        raise Exception("cannot change the backing of a root view")

    def __repr__(self):
        return "0x" + self.hex()

    def __str__(self):
        return "0x" + self.hex()

