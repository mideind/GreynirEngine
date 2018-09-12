"""
    Reynir: Natural language processing for Icelandic

    Parser base module

    Copyright (c) 2018 Miðeind ehf.
    All rights reserved

    This module defines a base parser class. The base is used in
    BIN_Parser (see binparser.py) which is again the base of the
    C++ Earley parser Fast_Parser (see fastparser.py)

"""


class Base_Parser:

    """ Parses a sequence of tokens according to a given grammar and
        a root nonterminal within that grammar, returning a forest of
        possible parses. The parses uses an optimized Earley algorithm.
    """

    # Parser version - change when logic changes so that output is affected
    _VERSION = "1.0"

    class PackedProduction:

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
            # Cache the hash
            self._hash = production.__hash__()

        @property
        def production(self):
            return self._production

        @property
        def priority(self):
            return self._priority

        def __hash__(self):
            return self._hash

        def __getitem__(self, index):
            return self._ix_list[index] if index < self._len else 0

        def __len__(self):
            return self._len

        def __eq__(self, other):
            return id(self) == id(other)

        def __iter__(self):
            return iter(self._ix_list)

    def __init__(self, g):

        """ Initialize a parser for a given grammar """

        nt_d = g.nt_dict
        r = g.root
        assert nt_d is not None
        assert r is not None
        assert r in nt_d
        # Convert the grammar to integer index representation for speed
        self._root = r.index
        # Make new grammar dictionary, keyed by nonterminal index and
        # containing packed productions with integer indices
        self._nt_dict = { }
        for nt, plist in nt_d.items():
            self._nt_dict[nt.index] = None if plist is None else \
                [ Base_Parser.PackedProduction(prio, p) for prio, p in plist ]
        self._nonterminals = g.nonterminals_by_ix
        self._terminals = g.terminals_by_ix

    @classmethod
    def for_grammar(cls, g):
        """ Create a parser for the Grammar in g """
        return cls(g)

    def _lookup(self, ix):
        """ Convert a production item from an index to an object reference """
        assert ix != 0
        return self._nonterminals[ix] if ix < 0 else self._terminals[ix]

