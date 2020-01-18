from remerkleable.tree import Gindex, Node, get_anchor_gindex, LEFT_GINDEX, RIGHT_GINDEX, ROOT_GINDEX
from typing import List as Iterable, Tuple, TypeVar

K = TypeVar('K')
History = Iterable[Tuple[K, Node]]


def get_target_history(history: History, target: Gindex) -> History:
    """
    Fetch an ordered, keyed, history of nodes at the given target.
    The sequential equal values are reduced into a single value, and keyed by the first occurrence.
    This is done efficiently by first comparing the top of the tree,
     de-duplicating, and then recursively going deeper into the tree.
    :param history: An ordered keyed series of nodes, the root nodes to get the target from
    :param target: The target node to look up, pointing to the values to return.
    :return: the target values, keyed by the keys of the top nodes the target values first occurred in.
    """
    anchor = get_anchor_gindex(target)
    pivot = anchor >> 1
    unanchor = target ^ anchor
    sub_index = LEFT_GINDEX if unanchor < pivot else RIGHT_GINDEX

    # Don't go deeper than the anchor. In this case we just return the (duplicate reduced) history.
    if anchor == ROOT_GINDEX:
        pivot = ROOT_GINDEX
        sub_index = anchor

    out = []
    last = None

    for key, node in history:
        child_node = node.getter(sub_index)
        if last is None or child_node.merkle_root() == last:
            continue
        out.append((key, child_node))
        last = child_node

    if pivot != ROOT_GINDEX:
        out = get_target_history(out, Gindex(pivot | unanchor))

    return out
