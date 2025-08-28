#!/usr/bin/env python3
"""
This file is retained for CFFI compilation.
All package metadata is defined in pyproject.toml.
"""

from setuptools import setup

# The cffi_modules and zip_safe settings are not yet supported in pyproject.toml
# and must be defined here.
setup(
    zip_safe=True,
    cffi_modules=["src/reynir/eparser_build.py:ffibuilder"],
)
