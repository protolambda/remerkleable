# `remerkleable` ![](https://github.com/protolambda/remerkleable/workflows/Remerkleable%20Python%20CI/badge.svg)

**Remerkleable**: Typed mutable SSZ views over cached and immutable binary Merkle trees.

Features:
- Types:
    - custom byte-vector view for Python bytes-like behavior
    - bitfields: bitlist, bitvector
    - list, container, vector
    - basic types
- Functionality:
    - Serialize all types. Into output stream (returning the written count) and as `bytes`
    - Deserialize all types. From input stream (and scope) and from `bytes`
    - Hash-tree-root all types
    - Merkle-based data-sharing:
        - every view can be initialized/backed by a binary Merkle tree
        - complex views have backings, and can share data.
        - complex views provide a nice mutable interface, and replace their backing.
          And this also works for child-views through view-hooks.
        - *SSZ-Partials*: if a *partial* proof is loaded as backing, a view can be overlaid,
          and the partial backing works as long as no excluded branches are accessed.
    - Get serialization info from the bare types: min/max byte length, or just byte length for fixed-length types.

## Also see

- [SSZ: "SimpleSerialize", part of Ethereum 2.0](https://github.com/ethereum/eth2.0-specs/blob/dev/specs/simple-serialize.md)
- [SSZ draft spec](https://github.com/protolambda/eth2.0-ssz/)
- [Ethereum Merkle trees information aggregate](https://github.com/protolambda/eth-merkle-trees)

## Contact

Author: [`@protolambda`](https://github.com/protolambda)

## License

MIT, see [`LICENSE` file](LICENSE).
