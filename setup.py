#!/usr/bin/env python3
"""
This file is retained for CFFI compilation.
All package metadata is defined in pyproject.toml.
"""

import platform

from setuptools import setup

options = {}
if platform.python_implementation() == "CPython":
    # Tag CPython wheels with the stable ABI (e.g. cp310-abi3), so that a
    # single wheel serves all CPython versions >= 3.10. The extension
    # module itself is compiled with Py_LIMITED_API via the py_limited_api
    # flag in eparser_build.py; this option makes the *wheel tag* reflect
    # that. Not applicable to PyPy, which has no stable ABI.
    options = {"bdist_wheel": {"py_limited_api": "cp310"}}

# The cffi_modules and zip_safe settings are not yet supported in pyproject.toml
# and must be defined here.
setup(
    zip_safe=True,
    cffi_modules=["src/reynir/eparser_build.py:ffibuilder"],
    options=options,
)
