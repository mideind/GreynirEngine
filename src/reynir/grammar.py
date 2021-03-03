"""

    Greynir: Natural language processing for Icelandic

    Grammar module

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

    This module parses a text file containing the description of
    a context-free grammar.

    A grammar is specified as a set of rules. Each rule has a single
    left-hand-side nonterminal, associated with 1..n right-hand-side
    productions. Each right-hand-side production is a sequence of
    nonterminals and terminals. A terminal can match a token of
    input.

    In Greynir grammars, nonterminals always start with an uppercase letter.
    Terminals may be identifiers starting with lowercase letters, or
    literals enclosed within single or double quotes. Epsilon (empty)
    productions are allowed and denoted by 0.

    Examples:

    # Sequence (where terminal_X is optional at the start)
    Nonterminal_A -> terminal_X? Nonterminal_B terminal_Y

    # Alternatives (where terminal_W may occur one or more times sequentially)
    Nonterminal_B ->
        terminal_Z | terminal_W+ | Nonterminal_C

    # Literal terminals:
    # 'x' matches words with stem 'x'
    # "y" matches the token 'y' exactly (after conversion to lower case)
    Nonterminal_C ->
        Nonterminal_D | 'literal_1'* | "exact_literal_2"+

    # Epsilon
    Nonterminal_D ->
        'literal_2' | 0   # 0 means epsilon (in this case equivalent to 'literal_2'?)

"""

from typing import (
    FrozenSet,
    List,
    Dict,
    Set,
    Tuple,
    Iterable,
    Iterator,
    Optional,
    Union,
    Any,
    cast,
)

import os
import struct

from datetime import datetime
from collections import defaultdict, OrderedDict

# pylint: disable=no-name-in-module
if __package__:
    from .settings import Settings, StaticPhrases
    from .basics import changedlocale, ConfigError
else:
    from settings import Settings, StaticPhrases  # type: ignore
    from basics import changedlocale, ConfigError  # type: ignore


ProductionTuple = Tuple[int, "Production"]


class GrammarError(Exception):

    """ Exception class for errors in a grammar """

    def __init__(self, text: str, fname: Optional[str] = None, line: int = 0) -> None:
        """ A GrammarError contains an error text and optionally the name
            of a grammar file and a line number where the error occurred """
        super().__init__(text)
        self.fname = fname
        self.line = line

    def augment(self, fname: str, line: int) -> None:
        """ Add filename and line information, if missing """
        if self.fname is None:
            self.fname = fname
        if self.line == 0:
            self.line = line

    def __str__(self) -> str:
        """ Create a string representation showing the file name and
            line number where the error originated, if available """
        prefix = ""
        if self.line:
            prefix = "Line " + str(self.line) + ": "
        if self.fname:
            prefix = self.fname + " - " + prefix
        return prefix + super().__str__()


class GrammarItem:

    """ An item that can occur in a production in a grammar.
        This is either a Nonterminal or a Terminal. """

    def __init__(self) -> None:
        self._index = 0

    @property
    def literal_text(self) -> str:
        """ The literal text of a terminal, if it is a literal terminal """
        return ""

    @property
    def index(self) -> int:
        """ Return the sequence number of this grammar item """
        return self._index

    def set_index(self, ix: int) -> None:
        """ Set a new sequence number for this grammar item """
        self._index = ix


class Nonterminal(GrammarItem):

    """ A nonterminal, either at the left hand side of
        a rule or within a production """

    _index = -1  # Running sequence number (negative) of all nonterminals

    # If no_reduce is True for a nonterminal, its child families are
    # not reduced to the single highest-scoring family after parsing.
    # This feature is used in query processing.
    no_reduce: bool = False

    def __init__(self, name: str, fname: Optional[str] = None, line: int = 0) -> None:
        super().__init__()
        self._name = name
        # Place of initial definition in a grammar file
        self._fname = fname
        self._line = line
        # Tags for this nonterminal
        self._tags: Optional[Set[str]] = None
        # Has this nonterminal been referenced in a production?
        self._ref = False
        # Is this an optional nonterminal, i.e. one that is
        # explicitly nullable?
        self._optional = name.endswith("?") or name.endswith("*")
        # Give all nonterminals a unique, negative sequence number for hashing purposes
        self._index = Nonterminal._index
        Nonterminal._index -= 1
        self._hash = id(self).__hash__()

    def __hash__(self) -> int:
        """ Use the id of this nonterminal as a basis for the hash """
        # The index may change after the entire grammar has been
        # read and processed; therefore it is not suitable for hashing
        return self._hash

    def __eq__(self, other: Any) -> bool:
        return self is other

    def __ne__(self, other: Any) -> bool:
        return self is not other

    def set_index(self, ix: int) -> None:
        """ Set a new sequence number for this nonterminal """
        # Nonterminals have negative indices
        assert ix < 0
        super().set_index(ix)

    def add_ref(self) -> None:
        """ Mark this as being referenced """
        self._ref = True

    @property
    def has_ref(self) -> bool:
        """ Return True if the nonterminal has been referenced in a production """
        return self._ref

    @property
    def is_optional(self) -> bool:
        """ Return True if this nonterminal is explicitly nullable """
        return self._optional

    @property
    def name(self) -> str:
        return self._name

    @property
    def fname(self) -> str:
        """ Return the name of the grammar file where this nonterminal was defined """
        return self._fname or ""

    @property
    def line(self) -> int:
        """ Return the number of the line within the grammar file
            where this nt was defined """
        return self._line

    @property
    def has_tags(self) -> bool:
        """ Return True if this nonterminal has a tag associated with it """
        return bool(self._tags)

    def has_tag(self, tag: str) -> bool:
        """ Check whether this nonterminal has been tagged with the given tag """
        return self._tags is not None and tag in self._tags

    def has_any_tag(self, tagset: FrozenSet[str]) -> bool:
        """ Check whether this nonterminal has been tagged
            with any of the given tags """
        return False if self._tags is None else not self._tags.isdisjoint(tagset)

    def add_tag(self, tag: str) -> None:
        """ Add a tag to this nonterminal """
        if self._tags is None:
            self._tags = {tag}
        else:
            self._tags.add(tag)
        # Optimization for the no_reduce tag
        if tag == "no_reduce":
            self.no_reduce = True

    @property
    def is_noun_phrase(self) -> bool:
        """ This is overwritten in BIN_Nonterminal in binparser.py """
        return False

    def __repr__(self) -> str:
        return self._name

    def __str__(self) -> str:
        return self._name


class Terminal(GrammarItem):

    """ A terminal within a right-hand-side production """

    _index = 1  # Running sequence number (positive) of all terminals

    def __init__(self, name: str) -> None:
        super().__init__()
        self._name = name
        self._index = Terminal._index
        Terminal._index += 1
        # The hash is used quite often so it is worth caching
        self._hash = id(self).__hash__()

    def __hash__(self) -> int:
        return self._hash

    def __repr__(self) -> str:
        return self._name

    def __str__(self) -> str:
        return self._name

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_literal(self) -> bool:
        """ Return True if this is a literal terminal, i.e. one enclosed
            within single or double quotes """
        return False

    def set_index(self, ix: int) -> None:
        """ Set a new sequence number for this nonterminal """
        # Terminals have indices larger than zero
        assert ix > 0
        super().set_index(ix)

    def matches(self, t_kind: str, t_val: str, t_lit: str) -> bool:
        """ Does this terminal match the given token? """
        return self._name == t_kind


class LiteralTerminal(Terminal):

    """ A literal (constant string) terminal within a right-hand-side production.
        A literal within single quotes 'x' is matched canonically, i.e. with
        the corresponding word stem, if available.
        A literal within double quotes "x" is matched absolutely, i.e. with
        the exact source text (except for a conversion to lowercase). """

    def __init__(self, lit: str) -> None:
        q = lit[0]
        assert q in "'\""
        super().__init__(lit)
        # If a double quote was used, this is a 'strong' literal
        # that matches an exact terminal string as it appeared in the source
        # - no stemming or other canonization should be applied,
        # although the string will be converted to lowercase
        self._strong = q == '"'

    @property
    def literal_text(self) -> str:
        """ If this is a strong literal, return that literal """
        if self._strong:
            return self._name[1:-1]
        return ""

    @property
    def is_literal(self) -> bool:
        """ Return True if this is a literal terminal, i.e. one enclosed
            within single or double quotes """
        return True

    def matches(self, t_kind: str, t_val: str, t_lit: str) -> bool:
        """ A literal terminal matches a token if the token text is
            canonically or absolutely identical to the literal """
        if self._strong:
            # Absolute literal match
            return self._name == t_lit
        # Canonical match of stems or prototypes
        return self._name == t_val


class Token:

    """ A single input token as seen by the parser """

    def __init__(self, kind: str, val: str, lit: Optional[str] = None) -> None:
        """ A basic token has a kind, a canonical value
            and an optional literal value, all strings """
        self._kind = kind
        self._val = val
        self._lit = lit or val

    def __repr__(self) -> str:
        """ Return a simple string representation of this token """
        if self._kind == self._val:
            return self._kind
        return "{0}:{1}".format(self._kind, self._val)

    @property
    def kind(self) -> str:
        """ Return the token kind """
        return self._kind

    @property
    def text(self) -> str:
        """ Return the 'canonical' token text, which may be a stem or
            prototype of the literal, original token text as it appeared
            in the source """
        return self._val

    @property
    def literal(self) -> str:
        """ Return the literal, original token text as it appeared in the source """
        return self._lit

    def matches(self, terminal: Terminal) -> bool:
        """ Does this token match the given terminal? """
        # By default, ask the terminal
        return terminal.matches(self._kind, self._val, self._lit)


class Production:

    """ A right-hand side of a grammar rule """

    _index = 0  # Running sequence number of all productions

    def __init__(
        self,
        fname: Optional[str] = None,
        line: int = 0,
        rhs: Optional[List[GrammarItem]] = None,
        priority: int = 0,
    ) -> None:

        """ Initialize a production from a list of
            right-hand-side nonterminals and terminals """

        self._rhs: List[GrammarItem] = [] if rhs is None else rhs
        # If parsing a grammar file, note the position of the production
        # in the file
        self._fname = fname
        self._line = line
        self._priority = priority
        # Cache the length of the production as it is used A LOT
        self._len = len(self._rhs)
        # Give all productions a unique sequence number for hashing purposes
        self._index = Production._index
        Production._index += 1
        # Cached tuple representation of this production
        self._tuple: Optional[Tuple[int, ...]] = None

    @classmethod
    def reset(cls) -> None:
        """ Reset the production index sequence to zero """
        cls._index = 0

    def append(self, t: GrammarItem) -> None:
        """ Append a terminal or nonterminal to this production """
        self._rhs.append(t)
        self._len += 1
        # Destroy the cached tuple, if any
        self._tuple = None

    @property
    def index(self) -> int:
        return self._index

    @property
    def length(self) -> int:
        """ Return the length of this production """
        return self._len

    @property
    def is_empty(self) -> bool:
        """ Return True if this is an empty (epsilon) production """
        return self._len == 0

    @property
    def fname(self) -> Optional[str]:
        return self._fname

    @property
    def line(self) -> int:
        return self._line

    @property
    def priority(self) -> int:
        return self._priority

    @property
    def prod(self) -> Tuple[int, ...]:
        """ Return this production in tuple form """
        if self._tuple is None:
            # Nonterminals have negative indices and terminals have positive ones
            self._tuple = tuple(t.index for t in self._rhs) if self._rhs else tuple()
        return self._tuple

    def nonterminal_at(self, dot: int) -> bool:
        """ Return True if prod[dot] is a nonterminal or completed """
        return dot >= self._len or isinstance(self._rhs[dot], Nonterminal)

    def __getitem__(self, index: int) -> GrammarItem:
        """ Return the Terminal or Nonterminal at the given index position """
        return self._rhs[index]

    def __setitem__(self, index: int, item: GrammarItem):
        """ Set the Terminal or Nonterminal at the given index position """
        self._rhs[index] = item

    def __len__(self) -> int:
        """ Return the length of this production """
        return self._len

    def __iter__(self) -> Iterator[GrammarItem]:
        return iter(self._rhs)

    def __repr__(self) -> str:
        """ Return a representation of this production """
        return "<P: " + repr(self._rhs) + ">"

    def __str__(self) -> str:
        """ Return a representation of this production """
        return " ".join([str(t) for t in self._rhs]) if self._rhs else "0"


_PRAGMA_SCORE = "$score("
_PRAGMA_ROOT = "$root("
_PRAGMA_TAG = "$tag("
_PRAGMA_IF = "$if("
_PRAGMA_ENDIF = "$endif("


class Grammar:

    """
        A grammar maps nonterminals to a list of right hand sides.
        Each right hand side is a list of terminals and nonterminals.

        The text representation of a grammar is as follows:

        A -> A B terminal C
            | A '/' D
            | 0
        B -> terminal "+" C

        Nonterminals start with uppercase letters.

        Terminals start with lowercase letters or are enclosed
        in single or double quotes.

        0 means an empty (epsilon) production.

        As an alternative to the '|' symbol, productions may also
        be separated by '>'. This indicates a priority ordering
        between the alternatives, so that the result tree is
        automatically reduced to the highest-priority alternative
        in case of ambiguity.

    """

    def __init__(self) -> None:

        self._nonterminals: Dict[str, Nonterminal] = OrderedDict()
        self._terminals: Dict[str, Terminal] = OrderedDict()

        # Dictionary of nonterminals indexed by integers < 0
        self._nonterminals_by_ix: Dict[int, Nonterminal] = {}
        # Dictionary of terminals indexed by integers > 0
        self._terminals_by_ix: Dict[int, Terminal] = {}
        # Dictionary of productions indexed by integers >= 0
        self._productions_by_ix: Dict[int, Production] = {}

        # Mapping of nonterminals to a list of their productions
        self._nt_dict: Dict[Nonterminal, List[ProductionTuple]] = OrderedDict()
        # Nonterminal score adjustment as specified by $score(n)
        self._nt_scores: Dict[Nonterminal, int] = {}

        self._root: Optional[Nonterminal] = None
        # Additional, secondary roots, if any
        self._secondary_roots: List[Nonterminal] = []

        # Information about the grammar file
        self._file_name: Optional[str] = None
        self._file_time: Optional[datetime] = None

        # Grammar parsing conditions, checkable with $if()...$endif()
        # This should be a set of strings
        self._conditions: Set[str] = set()

    @property
    def nt_dict(self) -> Dict[Nonterminal, List[ProductionTuple]]:
        """ Return the raw grammar dictionary, Nonterminal -> [ Productions ] """
        return self._nt_dict

    def nt_score(self, nt: Nonterminal) -> int:
        """ Return the score adjustment for the given nonterminal """
        return self._nt_scores.get(nt, 0)

    @property
    def root(self) -> Optional[Nonterminal]:
        """ Return the root nonterminal for this grammar """
        return self._root

    @property
    def terminals(self) -> Dict[str, Terminal]:
        """ Return a dictionary of terminals in the grammar """
        return self._terminals

    @property
    def nonterminals(self) -> Dict[str, Nonterminal]:
        """ Return a dictionary of nonterminals in the grammar """
        return self._nonterminals

    @property
    def nonterminals_by_ix(self) -> Dict[int, Nonterminal]:
        """ Return a dictionary of nonterminals in the grammar,
            indexed by integer < 0 """
        return self._nonterminals_by_ix

    @property
    def terminals_by_ix(self) -> Dict[int, Terminal]:
        """ Return a dictionary of terminals in the grammar,
            indexed by integer > 0 """
        return self._terminals_by_ix

    @property
    def productions_by_ix(self) -> Dict[int, Production]:
        """ Return a dictionary of productions in the grammar,
            indexed by integer >= 0 """
        return self._productions_by_ix

    def lookup(self, index: int) -> Optional[GrammarItem]:
        """ Look up a nonterminal or terminal by integer index """
        if index < 0:
            return self._nonterminals_by_ix.get(index)
        if index > 0:
            return self._terminals_by_ix.get(index)
        # index == 0
        return None

    def lookup_nonterminal(self, index: int) -> Optional[Nonterminal]:
        """ Look up a nonterminal by (negative) integer index """
        return None if index >= 0 else self._nonterminals_by_ix.get(index)

    def lookup_terminal(self, index: int) -> Optional[Terminal]:
        """ Look up a terminal by (positive) integer index """
        return None if index <= 0 else self._terminals_by_ix.get(index)

    @property
    def num_nonterminals(self) -> int:
        """ Return the number of nonterminals in the grammar """
        return len(self._nonterminals)

    @property
    def num_terminals(self) -> int:
        """ Return the number of terminals in the grammar """
        return len(self._terminals)

    @property
    def num_productions(self) -> int:
        """ Return the total number of productions in the grammar,
            were each right hand side option is counted as one """
        return sum(len(pp) for pp in self._nt_dict.values())

    @property
    def file_name(self) -> Optional[str]:
        """ Return the name of the grammar file, or None """
        return self._file_name

    @property
    def file_time(self) -> Optional[datetime]:
        """ Return the timestamp of the grammar file, or None """
        return self._file_time

    def set_conditions(self, cond_set: Set[str]) -> None:
        """ Set the parsing conditions for this grammar,
            checkable with $if()...$endif() """
        self._conditions = cond_set

    def __getitem__(self, nt: Nonterminal) -> List[ProductionTuple]:
        """ Look up a nonterminal, yielding a list of (priority, production) tuples """
        return self._nt_dict[nt]

    def __str__(self) -> str:
        """ Return a string representation of this grammar """

        def to_str(plist: Iterable[ProductionTuple]) -> str:
            return " | ".join([str(p) for _, p in plist])

        return "\n".join(
            [str(nt) + " → " + to_str(ptl) + "\n" for nt, ptl in self._nt_dict.items()]
        )

    @staticmethod
    def _make_terminal(name: str) -> Terminal:
        """ Create a new Terminal instance within the grammar """
        # Override this to create custom terminals or add optimizations
        return Terminal(name)

    @staticmethod
    def _make_literal_terminal(name: str) -> LiteralTerminal:
        """ Create a new LiteralTerminal instance within the grammar """
        # Override this to create custom terminals or add optimizations
        return LiteralTerminal(name)

    @staticmethod
    def _make_nonterminal(name: str, fname: str, line: int) -> Nonterminal:
        """ Create a new Nonterminal instance within the grammar """
        # Override this to create custom nonterminals or add optimizations
        return Nonterminal(name, fname, line)

    def _write_binary(self, fname: str) -> None:
        """ Write grammar to binary file. Called after reading a grammar text file
            that is newer than the corresponding binary file. """
        with open(fname, "wb") as f:
            if Settings.DEBUG:
                print("Writing binary grammar file {0}".format(fname))
            # Version header
            f.write("Greynir00.00.01\n".encode("ascii"))  # 16 bytes total
            num_nt = self.num_nonterminals
            # Number of terminals and nonterminals in grammar
            f.write(struct.pack("<II", self.num_terminals, num_nt))
            # Root nonterminal
            assert self.root is not None
            if Settings.DEBUG:
                print("Root index is {0}".format(self.root.index))
            f.write(struct.pack("<i", self.root.index))
            # Write nonterminals in numeric order, -1 first downto -N
            for ix in range(num_nt):
                nt = self.lookup_nonterminal(-1 - ix)
                plist = self[nt] if nt else []
                f.write(struct.pack("<I", len(plist)))
                # Write productions along with their indices and priorities
                for prio, p in plist:
                    lenp = len(p)
                    f.write(struct.pack("<III", p.index, prio, lenp))
                    if lenp:
                        f.write(struct.pack("<" + str(lenp) + "i", *p.prod))
        if Settings.DEBUG:
            print("Writing of binary grammar file completed")
            print(
                "num_terminals was {0}, num_nonterminals {1}".format(
                    self.num_terminals, num_nt
                )
            )

    def read(
        self, fname: str, verbose: bool = False, binary_fname: Optional[str] = None
    ) -> None:
        """ Read grammar from a text file. Set verbose=True to get diagnostic messages
            about unused nonterminals and nonterminals that are unreachable
            from the root.
            Pass a file name in binary_fname to write a fresh binary file if the
            grammar text file is newer than the existing binary file. """
        try:
            with open(fname, "r", encoding="utf-8") as inp:
                # Read grammar file line-by-line
                self.read_from_generator(fname, inp, verbose, binary_fname)
        except (IOError, OSError):
            raise GrammarError("Unable to open or read grammar file", fname, 0)

    def read_from_generator(
        self,
        fname: str,
        line_generator: Iterator[str],
        verbose: bool = False,
        binary_fname: Optional[str] = None,
        force_new_binary: bool = False,
    ) -> None:
        """ Read grammar from a generator of lines. Set verbose=True to get
            diagnostic messages about unused nonterminals and nonterminals that are
            unreachable from the root. Pass a file name in binary_fname to write
            a fresh binary file if the grammar text file is newer than the
            existing binary file. Set force_new_binary=True to write a fresh
            binary file regardless of timestamps. """

        # Clear previous file info, if any
        self._file_time = self._file_name = None
        # Shortcuts
        terminals = self._terminals
        nonterminals = self._nonterminals
        grammar = self._nt_dict
        # Reset the sequence of production indices
        Production.reset()
        # Dictionary of variants, keyed by variant name
        # where the values are lists of variant options (strings)
        variants: Dict[str, List[str]] = OrderedDict()

        def parse_line(s: str) -> None:

            s = s.strip()
            if not s:
                # Blank line: ignore
                return

            def highest_priority(nt_id: str) -> int:
                """ Return the highest priority index for a production
                    of the given nonterminal """
                try:
                    nt = nonterminals[nt_id]
                    return max(prio for prio, _ in grammar[nt])
                except (KeyError, ValueError):
                    return 0

            def parse_rhs(nt_id: str, vts: List[str], s: str, priority: int):
                """ Parse a right-hand side sequence, eventually with
                    relative priority within the nonterminal """

                def add_rhs(
                    nt_id: str, rhs: Optional[Production], priority: int = 0
                ) -> None:
                    """ Add a fully expanded right-hand-side production
                        to a nonterminal rule """
                    nt = nonterminals[nt_id]
                    if nt not in grammar:
                        # First production of this nonterminal
                        grammar[nt] = [] if rhs is None else [(priority, rhs)]
                        return
                    if rhs is None:
                        return
                    if rhs.is_empty:
                        # Adding epsilon production: avoid multiple ones
                        if any(p.is_empty for _, p in grammar[nt]):
                            return
                    # Append to the list of productions of this nonterminal
                    grammar[nt].append((priority, rhs))

                s = s.strip()
                if not s:
                    raise GrammarError("Invalid syntax for production", fname, line)

                tokens = s.split()

                # rhs is a list of tuples, one for each token, as follows:
                # (id, repeat, variants)
                rhs: List[Tuple[Optional[str], Optional[str], Optional[List[str]]]] = []

                # vfree is a set of 'free variants', i.e. variants that
                # occur in the right hand side of the production but not in
                # the nonterminal (those are in vts)
                vfree = set()

                for r in tokens:

                    if r in {"0", "ø", "∅"}:
                        # Empty (epsilon) production
                        if len(tokens) != 1:
                            raise GrammarError(
                                "Empty (epsilon) rule must be of the form NT -> 0",
                                fname,
                                line,
                            )
                        rhs.append((None, None, None))
                        break

                    # Check for repeat/conditionality
                    repeat = None
                    if r[-1] in "*+?":
                        # Optional repeat/conditionality specifier
                        # Asterisk: Can be repeated 0 or more times
                        # Plus: Can be repeated 1 or more times
                        # Question mark: optionally present once
                        repeat = r[-1]
                        r = r[0:-1]

                    # Check for variant specs
                    if r == "\"/\"" or r == "'/'":
                        # Hack: Allow specifying the forward slash as "/" or '/'
                        rsplit = [r]
                    else:
                        rsplit = r.split("/")
                        r = rsplit[0]
                    v: Optional[List[str]] = rsplit[1:]
                    if not v:
                        v = None
                    else:
                        for vspec in v:
                            if vspec not in variants:
                                raise GrammarError(
                                    "Unknown variant '{0}'".format(vspec), fname, line
                                )
                            if vspec not in vts:
                                # Free variant: add to set
                                vfree.add(vspec)

                    if r[0] in "\"'":
                        # Literal terminal symbol
                        if r == '""':
                            # Empty literal: matches nothing
                            pass
                        elif len(r) < 3 or r[0] not in r[2:]:
                            raise GrammarError(
                                "Invalid literal terminal {0}".format(r), fname, line
                            )
                    else:
                        # Identifier of nonterminal or terminal
                        if not r.isidentifier():
                            raise GrammarError(
                                "Invalid identifier '{0}'".format(r), fname, line
                            )
                    rhs.append((r, repeat, v))

                assert len(rhs) == len(tokens)

                # Generate productions for all variants

                def variant_values(vlist):
                    """ Returns a list of names with all applicable
                        variant options appended """
                    if not vlist:
                        yield [""]
                        return
                    if len(vlist) == 1:
                        for vopt in variants[vlist[0]]:
                            yield [vopt]
                        return
                    for v in variant_values(vlist[1:]):
                        for vopt in variants[vlist[0]]:
                            yield [vopt] + v

                # Make a list of all variants that occur in the
                # nonterminal or on the right hand side
                vall = vts + list(vfree)

                for vval in variant_values(vall):
                    # Generate a production for every variant combination

                    # Calculate the nonterminal suffix for this variant
                    # combination
                    nt_suffix = (
                        "_".join(vval[vall.index(vx)] for vx in vts) if vts else ""
                    )
                    if nt_suffix:
                        nt_suffix = "_" + nt_suffix

                    result = Production(fname, line, priority=priority)
                    for rname, repeat, v in rhs:
                        # Calculate the token suffix, if any
                        # This may be different from the nonterminal suffix as
                        # the token may have fewer variants than the nonterminal,
                        # and/or free ones that don't appear in the nonterminal.
                        n: Union[None, Nonterminal, Terminal]
                        if rname is None:
                            # Epsilon
                            n = None
                            sym = ""
                        else:
                            suffix = (
                                "_".join(vval[vall.index(vx)] for vx in v) if v else ""
                            )
                            if suffix:
                                suffix = "_" + suffix
                            sym = rname + suffix
                            if rname[0] in "'\"":
                                # Literal terminal
                                if sym not in terminals:
                                    terminals[sym] = self._make_literal_terminal(sym)
                                n = terminals[sym]
                            elif rname[0].isupper():
                                # Identifier of nonterminal
                                if sym not in nonterminals:
                                    nonterminals[sym] = self._make_nonterminal(
                                        sym, fname, line
                                    )
                                n = nonterminals[sym]
                                # Note that the nonterminal has been referenced
                                n.add_ref()
                            else:
                                # Identifier of terminal
                                if sym not in terminals:
                                    terminals[sym] = self._make_terminal(sym)
                                n = terminals[sym]

                        # Convert Enhanced Backus-Naur Format (EBNF)
                        # to plain old BNF

                        # If the production item can be repeated or is optional,
                        # create a new production and substitute.

                        # A -> B C* D becomes:
                        # A -> B C_star D
                        # C_star -> C_star C | 0

                        # A -> B C+ D becomes:
                        # A -> B C_plus D
                        # C_plus -> C_plus C | C

                        # A -> B C? D becomes:
                        # A -> B C_opt D
                        # C_opt -> C | 0

                        # (The new productions are actually called
                        # C*, C+ and C? respectively, not C_star, C_plus, C_opt)

                        if repeat is not None:
                            if n is None:
                                raise GrammarError(
                                    "Epsilon (0) cannot be suffixed with ?, * or +",
                                    fname,
                                    line,
                                )
                            # Create C*, C+ or C?
                            new_nt_id = sym + repeat
                            # Make the new nonterminal and production,
                            # if not already there
                            if new_nt_id not in nonterminals:
                                new_nt = nonterminals[
                                    new_nt_id
                                ] = self._make_nonterminal(new_nt_id, fname, line)
                                new_nt.add_ref()
                                # Note that the Earley algorithm is more efficient
                                # on left recursion than middle or right recursion.
                                # Therefore it is better to generate
                                # Cx -> Cx C than Cx -> C Cx.
                                # First production: Cx C
                                new_p = Production(fname, line)
                                if repeat != "?":
                                    new_p.append(new_nt)  # C* / C+
                                new_p.append(n)  # C
                                add_rhs(new_nt_id, new_p)  # Default priority 0
                                # Second production: epsilon(*, ?) or C(+)
                                new_p = Production(fname, line)
                                if repeat == "+":
                                    new_p.append(n)
                                add_rhs(new_nt_id, new_p)  # Default priority 0
                            # Substitute the Cx in the original production
                            n = nonterminals[new_nt_id]

                        if n is not None:
                            result.append(n)

                    assert len(result) == len(rhs) or (
                        len(rhs) == 1 and rhs[0] == (None, None, None)
                    )

                    nt_id_full = nt_id + nt_suffix

                    if len(result) == 1 and result[0] == nonterminals[nt_id_full]:
                        # Nonterminal derives itself
                        raise GrammarError(
                            "Nonterminal {0} deriving itself".format(nt_id_full),
                            fname,
                            line,
                        )
                    add_rhs(nt_id_full, result, priority)

            def variant_names(nt, vts):
                """ Returns a list of names with all applicable
                    variant options appended """
                result = [nt]
                for v in vts:
                    newresult = []
                    for vopt in variants[v]:
                        for r in result:
                            newresult.append(r + "_" + vopt)
                    result = newresult
                return result

            def apply_to_nonterminals(s, func):
                """ Parse a nonterminal/var list from string s,
                    then apply func(nt, p) to all nonterminals,
                    where p is the parameter of the pragma """
                ix = s.rfind(")")
                if ix < 0:
                    raise GrammarError(
                        "Expected right parenthesis in pragma", fname, line
                    )
                param = s[0:ix].strip()
                s = s[ix + 1 :]
                nts = s.split()
                cnt = 0
                for nt_name in nts:
                    ntv = nt_name.split("/")
                    for vname in ntv[1:]:
                        if vname not in variants:
                            raise GrammarError(
                                "Unknown variant '{0}' for nonterminal '{1}'".format(
                                    vname, ntv[0]
                                ),
                                fname,
                                line,
                            )
                    for vname in variant_names(ntv[0], ntv[1:]):
                        if vname not in nonterminals:
                            raise GrammarError(
                                "Unknown nonterminal '{0}'".format(vname), fname, line
                            )
                        try:
                            # Found a nonterminal to which this pragma applies
                            func(nonterminals[vname], param)
                            cnt += 1
                        except:
                            raise GrammarError(
                                "Invalid pragma argument '{0}'".format(param),
                                fname,
                                line,
                            )
                if cnt == 0:
                    # This pragma has no effect
                    raise GrammarError(
                        "Pragma does not affect any nonterminal", fname, line
                    )

            if s.startswith("/"):

                # Definition of variant
                # A variant is specified as /varname = opt1 opt2 opt3...
                v = s.split("=", maxsplit=1)
                if len(v) != 2:
                    raise GrammarError("Invalid variant syntax", fname, line)
                vname = v[0].strip()[1:]
                if "_" in vname or not vname.isidentifier():
                    # Variant names must be valid identifiers without underscores
                    raise GrammarError(
                        "Invalid variant name '{0}'".format(vname), fname, line
                    )
                v = v[1].split()
                for vopt in v:
                    if "_" in vopt or not vopt.isidentifier():
                        # Variant options must be valid identifiers without underscores
                        raise GrammarError(
                            "Invalid option '{0}' in variant '{1}'".format(vopt, vname),
                            fname,
                            line,
                        )
                variants[vname] = v

            elif s.startswith("$"):

                # Pragma
                s = s.strip()

                if s.startswith(_PRAGMA_SCORE):

                    # Pragma $score(int) Nonterminal/var1/var2 ...
                    s = s[len(_PRAGMA_SCORE) :]

                    def set_score(nt, score):
                        self._nt_scores[nt] = int(score)

                    apply_to_nonterminals(s, set_score)

                elif s.startswith(_PRAGMA_TAG):

                    # Pragma $tag(tagstring) Nonterminal/var1/var2 ...
                    s = s[len(_PRAGMA_TAG) :]
                    apply_to_nonterminals(s, lambda nt, tag: nt.add_tag(tag))

                elif s.startswith(_PRAGMA_ROOT):

                    # Pragma $root(Nonterminal)
                    # Identify a nonterminal as a secondary parse root
                    if s[-1] != ")":
                        raise GrammarError(
                            "Expected right parenthesis in $root() pragma", fname, line
                        )
                    root_nt = s[len(_PRAGMA_ROOT) : -1].strip()
                    if not root_nt.isidentifier():
                        raise GrammarError(
                            "Invalid nonterminal name '{0}'".format(root_nt),
                            fname,
                            line,
                        )
                    if root_nt not in nonterminals:
                        raise GrammarError("Unknown nonterminal '{0}'".format(root_nt))
                    # Add an implicit reference to the root
                    nonterminals[root_nt].add_ref()
                    self._secondary_roots.append(nonterminals[root_nt])

                else:
                    raise GrammarError("Unknown pragma '{0}'".format(s), fname, line)

            else:

                # New nonterminal
                if "→" in s:
                    # Fancy schmancy arrow sign: use it
                    rule = s.split("→", maxsplit=1)
                else:
                    rule = s.split("->", maxsplit=1)
                if len(rule) != 2:
                    raise GrammarError("Invalid syntax", fname, line)

                # Split nonterminal spec into name and variant(s),
                # i.e. NtName/var1/var2...
                ntv = rule[0].strip().split("/")
                current_NT = nt = ntv[0]
                current_variants = ntv[1:]
                if not nt.isidentifier():
                    raise GrammarError(
                        "Invalid nonterminal name '{0}'".format(nt), fname, line
                    )
                for vname in current_variants:
                    if vname not in variants:
                        raise GrammarError(
                            "Unknown variant '{0}' for nonterminal '{1}'".format(
                                vname, nt
                            ),
                            fname,
                            line,
                        )

                # Add all previously unknown nonterminal variants
                for nt_var in variant_names(nt, current_variants):
                    if nt_var in nonterminals:
                        cnt = nonterminals[nt_var]
                    else:
                        cnt = self._make_nonterminal(nt_var, fname, line)
                        nonterminals[nt_var] = cnt
                        if self._root is None:
                            # Remember first nonterminal as the root
                            self._root = cnt
                            self._root.add_ref()  # Implicitly referenced
                    if cnt not in grammar:
                        grammar[cnt] = []

                sep = "|"  # Default production separator
                priority = 0  # Default production priority
                if ">" in rule[1]:
                    # Looks like a priority specification between productions
                    if "|" in rule[1]:
                        raise GrammarError(
                            "Cannot mix '|' and '>' between productions", fname, line
                        )
                    sep = ">"
                    # In the case of a prioritized list of productions,
                    # start with a priority index equal to the highest priority
                    # of the existing productions plus one, ensuring that
                    # additional productions always have less priority
                    # (higher index) than the pre-existing ones
                    priority = highest_priority(current_NT) + 1

                for prod in rule[1].split(sep):
                    # Add the productions on the right hand side,
                    # delimited by '|' or '>'
                    # Note: we explicitly tolerate extra separators without error;
                    # this can be used to attach lower-priority productions
                    # to nonterminals, for instance fallback rules to be used
                    # for grammar error checking.
                    prod = prod.strip()
                    if prod:
                        parse_rhs(current_NT, current_variants, prod, priority)
                        # If productions are separated by the > sign, we increase
                        # the priority number (which lowers the priority) by one
                        # for each production
                        if sep == ">":
                            priority += 1

        # Main parse loop

        # The number of the current line in the grammar file
        line = 0
        # The current logical line, eventually amalgamated from
        # multiple physical lines via continuation
        current_line = ""
        # Stack of conditional sections
        cond_stack: List[Tuple[str, bool]] = [("", True)]

        try:
            # Read grammar file line-by-line

            for s in line_generator:

                line += 1
                # Ignore comments
                ix = s.find("#")
                if ix >= 0:
                    s = s[0:ix]

                s = s.rstrip()
                if not s:
                    continue

                # If line starts with a blank, assume it's a continuation
                if s[0].isspace():
                    current_line += s
                    continue

                if cond_stack[-1][1]:
                    # New item starting: parse the previous one and start a new
                    parse_line(current_line)

                # Check conditional section
                if s.startswith(_PRAGMA_IF) and s.endswith(")"):
                    cond = s[4:-1].strip()
                    if not cond.isidentifier():
                        raise GrammarError("$if() condition must be a valid identifier")
                    # Establish whether we want to parse the conditional
                    # section or not
                    new_cond = cond_stack[-1][1] and cond in self._conditions
                    cond_stack.append((cond, new_cond))
                    s = ""
                elif s.startswith(_PRAGMA_ENDIF) and s.endswith(")"):
                    cond = s[7:-1].strip()
                    if not cond.isidentifier():
                        raise GrammarError(
                            "$endif() condition must be a valid identifier"
                        )
                    if len(cond_stack) < 2:
                        raise GrammarError("$endif() with no matching $if()")
                    if cond != cond_stack[-1][0]:
                        raise GrammarError(
                            "$endif({0}) does not match $if({1})".format(
                                cond, cond_stack[-1][0]
                            )
                        )
                    del cond_stack[-1]
                    s = ""

                current_line = s

            # Parse the final chunk
            if current_line:
                parse_line(current_line)

        except GrammarError as e:
            e.augment(fname, line)
            raise e

        # Check all nonterminals to verify that they have productions and are referenced
        for nt in nonterminals.values():
            if verbose and not nt.has_ref:
                # Emit a warning message if verbose=True
                print("Nonterminal {0} is never referenced in a production".format(nt))
            if nt not in grammar:
                raise GrammarError(
                    "Nonterminal {0} is referenced but not defined".format(nt),
                    nt.fname,
                    nt.line,
                )
        for nt, plist in grammar.items():
            if len(plist) == 0:
                raise GrammarError(
                    "Nonterminal {0} has no productions".format(nt), nt.fname, nt.line
                )
            else:
                for _, p in plist:
                    if len(p) == 1 and p[0] == nt:
                        raise GrammarError(
                            "Nonterminal {0} produces itself".format(nt),
                            p.fname,
                            p.line,
                        )

        # Check that productions do not contain consecutive literals
        # that are joined to become a single multi-word phrase token
        # Loop through nonterminals of the grammar
        for _, plist in grammar.items():
            # Loop through the production list of a nonterminal
            for _, p in plist:
                phrase = []
                # Loop through items in a production
                for item in p:
                    item_text = item.literal_text
                    if item_text:
                        # This is a literal terminal: append to phrase
                        phrase.append(item_text)
                        if len(phrase) >= 2:
                            # We have a phrase: check it
                            ptxt = " ".join(phrase)
                            if ptxt in StaticPhrases.MAP:
                                # Oops: defined as a multi-word token in
                                # the [static_phrases] section of Phrases.conf
                                raise GrammarError(
                                    "Consecutive literal terminals match "
                                    "static phrase; use {0} instead".format(
                                        '"' + "_".join(phrase) + '"'
                                    )
                                )
                    else:
                        # Restart phrase
                        phrase = []

        # Check that all nonterminals derive terminal strings
        agenda = [nt for nt in nonterminals.values()]
        der_t = set()
        while agenda:
            reduced = False
            for nt in agenda:
                for _, p in grammar[nt]:
                    if all(isinstance(s, Terminal) or s in der_t for s in p):
                        der_t.add(nt)
                        break
                if nt in der_t:
                    reduced = True
            if not reduced:
                break
            agenda = [nt for nt in nonterminals.values() if nt not in der_t]
        if agenda:
            raise GrammarError(
                "Nonterminals {0} do not derive terminal strings".format(
                    ", ".join([str(nt) for nt in agenda])
                ),
                fname,
                0,
            )

        # Short-circuit nonterminals that point directly and uniquely
        # to other nonterminals.
        # Becausee this creates a gap between the original grammar
        # and the resulting trees, we only do this for nonterminals with variants
        # that do not have a $score pragma

        # Dictionary of shortcuts
        shortcuts: Dict[Nonterminal, Nonterminal] = {}

        for nt, plist in grammar.items():
            if not "_" in nt.name:
                # 'Pure' nonterminal with no variants: don't shortcut
                continue
            if self.nt_score(nt) != 0 or nt.has_tags:
                # Nonterminal has a score adjustment or a tag: don't shortcut
                continue
            if (
                len(plist) == 1
                and len(plist[0][1]) == 1
                and isinstance(plist[0][1][0], Nonterminal)
            ):
                # This nonterminal has only one production,
                # with only one nonterminal item
                target_nt: Nonterminal = cast(Nonterminal, plist[0][1][0])
                assert target_nt != nt
                while target_nt in shortcuts:
                    # Find ultimate destination of shortcut
                    assert target_nt != shortcuts[target_nt]
                    target = shortcuts[target_nt]
                shortcuts[nt] = target_nt

        # Go through all productions and replace the shortcuts with their targets
        for nt, plist in grammar.items():
            for _, p in plist:
                for ix, item in enumerate(p):
                    if isinstance(item, Nonterminal) and item in shortcuts:
                        # Replace the nonterminal in the production
                        target = shortcuts[item]
                        # if verbose:
                        #    # Print informational message in verbose mode
                        #    print("Production of {2}: Replaced {0} with {1}"
                        #        .format(s, target, nt))
                        p[ix] = target

        # Now, after applying shortcuts, check that all nonterminals
        # are reachable from the root
        unreachable = {nt for nt in nonterminals.values()}

        def _remove(nt: Nonterminal) -> None:
            """ Recursively remove all nonterminals that are reachable from nt """
            unreachable.remove(nt)
            for _, p in grammar[nt]:
                for s in p:
                    if isinstance(s, Nonterminal) and s in unreachable:
                        _remove(s)

        # Remove the main root and any secondary roots
        if self._root is not None:
            _remove(self._root)
            for r in self._secondary_roots:
                _remove(r)

        if unreachable:
            if verbose:
                # Emit a warning message if verbose=True
                print(
                    "The following nonterminals are unreachable from the root\n"
                    "and will be removed from the grammar:"
                )
                with changedlocale() as strxfrm:
                    for nt_name in sorted([str(nt) for nt in unreachable], key=strxfrm):
                        print("* {0}".format(nt_name))
            # Simplify the grammar dictionary by removing unreachable nonterminals
            for nt in unreachable:
                del grammar[nt]
                del nonterminals[nt.name]

        # Reassign indices for nonterminals to avoid gaps in the number sequence
        # Nonterminals are indexed downwards from -1
        # We must take care to sort the dictionary before enumerating it,
        # as the ordering will otherwise be non-deterministic and non-repeatable.
        # Note also that the sorting is by design not done on the Icelandic locale,
        # but rather on the default Python string sorting order for maximum
        # repeatability and to avoid requiring the is-IS locale to be installed.
        nt_sorted = sorted(nonterminals.keys())
        self._nonterminals_by_ix = {
            -1 - ix: nonterminals[key] for ix, key in enumerate(nt_sorted)
        }
        for key, nt in self._nonterminals_by_ix.items():
            nt.set_index(key)

        # Reassign indices for terminals
        # Terminals are indexed upwards from 1
        t_sorted = sorted(terminals.keys())
        self._terminals_by_ix = {
            ix + 1: terminals[key] for ix, key in enumerate(t_sorted)
        }
        for key, t in self._terminals_by_ix.items():
            t.set_index(key)

        # Make a dictionary of productions by integer index >= 0.
        # Here, no sorting is required for repeatability, as global production indices
        # are assigned by order of appearance in the grammar file, and the same
        # applies for the local order of productions within a nonterminal.
        for plist in grammar.values():
            for _, p in plist:
                self._productions_by_ix[p.index] = p

        # Grammar successfully read: note the file name and timestamp
        self._file_name = fname
        self._file_time = datetime.fromtimestamp(os.path.getmtime(fname))

        if binary_fname is not None:
            # Check whether to write a fresh binary file
            if force_new_binary:
                # Always write a fresh binary file if this flag is set
                binary_file_time = None
            else:
                try:
                    binary_file_time = datetime.fromtimestamp(
                        os.path.getmtime(binary_fname)
                    )
                except os.error:
                    binary_file_time = None
            if binary_file_time is None or binary_file_time < self._file_time:
                # No binary file or older than text file: write a fresh one
                self._write_binary(binary_fname)

    def follow_set(self, nonterminal):
        """ Return the set of terminals that can follow
            the given nonterminal, as a dictionary keyed
            by terminal, containing a list of productions
            by which the terminal follows the nonterminal """

        nullable = set()

        def is_nullable(nt):
            def is_nullable_prod(p):
                return p.is_empty or all(s in nullable for s in p)

            plist = self._nt_dict[nt]
            return any(is_nullable_prod(p) for _, p in plist)

        changed = True
        while changed:
            changed = False
            for nt in self._nonterminals.values():
                if nt not in nullable and is_nullable(nt):
                    nullable.add(nt)
                    changed = True

        follow = defaultdict(list)
        seen = set()

        def add_follow(nt, prod_seq):
            plist = self._nt_dict[nt]
            for _, p in plist:
                for s in p:
                    if isinstance(s, Terminal):
                        follow[s].append(prod_seq + [p])
                        break
                    if s not in seen:
                        seen.add(s)
                        add_follow(s, prod_seq + [p])
                    if s not in nullable:
                        break

        seen.add(nonterminal)
        add_follow(nonterminal, [])

        for terminal, pseq in follow.items():
            print("Terminal {0} can follow by these productions:".format(terminal))
            for p in pseq:
                print("   {0}".format(str(p)))
            print()

        return follow


if __name__ == "__main__":

    # If run as a main program, do a verbose grammar check

    import sys

    try:
        # Read configuration file
        basepath, _ = os.path.split(os.path.realpath(__file__))
        Settings.read(os.path.join(basepath, "config", "GreynirPackage.conf"))
    except ConfigError as e:
        print("Configuration error: {0}".format(e))
        quit()

    from tokenizer.abbrev import Abbreviations

    # Make sure that the tokenizer has loaded its abbreviations
    # before we parse the grammar, since they are used in error checking
    Abbreviations.initialize()

    fname = "Greynir.grammar"
    args = sys.argv
    if len(args) == 2:
        fname = args[1]

    ts = os.path.getmtime(fname)
    if ts is None:
        print("Unable to read grammar file {0}".format(fname))
    else:
        print(
            "Reading grammar file {0} with timestamp {1:%Y-%m-%d %H:%M:%S}\n".format(
                fname, datetime.fromtimestamp(ts)
            )
        )
        import time

        t0 = time.time()
        g = Grammar()
        try:
            g.read(fname, verbose=True)
            print(
                "Grammar parsed and loaded in {0:.2f} seconds".format(time.time() - t0)
            )
            print(
                "Grammar has {0:,} terminals, {1:,} nonterminals and {2:,} productions".format(
                    g.num_terminals, g.num_nonterminals, g.num_productions
                )
            )
        except GrammarError as err:
            print(str(err))
