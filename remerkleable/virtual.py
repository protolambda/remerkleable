from typing import Protocol, Optional
from remerkleable.tree import Node, Root, RebindableNode


class VirtualSource(Protocol):
    def get_left(self, key: Root) -> Node:
        ...

    def get_right(self, key: Root) -> Node:
        ...


class VirtualNode(RebindableNode, Node):
    """A node that instead of lazily computing the root, lazily fetches the left and right child based on the root."""

    _root: Root
    _src: VirtualSource
    _left: Optional[Node] = None
    _right: Optional[Node] = None

    def __init__(self, root: Root, src: VirtualSource):
        self._root = root
        self._src = src

    def get_left(self) -> Node:
        if self._left is None:
            self._left = self._src.get_left(self._root)
        return self._left

    def get_right(self) -> Node:
        if self._right is None:
            self._right = self._src.get_right(self._root)
        return self._right

    def is_root(self) -> bool:
        return False

    @property
    def root(self) -> Root:
        return self._root

    def merkle_root(self) -> Root:
        return self._root

    def __repr__(self):
        return f"0x{self._root.hex()}"
