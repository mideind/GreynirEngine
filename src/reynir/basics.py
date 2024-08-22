"""
    Greynir: Natural language processing for Icelandic

    Basic classes module

    Copyright © 2023 Miðeind ehf.

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


    This module contains basic functions that are used by the settings
    module and other modules. These functions have been extracted from the
    settings module to avoid circular imports or module references.

"""

from typing import (
    Callable,
    Iterable,
    Iterator,
    List,
    Optional,
)

import os
import locale

from contextlib import contextmanager
import importlib.resources as importlib_resources


# The locale used by default in the changedlocale function
_DEFAULT_LOCALE = ("IS_is", "UTF-8")

# A set of all valid verb argument cases
ALL_CASES = frozenset(("nf", "þf", "þgf", "ef"))
ALL_GENDERS = frozenset(("kk", "kvk", "hk"))
ALL_NUMBERS = frozenset(("et", "ft"))
SUBCLAUSES = frozenset(("nh", "nhx", "falls", "spurns"))
REFLPRN = {"sig": "sig_hk_et_þf", "sér": "sig_hk_et_þgf", "sín": "sig_hk_et_ef"}
REFLPRN_CASE = {"sig": "þf", "sér": "þgf", "sín": "ef"}
REFLPRN_SET = frozenset(REFLPRN.keys())

# BÍN compressed file format version (used in tools/binpack.py and bincompress.py)
BIN_COMPRESSOR_VERSION = b"Greynir 02.00.00"
assert len(BIN_COMPRESSOR_VERSION) == 16
BIN_COMPRESSED_FILE = "ord.compressed"


@contextmanager
def changedlocale(
    new_locale: Optional[str] = None, category: str = "LC_COLLATE"
) -> Iterator[Callable[[str], str]]:
    """Change locale for collation temporarily within a context (with-statement)"""
    # The newone locale parameter should be a tuple: ('is_IS', 'UTF-8')
    # The category should be a string such as 'LC_TIME', 'LC_NUMERIC' etc.
    cat = getattr(locale, category)
    old_locale = locale.getlocale(cat)
    try:
        locale.setlocale(cat, new_locale or _DEFAULT_LOCALE)
        yield locale.strxfrm  # Function to transform string for sorting
    finally:
        locale.setlocale(cat, old_locale)


def sort_strings(strings: Iterable[str], loc: Optional[str] = None) -> List[str]:
    """Sort a list of strings using the specified locale's collation order"""
    # Change locale temporarily for the sort
    with changedlocale(loc) as strxfrm:
        return sorted(strings, key=strxfrm)


class ConfigError(Exception):
    """Exception class for configuration errors"""

    def __init__(self, s: str) -> None:
        super().__init__(s)
        self.fname: Optional[str] = None
        self.line = 0

    def set_pos(self, fname: str, line: int) -> None:
        """Set file name and line information, if not already set"""
        if not self.fname:
            self.fname = fname
            self.line = line

    def __str__(self) -> str:
        """Return a string representation of this exception"""
        s = Exception.__str__(self)
        if not self.fname:
            return s
        return "File {0}, line {1}: {2}".format(self.fname, self.line, s)


class LineReader:
    """Read lines from a text file, recognizing $include directives"""

    def __init__(
        self,
        fname: str,
        *,
        package_name: Optional[str] = None,
        outer_fname: Optional[str] = None,
        outer_line: int = 0
    ) -> None:
        self._fname = fname
        self._package_name = package_name
        self._line = 0
        self._inner_rdr: Optional[LineReader] = None
        self._outer_fname = outer_fname
        self._outer_line = outer_line

    def fname(self) -> str:
        """The name of the file being read"""
        return self._fname if self._inner_rdr is None else self._inner_rdr.fname()

    def line(self) -> int:
        """The number of the current line within the file"""
        return self._line if self._inner_rdr is None else self._inner_rdr.line()

    def lines(self) -> Iterator[str]:
        """Generator yielding lines from a text file"""
        self._line = 0
        try:
            if self._package_name:
                ref = importlib_resources.files("reynir").joinpath(self._fname)
                stream = ref.open("rb")
            else:
                stream = open(self._fname, "rb")
            with stream as inp:
                # Read config file line-by-line from the package resources
                accumulator = ""
                for b in inp:
                    # We get byte strings; convert from utf-8 to Python strings
                    s = b.decode("utf-8")
                    self._line += 1
                    if s.rstrip().endswith("\\"):
                        # Backslash at end of line: continuation in next line
                        accumulator += s.strip()[:-1]
                        continue
                    if accumulator:
                        # Add accumulated text from preceding
                        # backslash-terminated lines, but drop leading whitespace
                        s = accumulator + s.lstrip()
                        accumulator = ""
                    # Check for include directive: $include filename.txt
                    if s.startswith("$") and s.lower().startswith("$include "):
                        iname = s.split(maxsplit=1)[1].strip()
                        # Do some path magic to allow the included path
                        # to be relative to the current file path, or a
                        # fresh (absolute) path by itself
                        head, _ = os.path.split(self._fname)
                        iname = os.path.join(head, iname)
                        rdr = self._inner_rdr = LineReader(
                            iname,
                            package_name=self._package_name,
                            outer_fname=self._fname,
                            outer_line=self._line,
                        )
                        yield from rdr.lines()
                        self._inner_rdr = None
                    else:
                        yield s
                if accumulator:
                    # Catch corner case where last line of file ends with a backslash
                    yield accumulator
        except (IOError, OSError):
            if self._outer_fname:
                # This is an include file within an outer config file
                c = ConfigError(
                    "Error while opening or reading include file '{0}'".format(
                        self._fname
                    )
                )
                c.set_pos(self._outer_fname, self._outer_line)
            else:
                # This is an outermost config file
                c = ConfigError(
                    "Error while opening or reading config file '{0}'".format(
                        self._fname
                    )
                )
            raise c
