from typing import Callable, NewType, Optional, Sequence, NamedTuple, cast
from merkling.tree import Link, Node, Root, RootNode, subtree_fill_to_length, subtree_fill_to_contents, to_gindex, zero_node, merkle_hash, Gindex, Commit


# Get the depth required for a given element count
# (in out): (0 0), (1 1), (2 1), (3 2), (4 2), (5 3), (6 3), (7 3), (8 3), (9 4)
def get_depth(elem_count: int) -> int:
    return (elem_count - 1).bit_length()


class TypeDef(type):
    pass


class TypeBase(type, metaclass=TypeDef):
    def default_node(self) -> Node:
        raise NotImplementedError

    def view_from_backing(self, node: Node, hook: Optional["ViewHook"]) -> "View":
        raise NotImplementedError

    def default(self, hook: Optional["ViewHook"]) -> "View":
        return self.view_from_backing(self.default_node(), hook)


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


class SubtreeType(BackedType):
    def depth(cls):
        raise NotImplementedError

    def item_elem_type(self, i: int) -> TypeBase:
        raise NotImplementedError


class SubtreeView(BackedView, metaclass=SubtreeType):

    def get(self, i: int) -> View:
        elem_type = self.__class__.item_elem_type(i)
        return elem_type.view_from_backing(
            self.get_backing().getter(to_gindex(i, self.__class__.depth())), lambda v: self.set(i, v))

    def set(self, i: int, v: View) -> None:
        setter_link: Link = self.get_backing().setter(to_gindex(i, self.__class__.depth()))
        self.set_backing(setter_link(v.get_backing()))


class BasicTypeDef(TypeDef):
    pass


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


class ListType(SubtreeType):
    def depth(cls) -> int:
        return get_depth(cls.limit()) + 1  # 1 extra for length mix-in

    def element_type(cls) -> TypeBase:
        raise NotImplementedError

    def item_elem_type(cls, i: int) -> TypeBase:
        return cls.element_type()

    def limit(cls) -> int:
        raise NotImplementedError

    def default_node(cls) -> Node:
        return Commit(zero_node(get_depth(cls.limit())), zero_node(0))

    def __repr__(self):
        return f"List[{self.element_type()}, {self.limit()}]"

    def __getitem__(self, params):
        (element_type, limit) = params

        class SpecialListType(ListType):
            def element_type(cls) -> TypeBase:
                return element_type

            def limit(cls) -> int:
                return limit

        class SpecialListView(List, metaclass=SpecialListType):
            pass

        return SpecialListView


class List(SubtreeView, metaclass=ListType):
    def length(self) -> int:
        ll_node = super().get_backing().getter(Gindex(3))
        ll = cast(Uint64, Uint64.view_from_backing(node=ll_node, hook=None))
        return int(ll)

    def append(self, v: View):
        ll = self.length()
        if ll >= self.__class__.limit():
            raise Exception("list is maximum capacity, cannot append")
        anchor = 1 << self.__class__.depth()
        set_last = self.get_backing().expand_into(Gindex(anchor | ll))
        next_backing = set_last(v.get_backing())
        set_length = next_backing.setter(Gindex(3))
        new_length = Uint64(ll + 1).get_backing()
        next_backing = set_length(new_length)
        self.set_backing(next_backing)

    def pop(self):
        ll = self.length()
        if ll == 0:
            raise Exception("list is empty, cannot pop")
        anchor = 1 << self.__class__.depth()
        set_last = self.get_backing().expand_into(Gindex(anchor | (ll - 1)))
        next_backing = set_last(zero_node(0))
        set_length = next_backing.setter(Gindex(3))
        new_length = Uint64(ll - 1).get_backing()
        next_backing = set_length(new_length)
        self.set_backing(next_backing)

    def get(self, i: int) -> View:
        if i > self.length():
            raise IndexError
        return super().get(i)

    def set(self, i: int, v: View) -> None:
        if i > self.length():
            raise IndexError
        super().set(i, v)


class VectorType(SubtreeType):
    def depth(cls) -> int:
        return get_depth(cls.length())

    def element_type(cls) -> TypeBase:
        raise NotImplementedError

    def item_elem_type(cls, i: int) -> TypeBase:
        return cls.element_type()

    def length(cls) -> int:
        raise NotImplementedError

    def default_node(cls) -> Node:
        elem = cls.element_type().default_node()
        return subtree_fill_to_length(elem, cls.depth(), cls.length())

    def __repr__(self):
        return f"Vector[{self.element_type()}, {self.length()}]"

    def __getitem__(self, params):
        (element_type, length) = params

        class SpecialVectorType(VectorType):
            def element_type(cls) -> TypeBase:
                return element_type

            def length(cls) -> int:
                return length

        class SpecialVectorView(Vector, metaclass=SpecialVectorType):
            pass

        return SpecialVectorView


class Vector(SubtreeView, metaclass=VectorType):
    def get(self, i: int) -> View:
        if i > self.__class__.length():
            raise IndexError
        return super().get(i)

    def set(self, i: int, v: View) -> None:
        if i > self.__class__.length():
            raise IndexError
        super().set(i, v)


class Uint64Type(BasicTypeBase, metaclass=BasicTypeDef):
    @classmethod
    def byte_length(mcs) -> int:
        return 8

    def __repr__(self):
        return "Uint64"


class Uint64(int, BasicView, metaclass=Uint64Type):
    pass


class Fields(NamedTuple):
    keys: Sequence[str]
    types: Sequence[TypeBase]


class ContainerType(SubtreeType):
    def depth(cls) -> int:
        return get_depth(len(cls.fields().keys))

    def item_elem_type(cls, i: int) -> TypeBase:
        return cls.fields().types[i]

    def fields(cls) -> Fields:
        raise NotImplementedError

    def default_node(cls) -> Node:
        return subtree_fill_to_contents([field.default_node() for field in cls.fields().types], cls.depth())

    def __repr__(self):
        return f"{self.__name__}(Container)\n" + '\n'.join(
            ('  ' + fkey + ': ' + repr(ftype)) for fkey, ftype in zip(self.fields().keys, self.fields().types)) + '\n'


class Container(SubtreeView, metaclass=ContainerType):

    @classmethod
    def fields(cls) -> Fields:
        if not hasattr(cls, '_fields'):
            annot = cls.__annotations__
            cls._fields = Fields(keys=list(annot.keys()), types=[v for v in annot.values()])
        return cls._fields

    def __getattribute__(self, item):
        if item.startswith('_'):
            return super().__getattribute__(item)
        else:
            keys = self.__class__.fields().keys
            if item in keys:
                return super().get(keys.index(item))
            else:
                return super().__getattribute__(item)

    def __setattr__(self, key, value):
        if key.startswith('_'):
            super().__setattr__(key, value)
        else:
            keys = self.__class__.fields().keys
            if key in keys:
                super().set(keys.index(key), value)
            else:
                super().__setattr__(key, value)


class Bytes32Type(TypeBase, metaclass=TypeDef):
    def default_node(self) -> Node:
        return zero_node(0)

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


class Validator(Container):
    pubkey: Bytes32 # TODO basic vec type for bytes48
    withdrawal_credentials: Bytes32  # Commitment to pubkey for withdrawals
    effective_balance: Uint64  # Balance at stake
    slashed: Bytes32 # todo
    # Status epochs
    activation_eligibility_epoch: Uint64  # When criteria for activation were met
    activation_epoch: Uint64
    exit_epoch: Uint64
    withdrawable_epoch: Uint64  # When validator can withdraw funds


print(Bytes32.default_node())
print(Uint64.default_node())
print(Vector[Uint64, 5].default_node())
print(List[Uint64, 5].default_node())

a = Validator
print(a)
b = a()
print(b)

print(Bytes32)
print(Bytes32())

SimpleVec = Vector[Uint64, 512]
print(SimpleVec)
data: Vector = SimpleVec()
print(data)
print(data.get_backing().merkle_root(merkle_hash).hex())
data.set(1, Uint64(123))
print(data.get_backing().merkle_root(merkle_hash).hex())
data.set(10, Uint64(42))
print(data.get_backing().merkle_root(merkle_hash).hex())
data.set(1, Uint64(0))
print(data.get_backing().merkle_root(merkle_hash).hex())
data.set(10, Uint64(0))
print(data.get_backing().merkle_root(merkle_hash).hex())

SimpleList = List[Uint64, 512]
print(SimpleList)
foo: List = SimpleList()
print(foo)
print(foo.get_backing().merkle_root(merkle_hash).hex())

Registry = List[Validator, 2**40]
print(Registry)
registry = Registry()
print(registry)
print(registry.get_backing().merkle_root(merkle_hash).hex())
print(registry.length())

val1 = Validator()
print(val1)
registry.append(val1)
print(registry)
print(registry.get_backing().merkle_root(merkle_hash).hex())
print(registry.length())

for i in range(100000):
    registry.append(val1)

print(registry)
print(registry.get_backing().merkle_root(merkle_hash).hex())
print(registry.length())

import time

N = 1000
start = time.time()
for i in range(N):
    registry.append(Validator())
    registry.get_backing().merkle_root(merkle_hash)

end = time.time()
delta = end - start
print(f"ops: {N}, time: {delta} seconds  ms/op: {(delta / N) * 1000}")
