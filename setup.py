#!/usr/bin/env python3
"""
    Greynir: Natural language processing for Icelandic

    Setup.py

    Copyright (C) 2022 Miðeind ehf.
    Original Author: Vilhjálmur Þorsteinsson

    This software is licensed under the MIT License:

        Permission is hereby granted, free of charge, to any person
        obtaining a copy of this software and associated documentation
        files (the "Software"), to deal in the Software without restriction,
        including without limitation the rights to use, copy, modify, merge,
        publish, distribute, sublicense, and/or sell copies of the Software,
        and to permit persons to whom the Software is furnished to do so,
        subject to the following conditions:

        The above copyright notice and this permission notice shall be
        included in all copies or substantial portions of the Software.

        THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
        EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
        MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
        IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
        CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
        TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
        SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


    This module sets up the Greynir package. It uses the cffi_modules
    parameter, available in recent versions of setuptools, to
    automatically compile the eparser.cpp module to eparser.*.so/.pyd
    and build the required CFFI Python wrapper via eparser_build.py.
    The same applies to bin.cpp -> bin.*.so and bin_build.py.

    Note that installing under PyPy >= 3.7 is supported (and recommended
    for best performance).

"""

from typing import Any

import io
import sys

from glob import glob
from os.path import basename, dirname, join, splitext

from setuptools import find_packages, setup


if sys.version_info < (3, 7):
    print("Greynir requires Python >= 3.7")
    sys.exit(1)


def read(*names: str, **kwargs: Any) -> str:
    try:
        return io.open(
            join(dirname(__file__), *names), encoding=kwargs.get("encoding", "utf8")
        ).read()
    except (IOError, OSError):
        return ""


# Load version string from file
__version__ = "[missing]"
exec(open(join("src", "reynir", "version.py")).read())

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="reynir",
    version=__version__,
    license="MIT",
    description="A natural language parser for Icelandic",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Miðeind ehf",
    author_email="mideind@mideind.is",
    url="https://github.com/mideind/GreynirPackage",
    packages=find_packages("src"),
    package_dir={"": "src"},
    py_modules=[splitext(basename(path))[0] for path in glob("src/*.py")],
    package_data={"reynir": ["py.typed"]},
    include_package_data=True,
    zip_safe=True,
    classifiers=[
        # complete classifier list: http://pypi.python.org/pypi?%3Aaction=list_classifiers
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Unix",
        "Operating System :: POSIX",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: MacOS",
        "Natural Language :: Icelandic",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Utilities",
        "Topic :: Text Processing :: Linguistic",
    ],
    keywords=["nlp", "parser", "icelandic"],
    setup_requires=["cffi>=1.15.1"],
    install_requires=[
        "cffi>=1.15.1",
        "tokenizer>=3.4.2",
        "islenska>=0.4.6",
        "typing_extensions",
    ],
    cffi_modules=["src/reynir/eparser_build.py:ffibuilder"],
)
