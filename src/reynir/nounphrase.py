"""

    Greynir: Natural language processing for Icelandic

    NounPhrase class implementation

    Copyright (C) 2021 Miðeind ehf.
    Original author: Vilhjálmur Þorsteinsson

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

    This module implements the NounPhrase class, a handy container
    for noun phrases (nafnliður) allowing them to be easily inflected
    and formatted.

"""

from typing import Optional, Mapping, Callable

import operator

from .reynir import Greynir, _NounPhrase, SimpleTree


# Format specifiers and how they relate to properties
# of the contained NounPhrase object
_FMT: Mapping[str, Callable[["_NounPhrase"], str]] = {
    # Icelandic format specifiers
    "nf": operator.attrgetter("nominative"),
    "þf": operator.attrgetter("accusative"),
    "þgf": operator.attrgetter("dative"),
    "ef": operator.attrgetter("genitive"),
    "ángr": operator.attrgetter("indefinite"),
    "stofn": operator.attrgetter("canonical"),
    # English/international format specifiers
    "nom": operator.attrgetter("nominative"),
    "acc": operator.attrgetter("accusative"),
    "dat": operator.attrgetter("dative"),
    "gen": operator.attrgetter("genitive"),
    "ind": operator.attrgetter("indefinite"),
    "can": operator.attrgetter("canonical"),
}


class NounPhrase:

    """A handy container for a noun phrase (nafnliður),
    allowing it to be easily inflected and formatted"""

    # Singleton parser instance
    _greynir: Optional[Greynir] = None

    def __init__(self, np_string: str, *, force_number: Optional[str] = None) -> None:
        """Initialize a NounPhrase from a text string.
        If force_number is set to "et" or "singular", we only
        consider singular interpretations of the string.
        If force_number is set to "ft" or "plural", we only
        consider plural interpretations of the string."""
        self._np_string = np_string or ""
        self._number: Optional[str] = None
        self._person: Optional[str] = None
        self._case: Optional[str] = None
        self._gender: Optional[str] = None
        self._np: Optional[_NounPhrase] = None
        if self._np_string:
            if self._greynir is None:
                # Initialize our parser singleton
                # When parsing noun phrases, we don't assume that they
                # start a sentence - so we don't attempt to interpret the
                # first word as a lowercase word, as we would otherwise
                self.__class__._greynir = Greynir(no_sentence_start=True)
            # Parse the noun phrase string into a _NounPhrase object
            assert self._greynir is not None
            self._np = self._greynir.parse_noun_phrase(
                self._np_string, force_number=force_number
            )
            if self._np is not None and self._np.deep_tree is not None:
                # Access the first child of the root 'Nl' nonterminal
                # of the deep parse tree
                nt = next(self._np.deep_tree.enum_child_nodes()).nonterminal.name
                # Sanity check
                assert nt.startswith("Nl_") or nt.startswith("NlEind_")
                # Extract the variants of the nonterminal
                variants = set(nt.split("_")[1:])
                self._number = (variants & {"et", "ft"}).pop()
                self._person = (variants & {"p1", "p2", "p3"}).pop()
                self._case = (variants & {"nf", "þf", "þgf", "ef"}).pop()
                self._gender = (variants & {"kk", "kvk", "hk"}).pop()

    def __str__(self) -> str:
        """Return the contained string as-is"""
        return self._np_string

    def __repr__(self) -> str:
        return "<reynir.NounPhrase('{0}'), {1}>".format(
            self._np_string, "parsed" if self.parsed else "not parsed"
        )

    def __len__(self) -> int:
        """Provide len() for convenience"""
        return self._np_string.__len__()

    def __format__(self, format_spec: str) -> str:
        """Return the contained string after inflecting it according
        to the format specification, if given"""
        # Examples:
        # >>> np = NounPhrase('skjótti hesturinn')
        # >>> f"Hér er {np:nf}"
        # 'Hér er skjótti hesturinn'
        # >>> f"Um {np:þf}"
        # 'Um skjótta hestinn'
        # >>> f"Frá {np:þgf}"
        # 'Frá skjótta hestinum'
        # >>> f"Til {np:ef}"
        # 'Til skjótta hestsins'
        # >>> f"Hér er {np:ángr}"
        # 'Hér er skjóttur hestur'
        # np = NounPhrase("þrír skjóttir hestar")
        # >>> f"Umræðuefnið er {np:stofn}"
        # 'Umræðuefnið er skjóttur hestur'
        if not format_spec or not self.parsed:
            return self._np_string
        # Find the attrgetter (property access function)
        # corresponding to the format spec
        fmt = _FMT.get(format_spec)
        if fmt is None:
            # We don't recognize this format specifier
            raise ValueError(
                "Invalid format specifier for NounPhrase: '{0}'".format(format_spec)
            )
        # Extract the requested property and return it
        assert self._np is not None
        return fmt(self._np)

    @property
    def parsed(self) -> bool:
        """Return True if the noun phrase was successfully parsed"""
        return self._np is not None and self._np.tree is not None

    @property
    def tree(self) -> Optional[SimpleTree]:
        """Return the SimpleTree object corresponding to the noun phrase"""
        return None if self._np is None else self._np.tree

    @property
    def case(self) -> Optional[str]:
        """Return the case of the noun phrase, as originally parsed"""
        return self._case

    @property
    def number(self) -> Optional[str]:
        """Return the number (singular='et'/plural='ft') of the noun phrase,
        as originally parsed"""
        return self._number

    @property
    def person(self) -> Optional[str]:
        """Return the person ('p1', 'p2', 'p3') of the noun phrase,
        as originally parsed"""
        return self._person

    @property
    def gender(self) -> Optional[str]:
        """Return the gender (masculine='kk', feminine='kvk', neutral='hk')
        of the noun phrase, as originally parsed"""
        return self._gender

    @property
    def nominative(self) -> Optional[str]:
        """Return nominative form (nefnifall)"""
        return None if self._np is None else self._np.nominative

    @property
    def indefinite(self) -> Optional[str]:
        """Return indefinite form (nefnifall án greinis)"""
        return None if self._np is None else self._np.indefinite

    @property
    def canonical(self) -> Optional[str]:
        """Return canonical form (nefnifall eintölu án greinis)"""
        return None if self._np is None else self._np.canonical

    @property
    def accusative(self) -> Optional[str]:
        """Return accusative form (þolfall)"""
        return None if self._np is None else self._np.accusative

    @property
    def dative(self) -> Optional[str]:
        """Return dative form (þágufall)"""
        return None if self._np is None else self._np.dative

    @property
    def genitive(self) -> Optional[str]:
        """Return genitive form (eignarfall)"""
        return None if self._np is None else self._np.genitive
