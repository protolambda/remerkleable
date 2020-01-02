from pymerkles.tree import Node, RootNode, Root, subtree_fill_to_contents, get_depth, to_gindex, must_leaf, \
    subtree_fill_to_length
from pymerkles.core import View, ViewHook, TypeDef, zero_node, FixedByteLengthTypeHelper, FixedByteLengthViewHelper, pack_bytes_to_chunks
from typing import Optional, Any
from types import GeneratorType


class ByteVectorType(FixedByteLengthTypeHelper, TypeDef):

    @classmethod
    def view_from_backing(mcs, node: Node, hook: Optional["ViewHook"] = None) -> View:
        depth = mcs.tree_depth()
        byte_len = mcs.type_byte_length()
        if depth == 0:
            if isinstance(node, RootNode):
                return mcs.decode_bytes(node.root[:byte_len])
            else:
                raise Exception("cannot create <= 32 byte view from composite node!")
        else:
            chunk_count = (byte_len + 31) // 32
            chunks = [node.getter(to_gindex(i, depth)) for i in range(chunk_count)]
            bytez = b"".join(map(must_leaf, chunks))[:byte_len]
            return mcs.decode_bytes(bytez)

    @classmethod
    def tree_depth(mcs) -> int:
        raise NotImplementedError

    def __getitem__(self, length):
        chunk_count = (length + 31) // 32
        tree_depth = get_depth(chunk_count)

        class SpecialByteVectorType(ByteVectorType):
            @classmethod
            def default_node(mcs) -> Node:
                return subtree_fill_to_length(zero_node(0), tree_depth, chunk_count)

            @classmethod
            def tree_depth(mcs) -> int:
                return tree_depth

            @classmethod
            def decode_bytes(mcs, bytez: bytes) -> "View":
                return SpecialByteVectorView(bytez)

            @classmethod
            def coerce_view(mcs, v: Any) -> View:
                return SpecialByteVectorView(v)

            @classmethod
            def type_byte_length(mcs) -> int:
                return length

        class SpecialByteVectorView(ByteVector, metaclass=SpecialByteVectorType):
            pass

        return SpecialByteVectorView

    def __repr__(self):
        return f"ByteVector[{self.type_byte_length()}]"


class ByteVector(bytes, FixedByteLengthViewHelper, View, metaclass=ByteVectorType):
    def __new__(cls, *args, **kwargs):
        byte_len = cls.__class__.type_byte_length()
        if len(args) == 0:
            return super().__new__(cls, b"\x00" * byte_len, **kwargs)
        elif len(args) == 1:
            val = args[0]
            if isinstance(args[0], (GeneratorType, list, tuple)):
                val = list(args[0])
            if isinstance(val, str):
                if val[:2] == '0x':
                    val = val[2:]
                data = bytes.fromhex(val)
            else:
                data = bytes(val)
            if len(data) != byte_len:
                raise Exception(f"incorrect byte length: {len(data)}, expected {byte_len}")
            return super().__new__(cls, data, **kwargs)
        else:
            raise Exception(f"unexpected arguments: {list(args)}")

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

    def encode_bytes(self) -> bytes:
        return self


# Define common special Byte vector view types, these are bytes-like:
# raw representation instead of backed by a binary tree. Inheriting Python "bytes"
Bytes1 = ByteVector[1]
Bytes4 = ByteVector[4]
Bytes8 = ByteVector[8]
Bytes32 = ByteVector[32]
Bytes48 = ByteVector[48]
Bytes96 = ByteVector[96]
