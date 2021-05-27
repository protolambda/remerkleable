Changelog
==========

v0.1.20
--------
- Union type support

v0.1.19
--------
- Bitfield access lookup-index type coercion fix

v0.1.18
--------
- Container extensions / inheritance

v0.1.17
--------

- Use r-op overloads to cover all uint operations better (Thanks @ericsson49 for help)
- Use MyPy for type checking, fix type inconsistencies (Thanks @hwwhww for help)
- Refactor TypeDef into part of View class


v0.1.16
--------

- Bare object handling: `cls.from_obj` and `value.to_obj`, to encode and decode json/yaml into remerkleable types.

v0.1.15
--------

- Fix release branch
- Update readthedocs for py 3.8 support

v0.1.14
--------

- Containers now check for unrecognized attribute inputs

v0.1.13
--------

- `mul` and `floordiv` type checks
- bitfield, packed-vector/list, complex-vector/list, container stack-based iterators
- Minor style fixes and optimizations

v0.1.12
--------

- Bugfixes for medium/big sized bitvectors

v0.1.11
--------

- `Node.root` is now a read-propery on every type of node.
- Generalized previous `RootNode` checking, any node type can be recognized as no-child-nodes now, or lazy-load them.
- Split `RebindableNode` from `PairNode` for rebinding behavior as mix-in.
- New `VirtualNode` to lazy-load the child nodes based on the root, instead of lazy-computing the root.
- `is_root()` was misleading; root nodes are not the only node classes without child nodes, and root is used for too many other things already. Renamed to `is_leaf()`.
- Added `leaf_iter(node)`, to iterate over the leafs of a tree
- Added `tree_diff(a, b)`, to iterate over the differences between a and b.
- Made `repr` and `type_repr` more sensible, and prettify nested `repr` of complex views.

v0.1.10
--------

- List/vector init improvements
- ByteList support, with new tests


v0.1.9
-------

- Fix empty bitfield tree initialization
- Check lengths of vector and container type declarations

v0.1.8
-------

- Fix bug in `ByteVector` chunkify padding. And add tests for this case.

v0.1.7
-------

- Fix bug in `readonly_iter` (and thus list/vector serialization) not being able to handle raw byte-vector element type.
- Check-dist command

v0.1.6
-------

- PyPi does not like SVG, change logo link to PNG

v0.1.5
-------
- Fix PyPi upload

v0.1.4
-------

- Fix README rst quirk
- Be explicit about RST description format
- Include logo SVG in description through github link

v0.1.3
-------

- Faster ``getter`` and ``setter`` for tree traversal.
- Add `is_root()` for quick tree content checks
- More direct rebinding of length tree nodes
- Early support for paths

v0.1.2
-------

- Launch of Sphinx-based documentation.
- History traversal, get subtree changelog.

v0.1.1
-------

Speed improvements and minor bugfixes.

v0.1.0
-------

Initial release.