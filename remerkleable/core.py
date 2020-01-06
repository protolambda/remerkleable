from typing import Callable, Optional, Any, cast, List as PyList, BinaryIO, TypeVar, Type, Protocol, runtime_checkable
from remerkleable.tree import Node, Root, RootNode, zero_node, merkle_hash
from itertools import zip_longest
from typing import Iterable, Tuple

OFFSET_BYTE_LENGTH = 4


V = TypeVar('V', bound="View")


@runtime_checkable
class TypeDef(Protocol):
    @classmethod
    def coerce_view(cls: Type[V], v: Any) -> V:
        ...

    @classmethod
    def default(cls: Type[V], hook: Optional["ViewHook[V]"]) -> V:
        ...

    @classmethod
    def default_node(cls) -> Node:
        ...

    @classmethod
    def view_from_backing(cls: Type[V], node: Node, hook: Optional["ViewHook[V]"] = None) -> V:
        ...

    @classmethod
    def is_fixed_byte_length(cls) -> bool:
        ...

    @classmethod
    def type_byte_length(cls) -> int:
        ...

    @classmethod
    def min_byte_length(cls) -> int:
        ...

    @classmethod
    def max_byte_length(cls) -> int:
        ...

    @classmethod
    def decode_bytes(cls: Type[V], bytez: bytes) -> V:
        ...

    @classmethod
    def deserialize(cls: Type[V], stream: BinaryIO, scope: int) -> V:
        ...

    @classmethod
    def type_repr(cls) -> str:
        ...


HV = TypeVar('HV', bound="View")
ViewHook = Callable[[HV], None]


class View(TypeDef):

    @classmethod
    def default(cls: Type[V], hook: Optional[ViewHook[V]]) -> V:
        return cls.view_from_backing(cls.default_node(), hook)

    def get_backing(self) -> Node:
        raise NotImplementedError

    def set_backing(self, value):
        raise NotImplementedError

    def copy(self: V) -> V:
        return self.__class__.view_from_backing(self.get_backing())

    @classmethod
    def type_byte_length(cls) -> int:
        raise Exception("type is dynamic length, or misses overrides. Cannot get type byte length.")

    def value_byte_length(self) -> int:
        raise NotImplementedError

    def __bytes__(self):
        return self.encode_bytes()

    def encode_bytes(self) -> bytes:
        raise NotImplementedError

    def serialize(self, stream: BinaryIO) -> int:
        out = self.encode_bytes()
        stream.write(out)
        return len(out)

    def hash_tree_root(self) -> Root:
        return self.get_backing().merkle_root(merkle_hash)

    def __eq__(self, other):
        # TODO: should we check types here?
        if not isinstance(other, View):
            other = self.__class__.coerce_view(other)
        return self.hash_tree_root() == other.hash_tree_root()

    def __hash__(self):
        return hash(self.hash_tree_root())


class FixedByteLengthViewHelper(View):
    @classmethod
    def is_fixed_byte_length(cls) -> bool:
        return True

    @classmethod
    def min_byte_length(cls) -> int:
        return cls.type_byte_length()

    @classmethod
    def max_byte_length(cls) -> int:
        return cls.type_byte_length()

    @classmethod
    def deserialize(cls: Type[V], stream: BinaryIO, scope: int) -> V:
        n = cls.type_byte_length()
        if n != scope:
            raise Exception(f"scope {scope} is not valid for expected byte length {n}")
        return cls.decode_bytes(stream.read(n))

    def value_byte_length(self) -> int:
        return self.type_byte_length()


class BackedView(View, TypeDef):
    _hook: Optional[ViewHook]
    _backing: Node

    @classmethod
    def view_from_backing(cls: Type[V], node: Node, hook: Optional[ViewHook[V]] = None) -> V:
        return cls(backing=node, hook=hook)

    def __new__(cls, backing: Optional[Node] = None, hook: Optional[ViewHook[V]] = None, **kwargs):
        if backing is None:
            backing = cls.default_node()
        out = super().__new__(cls, **kwargs)
        out._backing = backing
        out._hook = hook
        return out

    def get_backing(self) -> Node:
        return self._backing

    def set_backing(self, value):
        self._backing = value
        # Propagate up the change if the view is hooked to a super view
        if self._hook is not None:
            self._hook(self)


BV = TypeVar('BV', bound="BasicView")


@runtime_checkable
class BasicTypeDef(TypeDef, Protocol):
    @classmethod
    def basic_view_from_backing(cls: Type[BV], node: RootNode, i: int) -> BV:
        ...

    @classmethod
    def pack_views(cls: Type[BV], views: PyList[BV]) -> PyList[Node]:
        ...


class BasicView(FixedByteLengthViewHelper, BasicTypeDef):
    @classmethod
    def default_node(cls) -> Node:
        return zero_node(0)

    @classmethod
    def view_from_backing(cls: Type[BV], node: Node, hook: Optional[ViewHook[BV]] = None) -> V:
        if isinstance(node, RootNode):
            size = cls.type_byte_length()
            return cls.decode_bytes(node.root[0:size])
        else:
            raise Exception("cannot create basic view from composite node!")

    @classmethod
    def basic_view_from_backing(cls: Type[BV], node: RootNode, i: int) -> BV:
        size = cls.type_byte_length()
        return cls.decode_bytes(node.root[i*size:(i+1)*size])

    @classmethod
    def pack_views(cls: Type[BV], views: PyList[BV]) -> PyList[Node]:
        return list(pack_ints_to_chunks((cast(int, v) for v in views), 32 // cls.type_byte_length()))

    def copy(self: V) -> V:
        return self  # basic views do not have to be copied, they are immutable

    def backing_from_base(self, base: RootNode, i: int) -> RootNode:
        section_bytez = self.encode_bytes()
        chunk_bytez = base.root[:len(section_bytez)*i] + section_bytez + base.root[len(section_bytez)*(i+1):]
        return RootNode(Root(chunk_bytez))

    def get_backing(self) -> Node:
        bytez = self.encode_bytes()
        return RootNode(Root(bytez + b"\x00" * (32 - len(bytez))))

    def set_backing(self, value):
        raise Exception("cannot change the backing of a basic view")


# recipe from more-itertools, should have been in itertools really.
def grouper(items: Iterable, n: int, fillvalue=None) -> Iterable[Tuple]:
    """Collect data into fixed-length chunks or blocks
       grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx"""
    args = [iter(items)] * n
    # The *same* iterator is referenced n times, thus zip produces tuples of n elements from the same iterator
    return zip_longest(*args, fillvalue=fillvalue)


def pack_ints_to_chunks(items: Iterable[int], items_per_chunk: int) -> PyList[Node]:
    item_byte_len = 32 // items_per_chunk
    return [RootNode(Root(b"".join(v.to_bytes(length=item_byte_len, byteorder='little') for v in chunk_elems)))
            for chunk_elems in grouper(items, items_per_chunk, fillvalue=0)]


def bits_to_byte_int(byte: Tuple[bool, bool, bool, bool, bool, bool, bool, bool]) -> int:
    return sum([byte[i] << i for i in range(0, 8)])


def byte_int_to_byte(b: int) -> bytes:
    return b.to_bytes(length=1, byteorder='little')


def pack_bits_to_chunks(items: Iterable[bool]) -> PyList[Node]:
    return pack_byte_ints_to_chunks(map(bits_to_byte_int, grouper(items, 8, fillvalue=0)))


def pack_byte_ints_to_chunks(items: Iterable[int]) -> PyList[Node]:
    return [RootNode(Root(b"".join(map(byte_int_to_byte, chunk_bytes))))
            for chunk_bytes in grouper(items, 32, fillvalue=0)]


def pack_bytes_to_chunks(bytez: bytes) -> PyList[Node]:
    return [RootNode(Root(bytez[i:min(i+32, len(bytez))])) for i in range(0, len(bytez), 32)]
