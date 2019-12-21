from typing import Sequence, NamedTuple, cast
from pymerkles.core import TypeBase, View, BasicTypeDef
from pymerkles.basic import uint256
from pymerkles.tree import Node, subtree_fill_to_length, subtree_fill_to_contents, zero_node, Gindex, Commit, to_gindex
from pymerkles.subtree import SubtreeType, SubtreeView, get_depth


class ListType(SubtreeType):
    def contents_depth(cls) -> int:
        raise NotImplementedError

    def tree_depth(cls) -> int:
        return cls.contents_depth() + 1  # 1 extra for length mix-in

    def element_type(cls) -> TypeBase:
        raise NotImplementedError

    def item_elem_type(cls, i: int) -> TypeBase:
        return cls.element_type()

    def limit(cls) -> int:
        raise NotImplementedError

    def default_node(cls) -> Node:
        return Commit(zero_node(cls.contents_depth()), zero_node(0))  # mix-in 0 as list length

    def __repr__(self):
        return f"List[{self.element_type()}, {self.limit()}]"

    def __getitem__(self, params):
        (element_type, limit) = params
        contents_depth = 0
        if isinstance(element_type, BasicTypeDef):
            elems_per_chunk = 32 // element_type.byte_length()
            contents_depth = get_depth((limit + elems_per_chunk - 1) // elems_per_chunk)
        else:
            contents_depth = get_depth(limit)

        class SpecialListType(ListType):
            def contents_depth(cls) -> int:
                return contents_depth

            def element_type(cls) -> TypeBase:
                return element_type

            def limit(cls) -> int:
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
        target: Gindex = to_gindex(ll, self.__class__.tree_depth())
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
        target: Gindex = to_gindex(ll - 1, self.__class__.tree_depth())
        set_last = self.get_backing().setter(target)
        next_backing = set_last(zero_node(0))

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

    def get(self, i: int) -> View:
        if i > self.length():
            raise IndexError
        return super().get(i)

    def set(self, i: int, v: View) -> None:
        if i > self.length():
            raise IndexError
        super().set(i, v)


class VectorType(SubtreeType):
    def tree_depth(cls) -> int:
        raise NotImplementedError

    def element_type(cls) -> TypeBase:
        raise NotImplementedError

    def item_elem_type(cls, i: int) -> TypeBase:
        return cls.element_type()

    def length(cls) -> int:
        raise NotImplementedError

    def default_node(cls) -> Node:
        elem = cls.element_type().default_node()
        return subtree_fill_to_length(elem, cls.tree_depth(), cls.length())

    def __repr__(self):
        return f"Vector[{self.element_type()}, {self.length()}]"

    def __getitem__(self, params):
        (element_type, length) = params

        tree_depth = 0
        if isinstance(element_type, BasicTypeDef):
            elems_per_chunk = 32 // element_type.byte_length()
            tree_depth = get_depth((length + elems_per_chunk - 1) // elems_per_chunk)
        else:
            tree_depth = get_depth(length)

        class SpecialVectorType(VectorType):
            def tree_depth(cls) -> int:
                return tree_depth

            def element_type(cls) -> TypeBase:
                return element_type

            def length(cls) -> int:
                return length

        class SpecialVectorView(Vector, metaclass=SpecialVectorType):
            pass

        return SpecialVectorView


class Vector(SubtreeView, metaclass=VectorType):
    def get(self, i: int) -> View:
        if i > self.__class__.length():
            raise IndexError
        return super().get(i)

    def set(self, i: int, v: View) -> None:
        if i > self.__class__.length():
            raise IndexError
        super().set(i, v)


class Fields(NamedTuple):
    keys: Sequence[str]
    types: Sequence[TypeBase]


class ContainerType(SubtreeType):
    def depth(cls) -> int:
        return get_depth(len(cls.fields().keys))

    def item_elem_type(cls, i: int) -> TypeBase:
        return cls.fields().types[i]

    def fields(cls) -> Fields:
        raise NotImplementedError

    def default_node(cls) -> Node:
        return subtree_fill_to_contents([field.default_node() for field in cls.fields().types], cls.depth())

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
