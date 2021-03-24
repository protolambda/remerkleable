from typing import cast, Sequence, Any, BinaryIO, Optional, TypeVar, Type
from textwrap import indent
import io
from remerkleable.core import View, BackedView, ViewHook, ObjType
from remerkleable.basic import uint256
from remerkleable.tree import Node, zero_node, Gindex, PairNode
from remerkleable.tree import LEFT_GINDEX, RIGHT_GINDEX

Options = Sequence[Type[View]]

V = TypeVar('V', bound=View)


class Union(BackedView):
    def __new__(cls, *args, backing: Optional[Node] = None, hook: Optional[ViewHook] = None, **kwargs):
        """
        Create a value instance of a union, use selected=2, value=uint64(123) on
        a Union[1, [uint32, Bitvector, uint64]] to wrap an instance of the uint64 in the union type.
        The first type parameter is used to set the byte-length of the selector value,
        the second is a list of type options.
        """
        if backing is not None:
            if len(args) != 0:
                raise Exception("cannot have both a backing and elements to init Union")
            return super().__new__(cls, backing=backing, hook=hook, **kwargs)

        selected = kwargs.pop('selected')
        value = kwargs.pop('value')

        options = cls.options()
        option_count = len(options)
        if selected >= option_count:
            raise Exception(f"selected index {selected} was out of option range {option_count}")
        selected_type = options[selected]
        selected_value = selected_type.coerce_view(value)
        backing = PairNode(
            left=selected_value.get_backing(),
            right=uint256(selected).get_backing())
        return super().__new__(cls, backing=backing, hook=hook, **kwargs)

    def __class_getitem__(cls, params) -> Type["Union"]:
        if len(params) != 2:
            raise Exception("expected two Union type params: selector byte size, and a list of type options")
        (union_selector_byte_size, union_options) = params
        union_selector_byte_size = int(union_selector_byte_size)
        union_options = list(union_options)
        if union_selector_byte_size < 1:
            raise Exception(f"union selector byte size {union_selector_byte_size} is too small")
        if len(union_options) < 1:
            raise Exception("No type options to select")
        if not all(map(lambda x: issubclass(x, View), union_options)):
            raise Exception("Not all type options are a View type")

        class SpecialUnionView(Union):
            @classmethod
            def selector_byte_size(cls) -> int:
                return union_selector_byte_size

            @classmethod
            def options(cls) -> Options:
                return union_options

        SpecialUnionView.__name__ = SpecialUnionView.type_repr()
        return SpecialUnionView

    @classmethod
    def selector_byte_size(cls) -> int:
        raise NotImplementedError

    @classmethod
    def options(cls) -> Options:
        raise NotImplementedError

    def selected_index(self) -> int:
        selector_node = super().get_backing().get_right()
        selector = int(cast(uint256, uint256.view_from_backing(node=selector_node, hook=None)))
        selector_max_byte_size = self.__class__.selector_byte_size()
        if selector.bit_length() > selector_max_byte_size * 8:
            raise Exception(f"union selected_index backing value is unexpectedly large: {selector},"
                            f" max expected byte size: {selector_max_byte_size}")
        option_count = len(self.__class__.options())
        if selector >= option_count:
            raise Exception(f"union selector was {selector}, expected less than {option_count}")
        return selector

    def selected_type(self) -> Type[View]:
        return self.__class__.options()[self.selected_index()]

    def value(self) -> View:
        value_node = super().get_backing().get_left()
        selected_type = self.selected_type()

        def handle_change(v: View) -> None:
            self.get_backing().setter(LEFT_GINDEX)(v.get_backing())

        return selected_type.view_from_backing(value_node, handle_change)

    def value_byte_length(self) -> int:
        return self.selector_byte_size() + self.value().value_byte_length()

    def change(self, selected: int, value: View):
        options = self.__class__.options()
        option_count = len(options)
        if selected >= option_count:
            raise Exception(f"selected index {selected} was out of option range {option_count}")
        selected_type = options[selected]
        selected_value = selected_type.coerce_view(value)
        self.set_backing(PairNode(
            left=selected_value.get_backing(),
            right=uint256(selected).get_backing()))

    def __repr__(self):
        val_repr = repr(self.value())
        if '\n' in val_repr:
            val_repr = '\n' + indent(val_repr, '  ')
        return f"{self.__class__.type_repr()}:\n  selected={self.selected_index()}\n  value={val_repr}"

    @classmethod
    def type_repr(cls) -> str:
        return f"Union[{cls.selector_byte_size()}, [{', '.join(map(lambda x: x.type_repr(), cls.options()))}]]"

    @classmethod
    def is_packed(cls) -> bool:
        return False

    @classmethod
    def is_valid_selector(cls, selector: int) -> bool:
        return 0 <= selector < len(cls.options())

    @classmethod
    def navigate_type(cls, key: Any) -> Type[View]:
        if key == '__selector__':
            return uint256
        if not cls.is_valid_selector(key):
            raise KeyError
        return cls.options()[key]

    @classmethod
    def key_to_static_gindex(cls, key: Any) -> Gindex:
        if key == '__selector__':
            return RIGHT_GINDEX
        return LEFT_GINDEX

    @classmethod
    def default_node(cls) -> Node:
        return PairNode(cls.options()[0].default_node(), zero_node(0))  # mix-in 0 as selector

    @classmethod
    def is_fixed_byte_length(cls) -> bool:
        return False

    @classmethod
    def min_byte_length(cls) -> int:
        return cls.selector_byte_size() + min(map(lambda x: x.min_byte_length(), cls.options()))

    @classmethod
    def max_byte_length(cls) -> int:
        return cls.selector_byte_size() + max(map(lambda x: x.min_byte_length(), cls.options()))

    @classmethod
    def from_obj(cls: Type[V], obj: ObjType) -> V:
        if not isinstance(obj, dict):
            raise Exception("expected dict with 'selected' and 'value' keys")
        selected_index = obj["selected"]
        selected_type = cls.options()[selected_index]
        value = selected_type.from_obj(obj["value"])
        return cls(selected=selected_index, value=value)  # type: ignore

    def to_obj(self) -> ObjType:
        return {'selected': self.selected_index(), 'value': self.value().to_obj()}

    def encode_bytes(self) -> bytes:
        stream = io.BytesIO()
        self.serialize(stream)
        stream.seek(0)
        return stream.read()

    @classmethod
    def decode_bytes(cls: Type[V], bytez: bytes) -> V:
        stream = io.BytesIO()
        stream.write(bytez)
        stream.seek(0)
        return cls.deserialize(stream, len(bytez))

    @classmethod
    def deserialize(cls: Type[V], stream: BinaryIO, scope: int) -> V:
        selector_size = cls.selector_byte_size()
        if selector_size > scope:
            raise Exception("scope too small, cannot read Union selector")
        selected = int.from_bytes(stream.read(selector_size), byteorder='little')
        options = cls.options()
        option_count = len(options)
        if selected >= option_count:
            raise Exception(f"selected index {selected} was out of option range {option_count}")
        selected_type = options[selected]
        value = selected_type.deserialize(stream, scope - selector_size)
        return cls(selected=selected, value=value)  # type: ignore

    def serialize(self, stream: BinaryIO) -> int:
        selector_size = self.selector_byte_size()
        stream.write(self.selected_index().to_bytes(length=selector_size, byteorder='little'))
        return selector_size + self.value().serialize(stream)
