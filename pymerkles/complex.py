from typing import Sequence, NamedTuple, cast, List as PyList, Dict, Any
from pymerkles.core import TypeDef, View, BasicTypeDef, BasicView
from pymerkles.basic import uint256, uint8
from pymerkles.tree import Node, subtree_fill_to_length, subtree_fill_to_contents, zero_node, Gindex, Commit, to_gindex, NavigationError
from pymerkles.subtree import SubtreeTypeDef, SubtreeView, get_depth


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
            if isinstance(elem_type, BasicTypeDef):
                basic_elem_type: BasicTypeDef = elem_type
                elems_per_chunk = 32 // basic_elem_type.byte_length()
                return (elems_length + elems_per_chunk - 1) // elems_per_chunk
            else:
                raise Exception("cannot append a packed element that is not a basic type")
        else:
            return elems_length

    @classmethod
    def views_into_chunks(mcs, views: PyList[View]) -> PyList[Node]:
        if mcs.is_packed():
            elem_type: TypeDef = mcs.element_cls()
            if isinstance(elem_type, BasicTypeDef):
                basic_elem_type: BasicTypeDef = elem_type
                return basic_elem_type.pack_views(views)
            else:
                raise Exception("cannot append a packed element that is not a basic type")
        else:
            return [v.get_backing() for v in views]


class MutSeqLike(object):

    def length(self) -> int:
        raise NotImplementedError

    def get(self, i: int) -> View:
        raise NotImplementedError

    def set(self, i: int, v: View):
        raise NotImplementedError

    def __len__(self):
        return self.length()

    def __iter__(self):
        return iter(self.get(i) for i in range(self.length()))

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

    def count(self, v: View) -> int:
        i = 0
        for item in self:
            if item == v:
                i += 1
        return i


class ListType(MonoSubtreeTypeDef):
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
    def item_elem_cls(mcs, i: int) -> TypeDef:
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

        class SpecialListView(List, metaclass=SpecialListType):
            pass

        return SpecialListView


class List(SubtreeView, MutSeqLike, metaclass=ListType):

    def __new__(cls, *args, **kwargs):
        elem_cls = cls.__class__.element_cls()
        vals = list(args)
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
            kwargs['backing'] = Commit(contents, uint256(len(input_views)).get_backing())
        return super().__new__(cls, **kwargs)

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
        if i < 0 or i > self.length():
            raise IndexError
        return super().get(i)

    def set(self, i: int, v: View) -> None:
        if i < 0 or i > self.length():
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


class VectorType(MonoSubtreeTypeDef):
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
        length = mcs.to_chunk_length(mcs.vector_length())
        if mcs.is_packed():
            elem = zero_node(0)
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

        class SpecialVectorView(Vector, metaclass=SpecialVectorType):
            pass

        return SpecialVectorView


class Vector(SubtreeView, MutSeqLike, metaclass=VectorType):
    def __new__(cls, *args, **kwargs):
        elem_cls = cls.__class__.element_cls()
        vals = list(args)
        if issubclass(elem_cls, uint8) and len(vals) == 1 and isinstance(vals[0], bytes):
            vals = list(vals[0])
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
            kwargs['backing'] = subtree_fill_to_contents(input_nodes, cls.__class__.tree_depth())
        return super().__new__(cls, **kwargs)

    def get(self, i: int) -> View:
        if i < 0 or i > self.__class__.vector_length():
            raise IndexError
        return super().get(i)

    def set(self, i: int, v: View) -> None:
        if i < 0 or i > self.__class__.vector_length():
            raise IndexError
        super().set(i, v)

    def length(self) -> int:
        return self.__class__.vector_length()

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

    def __new__(cls, *args, **kwargs):
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
        kwargs['backing'] = subtree_fill_to_contents(input_nodes, cls.tree_depth())
        return super().__new__(cls, *args, **kwargs)

    @classmethod
    def fields(cls) -> Fields:
        annot = cls.__annotations__
        return Fields(keys=list(annot.keys()), types=[v for v in annot.values()])

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
