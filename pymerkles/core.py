from typing import Callable, NewType, Optional
from pymerkles.tree import Node, Root, RootNode, zero_node


class TypeDef(type):
    def coerce_view(self, v: "View") -> "View":
        raise NotImplementedError

    def default_node(self) -> Node:
        raise NotImplementedError

    def view_from_backing(self, node: Node, hook: Optional["ViewHook"]) -> "View":
        raise NotImplementedError

    def default(self, hook: Optional["ViewHook"]) -> "View":
        raise NotImplementedError


class TypeBase(type, metaclass=TypeDef):
    def coerce_view(cls, v: "View") -> "View":
        raise NotImplementedError

    def default_node(cls) -> Node:
        raise NotImplementedError

    def view_from_backing(cls, node: Node, hook: Optional["ViewHook"]) -> "View":
        raise NotImplementedError

    def default(cls, hook: Optional["ViewHook"]) -> "View":
        return cls.view_from_backing(cls.default_node(), hook)


class View(object, metaclass=TypeBase):
    def get_backing(self) -> Node:
        raise NotImplementedError

    def set_backing(self, value):
        raise NotImplementedError


class BackedType(TypeBase, metaclass=TypeDef):
    def view_from_backing(cls, node: Node, hook: Optional["ViewHook"]) -> "View":
        return cls(backing=node, hook=hook)


class BackedView(View, metaclass=BackedType):
    _hook: Optional["ViewHook"]
    _backing: Node

    def __init__(self, *args, **kw):
        if "backing" in kw:
            self._backing = kw.pop("backing")
        else:
            self._backing = self.__class__.default_node()
        self._hook = kw.pop("hook", None)
        super().__init__(*args, **kw)

    def get_backing(self) -> Node:
        return self._backing

    def set_backing(self, value):
        self._backing = value
        # Propagate up the change if the view is hooked to a super view
        if self._hook is not None:
            self._hook(self)


ViewHook = NewType("ViewHook", Callable[[View], None])


class BasicTypeDef(TypeDef):
    def default_node(self) -> Node:
        raise NotImplementedError

    def byte_length(self) -> int:
        raise NotImplementedError

    def from_bytes(self, bytez: bytes, byteorder: str):
        raise NotImplementedError

    def view_from_backing(self, node: Node, hook: Optional["ViewHook"]) -> "View":
        raise NotImplementedError

    def basic_view_from_backing(self, node: RootNode, i: int) -> "BasicView":
        raise NotImplementedError


class BasicTypeBase(TypeBase, metaclass=BasicTypeDef):
    def default_node(cls) -> Node:
        return zero_node(0)

    def byte_length(cls) -> int:
        raise NotImplementedError

    def from_bytes(cls, bytez: bytes, byteorder: str):
        raise NotImplementedError

    def view_from_backing(cls, node: Node, hook: Optional["ViewHook"]) -> "View":
        if isinstance(node, RootNode):
            size = cls.byte_length()
            return cls.from_bytes(node.root[0:size], byteorder='little')
        else:
            raise Exception("cannot create basic view from composite node!")

    def basic_view_from_backing(cls, node: RootNode, i: int) -> "BasicView":
        size = cls.byte_length()
        return cls.from_bytes(node.root[i*size:(i+1)*size], byteorder='little')


class BasicView(View, metaclass=BasicTypeBase):
    def backing_from_base(self, base: RootNode, i: int) -> RootNode:
        raise NotImplementedError

    def to_bytes(self, length: int, byteorder: str) -> bytes:
        raise NotImplementedError

    def get_backing(self) -> Node:
        return RootNode(Root(self.to_bytes(length=32, byteorder='little')))

    def set_backing(self, value):
        raise Exception("cannot change the backing of a basic view")
