# This file implements `StableContainer` according to https://eips.ethereum.org/EIPS/eip-7495
# The EIP is still under review, functionality may change or go away without deprecation.

import io
from typing import BinaryIO, Dict, List as PyList, Optional, Tuple, TypeVar, Type, Union as PyUnion, \
    get_args, get_origin
from textwrap import indent
from remerkleable.bitfields import Bitvector
from remerkleable.complex import ComplexView, Container, FieldOffset, \
    decode_offset, encode_offset
from remerkleable.core import View, ViewHook, OFFSET_BYTE_LENGTH
from remerkleable.tree import NavigationError, Node, PairNode, \
    get_depth, subtree_fill_to_contents, zero_node

N = TypeVar('N')
S = TypeVar('S', bound="ComplexView")


class StableContainer(ComplexView):
    _field_indices: Dict[str, Tuple[int, Type[View], bool]]
    __slots__ = '_field_indices'

    def __new__(cls, backing: Optional[Node] = None, hook: Optional[ViewHook] = None, **kwargs):
        if backing is not None:
            if len(kwargs) != 0:
                raise Exception("cannot have both a backing and elements to init fields")
            return super().__new__(cls, backing=backing, hook=hook, **kwargs)

        for fkey, (ftyp, fopt) in cls.fields().items():
            if fkey not in kwargs:
                if not fopt:
                    raise AttributeError(f"Field '{fkey}' is required in {cls}")
                kwargs[fkey] = None

        input_nodes = []
        active_fields = Bitvector[cls.N]()
        for findex, (fkey, (ftyp, fopt)) in enumerate(cls.fields().items()):
            fnode: Node
            assert fkey in kwargs
            finput = kwargs.pop(fkey)
            if finput is None:
                fnode = zero_node(0)
                active_fields.set(findex, False)
            else:
                if isinstance(finput, View):
                    fnode = finput.get_backing()
                else:
                    fnode = ftyp.coerce_view(finput).get_backing()
                active_fields.set(findex, True)
            input_nodes.append(fnode)

        if len(kwargs) > 0:
            raise AttributeError(f'The field names [{"".join(kwargs.keys())}] are not defined in {cls}')

        backing = PairNode(
            left=subtree_fill_to_contents(input_nodes, get_depth(cls.N)),
            right=active_fields.get_backing())
        return super().__new__(cls, backing=backing, hook=hook, **kwargs)

    def __init_subclass__(cls, *args, **kwargs):
        super().__init_subclass__(*args, **kwargs)
        cls._field_indices = {
            fkey: (i, ftyp, fopt)
            for i, (fkey, (ftyp, fopt)) in enumerate(cls.fields().items())
        }

    def __class_getitem__(cls, n) -> Type["StableContainer"]:
        if n <= 0:
            raise Exception(f"invalid stablecontainer capacity: {n}")

        class StableContainerView(StableContainer):
            N = n

        StableContainerView.__name__ = StableContainerView.type_repr()
        return StableContainerView

    @classmethod
    def fields(cls) -> Dict[str, Tuple[Type[View], bool]]:
        fields = {}
        for k, v in cls.__annotations__.items():
            fopt = get_origin(v) == PyUnion and type(None) in get_args(v)
            ftyp = get_args(v)[0] if fopt else v
            fields[k] = (ftyp, fopt)
        return fields

    @classmethod
    def is_fixed_byte_length(cls) -> bool:
        return False

    @classmethod
    def min_byte_length(cls) -> int:
        total = Bitvector[cls.N].type_byte_length()
        for _, (ftyp, fopt) in cls.fields().items():
            if fopt:
                continue
            if not ftyp.is_fixed_byte_length():
                total += OFFSET_BYTE_LENGTH
            total += ftyp.min_byte_length()
        return total

    @classmethod
    def max_byte_length(cls) -> int:
        total = Bitvector[cls.N].type_byte_length()
        for _, (ftyp, _) in cls.fields().items():
            if not ftyp.is_fixed_byte_length():
                total += OFFSET_BYTE_LENGTH
            total += ftyp.max_byte_length()
        return total

    def active_fields(self) -> Bitvector:
        active_fields_node = super().get_backing().get_right()
        return Bitvector[self.__class__.N].view_from_backing(active_fields_node)

    def __getattr__(self, item):
        if item[0] == '_':
            return super().__getattribute__(item)
        else:
            try:
                (findex, ftyp, fopt) = self.__class__._field_indices[item]
            except KeyError:
                raise AttributeError(f"unknown attribute {item}")

            if not self.active_fields().get(findex):
                assert fopt
                return None

            data = super().get_backing().get_left()
            fnode = data.getter(2**get_depth(self.__class__.N) + findex)
            return ftyp.view_from_backing(fnode)

    def __setattr__(self, key, value):
        if key[0] == '_':
            super().__setattr__(key, value)
        else:
            try:
                (findex, ftyp, fopt) = self.__class__._field_indices[key]
            except KeyError:
                raise AttributeError(f"unknown attribute {key}")

            next_backing = self.get_backing()

            assert value is not None or fopt
            active_fields = self.active_fields()
            active_fields.set(findex, value is not None)
            next_backing = next_backing.rebind_right(active_fields.get_backing())

            if value is not None:
                if isinstance(value, ftyp):
                    fnode = value.get_backing()
                else:
                    fnode = ftyp.coerce_view(value).get_backing()
            else:
                fnode = zero_node(0)
            data = next_backing.get_left()
            next_data = data.setter(2**get_depth(self.__class__.N) + findex)(fnode)
            next_backing = next_backing.rebind_left(next_data)

            self.set_backing(next_backing)

    def _get_field_val_repr(self, fkey: str, ftyp: Type[View], fopt: bool) -> str:
        field_start = '  ' + fkey + ': ' + (
            ('Optional[' if fopt else '') + ftyp.__name__ + (']' if fopt else '')
        ) + ' = '
        try:
            field_repr = repr(getattr(self, fkey))
            if '\n' in field_repr:  # if multiline, indent it, but starting from the value.
                i = field_repr.index('\n')
                field_repr = field_repr[:i+1] + indent(field_repr[i+1:], ' ' * len(field_start))
            return field_start + field_repr
        except NavigationError:
            return f"{field_start} *omitted from partial*"

    def __repr__(self):
        return f"{self.__class__.type_repr()}:\n" + '\n'.join(
            indent(self._get_field_val_repr(fkey, ftyp, fopt), '  ')
            for fkey, (ftyp, fopt) in self.__class__.fields().items())

    @classmethod
    def type_repr(cls) -> str:
        return f"StableContainer[{cls.N}]"

    @classmethod
    def deserialize(cls: Type[S], stream: BinaryIO, scope: int) -> S:
        num_prefix_bytes = Bitvector[cls.N].type_byte_length()
        if scope < num_prefix_bytes:
            raise ValueError("scope too small, cannot read StableContainer active fields")
        active_fields = Bitvector[cls.N].deserialize(stream, num_prefix_bytes)
        scope = scope - num_prefix_bytes

        max_findex = 0
        field_values: Dict[str, Optional[View]] = {}
        dyn_fields: PyList[FieldOffset] = []
        fixed_size = 0
        for findex, (fkey, (ftyp, _)) in enumerate(cls.fields().items()):
            max_findex = findex
            if not active_fields.get(findex):
                field_values[fkey] = None
                continue
            if ftyp.is_fixed_byte_length():
                fsize = ftyp.type_byte_length()
                field_values[fkey] = ftyp.deserialize(stream, fsize)
                fixed_size += fsize
            else:
                dyn_fields.append(FieldOffset(
                    key=fkey, typ=ftyp, offset=int(decode_offset(stream))))
                fixed_size += OFFSET_BYTE_LENGTH
        if len(dyn_fields) > 0:
            if dyn_fields[0].offset < fixed_size:
                raise Exception(f"first offset {dyn_fields[0].offset} is "
                                f"smaller than expected fixed size {fixed_size}")
            for i, (fkey, ftyp, foffset) in enumerate(dyn_fields):
                next_offset = dyn_fields[i + 1].offset if i + 1 < len(dyn_fields) else scope
                if foffset > next_offset:
                    raise Exception(f"offset {i} is invalid: {foffset} "
                                    f"larger than next offset {next_offset}")
                fsize = next_offset - foffset
                f_min_size, f_max_size = ftyp.min_byte_length(), ftyp.max_byte_length()
                if not (f_min_size <= fsize <= f_max_size):
                    raise Exception(f"offset {i} is invalid, size out of bounds: "
                                    f"{foffset}, next {next_offset}, implied size: {fsize}, "
                                    f"size bounds: [{f_min_size}, {f_max_size}]")
                field_values[fkey] = ftyp.deserialize(stream, fsize)
        for findex in range(max_findex + 1, cls.N):
            if active_fields.get(findex):
                raise Exception(f"unknown field index {findex}")
        return cls(**field_values)  # type: ignore

    def serialize(self, stream: BinaryIO) -> int:
        active_fields = self.active_fields()
        num_prefix_bytes = active_fields.serialize(stream)

        num_data_bytes = sum(
            ftyp.type_byte_length() if ftyp.is_fixed_byte_length() else OFFSET_BYTE_LENGTH
            for findex, (_, (ftyp, _)) in enumerate(self.__class__.fields().items())
            if active_fields.get(findex))

        temp_dyn_stream = io.BytesIO()
        data = super().get_backing().get_left()
        for findex, (_, (ftyp, _)) in enumerate(self.__class__.fields().items()):
            if not active_fields.get(findex):
                continue
            fnode = data.getter(2**get_depth(self.__class__.N) + findex)
            v = ftyp.view_from_backing(fnode)
            if ftyp.is_fixed_byte_length():
                v.serialize(stream)
            else:
                encode_offset(stream, num_data_bytes)
                num_data_bytes += v.serialize(temp_dyn_stream)  # type: ignore
        temp_dyn_stream.seek(0)
        stream.write(temp_dyn_stream.read(num_data_bytes))

        return num_prefix_bytes + num_data_bytes


class Variant(ComplexView):
    def __new__(cls, backing: Optional[Node] = None, hook: Optional[ViewHook] = None, **kwargs):
        if backing is not None:
            if len(kwargs) != 0:
                raise Exception("cannot have both a backing and elements to init fields")
            return super().__new__(cls, backing=backing, hook=hook, **kwargs)

        extra_kwargs = kwargs.copy()
        for fkey, (ftyp, fopt) in cls.fields().items():
            if fkey in extra_kwargs:
                extra_kwargs.pop(fkey)
            elif not fopt:
                raise AttributeError(f"Field '{fkey}' is required in {cls}")
            else:
                pass
        if len(extra_kwargs) > 0:
            raise AttributeError(f'The field names [{"".join(extra_kwargs.keys())}] are not defined in {cls}')

        value = cls.S(backing, hook, **kwargs)
        return cls(backing=value.get_backing())

    def __class_getitem__(cls, s) -> Type["Variant"]:
        if not issubclass(s, StableContainer):
            raise Exception(f"invalid variant container: {s}")

        class VariantView(Variant, s):
            S = s

            @classmethod
            def fields(cls) -> Dict[str, Tuple[Type[View], bool]]:
                return s.fields()

        VariantView.__name__ = VariantView.type_repr()
        return VariantView

    @classmethod
    def type_repr(cls) -> str:
        return f"Variant[{cls.S.__name__}]"

    @classmethod
    def deserialize(cls: Type[S], stream: BinaryIO, scope: int) -> S:
        value = cls.S.deserialize(stream, scope)
        return cls(backing=value.get_backing())


class OneOf(ComplexView):
    def __class_getitem__(cls, s) -> Type["OneOf"]:
        if not issubclass(s, StableContainer) and not issubclass(s, Container):
            raise Exception(f"invalid oneof container: {s}")

        class OneOfView(OneOf, s):
            S = s

            @classmethod
            def fields(cls):
                return s.fields()

        OneOfView.__name__ = OneOfView.type_repr()
        return OneOfView

    @classmethod
    def type_repr(cls) -> str:
        return f"OneOf[{cls.S}]"

    @classmethod
    def decode_bytes(cls: Type[S], bytez: bytes, *args, **kwargs) -> S:
        stream = io.BytesIO()
        stream.write(bytez)
        stream.seek(0)
        return cls.deserialize(stream, len(bytez), *args, **kwargs)

    @classmethod
    def deserialize(cls: Type[S], stream: BinaryIO, scope: int, *args, **kwargs) -> S:
        value = cls.S.deserialize(stream, scope)
        v = cls.select_variant(value, *args, **kwargs)
        if not issubclass(v.S, cls.S):
            raise Exception(f"unsupported select_variant result: {v}")
        return v(backing=value.get_backing())
