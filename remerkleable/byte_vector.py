from typing import Optional, Any, TypeVar, Type
from types import GeneratorType
from remerkleable.tree import Node, RootNode, Root, subtree_fill_to_contents, get_depth, to_gindex, must_leaf, \
    subtree_fill_to_length, Gindex
from remerkleable.core import View, ViewHook, zero_node, FixedByteLengthViewHelper, pack_bytes_to_chunks
from remerkleable.basic import byte

V = TypeVar('V', bound=View)


class ByteVector(bytes, FixedByteLengthViewHelper, View):
    def __new__(cls, *args, **kwargs):
        byte_len = cls.type_byte_length()
        if len(args) == 0:
            return super().__new__(cls, b"\x00" * byte_len, **kwargs)
        elif len(args) == 1:
            val = args[0]
            if isinstance(val, bytes):
                data = val
            elif isinstance(val, (GeneratorType, list, tuple)):
                data = bytes(args[0])
            elif isinstance(val, str):
                if val[:2] == '0x':
                    val = val[2:]
                data = bytes.fromhex(val)
            else:
                data = bytes(val)
            if len(data) != byte_len:
                raise Exception(f"incorrect byte length: {len(data)}, expected {byte_len}")
            return super().__new__(cls, data, **kwargs)
        else:
            return super().__new__(cls, bytes(args), **kwargs)

    def __class_getitem__(cls, length) -> Type["ByteVector"]:
        chunk_count = (length + 31) // 32
        tree_depth = get_depth(chunk_count)

        class SpecialByteVectorView(ByteVector):
            @classmethod
            def default_node(cls) -> Node:
                return subtree_fill_to_length(zero_node(0), tree_depth, chunk_count)

            @classmethod
            def tree_depth(cls) -> int:
                return tree_depth

            @classmethod
            def type_byte_length(cls) -> int:
                return length

        return SpecialByteVectorView

    @classmethod
    def type_repr(cls) -> str:
        return f"ByteVector[{cls.type_byte_length()}]"

    @classmethod
    def coerce_view(cls: Type[V], v: Any) -> V:
        return cls(v)

    @classmethod
    def view_from_backing(cls: Type[V], node: Node, hook: Optional[ViewHook[V]] = None) -> V:
        depth = cls.tree_depth()
        byte_len = cls.type_byte_length()
        if depth == 0:
            if isinstance(node, RootNode):
                return cls.decode_bytes(node.root[:byte_len])
            else:
                raise Exception("cannot create <= 32 byte view from composite node!")
        else:
            chunk_count = (byte_len + 31) // 32
            chunks = [node.getter(to_gindex(i, depth)) for i in range(chunk_count)]
            bytez = b"".join(map(must_leaf, chunks))[:byte_len]
            return cls.decode_bytes(bytez)

    @classmethod
    def tree_depth(cls) -> int:
        raise NotImplementedError

    def get_backing(self) -> Node:
        if len(self) == 32:  # super common case, optimize for it
            return RootNode(Root(self))
        elif len(self) < 32:
            return RootNode(Root(self + b"\x00" * (32 - len(self))))
        else:
            return subtree_fill_to_contents(pack_bytes_to_chunks(self), self.__class__.tree_depth())

    def set_backing(self, value):
        raise Exception("cannot change the backing of a ByteVector view, init a new view instead")

    def __repr__(self):
        return "0x" + self.hex()

    def __str__(self):
        return "0x" + self.hex()

    @classmethod
    def decode_bytes(cls: Type[V], bytez: bytes) -> V:
        return cls(bytez)

    def encode_bytes(self) -> bytes:
        return self

    @classmethod
    def navigate_type(cls, key: Any) -> Type[View]:
        if key < 0 or key > cls.type_byte_length():
            raise KeyError
        return byte

    @classmethod
    def key_to_static_gindex(cls, key: Any) -> Gindex:
        depth = cls.tree_depth()
        byte_len = cls.type_byte_length()
        if key < 0 or key >= byte_len:
            raise KeyError
        chunk_i = key // 32
        return to_gindex(chunk_i, depth)

    def navigate_view(self, key: Any) -> View:
        return byte(self.__getitem__(key))


# Define common special Byte vector view types, these are bytes-like:
# raw representation instead of backed by a binary tree. Inheriting Python "bytes"
Bytes1 = ByteVector[1]
Bytes4 = ByteVector[4]
Bytes8 = ByteVector[8]
Bytes32 = ByteVector[32]
Bytes48 = ByteVector[48]
Bytes96 = ByteVector[96]
