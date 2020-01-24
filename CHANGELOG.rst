Changelog
==========

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