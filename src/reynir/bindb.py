"""

    Greynir: Natural language processing for Icelandic

    BinDb module

    Copyright © 2026 Miðeind ehf.

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

from typing import Any, Dict, List, Optional, Tuple
from functools import lru_cache
from sys import intern

from islenska.basics import make_bin_entry, ALL_CASES
from islenska.bindb import GreynirBin as GBin, PERSON_NAME_FL

from tokenizer.definitions import BIN_Tuple

from .settings import StaticPhrases

# SHSnid tuple as seen by the Greynir compatibility layer
ResultTuple = Tuple[str, List[BIN_Tuple]]


# Size of name cache for lookup_name_gender
_NAME_GENDER_CACHE_SIZE = 128
# The maximum number of entries in the cache of GreynirBin.lookup_g()
_LOOKUP_CACHE_SIZE = 20_000


class GreynirBin(GBin):

    """Overridden class that adds a singleton instance of GreynirBin
    and a context manager protocol"""

    _singleton: Optional["GreynirBin"] = None

    def __init__(self) -> None:
        super().__init__()
        # Cache for lookup_g(): the tokenizer looks every word of the
        # text up, and what the underlying lookup does for each word is
        # considerable, even when the raw entries of the word are in the
        # cache of the base class: variations in upper and lower case are
        # tried, a word that is not in BÍN is analyzed as a compound word
        # (which is not cached at all), and a tuple is created twice over
        # for every entry found. The result only depends on the word and
        # the two flags, so it is kept here. The cache is simply emptied
        # when it is full, as the token/terminal matching cache of the
        # parser is. (A dict is used, not functools.lru_cache, since an
        # lru_cache on a method would be shared between instances with
        # different options.)
        self._lookup_cache: Dict[
            Tuple[str, bool, bool], Tuple[str, Tuple[BIN_Tuple, ...]]
        ] = dict()

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
        key = (w, at_sentence_start, auto_uppercase)
        cached = self._lookup_cache.get(key)
        if cached is None:
            w_found, m = self._lookup(
                w,
                at_sentence_start,
                auto_uppercase,
                self._meanings_cache_lookup,
                make_bin_entry,
            )
            # The lemmas, categories and inflection strings are interned,
            # as the same ones occur over and over in the cached entries
            cached = (
                w_found,
                tuple(
                    BIN_Tuple(
                        intern(mm[0]),
                        mm[1],
                        intern(mm[2]),
                        intern(mm[3]),
                        mm[4],
                        intern(mm[5]),
                    )
                    for mm in m
                ),
            )
            if len(self._lookup_cache) >= _LOOKUP_CACHE_SIZE:
                # The cache is full: start afresh. Note that the dict is
                # replaced, not cleared, as other threads may be using it.
                self._lookup_cache = dict()
            self._lookup_cache[key] = cached
        # The caller gets a list of its own, which it is free to modify
        return cached[0], list(cached[1])

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
    def lookup_name_gender(self, name: str, preferred_case: str = "nf") -> str:
        """Given a person name, lookup its gender"""
        assert preferred_case in ALL_CASES

        if not name:
            return "hk"  # Unknown gender

        w = name.split(maxsplit=1)[0]  # Get first name
        m = self.meanings(w)  # Look up meanings
        if m:
            # Find all meanings that can be person names
            nl = [x for x in m if x.fl in PERSON_NAME_FL]
            if nl:
                # Find all meanings in the preferred case
                prefc = [x for x in nl if x.beyging.lower().startswith(preferred_case)]
                if prefc:
                    # Found a name meaning in the preferred case
                    return prefc[0].ordfl
                # Found a name meaning *not* in the preferred case
                return nl[0].ordfl

        # The first name was not found: check whether the full name is
        # in the static phrases
        sp = StaticPhrases.lookup(name)
        if sp is not None:
            if sp.fl in PERSON_NAME_FL:
                return sp.ordfl
        return "hk"  # Unknown gender
