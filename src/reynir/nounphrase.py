"""

    Greynir: Natural language processing for Icelandic

    NounPhrase class implementation

    Copyright (c) 2020 Miðeind ehf.
    Original author: Vilhjálmur Þorsteinsson

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


    This module implements the NounPhrase class, a handy container
    for noun phrases (nafnliður) allowing them to be easily inflected
    and formatted.

"""

import operator

from .reynir import Greynir


# Format specifiers and how they relate to properties
# of the contained NounPhrase object
_FMT = {
    # Icelandic format specifiers
    "nf": operator.attrgetter('nominative'),
    "þf": operator.attrgetter('accusative'),
    "þgf": operator.attrgetter('dative'),
    "ef": operator.attrgetter('genitive'),
    "ángr": operator.attrgetter('indefinite'),
    "stofn": operator.attrgetter('canonical'),
    # English/international format specifiers
    "nom": operator.attrgetter('nominative'),
    "acc": operator.attrgetter('accusative'),
    "dat": operator.attrgetter('dative'),
    "gen": operator.attrgetter('genitive'),
    "ind": operator.attrgetter('indefinite'),
    "can": operator.attrgetter('canonical'),
}


class NounPhrase:

    """ A handy container for a noun phrase (nafnliður),
        allowing it to be easily inflected and formatted """

    # Singleton parser instance
    _greynir = None

    def __init__(self, np_string):
        """ Initialize a NounPhrase from a text string """
        self._np_string = np_string or ""
        self._number = None
        self._person = None
        self._case = None
        self._gender = None
        if self._np_string:
            if self._greynir is None:
                # Initialize our parser singleton
                self.__class__._greynir = Greynir()
            # Parse the noun phrase string into a _NounPhrase object
            self._np = self._greynir.parse_noun_phrase(self._np_string)
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
        else:
            # No string: no tree, no _NounPhrase
            self._np = None

    def __str__(self):
        """ Return the contained string as-is """
        return self._np_string

    def __repr__(self):
        return "<reynir.NounPhrase('{0}'), {1}>".format(
            self._np_string,
            "parsed" if self.parsed else "not parsed"
        )

    def __len__(self):
        """ Provide len() for convenience """
        return self._np_string.__len__()

    def __format__(self, spec):
        """ Return the contained string after inflecting it according
            to the format specification, if given """
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
        if not spec or not self.parsed:
            return self._np_string
        # Find the attrgetter (property access function)
        # corresponding to the format spec
        fmt = _FMT.get(spec)
        if fmt is None:
            # We don't recognize this format specifier
            raise ValueError(
                "Invalid format specifier for NounPhrase: '{0}'".format(spec)
            )
        # Extract the requested property and return it
        return fmt(self._np)

    @property
    def parsed(self):
        """ Return True if the noun phrase was successfully parsed """
        return self._np is not None and self._np.tree is not None

    @property
    def tree(self):
        """ Return the SimpleTree object corresponding to the noun phrase """
        return None if self._np is None else self._np.tree

    @property
    def case(self):
        """ Return the case of the noun phrase, as originally parsed """
        return self._case

    @property
    def number(self):
        """ Return the number (singular='et'/plural='ft') of the noun phrase,
            as originally parsed """
        return self._number

    @property
    def person(self):
        """ Return the person ('p1', 'p2', 'p3') of the noun phrase,
            as originally parsed """
        return self._person

    @property
    def gender(self):
        """ Return the gender (masculine='kk', feminine='kvk', neutral='hk')
            of the noun phrase, as originally parsed """
        return self._gender

    @property
    def nominative(self):
        """ Return nominative form (nefnifall) """
        return None if self._np is None else self._np.nominative

    @property
    def indefinite(self):
        """ Return indefinite form (nefnifall án greinis) """
        return None if self._np is None else self._np.indefinite

    @property
    def canonical(self):
        """ Return canonical form (nefnifall eintölu án greinis) """
        return None if self._np is None else self._np.canonical

    @property
    def accusative(self):
        """ Return accusative form (þolfall) """
        return None if self._np is None else self._np.accusative

    @property
    def dative(self):
        """ Return dative form (þágufall) """
        return None if self._np is None else self._np.dative

    @property
    def genitive(self):
        """ Return genitive form (eignarfall) """
        return None if self._np is None else self._np.genitive

