from setuptools import setup, find_packages

with open("README.rst", "rt", encoding="utf8") as f:
    readme = f.read()

setup(
    name="remerkleable",
    description="Typed mutable SSZ views over cached and immutable binary merkle trees",
    version="0.1.13",
    long_description=readme,
    long_description_content_type="text/x-rst",
    author="protolambda",
    author_email="proto+pip@protolambda.com",
    url="https://github.com/protolambda/remerkleable",
    python_requires=">=3.8, <4",
    license="MIT",
    packages=find_packages(),
    py_modules=["remerkleable"],
    tests_require=[],
    extras_require={
        "testing": ["pytest"],
        "linting": ["flake8"],
        "docs": ["sphinx", "sphinx-autodoc-typehints", "pallets_sphinx_themes", "sphinx_issues"]
    },
    install_requires=[],
    include_package_data=True,
    keywords=["merkle", "merkleize", "merkle-tree", "merkle-trie", "trie", "ssz", "hash-tree-root", "eth2"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Operating System :: OS Independent",
    ],
)
