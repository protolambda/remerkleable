from pymerkles.core import TypeDef, View, BackedView, BasicTypeDef, BasicView
from pymerkles.tree import Link, to_gindex, RootNode, NavigationError


# Get the depth required for a given element count
# (in out): (0 0), (1 1), (2 1), (3 2), (4 2), (5 3), (6 3), (7 3), (8 3), (9 4)
def get_depth(elem_count: int) -> int:
    return (elem_count - 1).bit_length()


class SubtreeTypeDef(TypeDef):
    @classmethod
    def is_packed(mcs) -> bool:
        raise NotImplementedError

    @classmethod
    def tree_depth(mcs) -> int:
        raise NotImplementedError

    @classmethod
    def item_elem_cls(mcs, i: int) -> TypeDef:
        raise NotImplementedError


class SubtreeView(BackedView, metaclass=SubtreeTypeDef):

    def get(self, i: int) -> View:
        elem_type: TypeDef = self.__class__.item_elem_cls(i)
        # basic types are more complicated: we operate on subsections packed into a bottom chunk
        if self.__class__.is_packed():
            if isinstance(elem_type, BasicTypeDef):
                basic_elem_type: BasicTypeDef = elem_type
                elems_per_chunk = 32 // basic_elem_type.byte_length()
                chunk_i = i // elems_per_chunk
                chunk = self.get_backing().getter(to_gindex(chunk_i, self.__class__.tree_depth()))
                if isinstance(chunk, RootNode):
                    return basic_elem_type.basic_view_from_backing(chunk, i % elems_per_chunk)
                else:
                    raise NavigationError(f"chunk {chunk_i} for basic element {i} is not available")
            else:
                raise Exception("cannot pack subtree elements that are not basic types")
        else:
            return elem_type.view_from_backing(
                self.get_backing().getter(to_gindex(i, self.__class__.tree_depth())), lambda v: self.set(i, v))

    def set(self, i: int, v: View) -> None:
        elem_type: TypeDef = self.__class__.item_elem_cls(i)
        # if not the right type, try to coerce it
        if not isinstance(v, elem_type):
            v = elem_type.coerce_view(v)
        if self.__class__.is_packed():
            # basic types are more complicated: we operate on a subsection of a bottom chunk
            if isinstance(elem_type, BasicTypeDef):
                if not isinstance(v, BasicView):
                    raise Exception("input element is not a basic view")
                basic_v: BasicView = v
                basic_elem_type: BasicTypeDef = elem_type
                elems_per_chunk = 32 // basic_elem_type.byte_length()
                chunk_i = i // elems_per_chunk
                target = to_gindex(chunk_i, self.__class__.tree_depth())
                chunk_setter_link: Link = self.get_backing().setter(target)
                chunk = self.get_backing().getter(target)
                if isinstance(chunk, RootNode):
                    new_chunk = basic_v.backing_from_base(chunk, i % elems_per_chunk)
                    self.set_backing(chunk_setter_link(new_chunk))
                else:
                    raise NavigationError(f"chunk {chunk_i} for basic element {i} is not available")
            else:
                raise Exception("cannot pack subtree elements that are not basic types")
        else:
            setter_link: Link = self.get_backing().setter(to_gindex(i, self.__class__.tree_depth()))
            self.set_backing(setter_link(v.get_backing()))
