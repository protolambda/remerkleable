from pymerkles.core import TypeBase, View, BackedType, BackedView
from pymerkles.basic import uint256
from typing import Sequence, NamedTuple, cast
from pymerkles.tree import Link, Node, subtree_fill_to_length, subtree_fill_to_contents, to_gindex, zero_node, Gindex, Commit


# Get the depth required for a given element count
# (in out): (0 0), (1 1), (2 1), (3 2), (4 2), (5 3), (6 3), (7 3), (8 3), (9 4)
def get_depth(elem_count: int) -> int:
    return (elem_count - 1).bit_length()


class SubtreeType(BackedType):
    def depth(cls):
        raise NotImplementedError

    def item_elem_type(self, i: int) -> TypeBase:
        raise NotImplementedError


class SubtreeView(BackedView, metaclass=SubtreeType):

    def get(self, i: int) -> View:
        elem_type = self.__class__.item_elem_type(i)
        return elem_type.view_from_backing(
            self.get_backing().getter(to_gindex(i, self.__class__.depth())), lambda v: self.set(i, v))

    def set(self, i: int, v: View) -> None:
        setter_link: Link = self.get_backing().setter(to_gindex(i, self.__class__.depth()))
        self.set_backing(setter_link(v.get_backing()))


class ListType(SubtreeType):
    def depth(cls) -> int:
        return get_depth(cls.limit()) + 1  # 1 extra for length mix-in

    def element_type(cls) -> TypeBase:
        raise NotImplementedError

    def item_elem_type(cls, i: int) -> TypeBase:
        return cls.element_type()

    def limit(cls) -> int:
        raise NotImplementedError

    def default_node(cls) -> Node:
        return Commit(zero_node(get_depth(cls.limit())), zero_node(0))

    def __repr__(self):
        return f"List[{self.element_type()}, {self.limit()}]"

    def __getitem__(self, params):
        (element_type, limit) = params

        class SpecialListType(ListType):
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
        anchor = 1 << self.__class__.depth()
        set_last = self.get_backing().expand_into(Gindex(anchor | ll))
        next_backing = set_last(v.get_backing())
        set_length = next_backing.setter(Gindex(3))
        new_length = uint256(ll + 1).get_backing()
        next_backing = set_length(new_length)
        self.set_backing(next_backing)

    def pop(self):
        ll = self.length()
        if ll == 0:
            raise Exception("list is empty, cannot pop")
        anchor = 1 << self.__class__.depth()
        set_last = self.get_backing().expand_into(Gindex(anchor | (ll - 1)))
        next_backing = set_last(zero_node(0))
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
    def depth(cls) -> int:
        return get_depth(cls.length())

    def element_type(cls) -> TypeBase:
        raise NotImplementedError

    def item_elem_type(cls, i: int) -> TypeBase:
        return cls.element_type()

    def length(cls) -> int:
        raise NotImplementedError

    def default_node(cls) -> Node:
        elem = cls.element_type().default_node()
        return subtree_fill_to_length(elem, cls.depth(), cls.length())

    def __repr__(self):
        return f"Vector[{self.element_type()}, {self.length()}]"

    def __getitem__(self, params):
        (element_type, length) = params

        class SpecialVectorType(VectorType):
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
