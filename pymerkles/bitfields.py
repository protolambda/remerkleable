from typing import cast, BinaryIO, List as PyList
from collections.abc import Sequence as ColSequence
from abc import ABC, abstractmethod
import io
from pymerkles.core import TypeDef, BackedView, FixedByteLengthTypeHelper, FixedByteLengthViewHelper, pack_bits_to_chunks
from pymerkles.tree import Node, Commit, zero_node, Gindex, to_gindex, Link, RootNode, NavigationError, Root, subtree_fill_to_contents
from pymerkles.subtree import get_depth
from pymerkles.basic import boolean, uint256


class BitsType(TypeDef):
    @classmethod
    def tree_depth(mcs) -> int:
        raise NotImplementedError


def _new_chunk_with_bit(chunk: RootNode, i: int, v: boolean) -> RootNode:
    new_chunk_root = bytearray(chunk.root)
    if v:
        new_chunk_root[(i & 0xf) >> 3] |= 1 << (i & 0x7)
    else:
        new_chunk_root[(i & 0xf) >> 3] &= (~(1 << (i & 0x7))) & 0xff
    return RootNode(root=Root(new_chunk_root))


# alike to the SubtreeView, but specialized to work on individual bits of chunks, instead of complex/basic types.
class BitsView(BackedView, ColSequence, ABC, metaclass=BitsType):

    @abstractmethod
    def length(self) -> int:
        raise NotImplementedError

    def get(self, i: int) -> boolean:
        ll = self.length()
        if i >= ll:
            raise NavigationError(f"cannot get bit {i} in bits of length {ll}")
        chunk_i = i >> 8
        chunk = self.get_backing().getter(to_gindex(chunk_i, self.__class__.tree_depth()))
        if isinstance(chunk, RootNode):
            chunk_byte = chunk.root[(i & 0xf) >> 3]
            return boolean((chunk_byte >> (i & 0x7)) & 1)
        else:
            raise NavigationError(f"chunk {chunk_i} for bit {i} is not available")

    def set(self, i: int, v: boolean) -> None:
        ll = self.length()
        if i >= ll:
            raise NavigationError(f"cannot set bit {i} in bits of length {ll}")
        chunk_i = i >> 8
        chunk_setter_link: Link = self.get_backing().setter(to_gindex(chunk_i, self.__class__.tree_depth()))
        chunk = self.get_backing().getter(to_gindex(chunk_i, self.__class__.tree_depth()))
        if isinstance(chunk, RootNode):
            new_chunk = _new_chunk_with_bit(chunk, i, v)
            self.set_backing(chunk_setter_link(new_chunk))
        else:
            raise NavigationError(f"chunk {chunk_i} for bit {i} is not available")

    def __len__(self):
        return self.length()

    def __iter__(self):
        return iter(self.get(i) for i in range(self.length()))

    def __getitem__(self, k):
        length = self.length()
        if isinstance(k, slice):
            start = 0 if k.start is None else k.start
            if start < 0:
                start = start % length
            end = length if k.stop is None else k.stop
            if end < 0:
                end = end % length
            return [self.get(i) for i in range(start, end)]
        else:
            return self.get(k)

    def __setitem__(self, k, v):
        length = self.length()
        if type(k) == slice:
            i = 0 if k.start is None else k.start
            end = length if k.stop is None else k.stop
            for item in v:
                self.set(i, item)
                i += 1
            if i != end:
                raise Exception("failed to do full slice-set, not enough values")
        else:
            self.set(k, v)


class BitListType(BitsType):
    @classmethod
    def contents_depth(mcs) -> int:  # depth excluding the length mix-in
        return get_depth((mcs.limit() + 255) // 256)

    @classmethod
    def tree_depth(mcs) -> int:
        return mcs.contents_depth() + 1  # 1 extra for length mix-in

    @classmethod
    @abstractmethod
    def limit(mcs) -> int:
        raise NotImplementedError

    @classmethod
    def default_node(mcs) -> Node:
        return Commit(zero_node(mcs.contents_depth()), zero_node(0))  # mix-in 0 as list length

    def __repr__(self):
        return f"BitList[{self.limit()}]"

    def __getitem__(self, limit):

        class SpecialBitListType(BitListType):
            @classmethod
            def limit(mcs) -> int:
                return limit

        class SpecialBitListView(BitList, metaclass=SpecialBitListType):
            pass

        return SpecialBitListView

    @classmethod
    def is_fixed_byte_length(mcs) -> bool:
        return False

    @classmethod
    def min_byte_length(mcs) -> int:
        return 1  # the delimiting bit will always require at least 1 byte

    @classmethod
    def max_byte_length(mcs) -> int:
        # maximum bit count in bytes rounded up + delimiting bit
        return (mcs.limit() + 7 + 1) // 8

    @classmethod
    def decode_bytes(mcs, bytez: bytes) -> "BitList":
        stream = io.BytesIO()
        stream.write(bytez)
        return mcs.deserialize(stream, len(bytez))

    @classmethod
    def deserialize(mcs, stream: BinaryIO, scope: int) -> "BitList":
        if scope < 1:
            raise Exception("cannot have empty scope for bitlist, need at least a delimiting bit")
        if scope*8 > mcs.max_byte_length():
            raise Exception(f"scope is too large: {scope}, max bitlist byte length is: {mcs.max_byte_length()}")
        chunks: PyList[Node] = []
        bytelen = scope - 1  # excluding the last byte (which contains the delimiting bit)
        while scope > 32:
            chunks.append(RootNode(Root(stream.read(32))))
            scope -= 32
        # scope is [1, 32] here
        last_chunk_part = stream.read(scope)
        last_byte = int(last_chunk_part[scope-1])
        if last_byte == 0:
            raise Exception("last byte must not be 0: bitlist requires delimiting bit")
        last_byte_bitlen = last_byte.bit_length() - 1  # excluding the delimiting bit
        last_chunk = last_chunk_part[:scope-1] + bytes(last_byte ^ (1 << last_byte_bitlen))
        last_chunk += b"\x00" * (32 - len(last_chunk))
        chunks.append(RootNode(Root(last_chunk)))
        bitlen = bytelen * 8 + last_byte_bitlen
        if bitlen > mcs.limit():
            raise Exception(f"bitlist too long: {bitlen}, delimiting bit is over limit ({mcs.limit()})")
        contents = subtree_fill_to_contents(chunks, mcs.contents_depth())
        backing = Commit(contents, uint256(bitlen).get_backing())
        return cast(BitList, mcs.view_from_backing(backing))


class BitList(BitsView, metaclass=BitListType):
    def __new__(cls, *args, **kwargs):
        vals = list(args)
        if len(vals) > 0:
            limit = cls.__class__.limit()
            if len(vals) > limit:
                raise Exception(f"too many bitlist inputs: {len(vals)}, limit is: {limit}")
            input_bits = list(map(bool, vals))
            input_nodes = pack_bits_to_chunks(input_bits)
            contents = subtree_fill_to_contents(input_nodes, cls.__class__.contents_depth())
            kwargs['backing'] = Commit(contents, uint256(len(input_bits)).get_backing())
        return super().__new__(cls, **kwargs)

    def length(self) -> int:
        ll_node = super().get_backing().getter(Gindex(3))
        ll = cast(uint256, uint256.view_from_backing(node=ll_node, hook=None))
        return int(ll)

    def append(self, v: boolean):
        ll = self.length()
        if ll >= self.__class__.limit():
            raise Exception("list is maximum capacity, cannot append")
        i = ll
        chunk_i = i // 256
        target: Gindex = to_gindex(chunk_i, self.__class__.tree_depth())
        if i & 0xff == 0:
            set_last = self.get_backing().expand_into(target)
            next_backing = set_last(_new_chunk_with_bit(zero_node(0), 0, v))
        else:
            set_last = self.get_backing().setter(target)
            chunk = self.get_backing().getter(target)
            if isinstance(chunk, RootNode):
                next_backing = set_last(_new_chunk_with_bit(chunk, i & 0xff, v))
            else:
                raise NavigationError(f"chunk {chunk_i} for bit {i} is not available")
        set_length = next_backing.setter(Gindex(3))
        new_length = uint256(ll + 1).get_backing()
        next_backing = set_length(new_length)
        self.set_backing(next_backing)

    def pop(self):
        ll = self.length()
        if ll == 0:
            raise Exception("list is empty, cannot pop")
        i = ll - 1
        chunk_i = i // 256
        target: Gindex = to_gindex(chunk_i, self.__class__.tree_depth())
        if i & 0xff == 0:
            set_last = self.get_backing().setter(target)
            next_backing = set_last(zero_node(0))
        else:
            set_last = self.get_backing().setter(target)
            chunk = self.get_backing().getter(target)
            if isinstance(chunk, RootNode):
                next_backing = set_last(_new_chunk_with_bit(chunk, ll & 0xff, boolean(False)))
            else:
                raise NavigationError(f"chunk {chunk_i} for bit {ll} is not available")

        # if possible, summarize
        can_summarize = (target & 1) == 0
        if can_summarize:
            # summarize to the highest node possible.
            # I.e. the resulting target must be a right-hand, unless it's the only content node.
            while (target & 1) == 0 and target != 0b10:
                target >>= 1
            summary_fn = next_backing.summarize_into(target)
            next_backing = summary_fn()

        set_length = next_backing.setter(Gindex(3))
        new_length = uint256(ll - 1).get_backing()
        next_backing = set_length(new_length)
        self.set_backing(next_backing)

    def get(self, i: int) -> boolean:
        if i > self.length():
            raise IndexError
        return super().get(i)

    def set(self, i: int, v: boolean) -> None:
        if i > self.length():
            raise IndexError
        super().set(i, v)

    def __repr__(self):
        try:
            length = self.length()
        except NavigationError:
            return f"Bitlist[{self.__class__.limit()}]~partial"
        try:
            bitstr = ''.join('1' if self.get(i) else '0' for i in range(length))
        except NavigationError:
            bitstr = " *partial bits* "
        return f"BitList[{self.__class__.limit()}]({length} bits: {bitstr})"

    def value_byte_length(self) -> int:
        # bit count in bytes rounded up + delimiting bit
        return (self.length() + 7 + 1) // 8

    def encode_bytes(self) -> bytes:
        raise NotImplementedError  # TODO concat chunks, end with delimiting bit

    def serialize(self, stream: BinaryIO) -> int:
        raise NotImplementedError  # TODO write chunks, end with delimiting bit


class BitVectorType(FixedByteLengthTypeHelper, BitsType):
    @classmethod
    def tree_depth(mcs) -> int:
        return get_depth((mcs.vector_length() + 255) // 256)

    @classmethod
    @abstractmethod
    def vector_length(mcs) -> int:
        raise NotImplementedError

    @classmethod
    def default_node(mcs) -> Node:
        return zero_node(mcs.tree_depth())

    def __repr__(self):
        return f"BitVector[{self.vector_length()}]"

    def __getitem__(self, length):

        class SpecialBitVectorType(BitVectorType):
            @classmethod
            def vector_length(mcs) -> int:
                return length

        class SpecialBitVectorView(BitVector, metaclass=SpecialBitVectorType):
            pass

        return SpecialBitVectorView

    @classmethod
    def type_byte_length(mcs) -> int:
        return (mcs.vector_length() + 7) // 8

    @classmethod
    def decode_bytes(mcs, bytez: bytes) -> "BitVector":
        stream = io.BytesIO()
        stream.write(bytez)
        return mcs.deserialize(stream, len(bytez))

    @classmethod
    def deserialize(mcs, stream: BinaryIO, scope: int) -> "BitVector":
        if scope*8 != mcs.max_byte_length():
            raise Exception(f"scope is invalid: {scope}, bitvector byte length is: {mcs.type_byte_length()}")
        chunks: PyList[Node] = []
        bytelen = scope - 1  # excluding the last byte
        while scope > 32:
            chunks.append(RootNode(Root(stream.read(32))))
            scope -= 32
        # scope is [1, 32] here
        last_chunk_part = stream.read(scope)
        last_byte = int(last_chunk_part[scope-1])
        bitlen = bytelen * 8 + last_byte.bit_length()
        if bitlen > mcs.vector_length():
            raise Exception(f"bitvector too long: {bitlen}, last byte has bits over bit length ({mcs.vector_length()})")
        last_chunk = last_chunk_part + (b"\x00" * (32 - len(last_chunk_part)))
        chunks.append(RootNode(Root(last_chunk)))
        backing = subtree_fill_to_contents(chunks, mcs.tree_depth())
        return cast(BitVector, mcs.view_from_backing(backing))


class BitVector(FixedByteLengthViewHelper, BitsView, metaclass=BitVectorType):
    def __new__(cls, *args, **kwargs):
        vals = list(args)
        if len(vals) > 0:
            veclen = cls.__class__.vector_length()
            if len(vals) != veclen:
                raise Exception(f"incorrect bitvector input: {len(vals)} bits, vector length is: {veclen}")
            input_bits = list(map(bool, vals))
            input_nodes = pack_bits_to_chunks(input_bits)
            kwargs['backing'] = subtree_fill_to_contents(input_nodes, cls.__class__.tree_depth())
        return super().__new__(cls, **kwargs)

    def length(self) -> int:
        return self.__class__.vector_length()

    def get(self, i: int) -> boolean:
        if i > self.length():
            raise IndexError
        return super().get(i)

    def set(self, i: int, v: boolean) -> None:
        if i > self.length():
            raise IndexError
        super().set(i, v)

    def __repr__(self):
        length = self.length()
        try:
            bitstr = ''.join('1' if self.get(i) else '0' for i in range(length))
        except NavigationError:
            bitstr = " *partial bits* "
        return f"BitVector[{length}]({bitstr})"

    def encode_bytes(self) -> bytes:
        raise NotImplementedError  # TODO concat chunks, end at length

    def serialize(self, stream: BinaryIO) -> int:
        raise NotImplementedError  # TODO write chunks, end at length
