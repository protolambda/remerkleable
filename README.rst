.. image:: https://raw.githubusercontent.com/protolambda/remerkleable/master/docs/_static/logo.png
   :width: 100 px

``remerkleable``
-----------------

.. image:: https://img.shields.io/pypi/l/remerkleable.svg
    :target: https://pypi.python.org/pypi/remerkleable

.. image:: https://img.shields.io/pypi/pyversions/remerkleable.svg
    :target: https://pypi.python.org/pypi/remerkleable

.. image::  https://img.shields.io/pypi/status/remerkleable.svg
    :target: https://pypi.python.org/pypi/remerkleable

.. image:: https://img.shields.io/pypi/implementation/remerkleable.svg
    :target: https://pypi.python.org/pypi/remerkleable

.. image:: https://github.com/protolambda/remerkleable/workflows/Remerkleable%20Python%20CI/badge.svg
    :target: https://github.com/protolambda/remerkleable/actions


**Re-merkle-able**: Typed mutable SSZ views over cached and immutable binary Merkle trees.

Features
---------

- Types:
    - custom byte-vector and byte-list view for Python bytes-like behavior
    - bitfields: bitlist, bitvector
    - list, container, vector
    - basic types
- Functionality:
    - **Serialize** all types. Into output stream (returning the written count) and as ``bytes``
    - **Deserialize** all types. From input stream (and scope) and from ``bytes``
    - **Hash-tree-root** all types
    - Merkle-based **data-sharing**:
        - every view can be initialized/backed by a binary Merkle tree
        - complex views have backings, and can share data.
        - complex views provide a nice mutable interface, and replace their backing.
          And this also works for child-views through view-hooks.
        - *SSZ-Partials*: if a *partial* proof is loaded as backing, a view can be overlaid,
          and the partial backing works as long as no excluded branches are accessed.
    - **Calculate byte lengths**:
        - Type min/max byte length
        - Byte length for fixed-length types
        - Output byte length for a value, without serializing
    - **Navigation**: construct paths from types, and convert to generalized indices.
    - **History**: traverse a sequence of nodes, and get the changelog for a given subtree location.

Project Links
--------------

- Docs: https://remerkleable.readthedocs.io/
- Changelog: https://remerkleable.readthedocs.io/en/latest/changelog.html
- PyPI: https://pypi.python.org/pypi/remerkleable
- Issues: https://github.com/protolambda/remerkleable/issues

Also see
---------

- `SSZ: "SimpleSerialize", part of Ethereum 2.0 <https://github.com/ethereum/eth2.0-specs/blob/dev/specs/simple-serialize.md>`_
- `SSZ draft spec <https://github.com/protolambda/eth2.0-ssz/>`_
- `Ethereum Merkle trees information aggregate <https://github.com/protolambda/eth-merkle-trees>`_

Contact
--------

Author: `@protolambda <https://github.com/protolambda>`_

License
--------

MIT, see `LICENSE <./LICENSE>`_ file.
