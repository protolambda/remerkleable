from setuptools import setup, find_packages

setup(
    name='pymerkles',
    packages=find_packages(),
    tests_require=["pytest"],
    install_requires=[
        "py_ecc==1.7.1",
    ]
)
