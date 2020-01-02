# pymerkles

Typed mutable SSZ views over cached and immutable binary merkle trees.


Goal: plug-in replacement for pyspec-ssz, to run a mainnet state with caching and merkle proof suite.

Features:
- Types:
    - custom byte-vector view for Python bytes-like behavior
    - bitfields: bitlist, bitvector
    - list, container, vector
    - basic types
- Functionality:
    - Serialize basic types. Into output stream and as `bytes`
    - Deserialize all types. From input stream (and scope) and from `bytes`
    - Hash-tree-root all types
    - Merkle-based data-sharing:
        - every view can be initialized/backed by a binary merkle tree
        - complex views have backings, and can share data.
        - complex views provide a nice mutable interface, and replace their backing.
          And this also works for child-views through view-hooks.
        - *SSZ-Partials*: if a *partial* proof is loaded as backing, a view can be overlaid,
          and the partial backing works as long as no excluded branches are accessed.
    - Get serialization info from the bare types: min/max byte length, or just byte length for fixed-length types.

TODO features:
 - custom bitvector,bitlist,vector,bitlist subclass checking: check element type and vector_length/limit
 - implement serialization for bitfield and complex types

 
## License

MIT
