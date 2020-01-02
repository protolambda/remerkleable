from typing import Callable, Optional, Any, cast, List as PyList, BinaryIO, TypeVar, Type
from abc import ABCMeta, ABC, abstractmethod
from pymerkles.tree import Node, Root, RootNode, zero_node, merkle_hash
from itertools import zip_longest
from typing import Iterable, Tuple

OFFSET_BYTE_LENGTH = 4


V = TypeVar('V', bound="View")


class TypeDef(ABCMeta):
    @classmethod
    @abstractmethod
    def coerce_view(mcs: Type[Type[V]], v: Any) -> V:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def default_node(mcs) -> Node:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def view_from_backing(mcs: Type[Type[V]], node: Node, hook: Optional["ViewHook[V]"] = None) -> V:
        raise NotImplementedError

    @classmethod
    def default(mcs: Type[Type[V]], hook: Optional["ViewHook[V]"]) -> V:
        return mcs.view_from_backing(mcs.default_node(), hook)

    @classmethod
    def is_fixed_byte_length(mcs) -> bool:
        raise NotImplementedError

    @classmethod
    def type_byte_length(mcs) -> int:
        raise Exception("type is dynamic length, or misses overrides. Cannot get type byte length.")

    @classmethod
    @abstractmethod
    def min_byte_length(mcs) -> int:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def max_byte_length(mcs) -> int:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def decode_bytes(mcs: Type[Type[V]], bytez: bytes) -> V:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def deserialize(mcs: Type[Type[V]], stream: BinaryIO, scope: int) -> V:
        raise NotImplementedError


class FixedByteLengthTypeHelper(TypeDef):
    @classmethod
    def is_fixed_byte_length(mcs) -> bool:
        return True

    @classmethod
    def type_byte_length(mcs) -> int:
        raise NotImplementedError

    @classmethod
    def min_byte_length(mcs) -> int:
        return mcs.type_byte_length()

    @classmethod
    def max_byte_length(mcs) -> int:
        return mcs.type_byte_length()

    @classmethod
    def deserialize(mcs: Type[Type[V]], stream: BinaryIO, scope: int) -> V:
        n = mcs.type_byte_length()
        if n != scope:
            raise Exception(f"scope {scope} is not valid for expected byte length {n}")
        return mcs.decode_bytes(stream.read(n))


HV = TypeVar('HV', bound="View")
ViewHook = Callable[[HV], None]


# Some class-methods call the metaclass method, and are only strictly here to track dependencies,
# as some view implementations only implement type-level methods as class-methods.
# E.g. Container, which would not have access to its annotations (fields) from the metaclass.
class View(ABC, object, metaclass=TypeDef):
    @classmethod
    def coerce_view(cls: Type[V], v: Any) -> V:
        return cls.__class__.coerce_view(v)

    @classmethod
    def default_node(cls) -> Node:
        return cls.__class__.default_node()

    @classmethod
    def view_from_backing(cls: Type[V], node: Node, hook: Optional[ViewHook[V]] = None) -> V:
        return cls.__class__.view_from_backing(node=node, hook=hook)

    @classmethod
    def default(cls: Type[V], hook: Optional[ViewHook[V]]) -> V:
        return cls.__class__.default(hook)

    @abstractmethod
    def get_backing(self) -> Node:
        raise NotImplementedError

    @abstractmethod
    def set_backing(self, value):
        raise NotImplementedError

    def copy(self: V) -> V:
        return self.__class__.view_from_backing(self.get_backing())

    @abstractmethod
    def value_byte_length(self) -> int:
        raise NotImplementedError

    @classmethod
    def decode_bytes(cls: Type[V], bytez: bytes) -> V:
        return cls.__class__.decode_bytes(bytez)

    @classmethod
    def deserialize(cls: Type[V], stream: BinaryIO, scope: int) -> V:
        return cls.__class__.deserialize(stream, scope)

    def __bytes__(self):
        return self.encode_bytes()

    @abstractmethod
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


class FixedByteLengthViewHelper(View, metaclass=FixedByteLengthTypeHelper):
    def value_byte_length(self) -> int:
        return self.__class__.type_byte_length()


class BackedView(View, metaclass=TypeDef):
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


BV = TypeVar('BV', bound='BasicView')


class BasicTypeHelperDef(FixedByteLengthTypeHelper, TypeDef):
    @classmethod
    def default_node(mcs) -> Node:
        return zero_node(0)

    @classmethod
    @abstractmethod
    def type_byte_length(mcs) -> int:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def decode_bytes(mcs: Type[Type[V]], bytez: bytes) -> V:
        raise NotImplementedError

    @classmethod
    def view_from_backing(mcs: Type[Type[V]], node: Node, hook: Optional[ViewHook[V]] = None) -> V:
        if isinstance(node, RootNode):
            size = mcs.type_byte_length()
            return mcs.decode_bytes(node.root[0:size])
        else:
            raise Exception("cannot create basic view from composite node!")

    @classmethod
    def basic_view_from_backing(mcs: Type[BV], node: RootNode, i: int) -> BV:
        size = mcs.type_byte_length()
        return mcs.decode_bytes(node.root[i*size:(i+1)*size])

    @classmethod
    def pack_views(mcs: Type[BV], views: PyList[BV]) -> PyList[Node]:
        return list(pack_ints_to_chunks((cast(int, v) for v in views), 32 // mcs.type_byte_length()))


class BasicView(FixedByteLengthViewHelper, ABC, metaclass=BasicTypeHelperDef):
    @classmethod
    def default_node(cls) -> Node:
        return cls.__class__.default_node()

    @classmethod
    def decode_bytes(cls: Type[BV], bytez: bytes) -> BV:
        return cls.__class__.decode_bytes(bytez)

    @classmethod
    def view_from_backing(cls: Type[V], node: Node, hook: Optional[ViewHook[V]] = None) -> V:
        return cls.__class__.view_from_backing(node=node, hook=hook)

    @classmethod
    def basic_view_from_backing(cls: Type[BV], node: RootNode, i: int) -> BV:
        return cls.__class__.basic_view_from_backing(node, i)

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
