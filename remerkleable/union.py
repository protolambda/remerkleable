from typing import cast, Sequence, Any, BinaryIO, Optional, TypeVar, Type, Union as PyUnion
from textwrap import indent
import io
from remerkleable.core import View, BackedView, ViewHook, ObjType
from remerkleable.basic import uint256
from remerkleable.tree import Node, zero_node, Gindex, PairNode
from remerkleable.tree import LEFT_GINDEX, RIGHT_GINDEX

Options = Sequence[PyUnion[Type[View], None]]

V = TypeVar('V', bound=View)


class Union(BackedView):
    def __new__(cls, *args, selector: Optional[int] = None, value: PyUnion[View, None] = None,
                backing: Optional[Node] = None, hook: Optional[ViewHook] = None, **kwargs):
        """
        Create a value instance of a union, use selector=2, value=uint64(123) on
        a Union[uint32, Bitvector, uint64] to wrap an instance of the uint64 in the union type.
        The Union type parameters define the list of options.
        """
        if backing is not None:
            if len(args) != 0:
                raise Exception("cannot have both a backing and elements to init Union")
            return super().__new__(cls, backing=backing, hook=hook, **kwargs)

        options = cls.options()

        selected_backing: Node
        if selector is not None:
            option_count = len(options)
            if selector >= option_count:
                raise ValueError(f"selected index {selector} was out of option range {option_count}")

            selected_type = options[selector]
            if selected_type is None:
                if value is not None:
                    raise ValueError(f"selected None option, but value is not None: {value}")
                selected_backing = zero_node(0)
            else:
                if value is not None:
                    selected_backing = selected_type.coerce_view(value).get_backing()
                else:
                    selected_backing = selected_type.default_node()
        else:
            selector = 0
            if value is not None:
                raise ValueError(f"cannot default 'selector' arg to 0 with explicit 'value': {value}")
            selected_type = options[selector]
            if selected_type is None:
                selected_backing = zero_node(0)
            else:
                selected_backing = selected_type.default_node()

        backing = PairNode(
            left=selected_backing,
            right=uint256(selector).get_backing())
        return super().__new__(cls, backing=backing, hook=hook, **kwargs)

    def __class_getitem__(cls, *union_options) -> Type["Union"]:
        if len(union_options) < 1:
            raise TypeError("expected at least one Union type option")
        if len(union_options) > 128:
            raise TypeError(f"expected no more than 128 type options, but got {len(union_options)}")

        union_options_list: Sequence[PyUnion[Type[View], None]] = list(*union_options)

        for (i, x) in enumerate(union_options_list):
            if x is None and i == 0:
                continue
            if x is None:
                raise TypeError(f"only option 0 can be None as type, index {i} cannot be None")
            if issubclass(x, View):
                continue
            raise TypeError(f"Not all type options are a View type, index {i} is wrong")

        if union_options_list[0] is None and len(union_options_list) < 2:
            raise TypeError("Union with a None option must have at least 2 options")

        class SpecialUnionView(Union):
            @classmethod
            def options(cls) -> Options:
                return union_options_list

        SpecialUnionView.__name__ = SpecialUnionView.type_repr()
        return SpecialUnionView

    @classmethod
    def options(cls) -> Options:
        raise NotImplementedError

    def selector(self) -> int:
        selector_node = super().get_backing().get_right()
        selector = int(cast(uint256, uint256.view_from_backing(node=selector_node, hook=None)))
        option_count = len(self.__class__.options())
        if selector >= option_count:
            raise KeyError(f"union selector was {selector}, expected less than {option_count}")
        return selector

    def selected_type(self) -> PyUnion[Type[View], None]:
        return self.__class__.options()[self.selector()]

    def value(self) -> PyUnion[View, None]:
        value_node = super().get_backing().get_left()
        selected_type = self.selected_type()
        if selected_type is None:
            assert value_node.root == zero_node(0).root
            return None

        def handle_change(v: View) -> None:
            self.get_backing().setter(LEFT_GINDEX)(v.get_backing())

        return selected_type.view_from_backing(value_node, handle_change)

    def value_byte_length(self) -> int:
        # 1 byte for the selector
        value = self.value()
        if value is None:
            return 1
        else:
            return 1 + value.value_byte_length()

    def change(self, selector: int, value: PyUnion[View, None]):
        options = self.__class__.options()
        option_count = len(options)
        if selector >= option_count:
            raise KeyError(f"selected index {selector} was out of option range {option_count}")
        selected_type = options[selector]
        if value is None:
            if selected_type is not None:
                raise TypeError(f"Tried to set union to selector {selector} to None,"
                                f" but type is {repr(selected_type)}, not None")
        selected_node: Node
        if selected_type is None:
            if value is not None:
                raise TypeError("When selecting None as type, the value must be none")
            selected_node = zero_node(0)
        else:
            selected_node = selected_type.coerce_view(value).get_backing()
        self.set_backing(PairNode(
            left=selected_node,
            right=uint256(selector).get_backing()))

    def __repr__(self):
        val_repr = repr(self.value())
        if '\n' in val_repr:
            val_repr = '\n' + indent(val_repr, '  ')
        return f"{self.__class__.type_repr()}:\n  selector={self.selector()}\n  value={val_repr}"

    @classmethod
    def type_repr(cls) -> str:
        def repr_option(x: PyUnion[Type[View], None]) -> str:
            if x is None:
                return 'None'
            else:
                return x.type_repr()
        return f"Union[{', '.join(map(repr_option, cls.options()))}]"

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
        if not isinstance(key, int):
            raise TypeError(f"expected integer key, got {key}")
        if not cls.is_valid_selector(int(key)):
            raise KeyError(f"key {key} is not a valid selector for union {repr(cls)}")
        return LEFT_GINDEX

    @classmethod
    def default_node(cls) -> Node:
        default_option = cls.options()[0]
        content_node: Node
        if default_option is None:
            content_node = zero_node(0)
        else:
            content_node = default_option.default_node()
        return PairNode(content_node, zero_node(0))  # mix-in 0 as selector

    @classmethod
    def is_fixed_byte_length(cls) -> bool:
        return False

    @classmethod
    def min_byte_length(cls) -> int:
        def min_option_size(x: PyUnion[Type[View], None]) -> int:
            if x is None:
                return 0
            else:
                return x.min_byte_length()
        return 1 + min(map(min_option_size, cls.options()))

    @classmethod
    def max_byte_length(cls) -> int:
        def max_option_size(x: PyUnion[Type[View], None]) -> int:
            if x is None:
                return 0
            else:
                return x.max_byte_length()
        return 1 + max(map(max_option_size, cls.options()))

    @classmethod
    def from_obj(cls: Type[V], obj: ObjType) -> V:
        if not isinstance(obj, dict):
            raise ValueError("expected dict with 'selector' and 'value' keys")
        selector = obj["selector"]
        selected_type = cls.options()[selector]
        if selected_type is None:
            if obj["value"] is not None:
                raise ValueError("expected None value for selector None type")
            value = None
        else:
            value = selected_type.from_obj(obj["value"])
        return cls(selector=selector, value=value)  # type: ignore

    def to_obj(self) -> ObjType:
        value = self.value()
        if value is None:
            return {'selector': self.selector(), 'value': None}
        else:
            return {'selector': self.selector(), 'value': value.to_obj()}

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
        if scope < 1:
            raise ValueError("scope too small, cannot read Union selector")
        selector = int.from_bytes(stream.read(1), byteorder='little')
        options = cls.options()
        option_count = len(options)
        if selector >= option_count:
            raise ValueError(f"selected index {selector} was out of option range {option_count}")
        selected_type = options[selector]
        if selected_type is None:
            value = None
        else:
            value = selected_type.deserialize(stream, scope - 1)
        return cls(selector=selector, value=value)  # type: ignore

    def serialize(self, stream: BinaryIO) -> int:
        stream.write(self.selector().to_bytes(length=1, byteorder='little'))
        value = self.value()
        if value is None:
            return 1
        else:
            return 1 + value.serialize(stream)
