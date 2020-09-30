"""

    Greynir: Natural language processing for Icelandic

    CFFI builder for _eparser module

    Copyright (C) 2020 Miðeind ehf.
    Author: Vilhjálmur Þorsteinsson

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

    This module only runs at setup/installation time. It is invoked
    from setup.py as requested by the cffi_modules=[] parameter of the
    setup() function. It causes the _eparser.*.so CFFI wrapper library
    to be built from its source in eparser.cpp.

"""

import os
import platform
import cffi  # type: ignore

# Don't change the name of this variable unless you
# change it in setup.py as well
ffibuilder = cffi.FFI()

_PATH = os.path.dirname(__file__) or "."
WINDOWS = platform.system() == "Windows"
MACOS = platform.system() == "Darwin"

# What follows is the actual Python-wrapped C interface to eparser.*.so

declarations = """

    typedef unsigned int UINT;
    typedef int INT;
    typedef int BOOL; // Different from C++
    typedef char CHAR;
    typedef unsigned char BYTE;

    struct Grammar {
        UINT nNonterminals;   // Number of nonterminals
        UINT nTerminals;      // Number of terminals (indexed from 1)
        INT iRoot;            // Index of root nonterminal (negative)
    };

    struct Parser {
        struct Grammar* pGrammar;
    };

    struct Production {
        UINT nId;
        UINT nPriority;
        UINT n;
        INT* pList;
    };

    struct Label {
        INT iNt;
        UINT nDot;
        struct Production* pProd;
        UINT nI;
        UINT nJ;
    };

    struct FamilyEntry {
        struct Production* pProd;
        struct Node* p1;
        struct Node* p2;
        struct FamilyEntry* pNext;
    };

    struct Node {
        struct Label label;
        struct FamilyEntry* pHead;
        UINT nRefCount;
    };

    typedef BOOL (*MatchingFunc)(UINT nHandle, UINT nToken, UINT nTerminal);
    typedef BYTE* (*AllocFunc)(UINT nHandle, UINT nToken, UINT nSize);

    struct Node* earleyParse(struct Parser*, UINT nTokens, INT iRoot, UINT nHandle, UINT* pnErrorToken);
    struct Grammar* newGrammar(const CHAR* pszGrammarFile);
    void deleteGrammar(struct Grammar*);
    struct Parser* newParser(struct Grammar*, MatchingFunc fpMatcher, AllocFunc fpAlloc);
    void deleteParser(struct Parser*);
    void deleteForest(struct Node*);
    void dumpForest(struct Node*, struct Grammar*);
    UINT numCombinations(struct Node*);

    void printAllocationReport(void);

"""

# Declare the Python callbacks from fastparser.py that will be called by the C code
# See: https://cffi.readthedocs.io/en/latest/using.html#extern-python-new-style-callbacks

callbacks = """

    extern "Python" BOOL matching_func(UINT, UINT, UINT);
    extern "Python" BYTE* alloc_func(UINT, UINT, UINT);

"""

# Do the magic CFFI incantations necessary to get CFFI and setuptools
# to compile eparser.cpp at setup time, generate a .so library and
# wrap it so that it is callable from Python and PyPy as _eparser

if WINDOWS:
    extra_compile_args = ["/Zc:offsetof-"]
elif MACOS:
    extra_compile_args = ["-mmacosx-version-min=10.7", "-stdlib=libc++"]
else:
    extra_compile_args = ["-std=c++11"]

ffibuilder.cdef(declarations + callbacks)

ffibuilder.set_source(
    "reynir._eparser",
    # eparser.cpp is written in C++ but must export a pure C interface.
    # This is the reason for the "extern 'C' { ... }" wrapper.
    'extern "C" {\n' + declarations + "\n}\n",
    source_extension=".cpp",
    sources=["src/reynir/eparser.cpp"],
    extra_compile_args=extra_compile_args,
)

if __name__ == "__main__":
    ffibuilder.compile(verbose=True)
