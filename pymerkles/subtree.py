from pymerkles.core import TypeBase, View, BackedType, BackedView
from pymerkles.tree import Link, to_gindex


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
