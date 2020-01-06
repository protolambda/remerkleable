from setuptools import setup, find_packages

setup(
    name='remerkleable',
    description='Typed mutable SSZ views over cached and immutable binary merkle trees',
    author='protolambda',
    url='https://github.com/protolambda/remerkleable',
    python_requires='>=3.8',
    packages=find_packages(),
    tests_require=["pytest", "flake8"],
    install_requires=[],
    keywords=['merkle', 'merkleize', 'merkle-tree', 'merkle-trie', 'trie', 'ssz', 'hash-tree-root', 'eth2'],
)
