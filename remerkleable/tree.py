from typing import Callable, NewType, List, Optional, Protocol, TypeVar
from hashlib import sha256


# Get the depth required for a given element count
# (in out): (0 0), (1 0), (2 1), (3 2), (4 2), (5 3), (6 3), (7 3), (8 3), (9 4)
def get_depth(elem_count: int) -> int:
    if elem_count <= 1:
        return 0
    return (elem_count - 1).bit_length()


Gindex = NewType("Gindex", int)

ROOT_GINDEX = Gindex(1)
LEFT_GINDEX = Gindex(2)
RIGHT_GINDEX = Gindex(3)


def to_gindex(index: int, depth: int):
    anchor = 1 << depth
    if index >= anchor:
        raise Exception("index %d too large for depth %d" % (index, depth))
    return anchor | index


def get_anchor_gindex(gindex: Gindex) -> Gindex:
    # noinspection PyTypeChecker
    return 1 << (gindex.bit_length() - 1)


Root = NewType("Root", bytes)

MerkleFn = NewType("MerkleFn", Callable[[Root, Root], Root])

ZERO_ROOT: Root = Root(b'\x00' * 32)


def merkle_hash(left: Root, right: Root):
    return sha256(left + right).digest()


Link = Callable[["Node"], "Node"]
SummaryLink = Callable[[], "Node"]


class Node(Protocol):

    def getter(self, target: Gindex) -> "Node":
        raise NavigationError

    def setter(self, target: Gindex, expand: bool = False) -> Link:
        ...

    def summarize_into(self, target: Gindex) -> SummaryLink:
        setter = self.setter(target)
        getter = self.getter(target)
        return lambda: setter(RootNode(getter.merkle_root(merkle_hash)))

    def merkle_root(self, h: MerkleFn) -> Root:
        ...


# hashes of hashes of zeroes etc.
zero_hashes: List[Root] = [ZERO_ROOT]

for i in range(100):
    zero_hashes.append(merkle_hash(zero_hashes[i], zero_hashes[i]))


def zero_node(depth: int) -> "RootNode":
    return RootNode(zero_hashes[depth])


def identity(v: Node) -> Node:
    return v


def compose(inner: Link, outer: Link) -> Link:
    return lambda v: outer(inner(v))


class NavigationError(RuntimeError):
    pass


V = TypeVar('V', bound=Node)


class PairNode(Node):
    left: Node
    right: Node
    root: Optional[Root]

    def __init__(self, left: Node, right: Node):
        self.left = left
        self.right = right
        self.root = None

    def getter(self, target: Gindex) -> Node:
        if target < 1:
            raise NavigationError
        if target == 1:
            return self
        if target == 2:
            return self.left
        if target == 3:
            return self.right
        anchor = get_anchor_gindex(target)
        pivot = anchor >> 1
        if target < (target | pivot):
            return self.left.getter(Gindex(target ^ anchor | pivot))
        else:
            return self.right.getter(Gindex(target ^ anchor | pivot))

    def setter(self, target: Gindex, expand: bool = False) -> Link:
        if target < 1:
            raise NavigationError
        if target == 1:
            return identity
        if target == 2:
            return self.rebind_left
        if target == 3:
            return self.rebind_right
        anchor = get_anchor_gindex(target)
        pivot = anchor >> 1
        if target < (target | pivot):
            inner = self.left.setter(Gindex(target ^ anchor | pivot), expand=expand)
            return compose(inner, self.rebind_left)
        else:
            inner = self.right.setter(Gindex(target ^ anchor | pivot), expand=expand)
            return compose(inner, self.rebind_right)

    def rebind_left(self, v: Node) -> "PairNode":
        return PairNode(v, self.right)

    def rebind_right(self, v: Node) -> "PairNode":
        return PairNode(self.left, v)

    def merkle_root(self, h: MerkleFn) -> Root:
        if self.root is not None:
            return self.root
        self.root = h(self.left.merkle_root(h), self.right.merkle_root(h))
        return self.root

    def __repr__(self) -> str:
        return f"H({self.left}, {self.right})"


def subtree_fill_to_depth(bottom: Node, depth: int) -> Node:
    node = bottom
    while depth > 0:
        node = PairNode(node, node)
        depth -= 1
    return node


def subtree_fill_to_length(bottom: Node, depth: int, length: int) -> Node:
    if length > (1 << depth):
        raise Exception("too many nodes")
    if length == (1 << depth):
        return subtree_fill_to_depth(bottom, depth)
    if depth == 0:
        if length == 1:
            return bottom
        else:
            raise NavigationError
    if depth == 1:
        return PairNode(bottom, bottom if length > 1 else zero_node(0))
    else:
        anchor = 1 << depth
        pivot = anchor >> 1
        if length <= pivot:
            return PairNode(subtree_fill_to_length(bottom, depth - 1, length), zero_node(depth))
        else:
            return PairNode(
                subtree_fill_to_depth(bottom, depth-1),
                subtree_fill_to_length(bottom, depth-1, length - pivot)
            )


def subtree_fill_to_contents(nodes: List[Node], depth: int) -> Node:
    if len(nodes) > (1 << depth):
        raise Exception("too many nodes")
    if depth == 0:
        if len(nodes) == 1:
            return nodes[0]
        else:
            raise NavigationError
    if depth == 1:
        return PairNode(nodes[0], nodes[1] if len(nodes) > 1 else zero_node(0))
    else:
        anchor = 1 << depth
        pivot = anchor >> 1
        if len(nodes) <= pivot:
            return PairNode(subtree_fill_to_contents(nodes, depth - 1), zero_node(depth - 1))
        else:
            return PairNode(
                subtree_fill_to_contents(nodes[:pivot], depth-1),
                subtree_fill_to_contents(nodes[pivot:], depth-1)
            )


class RootNode(Node):
    root: Root

    def __init__(self, root: Root):
        self.root = root

    def getter(self, target: Gindex) -> Node:
        if target != 1:
            raise NavigationError
        return self

    def setter(self, target: Gindex, expand: bool = False) -> Link:
        if target < 1:
            raise NavigationError
        if target == 1:
            return identity
        if expand:
            child = zero_node(target.bit_length() - 2)
            return PairNode(child, child).setter(target, expand=True)
        else:
            raise NavigationError

    def merkle_root(self, h: MerkleFn) -> Root:
        return self.root

    def __repr__(self):
        return f"0x{self.root.hex()}"


def must_leaf(n: Node) -> Root:
    if not isinstance(n, RootNode):
        raise Exception(f"node {n} is not a rootnode")
    else:
        return n.root
