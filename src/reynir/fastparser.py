"""

    Greynir: Natural language processing for Icelandic

    Python wrapper for C++ Earley/Scott parser

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

    This module wraps an Earley-Scott parser written in C++ to transform token
    sequences (sentences) into forests of parse trees, with each tree representing a
    possible parse of a sentence, according to a given context-free grammar.

    An Earley parser handles all valid context-free grammars,
    irrespective of ambiguity, recursion (left/middle/right), nullability, etc.
    The returned parse trees reflect the original grammar, which does not
    need to be normalized or modified in any way. All partial parses are
    available in the final parse state table.

    For further information see J. Earley, "An efficient context-free parsing algorithm",
    Communications of the Association for Computing Machinery, 13:2:94-102, 1970.

    The Earley parser used here is the improved version described by Scott & Johnstone,
    referencing Tomita. This allows worst-case cubic (O(n^3)) order, where n is the
    length of the input sentence, while still returning all possible parse trees
    for an ambiguous grammar.

    See Elizabeth Scott, Adrian Johnstone:
    "Recognition is not parsing — SPPF-style parsing from cubic recognisers"
    Science of Computer Programming, Volume 75, Issues 1–2, 1 January 2010, Pages 55–70

    The C++ source code is found in eparser.h and eparser.cpp.

    This wrapper uses the CFFI module (http://cffi.readthedocs.org/en/latest/)
    to call C++ code from CPython and PyPy, also allowing the C++ code to
    call back into Python.

"""

from typing import (
    Dict,
    Any,
    Optional,
    List,
    Sequence,
    Set,
    Union,
    Tuple,
    Iterable,
    Iterator,
    Hashable,
    IO,
    cast,
)

import os
import operator
from threading import Lock
from functools import reduce

from .binparser import (
    BIN_Parser,
    BIN_Token,
    simplify_terminal,
    augment_terminal,
    Tok,
    TokenDict,
)
from .grammar import Grammar, GrammarError, Nonterminal, Terminal, Production
from .settings import Settings
from .glock import GlobalLock

# Import the CFFI wrapper module for the _eparser.*.so library
# which is compiled from eparser.cpp (see eparser_build.py)
# pylint: disable=no-name-in-module
from ._eparser import lib as eparser, ffi  # type: ignore


ffi_NULL: Any = cast(Any, ffi).NULL

# The type of an entry on a ParseTreeFlattener stack
FlattenerType = Union[Tuple[Terminal, BIN_Token], Nonterminal]
ProductionTuple = Tuple[Production, List[Optional["Node"]]]


class ParseJob:

    """Dispatch token matching requests coming in from the C++ code"""

    # Parse jobs have rotating integer IDs, reaching _MAX_JOBS before cycling back
    _MAX_JOBS = 10_000
    _seq = 0
    _jobs: Dict[int, "ParseJob"] = dict()
    _lock = Lock()

    def __init__(
        self,
        handle: int,
        grammar: Grammar,
        tokens: List[BIN_Token],
        terminals: Dict[int, Terminal],
        matching_cache: Dict[Tuple[Hashable, ...], Any],
    ) -> None:
        self._handle = handle
        self.tokens = tokens
        self.terminals = terminals
        self.grammar = grammar
        self.c_dict: Dict[Any, "Node"] = dict()  # Node pointer conversion dictionary
        self.matching_cache = matching_cache  # Token/terminal matching buffers

    def matches(self, token_index: int, terminal_index: int) -> bool:
        """Convert the token reference from a 0-based token index
        to the token object itself; convert the terminal from a
        1-based terminal index to a terminal object."""
        return self.tokens[token_index].matches(self.terminals[terminal_index])

    def alloc_cache(self, token: int, size: int) -> Any:
        """Allocate a token/terminal matching cache buffer for the given token"""
        key = self.tokens[token].key  # Obtain the (hashable) key of the BIN_Token
        try:
            # Do we already have a token/terminal cache match buffer for this key?
            b: Any = self.matching_cache.get(key)
            if b is None:
                # No: create a fresh one (assumed to be initialized to zero)
                b = self.matching_cache[key] = ffi.new("BYTE[]", size)  # type: ignore
        except TypeError:
            assert False, "alloc_cache() unable to hash key: {0}".format(repr(key))
        return b

    def reset(self) -> None:
        """Reset the node pointer conversion dictionary"""
        self.c_dict = dict()

    @property
    def handle(self) -> int:
        return self._handle

    def __enter__(self):
        """Python context manager protocol"""
        return self

    # noinspection PyUnusedLocal
    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any):
        """Python context manager protocol"""
        self.__class__.delete(self._handle)
        # Return False to re-throw exception from the context, if any
        return False

    @classmethod
    def make(
        cls,
        grammar: Grammar,
        tokens: List[BIN_Token],
        terminals: Dict[int, Terminal],
        matching_cache: Dict[Tuple[Hashable, ...], Any],
    ) -> "ParseJob":
        """Create a new parse job with for a given token sequence and set of terminals"""
        with cls._lock:
            h = cls._seq
            cls._seq += 1
            if cls._seq >= cls._MAX_JOBS:
                cls._seq = 0
            j = cls._jobs[h] = ParseJob(h, grammar, tokens, terminals, matching_cache)
        return j

    @classmethod
    def delete(cls, handle: int) -> None:
        """Delete a no-longer-used parse job"""
        with cls._lock:
            del cls._jobs[handle]

    @classmethod
    def dispatch(cls, handle: int, token_index: int, terminal_index: int) -> bool:
        """Dispatch a match request to the correct parse job"""
        return cls._jobs[handle].matches(token_index, terminal_index)

    @classmethod
    def alloc(cls, handle: int, token_index: int, size: int):
        """Dispatch a cache buffer allocation request to the correct parse job"""
        return cls._jobs[handle].alloc_cache(token_index, size)


# Declare CFFI callback functions to be called from the C++ code
# See: https://cffi.readthedocs.io/en/latest/using.html#extern-python-new-style-callbacks


@ffi.def_extern()  # type: ignore
def matching_func(handle: int, token_index: int, terminal_index: int) -> bool:
    """This function is called from the C++ parser to determine
    whether a token matches a terminal. The token is referenced
    by 0-based index, and the terminal by a 1-based index.
    The handle is an arbitrary UINT that was passed to
    earleyParse(). In this case, it is used to identify
    a ParseJob object that dispatches the match query."""
    return ParseJob.dispatch(handle, token_index, terminal_index)


@ffi.def_extern()  # type: ignore
def alloc_func(handle: int, token_index: int, size: int):
    """Allocate a token/terminal matching cache buffer, at least size bytes.
    If the callback returns ffi.NULL, the parser will allocate its own buffer.
    The point of this callback is to allow re-using buffers for identical tokens,
    so we avoid making unnecessary matching calls."""
    return ParseJob.alloc(handle, token_index, size)


class Node:

    """Shared Packed Parse Forest (SPPF) node representation,
    mapped from C++ (see eparser.h/.cpp) to Python.

    A C++ node is described by a label tuple of
    (iNt, nI, nJ, nDot, pProd).

    nI and nJ are the start and end token indices of the span
    covered by the node.

    If iNt is >= 0, the node describes a token/terminal match
    and has no children. iNt is the index of the matched token.

    If iNt is < 0, it is the index of a nonterminal within the
    grammar being parsed. If pProd is not ffi.NULL, this is an
    interior node, corresponding to a dot position of nDot within
    the production pProd. Otherwise, i.e. if pProd is ffi.NULL,
    the node describes a completed nonterminal.

    Nonterminals, unless they are epsilon (empty) nodes, have
    a family of child (derivative) productions represented as a
    linked list starting with pHead. Since the SPPF trees coming
    from the Earley-Scott parser are binarized, the families have
    at most two child nodes each. When creating the Python nodes,
    interior nodes are coalesced as far as possible to form longer
    lists of children, thereby decreasing the total number of nodes
    necessary to represent the forest.

    A forest of Nodes can be navigated using a subclass of
    ParseForestNavigator.

    """

    # Note: __slots__ are not really required on PyPy,
    # but they are beneficial on CPython
    __slots__ = (
        "_start",
        "_end",
        "_families",
        "_highest_prio",
        "_nonterminal",
        "_terminal",
        "_token",
        "_completed",
        "score",
    )

    def __init__(self, start: int, end: int) -> None:
        # Start and end token indices, i.e. the span of this node
        self._start = start
        self._end = end
        # Families of children of this node
        self._families: Optional[List[ProductionTuple]] = None
        # Priority of highest-priority child family
        self._highest_prio = 0
        # The nonterminal corresponding to this node, if not a leaf node
        self._nonterminal: Optional[Nonterminal] = None
        # The terminal corresponding to this node, if it is a leaf node
        self._terminal: Optional[Terminal] = None
        # The token matching this terminal, if this is a leaf node
        self._token: Optional[BIN_Token] = None
        # If completed is True, this node represents a completed nonterminal.
        # Otherwise, it is an internal node representing a position within
        # a production of a nonterminal.
        self._completed = True
        # The score for this node, calculated by the reducer
        self.score = 0

    @classmethod
    def from_c_node(
        cls, job: ParseJob, c_node: Any, parent: Any = None, index: int = 0
    ) -> Optional["Node"]:
        """Initialize a Python node from a C++ SPPF node structure"""
        if c_node == ffi_NULL:
            return None

        lb = c_node.label
        if lb.nI >= lb.nJ:
            # Empty node (no tokens matched within it):
            # don't bother creating a corresponding Python object;
            # we never use these nodes anyway except as fillers
            # to help in matching children with the parent production
            return None

        node = cls(lb.nI, lb.nJ)  # Start token index, end token index

        if lb.iNt >= 0:
            # Token node: find the corresponding terminal
            assert parent is not None
            tix: int = parent.pList[index]
            node._terminal = job.grammar.lookup_terminal(tix)
            node._token = job.tokens[lb.iNt]
            return node

        # Nonterminal node
        nt = lb.iNt
        node._nonterminal = job.grammar.lookup_nonterminal(nt)
        node._completed = lb.pProd == ffi_NULL
        # Cache nonterminal nodes
        job.c_dict[c_node] = node

        # Loop through the families of children of this node
        fe = c_node.pHead
        while fe != ffi_NULL:

            # Save on node count by coalescing interior nodes
            # into the child list of the enclosing completed
            # nonterminal. Nodes can be coalesced while they
            # refer to the same nonterminal, are interior,
            # and not ambiguous.
            ch: List[Any] = []

            def push_pair(p1: Any, p2: Any) -> None:
                """Push a pair of child nodes onto the child list"""

                def push_child(p: Any) -> None:
                    """Push a single child node onto the child list"""
                    if p.label.iNt == nt and p.label.pProd != ffi_NULL:
                        # Interior node for the same nonterminal
                        if p.pHead.pNext == ffi_NULL:
                            # Unambiguous: recurse
                            push_pair(p.pHead.p1, p.pHead.p2)
                        else:
                            # Ambiguous node, i.e. more than one family of children.
                            # In this case we don't know which (p1,p2) pair
                            # to add as a child of the parent, so we must
                            # retain the original node with its family of children
                            # and end the recursion. We also need to add
                            # placeholder (dummy) nodes to keep the child
                            # list in sync with the nonterminal's production.
                            if p.label.nDot > 2:
                                # Add placeholders for the part of the production
                                # that is missing from the front since we abandon
                                # the recursion here
                                ch.extend([ffi_NULL] * (p.label.nDot - 2))
                            ch.append(p)
                            ch.append(ffi_NULL)  # Placeholder
                    else:
                        # Terminal, epsilon or unrelated nonterminal
                        ch.append(p)

                if p1 != ffi_NULL and p2 != ffi_NULL:
                    push_child(p1)
                    push_child(p2)
                elif p2 != ffi_NULL:
                    push_child(p2)
                else:
                    push_child(p1)

            push_pair(fe.p1, fe.p2)
            node._add_family(job, fe.pProd, ch)
            fe = fe.pNext

        return node

    @classmethod
    def copy(cls, other: "Node") -> "Node":
        """Returns a copy of a Node instance"""
        node = cls(other._start, other._end)
        node._nonterminal = other._nonterminal
        node._terminal = other._terminal
        node._token = other._token
        node._completed = other._completed
        node._highest_prio = other._highest_prio
        if other._families:
            # Create a new list object having the
            # same child nodes as the source node
            node._families = other._families[:]
        return node

    def _add_family(self, job: ParseJob, c_prod: Any, c_children: Any) -> None:
        """Add a family of children to this node, in parallel with other families"""
        assert c_prod != ffi_NULL
        prod: Production = job.grammar.productions_by_ix[c_prod.nId]
        prio: int = prod.priority
        # Note: lower priority values mean higher priority!
        if self._families and prio > self._highest_prio:
            # Lower priority than a family we already have: don't bother adding it
            return
        # Recreate the pc tuple from the production index
        pc: ProductionTuple = (
            prod,
            [
                # Convert child node from C++ form to Python form
                job.c_dict.get(ch) or Node.from_c_node(job, ch, c_prod, ix)
                for ix, ch in enumerate(c_children)
            ],
        )
        if self._families is None or prio < self._highest_prio:
            # First family of children, or highest priority so far: add as the only family
            self._families = [pc]
        else:
            # Same priority as the families we have already: add this
            self._families.append(pc)
        self._highest_prio = prio

    @property
    def start(self) -> int:
        """Return the start token index"""
        return self._start

    @property
    def end(self) -> int:
        """Return the end token index"""
        return self._end

    @property
    def is_span(self) -> bool:
        """Returns True if the node spans one or more tokens"""
        return self._end > self._start

    def _first_token(self) -> BIN_Token:
        """Return the first token within the span of this node"""
        p = self
        while p._token is None:
            # Note that this function may be called before the
            # tree is reduced; therefore we may have more than one
            # family of children. The families should however all
            # cover the same token span.
            assert p._families
            _, f = p._families[0]
            ix = 0
            while f[ix] is None:
                ix += 1
            assert f[ix] is not None
            p = cast(Node, f[ix])
        return p._token

    def _last_token(self) -> BIN_Token:
        """Return the last token within the span of this node"""
        p = self
        while p._token is None:
            # Note that this function may be called before the
            # tree is reduced; therefore we may have more than one
            # family of children. The families should however all
            # cover the same token span.
            assert p._families
            _, f = p._families[0]
            ix = -1
            while f[ix] is None:
                ix -= 1
            assert f[ix] is not None
            p = cast(Node, f[ix])
        return p._token

    @property
    def token_span(self) -> Tuple[BIN_Token, BIN_Token]:
        """Return the first and last tokens under this node"""
        return (self._first_token(), self._last_token())

    @property
    def nonterminal(self) -> Optional[Nonterminal]:
        """Return the nonterminal associated with this node"""
        return self._nonterminal

    @property
    def is_ambiguous(self):
        """Return True if this node has more than one family of children"""
        return self._families is not None and len(self._families) >= 2

    @property
    def is_interior(self) -> bool:
        """Returns True if this is an interior node (partially parsed production)"""
        return not self._completed

    @property
    def is_completed(self) -> bool:
        """Returns True if this is a node corresponding to a completed nonterminal"""
        return self._completed

    @property
    def is_token(self) -> bool:
        """Returns True if this is a token node"""
        return self._token is not None

    @property
    def terminal(self) -> Optional[Terminal]:
        """Return the terminal associated with a token node, or None if none"""
        return self._terminal

    @property
    def token(self) -> Optional[BIN_Token]:
        """Return the token associated with a token node, or None if none"""
        return self._token

    @property
    def has_children(self) -> bool:
        """Return True if there are any families of children of this node"""
        return bool(self._families)

    @property
    def is_empty(self) -> bool:
        """Return True if there is only a single empty family of this node"""
        if not self._families:
            return True
        return len(self._families) == 1 and not bool(self._families[0][1])

    @property
    def num_families(self) -> int:
        """Return the number of families of children of this node"""
        return len(self._families) if self._families is not None else 0

    def enum_children(self) -> Iterator[ProductionTuple]:
        """Enumerate families of children"""
        if self._families:
            for prod, children in self._families:
                yield (prod, children)

    def enum_child_nodes(self) -> Iterator[Optional["Node"]]:
        """Enumerate child nodes of this node, one by one"""
        # Note that for reduced trees, a nonterminal node
        # will only have one family of children, which
        # is the list that will be generated by this function.
        n = self.num_families
        if n == 0 or not self._families:
            # No children
            pass
        elif n == 1:
            # Single family of children: yield from that list
            _, children = self._families[0]
            yield from children
        else:
            # Multiple families of children,
            # meaning that this is an ambiguous, non-reduced node
            assert False, "enum_child_nodes() called on an ambiguous node"

    def reduce_to(self, child_ix: int) -> None:
        """Eliminate all child families except the given one"""
        if self._families and len(self._families) > 1:
            # More than one family to choose from:
            # collapse the list to one survivor
            f = self._families[child_ix]
            self._families = [f]

    def _repr(self, indent: int) -> str:
        if hasattr(self, "score"):
            sc = " [{0}] ".format(self.score)
        else:
            sc = ""
        if self._nonterminal is not None:
            label_rep = str(self._nonterminal) + sc
        else:
            label_rep = str(self._token) + " -> " + str(self._terminal) + sc
        families_rep = ""
        istr = "  " * indent
        if self._families:
            # Show the children in each family

            def child_rep(children: Iterable[Optional["Node"]]) -> str:
                if not children:
                    return ""
                return "\n".join(
                    ch._repr(indent + 1) for ch in children if ch is not None
                )

            if len(self._families) == 1:
                children = self._families[0][1]
                if not children:
                    families_rep = ""
                else:
                    families_rep = "\n" + child_rep(children)
            else:
                families_rep = "\n" + "\n".join(
                    istr + "Option " + str(ix + 1) + ":\n" + child_rep(child)
                    for ix, (_, child) in enumerate(self._families)
                )
        return istr + label_rep + families_rep

    def __repr__(self) -> str:
        """Create a reasonably nice text representation of this node
        and its families of children, if any"""
        return self._repr(0)

    def __str__(self) -> str:
        """Return a string representation of this node"""
        return "<Node: " + str(self._nonterminal or self._token) + ">"


class ParseError(Exception):

    """Exception class for parser errors"""

    def __init__(
        self, txt: str, token_index: Optional[int] = None, info: Any = None
    ) -> None:
        """Store an information object with the exception,
        containing the parser state immediately before the error"""
        super().__init__(txt)
        self._info = info
        self._token_index = token_index

    @property
    def info(self) -> Any:
        """Return the parser state information object"""
        return self._info

    @property
    def token_index(self) -> Optional[int]:
        """Return the 0-based index of the token where the parser ran out of options"""
        return self._token_index

    def __str__(self) -> str:
        """Return a string representation of the parse error"""
        return self.args[0]


class Fast_Parser(BIN_Parser):

    """This class wraps an Earley-Scott parser written in C++,
    which is called via CFFI.

    The class supports the context manager protocol so you can say:

    with Fast_Parser() as fast_p:
       node = fast_p.go(...)

    C++ objects associated with the parser will then be cleaned
    up automatically upon exit of the context, whether by normal
    means or as a consequence of an exception.

    Otherwise, i.e. if not using a context manager, call fast_p.cleanup()
    after using the fast_p parser instance, preferably in a try/finally block.
    """

    # The C++ grammar object (a binary blob)
    _c_grammar: Any = ffi_NULL
    # The C++ grammar timestamp
    _c_grammar_ts: Optional[float] = None

    @classmethod
    def _load_binary_grammar(cls) -> Any:
        """Load the binary grammar file into memory, if required"""
        fname = cls._GRAMMAR_BINARY_FILE
        try:
            ts = os.path.getmtime(fname)
        except os.error:
            raise GrammarError("Binary grammar file {0} not found".format(fname))
        if cls._c_grammar == ffi_NULL or cls._c_grammar_ts != ts:
            # Need to load or reload the grammar
            if cls._c_grammar != ffi_NULL:
                # Delete previous grammar instance, if any
                eparser.deleteGrammar(cls._c_grammar)  # type: ignore
                cls._c_grammar = ffi_NULL
            cls._c_grammar = eparser.newGrammar(fname.encode("utf-8"))  # type: ignore
            cls._c_grammar_ts = ts
            if cls._c_grammar == ffi_NULL:
                raise GrammarError(
                    "Unable to load binary grammar file {0}".format(fname)
                )
        return cls._c_grammar

    def __init__(self, verbose: bool = False, root: Optional[str] = None) -> None:

        # Only one initialization at a time, since we don't want a race
        # condition between threads with regards to reading and parsing the grammar file
        # vs. writing the binary grammar
        with GlobalLock("grammar"):
            # Read and parse the grammar text file
            super().__init__(verbose)
            # Create instances of the C++ Grammar and Parser classes
            c_grammar = self._load_binary_grammar()
            # Create a C++ parser object for the grammar, passing the proxies for the
            # two Python callback functions into it
            self._c_parser: Any = eparser.newParser(  # type: ignore
                c_grammar, eparser.matching_func, eparser.alloc_func  # type: ignore
            )
            # Find the index of the default root nonterminal for this parser instance
            self._root_index = (
                0 if root is None else self.grammar.nonterminals[root].index
            )
            # Maintain a token/terminal matching cache for the duration
            # of this parser instance. Note that this cache will grow with use,
            # as it includes an entry (consisting of one byte per terminal in the
            # grammar, or currently about 5K bytes for Greynir.grammar) for every
            # distinct token that the parser encounters.
            self._matching_cache: Dict[Tuple[Hashable, ...], Any] = dict()

    def __enter__(self):
        """Python context manager protocol"""
        return self

    # noinspection PyUnusedLocal
    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any):
        """Python context manager protocol"""
        self.cleanup()
        return False

    def go(self, tokens: Iterable[Tok], *, root: Optional[str] = None) -> Node:
        """Call the C++ parser module to parse the tokens. The parser's
        default root nonterminal can be overridden by passing its
        name in the root parameter."""

        wrapped_tokens = self._wrap(tokens)  # Inherited from BIN_Parser
        lw = len(wrapped_tokens)
        err: Sequence[int] = cast(Any, ffi).new("unsigned int*")
        result: Optional[Node] = None

        # Use the context manager protocol to guarantee that the parse job
        # handle will be properly deleted even if an exception is thrown

        with ParseJob.make(
            self.grammar, wrapped_tokens, self._terminals, self._matching_cache
        ) as job:

            # Determine the root nonterminal to be used for this parse
            if root is None:
                # Use the parser's default root
                root_index = self._root_index
            else:
                # Override the default root for this parse
                root_index = self.grammar.nonterminals[root].index

            node: Any = eparser.earleyParse(self._c_parser, lw, root_index, job.handle, err)  # type: ignore

            if node == ffi_NULL:
                ix = err[0]  # Token index
                if ix >= 1:
                    # Find the error token index in the original (unwrapped) token list
                    orig_ix = wrapped_tokens[ix].index if ix < lw else ix
                    raise ParseError(
                        "No parse available at token {0} ({1})".format(
                            orig_ix, wrapped_tokens[ix - 1]
                        ),
                        orig_ix - 1,
                    )
                else:
                    # Not a normal parse error, but report it anyway
                    raise ParseError(
                        "No parse available at token {0} ({1} tokens in input)".format(
                            ix, len(wrapped_tokens)
                        ),
                        0,
                    )

            # eparser.dumpForest(node, Fast_Parser._c_grammar) # !!! DEBUG
            # Create a new Python-side node forest corresponding to the C++ one
            result = Node.from_c_node(job, node)

        # Delete the C++ nodes
        eparser.deleteForest(node)  # type: ignore
        assert result is not None
        return result

    def go_no_exc(self, tokens: Iterable[Tok], **kwargs: Any) -> Optional[Node]:
        """Simple version of go() that returns None instead of throwing ParseError"""
        try:
            return self.go(tokens, **kwargs)
        except ParseError:
            return None

    def cleanup(self) -> None:
        """Delete C++ objects. Must call after last use of Fast_Parser
        to avoid memory leaks. The context manager protocol is recommended
        to guarantee cleanup."""
        if self._c_parser != ffi_NULL:
            eparser.deleteParser(self._c_parser)  # type: ignore
        self._c_parser = ffi_NULL
        if Settings.DEBUG:
            eparser.printAllocationReport()  # type: ignore
            print(
                "Matching cache contains {0} entries".format(len(self._matching_cache))
            )

    @classmethod
    def discard_grammar(cls) -> None:
        """Discard the C grammar object instance held as a class attribute"""
        if cls._c_grammar != ffi_NULL:
            eparser.deleteGrammar(cls._c_grammar)  # type: ignore
        cls._c_grammar = ffi_NULL
        cls._c_grammar_ts = None

    @classmethod
    def num_combinations(cls, forest: Node) -> int:
        """Count the number of possible parse tree combinations in the given forest"""

        nc: Dict[Node, int] = dict()
        mul = operator.mul

        def _num_comb(w: Node) -> int:
            if w._token is not None:
                # Empty (epsilon) node or token node
                return 1
            # If a subtree has already been counted, re-use that count
            # (this is less efficient for small trees but much more efficient
            # for extremely ambiguous trees, with combinations in the
            # millions)
            cnt = nc.get(w)
            if cnt is not None:
                assert cnt is not NotImplemented, "Loop in node tree at {0}".format(w)
                return cnt
            nc[w] = NotImplemented  # Special marker for an unassigned cache entry
            comb = 0
            for _, f in w.enum_children():
                comb += reduce(mul, (_num_comb(ch) for ch in f if ch is not None), 1)
            result = nc[w] = comb if comb > 0 else 1
            return result

        return _num_comb(forest)


class ParseForestNavigator:

    """Base class for navigating parse forests. Override the underscored
    methods to perform actions at the corresponding points of navigation."""

    # pylint: disable=assignment-from-none

    def __init__(self, visit_all: bool = False) -> None:
        """If visit_all is False, we only visit each packed node once.
        If True, we visit the entire tree in order."""
        self._visit_all = visit_all

    def visit_epsilon(self, level: int) -> Any:
        """At Epsilon node"""
        return None

    def visit_token(self, level: int, w: Node) -> Any:
        """At token node"""
        return None

    def visit_nonterminal(self, level: int, node: Node) -> Any:
        """At nonterminal node"""
        # Typically returns an accumulation object to collect results
        return None

    def visit_family(
        self, results: Any, level: int, w: Node, ix: int, prod: Production
    ) -> None:
        """At a family of children"""
        return

    def add_result(self, results: Any, ix: int, r: Any) -> None:
        """Append a single result r to the results accumulation object"""
        return

    def process_results(self, results: Any, node: Node) -> Any:
        """Process results after visiting children.
        The results list typically contains tuples (ix, r) where ix is
        the family index and r is the child result"""
        return None

    def force_visit(
        self, w: Optional[Node], visited: Dict[Optional[Node], Any]
    ) -> bool:
        """Override this and return True to visit a node, even if self._visit_all
        is False and the node has been visited before"""
        return False

    def go(self, root_node: Node) -> Any:
        """Navigate the forest from the root node"""

        # Memoization cache dictionary
        visited: Dict[Optional[Node], Any] = dict()

        def _nav_helper(w: Optional[Node], level: int) -> Any:
            """Navigate from w"""
            if (
                not self._visit_all
                and w in visited
                and not self.force_visit(w, visited)
            ):
                # Already seen: return the memoized result
                return visited[w]
            if w is None:
                # Epsilon node
                v = self.visit_epsilon(level)
            elif w._token is not None:
                # Return the score of this terminal option
                v = self.visit_token(level, w)
            else:
                # Init accumulator for child results
                results = self.visit_nonterminal(level, w)
                if results is NotImplemented:
                    # If visit_nonterminal() returns NotImplemented,
                    # don't bother visiting children or processing
                    # results; instead _nav_helper() returns NotImplemented
                    v = results
                else:
                    if w._families:
                        if w.is_interior and not w.is_ambiguous:
                            child_level = level
                        else:
                            child_level = level + 1
                        for ix, (prod, children) in enumerate(w._families):
                            self.visit_family(results, level, w, ix, prod)
                            for ch in children:
                                self.add_result(
                                    results, ix, _nav_helper(ch, child_level)
                                )
                    v = self.process_results(results, w)
            if not self._visit_all:
                # Mark the node as visited and store its result
                visited[w] = v
            return v

        return _nav_helper(root_node, 0)


class ParseForestPrinter(ParseForestNavigator):

    """Print a parse forest to stdout or a file"""

    def __init__(
        self,
        detailed: bool = False,
        file: Optional[IO[str]] = None,
        show_scores: bool = False,
        show_ids: bool = False,
        visit_all: bool = True,
        skip_duplicates: bool = False,
    ) -> None:

        # Normally, we visit all nodes, also those we've seen before
        super().__init__(visit_all=visit_all)
        self._detailed = detailed
        self._file = file
        self._show_scores = show_scores
        self._show_ids = show_ids
        self._skip_duplicates = skip_duplicates
        self._visited: Set[Node] = set()

    def _score(self, w: Node) -> str:
        """Return a string showing the node's score"""
        # !!! To enable this, assignment of the .score attribute
        # !!! needs to be uncommented in reducer.py
        return " [{0}]".format(w.score) if self._show_scores else ""

    def visit_epsilon(self, level: int) -> None:
        """Epsilon (null) node"""
        indent = "  " * level  # Two spaces per indent level
        print(indent + "(empty)", file=self._file)

    def visit_token(self, level: int, w: Node) -> None:
        """Token matching a terminal"""
        indent = "  " * level  # Two spaces per indent level
        h = str(w.token)
        if self._show_ids:
            h += " @ {0:x}".format(id(w))
        print(
            indent + "{0}: {1}{2}".format(w.terminal, h, self._score(w)),
            file=self._file,
        )

    def visit_nonterminal(self, level: int, node: Node) -> Any:
        # Interior nodes are not printed
        # and do not increment the indentation level
        if self._detailed or not node.is_interior:
            nt = cast(Nonterminal, node.nonterminal)
            if not self._detailed:
                if node.is_empty and nt.is_optional:
                    # Skip printing optional nodes that don't contain anything
                    return NotImplemented  # Don't visit child nodes
            h = nt.name
            indent = "  " * level  # Two spaces per indent level
            if self._show_ids:
                h += " @ {0:x}".format(id(node))
            print(indent + h + self._score(node), file=self._file)
            if self._skip_duplicates:
                # We don't want to redisplay entire subtrees that we've
                # seen before
                if node in self._visited:
                    print(indent + "  <Seen before>", file=self._file)
                    return NotImplemented  # Don't visit child nodes
                self._visited.add(node)
        return None  # No results required, but visit children

    def visit_family(
        self, results: Any, level: int, w: Node, ix: int, prod: Production
    ) -> None:
        """Show trees for different options, if ambiguous"""
        if w.is_ambiguous:
            indent = "  " * level  # Two spaces per indent level
            print(indent + "Option " + str(ix + 1) + ":", file=self._file)

    @classmethod
    def print_forest(
        cls,
        root_node: "Node",
        detailed: bool = False,
        file: Optional[IO[str]] = None,
        show_scores: bool = False,
        show_ids: bool = False,
        visit_all: bool = True,
        skip_duplicates: bool = False,
    ):
        """Print a parse forest to the given file, or stdout if none"""
        cls(
            detailed,
            file,
            show_scores,
            show_ids,
            visit_all,
            skip_duplicates=skip_duplicates,
        ).go(root_node)


class ParseForestDumper(ParseForestNavigator):

    """Dump a parse forest into a compact string"""

    # The result is a string consisting of lines separated by newline characters.
    # The format is as follows:
    # (n indicates a nesting level, >= 0)
    # R1 -- start indicator and version number
    # Cn -- the sentence's parse tree score
    # Ln -- the sentence length in tokens
    # Pn -- Epsilon node
    # Tn terminal token -- Token/terminal node
    # Nn nonterminal -- Nonterminal node
    # On index -- Option with index >= 0
    # Q0 -- end indicator (not followed by newline)

    def __init__(self, token_dicts: Optional[List[TokenDict]]) -> None:
        super().__init__(visit_all=True)  # Visit all nodes
        self._result = ["R1"]  # Start indicator and version number
        self._token_dicts = token_dicts

    def visit_epsilon(self, level: int) -> Any:
        # Identify this as an epsilon (null) node
        # !!! Not necessary - removed July 2018 VTh
        # self._result.append("P{0}".format(level))
        return None

    def visit_token(self, level: int, w: Node) -> Any:
        # Identify this as a terminal/token
        ta = ""  # Augmented terminal
        assert w.token is not None
        assert w.terminal is not None
        name = w.terminal.name
        if self._token_dicts is not None:
            # Get the descriptor dict for this token/terminal match
            td = self._token_dicts[w.token.index]
            if "t" in td and "m" in td:
                # Calculate an augmented terminal, including additional info from BÍN
                if td["t"] != name:
                    assert False
                ta = simplify_terminal(td["t"], td["m"][1])  # Fallback category
                # The m(3) field is 'beyging'
                ta = augment_terminal(ta, td["x"].lower(), td["m"][3])
                if name == ta:
                    ta = ""  # No need to repeat augmented terminal if it is identical
                else:
                    ta = " " + ta

        self._result.append("T{0} {1} {2}{3}".format(level, name, w.token.dump, ta))
        return None

    def visit_nonterminal(self, level: int, node: Node) -> Any:
        # Interior nodes are not dumped
        # and do not increment the indentation level
        if not node.is_interior:
            nt = node.nonterminal
            assert nt is not None
            if node.is_empty and nt.is_optional:
                # Skip printing optional nodes that don't contain anything
                return NotImplemented  # Don't visit child nodes
            # Identify this as a nonterminal
            self._result.append("N{0} {1}".format(level, nt.name))
        return None  # No results required, but visit children

    def visit_family(
        self, results: Any, level: int, w: Node, ix: int, prod: Production
    ) -> None:
        if w.is_ambiguous:
            # Identify this as an option
            self._result.append("O{0} {1}".format(level, ix))

    @classmethod
    def dump_forest(
        cls, root_node: Node, token_dicts: Optional[List[TokenDict]] = None
    ) -> str:
        """Return a string with a multi-line text representation of the parse tree"""
        dumper = cls(token_dicts)
        dumper.go(root_node)
        dumper._result.append("Q0")  # End marker
        return "\n".join(dumper._result)


class _FlattenerNode:

    """A node in a flattened parse tree, produced by
    the ParseTreeFlattener class (below)"""

    def __init__(self, p: FlattenerType, score: int) -> None:
        self._p = p
        self._score = score
        self._children: Optional[List[_FlattenerNode]] = None

    def add_child(self, child: "_FlattenerNode") -> None:
        if self._children is None:
            self._children = [child]
        else:
            self._children.append(child)

    @property
    def p(self) -> FlattenerType:
        return self._p

    @property
    def children(self) -> Optional[List["_FlattenerNode"]]:
        return self._children

    @property
    def has_children(self) -> bool:
        return self._children is not None

    @property
    def is_nonterminal(self) -> bool:
        return not isinstance(self._p, tuple)

    @property
    def score(self) -> int:
        return self._score

    def _to_str(self, indent: int) -> str:
        if self._children is not None:
            return "{0}{1}{2}".format(
                " " * indent,
                self._p,
                "".join("\n" + child._to_str(indent + 1) for child in self._children),
            )
        return "{0}{1}".format(" " * indent, self._p)

    def __str__(self) -> str:
        return self._to_str(0)


class ParseForestFlattener(ParseForestNavigator):

    """Create a simpler, flatter version of an already disambiguated parse tree"""

    def __init__(self) -> None:
        super().__init__(visit_all=True)  # Visit all nodes
        self._stack: Optional[List[_FlattenerNode]] = None

    def go(self, root_node: Node) -> None:
        self._stack = None
        super().go(root_node)

    @property
    def root(self) -> Optional[_FlattenerNode]:
        return self._stack[0] if self._stack else None

    def visit_epsilon(self, level: int) -> Any:
        """Epsilon (null) node: not included in a flattened tree"""
        return None

    def visit_token(self, level: int, w: Node) -> Any:
        """Add a terminal/token node to the flattened tree"""
        # assert level > 0
        # assert self._stack
        assert w.terminal is not None
        assert w.token is not None
        node = _FlattenerNode((w.terminal, w.token), w.score)
        assert self._stack is not None
        self._stack = self._stack[0:level]
        self._stack[-1].add_child(node)
        return None

    def visit_nonterminal(self, level: int, node: Node) -> Any:
        """Add a nonterminal node to the flattened tree"""
        # Interior nodes are not dumped
        # and do not increment the indentation level
        if not node.is_interior:
            assert node.nonterminal is not None
            if node.is_empty and node.nonterminal.is_optional:
                # Skip optional nodes that don't contain anything
                return NotImplemented  # Signal: Don't visit child nodes
            # Identify this as a nonterminal
            fnode = _FlattenerNode(node.nonterminal, node.score)
            if level == 0:
                # New root (must be the only one)
                assert self._stack is None
                self._stack = [fnode]
            else:
                # New child of the parent node
                assert self._stack is not None
                self._stack = self._stack[0:level]
                self._stack[-1].add_child(fnode)
                self._stack.append(fnode)
        return None  # No results required, but visit children

    def visit_family(
        self, results: Any, level: int, w: Node, ix: int, prod: Production
    ) -> None:
        """Visit different subtree options within a parse forest"""
        # In this case, the tree should be unambigous
        assert not w.is_ambiguous

    @classmethod
    def flatten(cls, root_node: Node) -> Optional[_FlattenerNode]:
        """Flatten a parse tree"""
        dumper = cls()
        dumper.go(root_node)
        return dumper.root
