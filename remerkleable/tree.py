from typing import Callable, NewType, List, Optional
from hashlib import sha256
from abc import ABC, abstractmethod


# Get the depth required for a given element count
# (in out): (0 0), (1 1), (2 1), (3 2), (4 2), (5 3), (6 3), (7 3), (8 3), (9 4)
def get_depth(elem_count: int) -> int:
    return (elem_count - 1).bit_length()


Gindex = NewType("Gindex", int)


def to_gindex(index: int, depth: int):
    anchor = 1 << depth
    if index >= anchor:
        raise Exception("index %d too large for depth %d" % (index, depth))
    return anchor | index


def get_anchor_gindex(gindex: Gindex) -> Gindex:
    return Gindex(1 << (gindex.bit_length() - 1))


Root = NewType("Root", bytes)

MerkleFn = NewType("MerkleFn", Callable[[Root, Root], Root])

ZERO_ROOT: Root = Root(b'\x00' * 32)


def merkle_hash(left: Root, right: Root):
    return sha256(left + right).digest()


class Node(ABC, object):

    @abstractmethod
    def getter(self, target: Gindex) -> "Node":
        raise NotImplementedError

    @abstractmethod
    def setter(self, target: Gindex) -> "Link":
        raise NotImplementedError

    @abstractmethod
    def expand_into(self, target: Gindex) -> "Link":
        raise NotImplementedError

    def summarize_into(self, target: Gindex) -> "SummaryLink":
        setter = self.setter(target)

        def summary() -> "Node":
            summary_root = self.getter(target).merkle_root(merkle_hash)
            return setter(RootNode(summary_root))

        return summary

    @abstractmethod
    def merkle_root(self, h: MerkleFn) -> "Root":
        raise NotImplementedError


# hashes of hashes of zeroes etc.
zero_hashes: List[Root] = [ZERO_ROOT]

for i in range(100):
    zero_hashes.append(merkle_hash(zero_hashes[i], zero_hashes[i]))


def zero_node(depth: int) -> "RootNode":
    return RootNode(zero_hashes[depth])


Link = NewType("Link", Callable[[Node], Node])

SummaryLink = NewType("SummaryLink", Callable[[], Node])


def identity(v: Node) -> Node:
    return v


def compose(inner: Link, outer: Link) -> Link:
    return lambda v: outer(inner(v))


class NavigationError(RuntimeError):
    pass


class InvalidTreeError(RuntimeError):
    pass


class Commit(Node):
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
            if self.left is None:
                raise InvalidTreeError
            return self.left.getter(Gindex(target ^ anchor | pivot))
        else:
            if self.right is None:
                raise InvalidTreeError
            return self.right.getter(Gindex(target ^ anchor | pivot))

    def setter(self, target: Gindex) -> Link:
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
            if self.left is None:
                raise InvalidTreeError
            inner = self.left.setter(Gindex(target ^ anchor | pivot))
            return compose(inner, self.rebind_left)
        else:
            if self.right is None:
                raise InvalidTreeError
            inner = self.right.setter(Gindex(target ^ anchor | pivot))
            return compose(inner, self.rebind_right)

    def rebind_left(self, v: Node) -> "Commit":
        return Commit(v, self.right)

    def rebind_right(self, v: Node) -> "Commit":
        return Commit(self.left, v)

    def expand_into(self, target: Gindex) -> Link:
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
            if self.left is None:
                raise InvalidTreeError
            inner = self.left.expand_into(Gindex(target ^ anchor | pivot))
            return compose(inner, self.rebind_left)
        else:
            if self.right is None:
                raise InvalidTreeError
            inner = self.right.expand_into(Gindex(target ^ anchor | pivot))
            return compose(inner, self.rebind_right)

    def merkle_root(self, h: MerkleFn) -> "Root":
        if self.root is not None:
            return self.root
        if self.left is None or self.right is None:
            raise InvalidTreeError
        self.root = h(self.left.merkle_root(h), self.right.merkle_root(h))
        return self.root

    def __repr__(self) -> str:
        return f"H({self.left}, {self.right})"


def subtree_fill_to_depth(bottom: Node, depth: int) -> Node:
    node = bottom
    while depth > 0:
        node = Commit(node, node)
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
        return Commit(bottom, bottom if length > 1 else zero_node(0))
    else:
        anchor = 1 << depth
        pivot = anchor >> 1
        if length <= pivot:
            return Commit(subtree_fill_to_length(bottom, depth-1, length), zero_node(depth))
        else:
            return Commit(
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
        return Commit(nodes[0], nodes[1] if len(nodes) > 1 else zero_node(0))
    else:
        anchor = 1 << depth
        pivot = anchor >> 1
        if len(nodes) <= pivot:
            return Commit(subtree_fill_to_contents(nodes, depth-1), zero_node(depth-1))
        else:
            return Commit(
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

    def setter(self, target: Gindex) -> Link:
        if target != 1:
            raise NavigationError
        return identity

    def expand_into(self, target: Gindex) -> Link:
        if target < 1:
            raise NavigationError
        if target == 1:
            return identity
        child = zero_node(target.bit_length() - 2)
        return Commit(child, child).expand_into(target)

    def merkle_root(self, h: MerkleFn) -> "Root":
        return self.root

    def __repr__(self):
        return f"0x{self.root.hex()}"


def must_leaf(n: Node) -> Root:
    if not isinstance(n, RootNode):
        raise Exception(f"node {n} is not a rootnode")
    else:
        return n.root
