"""

    Reynir: Natural language processing for Icelandic

    Python wrapper for C++ Earley/Scott parser

    Copyright (C) 2018 Miðeind ehf.
    Author: Vilhjálmur Þorsteinsson

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
    to call C++ code from CPython and PyPy.

"""

import os
import operator
from threading import Lock
from functools import reduce

from .binparser import BIN_Parser, simplify_terminal, augment_terminal
from .grammar import Terminal, GrammarError
from .settings import Settings
from .glock import GlobalLock

# Import the CFFI wrapper module for the _eparser.*.so library
# which is compiled from eparser.cpp (see eparser_build.py)
from ._eparser import lib as eparser, ffi


_PATH = os.path.dirname(__file__) or "."


class ParseJob:

    """ Dispatch token matching requests coming in from the C++ code """

    # Parse jobs have rotating integer IDs, reaching _MAX_JOBS before cycling back
    _MAX_JOBS = 10000
    _seq = 0
    _jobs = dict()
    _lock = Lock()

    def __init__(self, handle, grammar, tokens, terminals, matching_cache):
        self._handle = handle
        self.tokens = tokens
        self.terminals = terminals
        self.grammar = grammar
        self.c_dict = dict() # Node pointer conversion dictionary
        self.matching_cache = matching_cache # Token/terminal matching buffers

    def matches(self, token, terminal):
        """ Convert the token reference from a 0-based token index
            to the token object itself; convert the terminal from a
            1-based terminal index to a terminal object. """
        return self.tokens[token].matches(self.terminals[terminal])

    def alloc_cache(self, token, size):
        """ Allocate a token/terminal matching cache buffer for the given token """
        key = self.tokens[token].key # Obtain the (hashable) key of the BIN_Token
        try:
            # Do we already have a token/terminal cache match buffer for this key?
            b = self.matching_cache.get(key)
            if b is None:
                # No: create a fresh one (assumed to be initialized to zero)
                b = self.matching_cache[key] = ffi.new("BYTE[]", size)
        except TypeError:
            # b = ffi.NULL
            assert False, "alloc_cache() unable to hash key: {0}".format(repr(key))
        return b

    def reset(self):
        """ Reset the node pointer conversion dictionary """
        self.c_dict = dict()

    @property
    def handle(self):
        return self._handle

    def __enter__(self):
        """ Python context manager protocol """
        return self

    # noinspection PyUnusedLocal
    def __exit__(self, exc_type, exc_value, traceback):
        """ Python context manager protocol """
        self.__class__.delete(self._handle)
        # Return False to re-throw exception from the context, if any
        return False

    @classmethod
    def make(cls, grammar, tokens, terminals, matching_cache):
        """ Create a new parse job with for a given token sequence and set of terminals """
        with cls._lock:
            h = cls._seq
            cls._seq += 1
            if cls._seq >= cls._MAX_JOBS:
                cls._seq = 0
            j = cls._jobs[h] = ParseJob(h, grammar, tokens, terminals, matching_cache)
        return j

    @classmethod
    def delete(cls, handle):
        """ Delete a no-longer-used parse job """
        with cls._lock:
            del cls._jobs[handle]

    @classmethod
    def dispatch(cls, handle, token, terminal):
        """ Dispatch a match request to the correct parse job """
        return cls._jobs[handle].matches(token, terminal)

    @classmethod
    def alloc(cls, handle, token, size):
        """ Dispatch a cache buffer allocation request to the correct parse job """
        return cls._jobs[handle].alloc_cache(token, size)


# CFFI callback functions

@ffi.callback("BOOL(UINT, UINT, UINT)")
def matching_func(handle, token, terminal):
    """ This function is called from the C++ parser to determine
        whether a token matches a terminal. The token is referenced
        by 0-based index, and the terminal by a 1-based index.
        The handle is an arbitrary UINT that was passed to
        earleyParse(). In this case, it is used to identify
        a ParseJob object that dispatches the match query. """
    return ParseJob.dispatch(handle, token, terminal)


@ffi.callback("BYTE*(UINT, UINT, UINT)")
def alloc_func(handle, token, size):
    """ Allocate a token/terminal matching cache buffer, at least size bytes.
        If the callback returns ffi.NULL, the parser will allocate its own buffer.
        The point of this callback is to allow re-using buffers for identical tokens,
        so we avoid making unnecessary matching calls. """
    return ParseJob.alloc(handle, token, size)


class Node:

    """ Shared Packed Parse Forest (SPPF) node representation,
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

    def __init__(self, start, end):
        self._hash = id(self).__hash__()
        self._start = start
        self._end = end
        self._families = None
        self._highest_prio = 0 # Priority of highest-priority child family
        self._nonterminal = None
        self._terminal = None
        self._token = None
        self._completed = True

    @classmethod
    def from_c_node(cls, job, c_node, parent = None, index = 0):
        """ Initialize a Python node from a C++ SPPF node structure """
        if c_node == ffi.NULL:
            return None
        lb = c_node.label
        if lb.nI >= lb.nJ:
            # Empty node (no tokens matched within it):
            # don't bother creating a corresponding Python object,
            # we never use these nodes anyway except as fillers
            # to help in matching children with the parent production
            return None
        node = cls(lb.nI, lb.nJ) # Start token index, end token index
        if lb.iNt < 0:
            # Nonterminal node
            nt = lb.iNt
            node._nonterminal = job.grammar.lookup(nt)
            node._completed = lb.pProd == ffi.NULL
            job.c_dict[c_node] = node # Re-use nonterminal nodes if identical
            fe = c_node.pHead

            # Loop through the families of children of this node
            while fe != ffi.NULL:

                # Save on node count by coalescing interior nodes
                # into the child list of the enclosing completed
                # nonterminal. Nodes can be coalesced while they
                # refer to the same nonterminal, are interior,
                # and not ambiguous.
                ch = [ ]

                def push_pair(p1, p2):
                    """ Push a pair of child nodes onto the child list """

                    def push_child(p):
                        """ Push a single child node onto the child list """
                        if p.label.iNt == nt and p.label.pProd != ffi.NULL:
                            # Interior node for the same nonterminal
                            if p.pHead.pNext == ffi.NULL:
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
                                    ch.extend([ ffi.NULL ] * (p.label.nDot - 2))
                                ch.append(p)
                                ch.append(ffi.NULL) # Placeholder
                        else:
                            # Terminal, epsilon or unrelated nonterminal
                            ch.append(p)

                    if p1 != ffi.NULL and p2 != ffi.NULL:
                        push_child(p1)
                        push_child(p2)
                    elif p2 != ffi.NULL:
                        push_child(p2)
                    else:
                        push_child(p1)

                push_pair(fe.p1, fe.p2)
                node._add_family(job, fe.pProd, ch)

                fe = fe.pNext
        else:
            # Token node: find the corresponding terminal
            tix = parent.pList[index]
            node._terminal = job.grammar.lookup(tix)
            assert isinstance(node._terminal, Terminal) # !!! DEBUG
            node._token = job.tokens[lb.iNt]
        return node

    @classmethod
    def copy(cls, other):
        """ Returns a copy of a Node instance """
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

    def _add_family(self, job, c_prod, c_children):
        """ Add a family of children to this node, in parallel with other families """
        if c_prod == ffi.NULL:
            prod = None
            prio = 0
        else:
            prod = job.grammar.productions_by_ix[c_prod.nId]
            prio = prod.priority
        # Note: lower priority values mean higher priority!
        if self._families and prio > self._highest_prio:
            # Lower priority than a family we already have: don't bother adding it
            return
        # Recreate the pc tuple from the production index
        pc = (prod, [
            # Convert child node from C++ form to Python form
            job.c_dict.get(ch) or Node.from_c_node(job, ch, c_prod, ix)
            for ix, ch in enumerate(c_children)
        ])
        if self._families is None or prio < self._highest_prio:
            # First family of children, or highest priority so far: add as the only family
            self._families = [pc]
        else:
            # Same priority as the families we have already: add this
            self._families.append(pc)
        self._highest_prio = prio

    def transform_children(self, func):
        """ Apply a given function to all children of this node,
            replacing the children with the result. """
        if not self._families:
            return
        for ix, (prod, f) in enumerate(self._families):
            if f:
                f = [func(ch) for ch in f]
                self._families[ix] = (prod, f)

    def transform_child(self, family_ix, child_ix, func):
        """ Replace a single child of this node with the
            result of applying a function to it """
        _, children = self._families[family_ix]
        children[child_ix] = func(children[child_ix])

    @property
    def start(self):
        """ Return the start token index """
        return self._start

    @property
    def end(self):
        """ Return the end token index """
        return self._end

    @property
    def is_span(self):
        """ Returns True if the node spans one or more tokens """
        return self._end > self._start

    @property
    def nonterminal(self):
        """ Return the nonterminal associated with this node """
        return self._nonterminal

    @property
    def is_ambiguous(self):
        """ Return True if this node has more than one family of children """
        return self._families is not None and len(self._families) >= 2

    @property
    def is_interior(self):
        """ Returns True if this is an interior node (partially parsed production) """
        return not self._completed

    @property
    def is_completed(self):
        """ Returns True if this is a node corresponding to a completed nonterminal """
        return self._completed

    @property
    def is_token(self):
        """ Returns True if this is a token node """
        return self._token is not None

    @property
    def terminal(self):
        """ Return the terminal associated with a token node, or None if none """
        return self._terminal

    @property
    def token(self):
        """ Return the terminal associated with a token node, or None if none """
        return self._token

    @property
    def has_children(self):
        """ Return True if there are any families of children of this node """
        return bool(self._families)

    @property
    def is_empty(self):
        """ Return True if there is only a single empty family of this node """
        if not self._families:
            return True
        return len(self._families) == 1 and not bool(self._families[0][1])

    @property
    def num_families(self):
        return len(self._families) if self._families is not None else 0

    def enum_children(self):
        """ Enumerate families of children """
        if self._families:
            for prod, children in self._families:
                yield (prod, children)

    def reduce_to(self, child_ix):
        """ Eliminate all child families except the given one """
        if child_ix != 0 or len(self._families) != 1:
            f = self._families[child_ix] # The survivor
            # Collapse the list to one option
            self._families = [ f ]

    def __hash__(self):
        """ Make this node hashable """
        return self._hash

    def _repr(self, indent):
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
            def child_rep(children):
                if not children:
                    return ""
                return "\n".join(ch._repr(indent + 1) for ch in children if ch is not None)
            if len(self._families) == 1:
                if not self._families[0][1]:
                    families_rep = ""
                else:
                    families_rep = "\n" + child_rep(self._families[0][1])
            else:
                families_rep = "\n" + "\n".join(istr +
                    "Option " + str(ix + 1) + ":\n" + child_rep(child)
                    for ix, (prod, child) in enumerate(self._families))
        return istr + label_rep + families_rep

    def __repr__(self):
        """ Create a reasonably nice text representation of this node
            and its families of children, if any """
        return self._repr(0)

    def __str__(self):
        """ Return a string representation of this node """
        return "<Node: " + str(self._nonterminal or self._token) + ">"


class ParseError(Exception):

    """ Exception class for parser errors """

    def __init__(self, txt, token_index = None, info = None):
        """ Store an information object with the exception,
            containing the parser state immediately before the error """
        Exception.__init__(self, txt)
        self._info = info
        self._token_index = token_index

    @property
    def info(self):
        """ Return the parser state information object """
        return self._info

    @property
    def token_index(self):
        """ Return the 0-based index of the token where the parser ran out of options """
        return self._token_index


class Fast_Parser(BIN_Parser):

    """ This class wraps an Earley-Scott parser written in C++.
        It is called via CFFI.
        The class supports the context manager protocol so you can say:

        with Fast_Parser() as fast_p:
           node = fast_p.go(...)

        C++ objects associated with the parser will then be cleaned
        up automatically upon exit of the context, whether by normal
        means or as a consequence of an exception.

        Otherwise, i.e. if not using a context manager, call fast_p.cleanup()
        after using the fast_p parser instance, preferably in a try/finally block.
    """

    GRAMMAR_BINARY_FILE = os.path.join(_PATH, "Reynir.grammar.bin")
    GRAMMAR_BINARY_FILE_BYTES = GRAMMAR_BINARY_FILE.encode('ascii')

    _c_grammar = None
    _c_grammar_ts = None

    @classmethod
    def _load_binary_grammar(cls):
        """ Load the binary grammar file into memory, if required """
        fname = cls.GRAMMAR_BINARY_FILE_BYTES
        try:
            ts = os.path.getmtime(fname)
        except os.error:
            raise GrammarError("Binary grammar file {0} not found"
                .format(cls.GRAMMAR_BINARY_FILE))
        if cls._c_grammar is None or cls._c_grammar_ts != ts:
            # Need to load or reload the grammar
            if cls._c_grammar is not None:
                # Delete previous grammar instance, if any
                eparser.deleteGrammar(cls._c_grammar)
                cls._c_grammar = None
            cls._c_grammar = eparser.newGrammar(fname)
            cls._c_grammar_ts = ts
            if cls._c_grammar is None or cls._c_grammar == ffi.NULL:
                raise GrammarError("Unable to load binary grammar file " +
                    cls.GRAMMAR_BINARY_FILE)
        return cls._c_grammar

    def __init__(self, verbose = False, root = None):

        # Only one initialization at a time, since we don't want a race
        # condition between threads with regards to reading and parsing the grammar file
        # vs. writing the binary grammar
        with GlobalLock('grammar'):
            super().__init__(verbose) # Reads and parses the grammar text file
            # Create instances of the C++ Grammar and Parser classes
            c_grammar = Fast_Parser._load_binary_grammar()
            # Create a C++ parser object for the grammar
            self._c_parser = eparser.newParser(c_grammar, matching_func, alloc_func)
            # Find the index of the root nonterminal for this parser instance
            self._root_index = 0 if root is None else self.grammar.nonterminals[root].index
            # Maintain a token/terminal matching cache for the duration
            # of this parser instance. Note that this cache will grow with use,
            # as it includes an entry (about 2K bytes) for every distinct token that the parser
            # encounters.
            self._matching_cache = dict()

    def __enter__(self):
        """ Python context manager protocol """
        return self

    # noinspection PyUnusedLocal
    def __exit__(self, exc_type, exc_value, traceback):
        """ Python context manager protocol """
        self.cleanup()
        return False

    def go(self, tokens):
        """ Call the C++ parser module to parse the tokens """

        wrapped_tokens = self._wrap(tokens)  # Inherited from BIN_Parser
        lw = len(wrapped_tokens)
        err = ffi.new("unsigned int*")
        result = None

        # Use the context manager protocol to guarantee that the parse job
        # handle will be properly deleted even if an exception is thrown

        with ParseJob.make(self.grammar, wrapped_tokens, self._terminals, self._matching_cache) as job:

            node = eparser.earleyParse(self._c_parser, lw, self._root_index, job.handle, err)

            if node == ffi.NULL:
                ix = err[0]  # Token index
                if ix >= 1:
                    # Find the error token index in the original (unwrapped) token list
                    orig_ix = wrapped_tokens[ix].index if ix < lw else ix
                    raise ParseError("No parse available at token {0} ({1})"
                        .format(orig_ix, wrapped_tokens[ix-1]), orig_ix - 1)
                else:
                    # Not a normal parse error, but report it anyway
                    raise ParseError("No parse available at token {0} ({1} tokens in input)"
                        .format(ix, len(wrapped_tokens)), 0)

            # eparser.dumpForest(node, Fast_Parser._c_grammar) # !!! DEBUG
            # Create a new Python-side node forest corresponding to the C++ one
            result = Node.from_c_node(job, node)

        # Delete the C++ nodes
        eparser.deleteForest(node)
        return result

    def go_no_exc(self, tokens):
        """ Simple version of go() that returns None instead of throwing ParseError """
        try:
            return self.go(tokens)
        except ParseError:
            return None

    def cleanup(self):
        """ Delete C++ objects. Must call after last use of Fast_Parser
            to avoid memory leaks. The context manager protocol is recommended
            to guarantee cleanup. """
        eparser.deleteParser(self._c_parser)
        self._c_parser = None
        if Settings.DEBUG:
            eparser.printAllocationReport()

    @classmethod
    def discard_grammar(cls):
        eparser.deleteGrammar(cls._c_grammar)
        cls._c_grammar = None
        cls._c_grammar_ts = None

    @classmethod
    def num_combinations(cls, forest):
        """ Count the number of possible parse tree combinations in the given forest """

        nc = dict()

        def _num_comb(w):
            if w is None or w._token is not None:
                # Empty (epsilon) node or token node
                return 1
            # If a subtree has already been counted, re-use that count
            # (this is less efficient for small trees but much more efficient
            # for extremely ambiguous trees, with combinations in the
            # millions)
            cnt = nc.get(w)
            if cnt is not None:
                assert cnt is not NotImplemented, "Loop in node tree at {0}".format(str(w))
                return cnt
            nc[w] = NotImplemented  # Special marker for an unassigned cache entry
            comb = 0
            for _, f in w.enum_children():
                comb += reduce(operator.mul, (_num_comb(ch) for ch in f), 1)
            result = nc[w] = comb if comb > 0 else 1
            return result

        return _num_comb(forest)


class ParseForestNavigator:

    """ Base class for navigating parse forests. Override the underscored
        methods to perform actions at the corresponding points of navigation. """

    def __init__(self, visit_all = False):
        """ If visit_all is False, we only visit each packed node once.
            If True, we visit the entire tree in order. """
        self._visit_all = visit_all

    def _visit_epsilon(self, level):
        """ At Epsilon node """
        return None

    def _visit_token(self, level, node):
        """ At token node """
        return None

    def _visit_nonterminal(self, level, node):
        """ At nonterminal node """
        # Return object to collect results
        return None

    def _visit_family(self, results, level, node, ix, prod):
        """ At a family of children """
        return

    def _add_result(self, results, ix, r):
        """ Append a single result object r to the result object """
        return

    def _process_results(self, results, node):
        """ Process results after visiting children.
            The results list typically contains tuples (ix, r) where ix is
            the family index and r is the child result """
        return None

    def _force_visit(self, w, visited):
        """ Override this and return True to visit a node, even if self._visit_all
            is False and the node has been visited before """
        return False

    def go(self, root_node):
        """ Navigate the forest from the root node """

        visited = dict()

        def _nav_helper(w, index, level):
            """ Navigate from w """
            if not self._visit_all and w in visited and not self._force_visit(w, visited):
                # Already seen: return the previously calculated result
                return visited[w]
            if w is None:
                # Epsilon node
                v = self._visit_epsilon(level)
            elif w._token is not None:
                # Return the score of this terminal option
                v = self._visit_token(level, w)
            else:
                # Init container for child results
                results = self._visit_nonterminal(level, w)
                if results is NotImplemented:
                    # If _visit_nonterminal() returns NotImplemented,
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
                            # assert len(children) > 0
                            self._visit_family(results, level, w, ix, prod)
                            if w._completed:
                                # Completed nonterminal: restart children index
                                child_ix = -1
                            else:
                                child_ix = index
                            if len(children) > 1:
                                child_ix -= len(children) - 1
                            for ch in children:
                                self._add_result(results, ix, _nav_helper(ch, child_ix, child_level))
                                child_ix += 1
                    v = self._process_results(results, w)
            if not self._visit_all:
                # Mark the node as visited and store its result
                visited[w] = v
            return v

        return _nav_helper(root_node, 0, 0)


class ParseForestPrinter(ParseForestNavigator):

    """ Print a parse forest to stdout or a file """

    def __init__(self, detailed=False, file=None,
        show_scores=False, show_ids=False, visit_all=True,
        skip_duplicates=False):

        # Normally, we visit all nodes, also those we've seen before
        super().__init__(visit_all = visit_all)
        self._detailed = detailed
        self._file = file
        self._show_scores = show_scores
        self._show_ids = show_ids
        self._skip_duplicates = skip_duplicates
        self._visited = set()

    def _score(self, w):
        """ Return a string showing the node's score """
        # !!! To enable this, assignment of the .score attribute
        # !!! needs to be uncommented in reducer.py
        return " [{0}]".format(w.score) if self._show_scores else ""

    def _visit_epsilon(self, level):
        """ Epsilon (null) node """
        indent = "  " * level # Two spaces per indent level
        print(indent + "(empty)", file = self._file)
        return None

    def _visit_token(self, level, w):
        """ Token matching a terminal """
        indent = "  " * level # Two spaces per indent level
        h = str(w.token)
        if self._show_ids:
            h += " @ {0:x}".format(id(w))
        print(indent + "{0}: {1}{2}".format(w.terminal, h, self._score(w)),
            file = self._file)
        return None

    def _visit_nonterminal(self, level, w):
        # Interior nodes are not printed
        # and do not increment the indentation level
        if self._detailed or not w.is_interior:
            if not self._detailed:
                if w.is_empty and w.nonterminal.is_optional:
                    # Skip printing optional nodes that don't contain anything
                    return NotImplemented  # Don't visit child nodes
            h = w.nonterminal.name
            indent = "  " * level  # Two spaces per indent level
            if self._show_ids:
                h += " @ {0:x}".format(id(w))
            print(indent + h + self._score(w), file = self._file)
            if self._skip_duplicates:
                # We don't want to redisplay entire subtrees that we've
                # seen before
                if w in self._visited:
                    print(indent + "  <Seen before>", file = self._file)
                    return NotImplemented  # Don't visit child nodes
                self._visited.add(w)
        return None  # No results required, but visit children

    def _visit_family(self, results, level, w, ix, prod):
        """ Show trees for different options, if ambiguous """
        if w.is_ambiguous:
            indent = "  " * level  # Two spaces per indent level
            print(indent + "Option " + str(ix + 1) + ":", file=self._file)

    @classmethod
    def print_forest(cls, root_node, detailed=False, file=None,
        show_scores=False, show_ids=False, visit_all=True,
        skip_duplicates=False):
        """ Print a parse forest to the given file, or stdout if none """
        cls(detailed, file, show_scores, show_ids, visit_all,
            skip_duplicates=skip_duplicates).go(root_node)


class ParseForestDumper(ParseForestNavigator):

    """ Dump a parse forest into a compact string """

    # The result is a string consisting of lines separated by newline characters.
    # The format is as follows:
    # (n indicates a nesting level, >= 0)
    # R1 -- start indicator and version number
    # Pn -- Epsilon node
    # Tn terminal token -- Token/terminal node
    # Nn nonterminal -- Nonterminal node
    # On index -- Option with index >= 0
    # Q0 -- end indicator (not followed by newline)

    VERSION = "Reynir/1.00"

    def __init__(self, token_dicts):
        super().__init__(visit_all=True)  # Visit all nodes
        self._result = ["R1"]  # Start indicator and version number
        self._token_dicts = token_dicts

    def _visit_epsilon(self, level):
        # Identify this as an epsilon (null) node
        # !!! Not necessary - removed July 2018 VTh
        # self._result.append("P{0}".format(level))
        return None

    def _visit_token(self, level, w):
        # Identify this as a terminal/token
        ta = ""  # Augmented terminal
        if self._token_dicts is not None:
            # Get the descriptor dict for this token/terminal match
            td = self._token_dicts[w.token.index]
            if "t" in td and "m" in td:
                # Calculate an augmented terminal, including additional info from BÍN
                if td["t"] != w.terminal.name:
                    assert False
                ta = simplify_terminal(td["t"], td["m"][1])  # Fallback category
                ta = augment_terminal(ta, td["x"].lower(), td["m"][3])  # The m(3) field is 'beyging'
                if w.terminal.name == ta:
                    ta = ""  # No need to repeat augmented terminal if it is identical
                else:
                    ta = " " + ta

        self._result.append("T{0} {1} {2}{3}".format(level, w.terminal.name, w.token.dump, ta))
        return None

    def _visit_nonterminal(self, level, w):
        # Interior nodes are not dumped
        # and do not increment the indentation level
        if not w.is_interior:
            if w.is_empty and w.nonterminal.is_optional:
                # Skip printing optional nodes that don't contain anything
                return NotImplemented  # Don't visit child nodes
            # Identify this as a nonterminal
            self._result.append("N{0} {1}".format(level, w.nonterminal.name))
        return None  # No results required, but visit children

    def _visit_family(self, results, level, w, ix, prod):
        if w.is_ambiguous:
            # Identify this as an option
            self._result.append("O{0} {1}".format(level, ix))

    @classmethod
    def dump_forest(cls, root_node, token_dicts=None):
        """ Return a string with a multi-line text representation of the parse tree """
        dumper = cls(token_dicts)
        dumper.go(root_node)
        dumper._result.append("Q0")  # End marker
        return "\n".join(dumper._result)


class ParseForestFlattener(ParseForestNavigator):

    """ Create a simpler, flatter version of an already disambiguated parse tree """

    class Node:

        def __init__(self, p):
            self._p = p
            self._children = None

        def add_child(self, child):
            if self._children is None:
                self._children = [ child ]
            else:
                self._children.append(child)

        @property
        def p(self):
            return self._p

        @property
        def children(self):
            return self._children

        @property
        def has_children(self):
            return self._children is not None

        @property
        def is_nonterminal(self):
            return not isinstance(self._p, tuple)

        def _to_str(self, indent):
            if self.has_children:
                return "{0}{1}{2}".format(" " * indent,
                    self._p,
                    "".join("\n" + child._to_str(indent+1) for child in self._children))
            return "{0}{1}".format(" " * indent, self._p)

        def __str__(self):
            return self._to_str(0)

    def __init__(self):
        super().__init__(visit_all = True) # Visit all nodes
        self._stack = None

    def go(self, root_node):
        self._stack = None
        super().go(root_node)

    @property
    def root(self):
        return self._stack[0] if self._stack else None

    def _visit_epsilon(self, level):
        """ Epsilon (null) node: not included in a flattened tree """
        return None

    def _visit_token(self, level, w):
        """ Add a terminal/token node to the flattened tree """
        # assert level > 0
        # assert self._stack
        node = ParseForestFlattener.Node((w.terminal, w.token))
        self._stack = self._stack[0:level]
        self._stack[-1].add_child(node)
        return None

    def _visit_nonterminal(self, level, w):
        """ Add a nonterminal node to the flattened tree """
        # Interior nodes are not dumped
        # and do not increment the indentation level
        if not w.is_interior:
            if w.is_empty and w.nonterminal.is_optional:
                # Skip optional nodes that don't contain anything
                return NotImplemented # Signal: Don't visit child nodes
            # Identify this as a nonterminal
            node = ParseForestFlattener.Node(w.nonterminal)
            if level == 0:
                # New root (must be the only one)
                assert self._stack is None
                self._stack = [ node ]
            else:
                # New child of the parent node
                self._stack = self._stack[0:level]
                self._stack[-1].add_child(node)
                self._stack.append(node)
        return None # No results required, but visit children

    def _visit_family(self, results, level, w, ix, prod):
        """ Visit different subtree options within a parse forest """
        # In this case, the tree should be unambigous
        assert not w.is_ambiguous

    @classmethod
    def flatten(cls, root_node):
        """ Flatten a parse tree """
        dumper = cls()
        dumper.go(root_node)
        return dumper.root

