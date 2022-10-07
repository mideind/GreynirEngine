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

from typing import Any, List, Optional, Tuple
from functools import lru_cache

from islenska.basics import make_bin_entry
from islenska.bindb import GreynirBin as GBin, PERSON_NAME_FL

from tokenizer.definitions import BIN_Tuple

from .settings import StaticPhrases

# SHSnid tuple as seen by the Greynir compatibility layer
ResultTuple = Tuple[str, List[BIN_Tuple]]


# Size of name cache for lookup_name_gender
_NAME_GENDER_CACHE_SIZE = 128


class GreynirBin(GBin):

    """Overridden class that adds a singleton instance of GreynirBin
    and a context manager protocol"""

    _singleton: Optional["GreynirBin"] = None

    @classmethod
    def get_db(cls) -> "GreynirBin":
        if cls._singleton is None:
            cls._singleton = GreynirBin()
        return cls._singleton

    def __enter__(self) -> "GreynirBin":
        """Allow this class to be used in a with statement"""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass

    def lookup_g(
        self, w: str, at_sentence_start: bool = False, auto_uppercase: bool = False
    ) -> ResultTuple:
        """Returns BIN_Tuple instances, which are the Greynir version
        of islenska.BinEntry"""
        w, m = self._lookup(
            w,
            at_sentence_start,
            auto_uppercase,
            self._meanings_cache_lookup,
            make_bin_entry,
        )
        return w, [BIN_Tuple._make(mm) for mm in m]

    def lookup_nominative_g(self, w: str, **options: Any) -> List[BIN_Tuple]:
        """Returns the Greynir version of islenska.BinEntry"""
        return [BIN_Tuple._make(mm) for mm in super().lookup_nominative(w, **options)]

    def lookup_accusative_g(self, w: str, **options: Any) -> List[BIN_Tuple]:
        """Returns the Greynir version of islenska.BinEntry"""
        return [BIN_Tuple._make(mm) for mm in super().lookup_accusative(w, **options)]

    def lookup_dative_g(self, w: str, **options: Any) -> List[BIN_Tuple]:
        """Returns the Greynir version of islenska.BinEntry"""
        return [BIN_Tuple._make(mm) for mm in super().lookup_dative(w, **options)]

    def lookup_genitive_g(self, w: str, **options: Any) -> List[BIN_Tuple]:
        """Returns the Greynir version of islenska.BinEntry"""
        return [BIN_Tuple._make(mm) for mm in super().lookup_genitive(w, **options)]

    def meanings(self, w: str) -> List[BIN_Tuple]:
        """Low-level lookup of BIN_Tuple instances for the given word"""
        return [
            BIN_Tuple(k.ord, k.bin_id, k.ofl, k.hluti, k.bmynd, k.mark)
            for k in self._ksnid_lookup(w)
        ]

    @lru_cache(maxsize=_NAME_GENDER_CACHE_SIZE)
    def lookup_name_gender(self, name: str) -> str:
        """Given a person name, lookup its gender"""
        if not name:
            return "hk"  # Unknown gender
        w = name.split(maxsplit=1)[0]  # First name
        g = self.meanings(w)
        m = next((x for x in g if x.fl in PERSON_NAME_FL), None)
        if m:
            # Found a name meaning
            return m.ordfl
        # The first name was not found: check whether the full name is
        # in the static phrases
        m = StaticPhrases.lookup(name)
        if m is not None:
            if m.fl in PERSON_NAME_FL:
                return m.ordfl
        return "hk"  # Unknown gender
