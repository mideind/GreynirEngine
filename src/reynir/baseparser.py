"""
    Greynir: Natural language processing for Icelandic

    Parser base module

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

    This module defines a base parser class. The base is used in
    BIN_Parser (see binparser.py) which is again the base of the
    C++ Earley parser Fast_Parser (see fastparser.py)

"""

from typing import Dict, List, Iterator, Optional

from .grammar import Grammar, GrammarItem, Terminal, Nonterminal, Production


class _PackedProduction:

    """A container for a packed production, i.e. a grammar Production
    where the component terminals and nonterminals have been packed
    into a list of integer indices"""

    def __init__(self, priority: int, production: Production) -> None:
        # Store the relative priority of this production within its nonterminal
        self._priority = priority
        # Keep a reference to the original production
        self._production = production
        # Store the packed list of indices
        self._ix_list = production.prod
        # Cache the length
        self._len = len(self._ix_list)

    @property
    def production(self) -> Production:
        return self._production

    @property
    def priority(self) -> int:
        return self._priority

    def __getitem__(self, index: int) -> int:
        return self._ix_list[index] if 0 <= index < self._len else 0

    def __len__(self) -> int:
        return self._len

    def __iter__(self) -> Iterator[int]:
        return iter(self._ix_list)


class Base_Parser:

    """Parses a sequence of tokens according to a given grammar and
    a root nonterminal within that grammar, returning a forest of
    possible parses. The parses uses an optimized Earley algorithm.
    """

    def __init__(self) -> None:
        self._root: Optional[int] = None
        self._nt_dict: Dict[int, Optional[List[_PackedProduction]]] = {}
        self._nonterminals: Dict[int, Nonterminal] = {}
        self._terminals: Dict[int, Terminal] = {}

    def init_from_grammar(self, g: Grammar) -> None:
        """Initialize the parser with the given grammar"""
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
        """Create a parser for the Grammar in g"""
        p = cls()
        p.init_from_grammar(g)
        return p

    def _lookup(self, ix: int) -> GrammarItem:
        """Convert a production item from an index to an object reference"""
        # Terminals have positive indices
        # Nonterminals have negative indices
        # A zero index is not allowed
        assert ix != 0
        return self._nonterminals[ix] if ix < 0 else self._terminals[ix]
