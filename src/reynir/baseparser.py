"""
    Reynir: Natural language processing for Icelandic

    Parser base module

    Copyright (C) 2020 Miðeind ehf.

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


    This module defines a base parser class. The base is used in
    BIN_Parser (see binparser.py) which is again the base of the
    C++ Earley parser Fast_Parser (see fastparser.py)

"""

from typing import Union, Dict, List, Optional

from .grammar import Grammar, Terminal, Nonterminal


class _PackedProduction:

    """ A container for a packed production, i.e. a grammar Production
        where the component terminals and nonterminals have been packed
        into a list of integer indices """

    def __init__(self, priority, production):
        # Store the relative priority of this production within its nonterminal
        self._priority = priority
        # Keep a reference to the original production
        self._production = production
        # Store the packed list of indices
        self._ix_list = production.prod
        # Cache the length
        self._len = len(self._ix_list)

    @property
    def production(self):
        return self._production

    @property
    def priority(self):
        return self._priority

    def __getitem__(self, index):
        return self._ix_list[index] if 0 <= index < self._len else 0

    def __len__(self):
        return self._len

    def __iter__(self):
        return iter(self._ix_list)


class Base_Parser:

    """ Parses a sequence of tokens according to a given grammar and
        a root nonterminal within that grammar, returning a forest of
        possible parses. The parses uses an optimized Earley algorithm.
    """

    def __init__(self) -> None:
        self._root = None
        self._nt_dict = {}  # type: Dict[int, Optional[List[_PackedProduction]]]
        self._nonterminals = {}  # type: Dict[int, Nonterminal]
        self._terminals = {}  # type: Dict[int, Terminal]

    def init_from_grammar(self, g: Grammar) -> None:
        """ Initialize the parser with the given grammar """
        nt_d = g.nt_dict
        r = g.root
        assert nt_d is not None
        assert r is not None
        assert r in nt_d
        # Convert the grammar to integer index representation for speed
        self._root = r.index
        # Make new grammar dictionary, keyed by nonterminal index and
        # containing packed productions with integer indices
        self._nt_dict = {}
        for nt, plist in nt_d.items():
            self._nt_dict[nt.index] = (
                None
                if plist is None
                else [_PackedProduction(prio, p) for prio, p in plist]
            )
        self._nonterminals = g.nonterminals_by_ix
        self._terminals = g.terminals_by_ix

    @classmethod
    def for_grammar(cls, g: Grammar) -> "Base_Parser":
        """ Create a parser for the Grammar in g """
        p = cls()
        p.init_from_grammar(g)
        return p

    def _lookup(self, ix: int) -> Union[Terminal, Nonterminal]:
        """ Convert a production item from an index to an object reference """
        # Terminals have positive indices
        # Nonterminals have negative indices
        # A zero index is not allowed
        assert ix != 0
        return self._nonterminals[ix] if ix < 0 else self._terminals[ix]
