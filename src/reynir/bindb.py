"""

    Greynir: Natural language processing for Icelandic

    BinDb module

    Copyright (C) 2021 Miðeind ehf.

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

    This module implements a thin wrapper on top of the GreynirBin
    class from BinPackage, as well as a couple of basic data classes.

"""

from typing import Any, Optional

from islenska import Ksnid, BinMeaning
from islenska.bindb import GreynirBin as GBin


class GreynirBin(GBin):

    """ Overridden class that adds a singleton instance of GreynirBin
        and a context manager protocol """

    _singleton: Optional["GreynirBin"] = None

    @classmethod
    def get_db(cls) -> "GreynirBin":
        if cls._singleton is None:
            cls._singleton = GreynirBin()
        return cls._singleton

    def __enter__(self) -> "GreynirBin":
        """ Allow this class to be used in a with statement """
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass

