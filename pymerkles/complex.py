from typing import Sequence, NamedTuple, cast
from pymerkles.core import TypeDef, View, BasicTypeDef, BasicView
from pymerkles.basic import uint256
from pymerkles.tree import Node, subtree_fill_to_length, subtree_fill_to_contents, zero_node, Gindex, Commit, to_gindex
from pymerkles.subtree import SubtreeTypeDef, SubtreeView, get_depth


class ListType(SubtreeTypeDef):
    @classmethod
    def is_packed(mcs) -> bool:
        raise NotImplementedError

    @classmethod
    def contents_depth(mcs) -> int:
        raise NotImplementedError

    @classmethod
    def tree_depth(mcs) -> int:
        return mcs.contents_depth() + 1  # 1 extra for length mix-in

    @classmethod
    def element_cls(mcs) -> TypeDef:
        raise NotImplementedError

    @classmethod
    def item_elem_type(mcs, i: int) -> TypeDef:
        return mcs.element_cls()

    @classmethod
    def limit(mcs) -> int:
        raise NotImplementedError

    @classmethod
    def default_node(mcs) -> Node:
        return Commit(zero_node(mcs.contents_depth()), zero_node(0))  # mix-in 0 as list length

    def __repr__(self):
        return f"List[{self.element_cls()}, {self.limit()}]"

    def __getitem__(self, params):
        (element_type, limit) = params
        contents_depth = 0
        packed = False
        if isinstance(element_type, BasicTypeDef):
            elems_per_chunk = 32 // element_type.byte_length()
            contents_depth = get_depth((limit + elems_per_chunk - 1) // elems_per_chunk)
            packed = True
        else:
            contents_depth = get_depth(limit)

        class SpecialListType(ListType):
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

        class SpecialListView(List, metaclass=SpecialListType):
            pass

        return SpecialListView


class List(SubtreeView, metaclass=ListType):
    def length(self) -> int:
        ll_node = super().get_backing().getter(Gindex(3))
        ll = cast(uint256, uint256.view_from_backing(node=ll_node, hook=None))
        return int(ll)

    def append(self, v: View):
        ll = self.length()
        if ll >= self.__class__.limit():
            raise Exception("list is maximum capacity, cannot append")
        i = ll
        if self.__class__.is_packed():
            next_backing = self.get_backing()
            elem_type: TypeDef = self.__class__.element_cls()
            if isinstance(elem_type, BasicTypeDef):
                if not isinstance(v, BasicView):
                    raise Exception("input element is not a basic view")
                basic_v: BasicView = v
                basic_elem_type: BasicTypeDef = elem_type
                elems_per_chunk = 32 // basic_elem_type.byte_length()
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
            if isinstance(elem_type, BasicTypeDef):
                basic_elem_type: BasicTypeDef = elem_type
                elems_per_chunk = 32 // basic_elem_type.byte_length()
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
        if i > self.length():
            raise IndexError
        return super().get(i)

    def set(self, i: int, v: View) -> None:
        if i > self.length():
            raise IndexError
        super().set(i, v)


class VectorType(SubtreeTypeDef):
    @classmethod
    def is_packed(mcs) -> bool:
        raise NotImplementedError

    @classmethod
    def tree_depth(mcs) -> int:
        raise NotImplementedError

    @classmethod
    def element_cls(mcs) -> TypeDef:
        raise NotImplementedError

    @classmethod
    def item_elem_cls(mcs, i: int) -> TypeDef:
        return mcs.element_cls()

    @classmethod
    def vector_length(mcs) -> int:
        raise NotImplementedError

    @classmethod
    def default_node(mcs) -> Node:
        elem_type: TypeDef = mcs.element_cls()
        length = mcs.vector_length()
        if mcs.is_packed():
            if isinstance(elem_type, BasicTypeDef):
                basic_elem_type: BasicTypeDef = elem_type
                elems_per_chunk = 32 // basic_elem_type.byte_length()
                length = (length + elems_per_chunk - 1) // elems_per_chunk
                elem = zero_node(0)
            else:
                raise Exception("cannot append a packed element that is not a basic type")
        else:
            elem = elem_type.default_node()
        return subtree_fill_to_length(elem, mcs.tree_depth(), length)

    def __repr__(self):
        return f"Vector[{self.element_cls()}, {self.vector_length()}]"

    def __getitem__(self, params):
        (element_view_cls, length) = params

        tree_depth = 0
        packed = False
        if isinstance(element_view_cls, BasicTypeDef):
            elems_per_chunk = 32 // element_view_cls.byte_length()
            tree_depth = get_depth((length + elems_per_chunk - 1) // elems_per_chunk)
            packed = True
        else:
            tree_depth = get_depth(length)

        class SpecialVectorType(VectorType):
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

        class SpecialVectorView(Vector, metaclass=SpecialVectorType):
            pass

        return SpecialVectorView


class Vector(SubtreeView, metaclass=VectorType):
    def get(self, i: int) -> View:
        if i > self.__class__.vector_length():
            raise IndexError
        return super().get(i)

    def set(self, i: int, v: View) -> None:
        if i > self.__class__.vector_length():
            raise IndexError
        super().set(i, v)


class Fields(NamedTuple):
    keys: Sequence[str]
    types: Sequence[TypeDef]


class ContainerType(SubtreeTypeDef):

    @classmethod
    def fields(mcs) -> Fields:
        raise NotImplementedError()

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

    @classmethod
    def tree_depth(cls) -> int:
        return get_depth(len(cls.fields().keys))

    @classmethod
    def item_elem_cls(cls, i: int) -> TypeDef:
        return cls.fields().types[i]

    @classmethod
    def default_node(cls) -> Node:
        return subtree_fill_to_contents([field.default_node() for field in cls.fields().types], cls.tree_depth())

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
