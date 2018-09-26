"""

    Reynir: Natural language processing for Icelandic

    CFFI builder for _bin module

    Copyright (C) 2018 Miðeind ehf.
    Author: Vilhjálmur Þorsteinsson

       This program is free software: you can redistribute it and/or modify
       it under the terms of the GNU General Public License as published by
       the Free Software Foundation, either version 3 of the License, or
       (at your option) any later version.
       This program is distributed in the hope that it will be useful,
       but WITHOUT ANY WARRANTY; without even the implied warranty of
       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
       GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see http://www.gnu.org/licenses/.


    This module only runs at setup/installation time. It is invoked
    from setup.py as requested by the cffi_modules=[] parameter of the
    setup() function. It causes the _bin.*.so CFFI wrapper library
    to be built from its source in bin.cpp.

"""

import os
import platform
import cffi

# Don't change the name of this variable unless you
# change it in setup.py as well
ffibuilder = cffi.FFI()

_PATH = os.path.dirname(__file__) or "."
WINDOWS = platform.system() == "Windows"

# What follows is the actual Python-wrapped C interface to bin.*.so

declarations = """

    typedef uint32_t UINT;
    typedef char CHAR;
    typedef unsigned char BYTE;

    UINT mapping(const BYTE* pbMap, const CHAR* pszWord);

"""

# Do the magic CFFI incantations necessary to get CFFI and setuptools
# to compile eparser.cpp at setup time, generate a .so library and
# wrap it so that it is callable from Python and PyPy as _eparser

if WINDOWS:
    extra_compile_args = ["/Zc:offsetof-"]
else:
    extra_compile_args = ["-std=c++11"]

ffibuilder.set_source(
    "reynir._bin",
    # bin.cpp is written in C++ but must export a pure C interface.
    # This is the reason for the "extern 'C' { ... }" wrapper.
    'extern "C" {\n' + declarations + "\n}\n",
    source_extension=".cpp",
    sources=["src/reynir/bin.cpp"],
    extra_compile_args=extra_compile_args,
)

ffibuilder.cdef(declarations)

if __name__ == "__main__":
    ffibuilder.compile(verbose=True)
