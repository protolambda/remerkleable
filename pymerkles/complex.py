from typing import Sequence, NamedTuple, cast, List as PyList, Dict, Any, BinaryIO, Optional
from types import GeneratorType
from collections.abc import Sequence as ColSequence
from itertools import chain
from abc import ABC, abstractmethod
import io
from pymerkles.core import TypeDef, View, BasicTypeHelperDef, BasicView, OFFSET_BYTE_LENGTH, ViewHook
from pymerkles.basic import uint256, uint8, uint32
from pymerkles.tree import Node, subtree_fill_to_length, subtree_fill_to_contents,\
    zero_node, Gindex, Commit, to_gindex, NavigationError, get_depth
from pymerkles.subtree import SubtreeTypeDef, SubtreeView


def decode_offset(stream: BinaryIO) -> uint32:
    return cast(uint32, uint32.deserialize(stream, OFFSET_BYTE_LENGTH))


class MonoSubtreeTypeDef(SubtreeTypeDef):
    @classmethod
    def element_cls(mcs) -> TypeDef:
        raise NotImplementedError

    @classmethod
    def is_packed(mcs) -> bool:
        raise NotImplementedError

    @classmethod
    def to_chunk_length(mcs, elems_length: int) -> int:
        if mcs.is_packed():
            elem_type: TypeDef = mcs.element_cls()
            if isinstance(elem_type, BasicTypeHelperDef):
                basic_elem_type: BasicTypeHelperDef = elem_type
                elems_per_chunk = 32 // basic_elem_type.type_byte_length()
                return (elems_length + elems_per_chunk - 1) // elems_per_chunk
            else:
                raise Exception("cannot append a packed element that is not a basic type")
        else:
            return elems_length

    @classmethod
    def views_into_chunks(mcs, views: PyList[View]) -> PyList[Node]:
        if mcs.is_packed():
            elem_type: TypeDef = mcs.element_cls()
            if isinstance(elem_type, BasicTypeHelperDef):
                basic_elem_type: BasicTypeHelperDef = elem_type
                return basic_elem_type.pack_views(views)
            else:
                raise Exception("cannot append a packed element that is not a basic type")
        else:
            return [v.get_backing() for v in views]

    @classmethod
    @abstractmethod
    def is_valid_count(mcs, count: int) -> bool:
        raise NotImplementedError

    @classmethod
    def deserialize_elements(mcs, stream: BinaryIO, scope: int) -> PyList[View]:
        elem_cls = mcs.element_cls()
        if elem_cls.is_fixed_byte_length():
            elem_byte_length = elem_cls.type_byte_length()
            if scope % elem_byte_length != 0:
                raise Exception(f"scope {scope} does not match element byte length {elem_byte_length} multiple")
            count = scope // elem_byte_length
            if not mcs.is_valid_count(count):
                raise Exception(f"count {count} is invalid")
            return [elem_cls.deserialize(stream, elem_byte_length) for _ in range(count)]
        else:
            if scope == 0:
                if not mcs.is_valid_count(0):
                    raise Exception("scope cannot be 0, count must not be 0")
                return []
            first_offset = decode_offset(stream)
            if first_offset > scope:
                raise Exception(f"first offset is too big: {first_offset}, scope: {scope}")
            if first_offset % OFFSET_BYTE_LENGTH != 0:
                raise Exception(f"first offset {first_offset} is not a multiple of offset length {OFFSET_BYTE_LENGTH}")
            count = first_offset // OFFSET_BYTE_LENGTH
            if not mcs.is_valid_count(count):
                raise Exception(f"count {count} is invalid")
            offsets = [first_offset] + [decode_offset(stream) for _ in range(count)] + [uint32(scope)]
            elem_min, elem_max = elem_cls.min_byte_length(), elem_cls.max_byte_length()
            elems = []
            for i in range(count):
                start, end = offsets[i], offsets[i+1]
                if end < start:
                    raise Exception(f"offsets[{i}] value {start} is invalid, next offset is {end}")
                elem_size = end - start
                if not (elem_min <= elem_size <= elem_max):
                    raise Exception(f"offset[{i}] value {start} is invalid, next offset is {end},"
                                    f" implied size is {elem_size}, size bounds: [{elem_min}, {elem_max}]")
                elems.append(elem_cls.deserialize(stream, elem_size))
            return elems


class MutSeqLike(ABC, ColSequence, object, metaclass=MonoSubtreeTypeDef):

    @abstractmethod
    def length(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def get(self, i: int) -> View:
        raise NotImplementedError

    @abstractmethod
    def set(self, i: int, v: View):
        raise NotImplementedError

    def __len__(self):
        return self.length()

    def __iter__(self):
        return iter(self.get(i) for i in range(self.length()))

    def __add__(self, other):
        if issubclass(self.__class__.element_cls(), uint8):
            return bytes(self) + bytes(other)
        else:
            return list(chain(self, other))

    def __getitem__(self, k):
        length = self.length()
        if isinstance(k, slice):
            start = 0 if k.start is None else k.start
            end = length if k.stop is None else k.stop
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


class ListType(MonoSubtreeTypeDef):
    @classmethod
    @abstractmethod
    def is_packed(mcs) -> bool:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def contents_depth(mcs) -> int:
        raise NotImplementedError

    @classmethod
    def tree_depth(mcs) -> int:
        return mcs.contents_depth() + 1  # 1 extra for length mix-in

    @classmethod
    @abstractmethod
    def element_cls(mcs) -> TypeDef:
        raise NotImplementedError

    @classmethod
    def item_elem_cls(mcs, i: int) -> TypeDef:
        return mcs.element_cls()

    @classmethod
    @abstractmethod
    def limit(mcs) -> int:
        raise NotImplementedError

    @classmethod
    def is_valid_count(mcs, count: int) -> bool:
        return 0 <= count <= mcs.limit()

    @classmethod
    def default_node(mcs) -> Node:
        return Commit(zero_node(mcs.contents_depth()), zero_node(0))  # mix-in 0 as list length

    @classmethod
    def is_fixed_byte_length(mcs) -> bool:
        return False

    @classmethod
    def min_byte_length(mcs) -> int:
        return 0

    @classmethod
    def max_byte_length(mcs) -> int:
        elem_cls = mcs.element_cls()
        bytes_per_elem = elem_cls.max_byte_length()
        if not elem_cls.is_fixed_byte_length():
            bytes_per_elem += OFFSET_BYTE_LENGTH
        return bytes_per_elem * mcs.limit()

    @classmethod
    def decode_bytes(mcs, bytez: bytes) -> "List":
        stream = io.BytesIO()
        stream.write(bytez)
        return mcs.deserialize(stream, len(bytez))

    @classmethod
    @abstractmethod
    def deserialize(mcs, stream: BinaryIO, scope: int) -> "List":
        raise NotImplementedError  # override in parametrized list type

    def __repr__(self):
        return f"List[{self.element_cls()}, {self.limit()}]"

    def __getitem__(self, params):
        (element_type, limit) = params
        contents_depth = 0
        packed = False
        if isinstance(element_type, BasicTypeHelperDef):
            elems_per_chunk = 32 // element_type.type_byte_length()
            contents_depth = get_depth((limit + elems_per_chunk - 1) // elems_per_chunk)
            packed = True
        else:
            contents_depth = get_depth(limit)

        class SpecialListType(ListType):

            @classmethod
            def coerce_view(mcs, v: Any) -> View:
                return SpecialListView(*v)

            @classmethod
            def is_packed(mcs) -> bool:
                return packed

            @classmethod
            def contents_depth(mcs) -> int:
                return contents_depth

            @classmethod
            def element_cls(mcs) -> TypeDef:
                return element_type

            @classmethod
            def limit(mcs) -> int:
                return limit

            @classmethod
            def deserialize(mcs, stream: BinaryIO, scope: int) -> List:
                return SpecialListView(*mcs.deserialize_elements(stream, scope))

        class SpecialListView(List, metaclass=SpecialListType):
            pass

        return SpecialListView


class List(SubtreeView, MutSeqLike, metaclass=ListType):
    def __new__(cls, *args, backing: Optional[Node] = None, hook: Optional[ViewHook] = None, **kwargs):
        if backing is not None:
            if len(args) != 0:
                raise Exception("cannot have both a backing and elements to init List")
            return super().__new__(cls, backing=backing, hook=hook, **kwargs)

        elem_cls = cls.__class__.element_cls()
        vals = list(args)
        if len(vals) == 1:
            if isinstance(vals[0], (GeneratorType, list, tuple)):
                vals = list(vals[0])
            if issubclass(elem_cls, uint8):
                val = vals[0]
                if isinstance(val, bytes):
                    vals = list(val)
                if isinstance(val, str):
                    if val[:2] == '0x':
                        val = val[2:]
                    vals = list(bytes.fromhex(val))
        if len(vals) > 0:
            limit = cls.__class__.limit()
            if len(vals) > limit:
                raise Exception(f"too many list inputs: {len(vals)}, limit is: {limit}")
            input_views = []
            for el in vals:
                if isinstance(el, View):
                    input_views.append(el)
                else:
                    input_views.append(elem_cls.coerce_view(el))
            input_nodes = cls.__class__.views_into_chunks(input_views)
            contents = subtree_fill_to_contents(input_nodes, cls.__class__.contents_depth())
            backing = Commit(contents, uint256(len(input_views)).get_backing())
        return super().__new__(cls, backing=backing, hook=hook, **kwargs)

    def length(self) -> int:
        ll_node = super().get_backing().getter(Gindex(3))
        ll = cast(uint256, uint256.view_from_backing(node=ll_node, hook=None))
        return int(ll)

    def value_byte_length(self) -> int:
        elem_cls = self.__class__.element_cls()
        if elem_cls.is_fixed_byte_length():
            return elem_cls.type_byte_length() * self.length()
        else:
            return sum(OFFSET_BYTE_LENGTH + cast(View, el).value_byte_length() for el in self)

    def append(self, v: View):
        ll = self.length()
        if ll >= self.__class__.limit():
            raise Exception("list is maximum capacity, cannot append")
        i = ll
        elem_type: TypeDef = self.__class__.element_cls()
        if not isinstance(v, elem_type):
            v = elem_type.coerce_view(v)
        if self.__class__.is_packed():
            next_backing = self.get_backing()
            if isinstance(elem_type, BasicTypeHelperDef):
                if not isinstance(v, BasicView):
                    raise Exception("input element is not a basic view")
                basic_v: BasicView = v
                basic_elem_type: BasicTypeHelperDef = elem_type
                elems_per_chunk = 32 // basic_elem_type.type_byte_length()
                chunk_i = i // elems_per_chunk
                target: Gindex = to_gindex(chunk_i, self.__class__.tree_depth())
                if i % elems_per_chunk == 0:
                    set_last = next_backing.expand_into(target)
                    chunk = zero_node(0)
                else:
                    set_last = next_backing.setter(target)
                    chunk = next_backing.getter(target)
                chunk = basic_v.backing_from_base(chunk, i % elems_per_chunk)
                next_backing = set_last(chunk)
            else:
                raise Exception("cannot append a packed element that is not a basic type")
        else:
            target: Gindex = to_gindex(i, self.__class__.tree_depth())
            set_last = self.get_backing().expand_into(target)
            next_backing = set_last(v.get_backing())

        set_length = next_backing.setter(Gindex(3))
        new_length = uint256(ll + 1).get_backing()
        next_backing = set_length(new_length)
        self.set_backing(next_backing)

    def pop(self):
        ll = self.length()
        if ll == 0:
            raise Exception("list is empty, cannot pop")
        i = ll - 1
        target: Gindex
        can_summarize: bool
        if self.__class__.is_packed():
            next_backing = self.get_backing()
            elem_type: TypeDef = self.__class__.element_cls()
            if isinstance(elem_type, BasicTypeHelperDef):
                basic_elem_type: BasicTypeHelperDef = elem_type
                elems_per_chunk = 32 // basic_elem_type.type_byte_length()
                chunk_i = i // elems_per_chunk
                target = to_gindex(chunk_i, self.__class__.tree_depth())
                if i % elems_per_chunk == 0:
                    chunk = zero_node(0)
                else:
                    chunk = next_backing.getter(target)
                set_last = next_backing.setter(target)
                chunk = cast(BasicView, basic_elem_type.default(None)).backing_from_base(chunk, i % elems_per_chunk)
                next_backing = set_last(chunk)

                can_summarize = (target & 1) == 0 and i % elems_per_chunk == 0
            else:
                raise Exception("cannot pop a packed element that is not a basic type")
        else:
            target = to_gindex(i, self.__class__.tree_depth())
            set_last = self.get_backing().setter(target)
            next_backing = set_last(zero_node(0))
            can_summarize = (target & 1) == 0

        # if possible, summarize
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

    def get(self, i: int) -> View:
        if i < 0 or i >= self.length():
            raise IndexError
        return super().get(i)

    def set(self, i: int, v: View) -> None:
        if i < 0 or i >= self.length():
            raise IndexError
        super().set(i, v)

    def __repr__(self):
        length: int
        try:
            length = self.length()
        except NavigationError:
            return f"List[{self.__class__.element_cls()}, {self.__class__.limit()}]( *summary root, no length known* )"
        vals: Dict[int, View] = {}
        partial = False
        for i in range(length):
            try:
                vals[i] = self.get(i)
            except NavigationError:
                partial = True
                continue
        if partial:
            return f"List[{self.__class__.element_cls()}, {self.__class__.limit()}]~partial(length={length})" + \
                   '(' + ', '.join(f"{i}: {repr(v)}" for i, v in vals.items()) + ')'
        else:
            return f"List[{self.__class__.element_cls()}, {self.__class__.limit()}]" + \
                   '(' + ', '.join(repr(v) for v in vals.values()) + ')'

    def encode_bytes(self) -> bytes:
        stream = io.BytesIO()
        self.serialize(stream)
        stream.seek(0)
        return stream.read()

    def serialize(self, stream: BinaryIO) -> int:
        raise NotImplementedError  # TODO


class VectorType(MonoSubtreeTypeDef):
    @classmethod
    @abstractmethod
    def is_packed(mcs) -> bool:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def tree_depth(mcs) -> int:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def element_cls(mcs) -> TypeDef:
        raise NotImplementedError

    @classmethod
    def item_elem_cls(mcs, i: int) -> TypeDef:
        return mcs.element_cls()

    @classmethod
    @abstractmethod
    def vector_length(mcs) -> int:
        raise NotImplementedError

    @classmethod
    def is_valid_count(mcs, count: int) -> bool:
        return count == mcs.vector_length()

    @classmethod
    def default_node(mcs) -> Node:
        elem_type: TypeDef = mcs.element_cls()
        length = mcs.to_chunk_length(mcs.vector_length())
        if mcs.is_packed():
            elem = zero_node(0)
        else:
            elem = elem_type.default_node()
        return subtree_fill_to_length(elem, mcs.tree_depth(), length)

    @classmethod
    def is_fixed_byte_length(mcs) -> bool:
        return mcs.element_cls().is_fixed_byte_length()  # only if the element type is fixed byte length.

    @classmethod
    def min_byte_length(mcs) -> int:
        elem_cls = mcs.element_cls()
        bytes_per_elem = elem_cls.min_byte_length()
        if not elem_cls.is_fixed_byte_length():
            bytes_per_elem += OFFSET_BYTE_LENGTH
        return bytes_per_elem * mcs.vector_length()

    @classmethod
    def max_byte_length(mcs) -> int:
        elem_cls = mcs.element_cls()
        bytes_per_elem = elem_cls.max_byte_length()
        if not elem_cls.is_fixed_byte_length():
            bytes_per_elem += OFFSET_BYTE_LENGTH
        return bytes_per_elem * mcs.vector_length()

    @classmethod
    def decode_bytes(mcs, bytez: bytes) -> "Vector":
        stream = io.BytesIO()
        stream.write(bytez)
        return mcs.deserialize(stream, len(bytez))

    @classmethod
    @abstractmethod
    def deserialize(mcs, stream: BinaryIO, scope: int) -> "Vector":
        raise NotImplementedError  # override in parametrized vector type

    def __repr__(self):
        return f"Vector[{self.element_cls()}, {self.vector_length()}]"

    def __getitem__(self, params):
        (element_view_cls, length) = params

        tree_depth = 0
        packed = False
        if isinstance(element_view_cls, BasicTypeHelperDef):
            elems_per_chunk = 32 // element_view_cls.type_byte_length()
            tree_depth = get_depth((length + elems_per_chunk - 1) // elems_per_chunk)
            packed = True
        else:
            tree_depth = get_depth(length)

        class SpecialVectorType(VectorType):
            @classmethod
            def coerce_view(mcs, v: Any) -> View:
                return SpecialVectorView(*v)

            @classmethod
            def is_packed(mcs) -> bool:
                return packed

            @classmethod
            def tree_depth(mcs) -> int:
                return tree_depth

            @classmethod
            def element_cls(mcs) -> TypeDef:
                return element_view_cls

            @classmethod
            def vector_length(mcs) -> int:
                return length

            @classmethod
            def deserialize(mcs, stream: BinaryIO, scope: int) -> Vector:
                return SpecialVectorView(*mcs.deserialize_elements(stream, scope))

        # for fixed-size vectors, pre-compute the size.
        if element_view_cls.is_fixed_byte_length():
            byte_length = element_view_cls.type_byte_length() * length

            class FixedSpecialVectorType(SpecialVectorType):
                @classmethod
                def type_byte_length(mcs) -> int:
                    return byte_length

                @classmethod
                def min_byte_length(mcs) -> int:
                    return byte_length

                @classmethod
                def max_byte_length(mcs) -> int:
                    return byte_length

            SpecialVectorType = FixedSpecialVectorType

        class SpecialVectorView(Vector, metaclass=SpecialVectorType):
            pass

        return SpecialVectorView


class Vector(SubtreeView, MutSeqLike, metaclass=VectorType):
    def __new__(cls, *args, backing: Optional[Node] = None, hook: Optional[ViewHook] = None, **kwargs):
        if backing is not None:
            if len(args) != 0:
                raise Exception("cannot have both a backing and elements to init Vector")
            return super().__new__(cls, backing=backing, hook=hook, **kwargs)

        elem_cls = cls.__class__.element_cls()
        vals = list(args)
        if len(vals) == 1:
            if isinstance(vals[0], (GeneratorType, list, tuple)):
                vals = list(vals[0])
            if issubclass(elem_cls, uint8):
                val = vals[0]
                if isinstance(val, bytes):
                    vals = list(val)
                if isinstance(val, str):
                    if val[:2] == '0x':
                        val = val[2:]
                    vals = list(bytes.fromhex(val))
        if len(vals) > 0:
            vector_length = cls.__class__.vector_length()
            if len(vals) != vector_length:
                raise Exception(f"invalid inputs length: {len(vals)}, vector length is: {vector_length}")
            input_views = []
            for el in vals:
                if isinstance(el, View):
                    input_views.append(el)
                else:
                    input_views.append(elem_cls.coerce_view(el))
            input_nodes = cls.__class__.views_into_chunks(input_views)
            backing = subtree_fill_to_contents(input_nodes, cls.__class__.tree_depth())
        return super().__new__(cls, backing=backing, hook=hook, **kwargs)

    def get(self, i: int) -> View:
        if i < 0 or i >= self.__class__.vector_length():
            raise IndexError
        return super().get(i)

    def set(self, i: int, v: View) -> None:
        if i < 0 or i >= self.__class__.vector_length():
            raise IndexError
        super().set(i, v)

    def length(self) -> int:
        return self.__class__.vector_length()

    def value_byte_length(self) -> int:
        if self.__class__.is_fixed_byte_length():
            return self.__class__.type_byte_length()
        else:
            return sum(OFFSET_BYTE_LENGTH + cast(View, el).value_byte_length() for el in self)

    def __repr__(self):
        vals: Dict[int, View] = {}
        length = self.length()
        partial = False
        for i in range(length):
            try:
                vals[i] = self.get(i)
            except NavigationError:
                partial = True
                continue
        if partial:
            return f"Vector[{self.__class__.element_cls()}, {self.__class__.vector_length()}]~partial" + \
               '(' + ', '.join(f"{i}: {repr(v)}" for i, v in vals.items()) + ')'
        else:
            return f"Vector[{self.__class__.element_cls()}, {self.__class__.vector_length()}]" + \
                   '(' + ', '.join(repr(v) for v in vals.values()) + ')'

    def encode_bytes(self) -> bytes:
        stream = io.BytesIO()
        self.serialize(stream)
        stream.seek(0)
        return stream.read()

    def serialize(self, stream: BinaryIO) -> int:
        elem_cls = self.__class__.element_cls()
        if issubclass(elem_cls, uint8):
            out = bytes(self.__iter__())
            stream.write(out)
            return len(out)
        raise NotImplementedError  # TODO other element types


class Fields(NamedTuple):
    keys: Sequence[str]
    types: Sequence[TypeDef]


class ContainerType(SubtreeTypeDef):

    @classmethod
    @abstractmethod
    def fields(mcs) -> Fields:
        raise NotImplementedError

    def __repr__(self):
        return f"{self.__name__}(Container)\n" + '\n'.join(
            ('  ' + fkey + ': ' + repr(ftype)) for fkey, ftype in zip(self.fields().keys, self.fields().types)) + '\n'


class FieldOffset(NamedTuple):
    key: str
    typ: TypeDef
    offset: int


class Container(SubtreeView, metaclass=ContainerType):
    # Container types should declare fields through class annotations.
    # If none are specified, it will fall back on this (to avoid annotations of super classes),
    # and error on construction, since empty container types are invalid.
    _empty_annotations: bool

    def __new__(cls, *args, backing: Optional[Node] = None, hook: Optional[ViewHook] = None, **kwargs):
        if backing is not None:
            if len(args) != 0:
                raise Exception("cannot have both a backing and elements to init List")
            return super().__new__(cls, backing=backing, hook=hook, **kwargs)

        fields = cls.fields()

        input_nodes = []
        for fkey, ftyp in zip(fields.keys, fields.types):
            fnode: Node
            if fkey in kwargs:
                finput = kwargs.pop(fkey)
                if isinstance(finput, View):
                    fnode = finput.get_backing()
                else:
                    fnode = cast(TypeDef, ftyp).coerce_view(finput).get_backing()
            else:
                fnode = cast(TypeDef, ftyp).default_node()
            input_nodes.append(fnode)
        backing = subtree_fill_to_contents(input_nodes, cls.tree_depth())
        return super().__new__(cls, backing=backing, hook=hook, **kwargs)

    @classmethod
    def fields(cls) -> Fields:
        annot = cls.__annotations__
        if '_empty_annotations' in annot.keys():
            raise Exception("detected fallback empty annotation, cannot have container type without fields")
        return Fields(keys=list(annot.keys()), types=[v for v in annot.values()])

    @classmethod
    def is_fixed_byte_length(mcs) -> bool:
        return all(f.is_fixed_byte_length() for f in mcs.fields().types)

    @classmethod
    def type_byte_length(mcs) -> int:
        if mcs.is_fixed_byte_length():
            return mcs.min_byte_length()
        else:
            raise Exception("dynamic length container does not have a fixed byte length")


    @classmethod
    def min_byte_length(mcs) -> int:
        total = 0
        for ftyp in mcs.fields().types:
            if not ftyp.is_fixed_byte_length():
                total += OFFSET_BYTE_LENGTH
            total += ftyp.min_byte_length()
        return total

    @classmethod
    def max_byte_length(mcs) -> int:
        total = 0
        for ftyp in mcs.fields().types:
            if not ftyp.is_fixed_byte_length():
                total += OFFSET_BYTE_LENGTH
            total += ftyp.max_byte_length()
        return total

    @classmethod
    def decode_bytes(mcs, bytez: bytes) -> "Container":
        stream = io.BytesIO()
        stream.write(bytez)
        return mcs.deserialize(stream, len(bytez))

    @classmethod
    def is_packed(cls) -> bool:
        return False

    @classmethod
    def tree_depth(cls) -> int:
        return get_depth(len(cls.fields().keys))

    @classmethod
    def item_elem_cls(cls, i: int) -> TypeDef:
        return cls.fields().types[i]

    @classmethod
    def default_node(cls) -> Node:
        return subtree_fill_to_contents([field.default_node() for field in cls.fields().types], cls.tree_depth())

    def value_byte_length(self) -> int:
        if self.__class__.is_fixed_byte_length():
            return self.__class__.type_byte_length()
        else:
            total = 0
            fields = self.fields()
            for fkey, ftyp in zip(fields.keys, fields.types):
                if ftyp.is_fixed_byte_length():
                    total += ftyp.type_byte_length()
                else:
                    total += OFFSET_BYTE_LENGTH
                    total += cast(View, getattr(self, fkey)).value_byte_length()
            return total

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

    def __repr__(self):
        fields = self.fields()

        def get_field_val_repr(fkey: str) -> str:
            try:
                return repr(getattr(self, fkey))
            except NavigationError:
                return "*omitted from partial*"

        return f"{self.__class__.__name__}(Container)\n" + '\n'.join(
            ('  ' + fkey + ': ' + repr(ftype) + ' = ' + get_field_val_repr(fkey))
            for fkey, ftype in zip(fields.keys, fields.types)) + '\n'

    @classmethod
    def deserialize(cls, stream: BinaryIO, scope: int) -> "Container":
        fields = cls.fields()
        field_values: Dict[str, View]
        if cls.is_fixed_byte_length():
            field_values = {fkey: ftyp.deserialize(stream, ftyp.type_byte_length())
                            for fkey, ftyp in zip(fields.keys, fields.types)}
        else:
            field_values = {}
            dyn_fields: PyList[FieldOffset] = []
            fixed_size = 0
            for fkey, ftyp in zip(fields.keys, fields.types):
                if ftyp.is_fixed_byte_length():
                    fsize = ftyp.type_byte_length()
                    field_values[fkey] = ftyp.deserialize(stream, fsize)
                    fixed_size += fsize
                else:
                    dyn_fields.append(FieldOffset(key=fkey, typ=ftyp, offset=int(decode_offset(stream))))
                    fixed_size += OFFSET_BYTE_LENGTH
            if len(dyn_fields) > 0:
                if dyn_fields[0].offset < fixed_size:
                    raise Exception(f"first offset is smaller than expected fixed size")
                for i, (fkey, ftyp, foffset) in enumerate(dyn_fields):
                    next_offset = dyn_fields[i + 1].offset if i + 1 < len(dyn_fields) else scope
                    if foffset > next_offset:
                        raise Exception(f"offset {i} is invalid: {foffset} larger than next offset {next_offset}")
                    fsize = next_offset - foffset
                    f_min_size, f_max_size = ftyp.min_byte_length(), ftyp.max_byte_length()
                    if not (f_min_size <= fsize <= f_max_size):
                        raise Exception(f"offset {i} is invalid, size out of bounds: {foffset}, next {next_offset},"
                                        f" implied size: {fsize}, size bounds: [{f_min_size}, {f_max_size}]")
                    field_values[fkey] = ftyp.deserialize(stream, fsize)
        # noinspection PyArgumentList
        return cls(**field_values)

    def encode_bytes(self) -> bytes:
        stream = io.BytesIO()
        self.serialize(stream)
        stream.seek(0)
        return stream.read()

    def serialize(self, stream: BinaryIO) -> int:
        raise NotImplementedError  # TODO
