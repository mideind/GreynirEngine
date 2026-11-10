"""

    test_earley_core.py

    Tests for the C++ Earley-Scott parser core (eparser.cpp), independent
    of the Icelandic grammar and of BÍN.

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

    The tests feed small synthetic grammars, written directly in the binary
    grammar format, to the core, together with token sequences where each
    token simply is a terminal index. The resulting shared packed parse
    forests (SPPFs) are then inspected directly through CFFI and checked
    against known results:

    * the number of parse trees in the forest, compared with closed-form
      results (Catalan numbers) and with an independent, straightforward
      dynamic programming tree counter written in Python, over a set of
      pseudo-random grammars;
    * correct handling of nullable nonterminals (the H set of the
      Scott algorithm), of long inputs and of columns with many states;
    * the error position reported for inputs that don't parse;
    * determinism: repeated parses give identical forests, including the
      order of the families of children of each node (which determines
      the outcome of tie-breaks in the reducer);
    * consistency of the internal allocation counters.

    These tests guard the data structures on the hot path of the core
    (the state lists of the columns, the set of states for detecting
    duplicates, the prediction tables, the lookahead filter, the H set
    index, the node dictionary, the forest storage and the batched
    allocation counters).

"""

from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

import random
import re
import struct
from contextlib import contextmanager
from functools import lru_cache

import pytest

from reynir._eparser import lib as eparser, ffi  # type: ignore
from reynir.fastparser import ParseJob

SIGNATURE = b"Greynir00.00.01\n"

# A grammar is a list of nonterminals, each of which is a list of
# productions, each of which is a list of items: a positive item is
# a terminal index (1-based), and a negative item -1-n refers to the
# nonterminal with index n (0-based). The root is nonterminal 0.
Production = List[int]
GrammarSpec = List[List[Production]]


def nt(n: int) -> int:
    """Return the production item that refers to nonterminal number n"""
    return -1 - n


def num_terminals(spec: GrammarSpec) -> int:
    return max((item for prods in spec for p in prods for item in p), default=0)


def binary_grammar(spec: GrammarSpec) -> bytes:
    """Encode a grammar in the binary format read by newGrammar()
    (see Grammar._write_binary() in grammar.py)"""
    buf = [SIGNATURE, struct.pack("<IIi", num_terminals(spec), len(spec), -1)]
    prod_id = 0
    for prods in spec:
        buf.append(struct.pack("<I", len(prods)))
        for p in prods:
            buf.append(struct.pack("<III", prod_id, 0, len(p)))
            buf.append(struct.pack("<{0}i".format(len(p)), *p))
            prod_id += 1
    return b"".join(buf)


class Tok:

    """A minimal stand-in for BIN_Token: a token that
    matches exactly one terminal"""

    def __init__(self, terminal: int) -> None:
        self.terminal = terminal

    @property
    def key(self) -> Tuple[int]:
        return (self.terminal,)

    def matches(self, terminal: int) -> bool:
        return self.terminal == terminal


# A canonical, order-preserving description of a forest: for each node,
# numbered in order of first visit, its label and its families of children
ForestDump = List[Tuple[Any, ...]]


class Forest:

    """Wrapper for a parse forest returned from the C++ core"""

    def __init__(self, c_node: Any) -> None:
        self._root = c_node

    def _postorder(self) -> Iterator[Any]:
        """Generate the nodes of the forest, children before parents,
        each node once. Iterative, since forests can be deep."""
        seen = set()
        stack: List[Tuple[Any, bool]] = [(self._root, False)]
        while stack:
            node, expanded = stack.pop()
            if expanded:
                yield node
                continue
            if node == ffi.NULL or node in seen:
                continue
            seen.add(node)
            stack.append((node, True))
            fe = node.pHead
            while fe != ffi.NULL:
                stack.append((fe.p2, False))
                stack.append((fe.p1, False))
                fe = fe.pNext

    @property
    def num_trees(self) -> int:
        """The number of distinct parse trees in the forest"""
        count: Dict[Any, int] = {ffi.NULL: 1}
        for node in self._postorder():
            fe = node.pHead
            if node.label.iNt >= 0 or fe == ffi.NULL:
                # Token node
                count[node] = 1
                continue
            n = 0
            while fe != ffi.NULL:
                n += count[fe.p1] * count[fe.p2]
                fe = fe.pNext
            count[node] = n
        return count[self._root]

    def dump(self) -> ForestDump:
        """Return a canonical description of the forest, sensitive
        to the order of the families of children of each node"""
        ids: Dict[Any, int] = {ffi.NULL: 0}
        result: ForestDump = []
        for node in self._postorder():
            ids[node] = len(ids)
            lb = node.label
            families = []
            fe = node.pHead
            while fe != ffi.NULL:
                families.append((fe.pProd.nId, ids[fe.p1], ids[fe.p2]))
                fe = fe.pNext
            result.append(
                (
                    lb.iNt,
                    lb.nDot,
                    -1 if lb.pProd == ffi.NULL else lb.pProd.nId,
                    lb.nI,
                    lb.nJ,
                    tuple(families),
                )
            )
        return result

    def content(self) -> Any:
        """Return a description of the content of the forest that does
        not depend on the order of the families of children of each node,
        nor on anything else than the nodes that are in the forest"""

        def label(node: Any) -> Any:
            if node == ffi.NULL:
                return None
            lb = node.label
            return (
                lb.iNt,
                lb.nDot,
                -1 if lb.pProd == ffi.NULL else lb.pProd.nId,
                lb.nI,
                lb.nJ,
            )

        result = set()
        for node in self._postorder():
            families = set()
            fe = node.pHead
            while fe != ffi.NULL:
                families.add((fe.pProd.nId, label(fe.p1), label(fe.p2)))
                fe = fe.pNext
            result.add((label(node), frozenset(families)))
        return (label(self._root), frozenset(result))

    @property
    def span(self) -> Tuple[int, int]:
        return (self._root.label.nI, self._root.label.nJ)


class Core:

    """A C++ parser instance for a synthetic grammar"""

    def __init__(self, spec: GrammarSpec, path: Any) -> None:
        path.write_bytes(binary_grammar(spec))
        self._nterm = num_terminals(spec)
        self._grammar = eparser.newGrammar(str(path).encode("utf-8"))
        assert self._grammar != ffi.NULL
        self._parser = eparser.newParser(
            self._grammar, eparser.matching_func, eparser.alloc_func
        )
        assert self._parser != ffi.NULL
        self._terminals: Any = {i: i for i in range(1, self._nterm + 1)}
        self._cache: Dict[Any, Any] = dict()
        self._forests: List[Any] = []
        self.error_token = 0

    def parse(self, tokens: Sequence[int]) -> Optional[Forest]:
        """Parse a sequence of terminal indices. Returns None if there
        is no parse, in which case self.error_token is set."""
        toks: Any = [Tok(t) for t in tokens]
        err = ffi.new("unsigned int*")
        grammar: Any = None  # Only needed for conversion to Python nodes
        with ParseJob.make(grammar, toks, self._terminals, self._cache) as job:
            node = eparser.earleyParse(self._parser, len(toks), 0, job.handle, err)
        self.error_token = err[0]
        if node == ffi.NULL:
            return None
        self._forests.append(node)
        return Forest(node)

    def set_lookahead(self, lookahead: bool) -> None:
        """Turn the lookahead filter of the parser on or off"""
        eparser.setLookahead(self._parser, 1 if lookahead else 0)

    def num_trees(self, tokens: Sequence[int]) -> int:
        """Return the number of parse trees for the tokens, or 0 if no parse"""
        forest = self.parse(tokens)
        if forest is None:
            return 0
        assert forest.span == (0, len(tokens))
        return forest.num_trees

    def close(self) -> None:
        """Release the forests, the parser and the grammar (idempotent)"""
        for node in self._forests:
            eparser.deleteForest(node)
        self._forests = []
        if self._parser != ffi.NULL:
            eparser.deleteParser(self._parser)
            self._parser = ffi.NULL
        if self._grammar != ffi.NULL:
            eparser.deleteGrammar(self._grammar)
            self._grammar = ffi.NULL


@pytest.fixture
def core(tmp_path):
    """Fixture yielding a factory of Core instances that
    are properly cleaned up after the test"""
    cores: List[Core] = []

    def make(spec: GrammarSpec) -> Core:
        c = Core(spec, tmp_path / "grammar{0}.bin".format(len(cores)))
        cores.append(c)
        return c

    yield make
    for c in cores:
        c.close()


def count_trees(spec: GrammarSpec, tokens: Sequence[int]) -> int:
    """Reference implementation: count the parse trees of a token
    sequence by straightforward dynamic programming over spans.
    Only valid for grammars without epsilon productions and
    without cyclic unit productions."""
    toks = tuple(tokens)

    @lru_cache(maxsize=None)
    def derive(item: int, i: int, j: int) -> int:
        """Number of ways in which the item derives tokens i..j-1"""
        if item > 0:
            return 1 if j == i + 1 and toks[i] == item else 0
        return sum(seq(tuple(p), i, j) for p in spec[-1 - item])

    @lru_cache(maxsize=None)
    def seq(items: Tuple[int, ...], i: int, j: int) -> int:
        """Number of ways in which the sequence of items derives tokens i..j-1"""
        if not items:
            return 1 if i == j else 0
        if len(items) == 1:
            return derive(items[0], i, j)
        # Every item derives at least one token
        return sum(
            derive(items[0], i, k) * seq(items[1:], k, j)
            for k in range(i + 1, j - len(items) + 2)
            if derive(items[0], i, k)
        )

    return derive(nt(0), 0, len(toks)) if toks else 0


def catalan(n: int) -> int:
    c = 1
    for i in range(n):
        c = c * 2 * (2 * i + 1) // (i + 2)
    return c


def test_trivial(core) -> None:
    # S -> a
    c = core([[[1]]])
    forest = c.parse([1])
    assert forest is not None
    assert forest.num_trees == 1
    assert forest.span == (0, 1)
    assert c.parse([1, 1]) is None


def test_catalan(core) -> None:
    """S -> S S | a has Catalan(n-1) parse trees for n tokens"""
    spec = [[[nt(0), nt(0)], [1]]]
    c = core(spec)
    for n in range(1, 15):
        assert c.num_trees([1] * n) == catalan(n - 1)


def test_ambiguous_expressions(core) -> None:
    """E -> E + E | E * E | ( E ) | a, without precedence"""
    PLUS, TIMES, LPAR, RPAR, A = 1, 2, 3, 4, 5
    spec = [[[nt(0), PLUS, nt(0)], [nt(0), TIMES, nt(0)], [LPAR, nt(0), RPAR], [A]]]
    c = core(spec)
    for n in range(1, 10):
        # n operands with n-1 operators: Catalan(n-1) trees
        tokens = [A]
        for i in range(n - 1):
            tokens += [PLUS if i % 2 else TIMES, A]
        assert c.num_trees(tokens) == catalan(n - 1)
    # a + ( a * a + a ) * a: 2 trees inside the parentheses, 2 outside
    tokens = [A, PLUS, LPAR, A, TIMES, A, PLUS, A, RPAR, TIMES, A]
    assert c.num_trees(tokens) == 4
    assert c.num_trees(tokens) == count_trees(spec, tokens)
    # Unbalanced parentheses
    assert c.parse([LPAR, A, PLUS, A]) is None
    assert c.parse([A, RPAR]) is None


def test_unambiguous_expressions(core) -> None:
    """A classic layered expression grammar: exactly one tree"""
    PLUS, TIMES, LPAR, RPAR, A = 1, 2, 3, 4, 5
    E, T, F = 0, 1, 2
    spec = [
        [[nt(E), PLUS, nt(T)], [nt(T)]],
        [[nt(T), TIMES, nt(F)], [nt(F)]],
        [[LPAR, nt(E), RPAR], [A]],
    ]
    c = core(spec)
    tokens = [A, PLUS, LPAR, A, TIMES, A, PLUS, A, RPAR, TIMES, A]
    assert c.num_trees(tokens) == 1
    assert c.num_trees([LPAR] * 40 + [A] + [RPAR] * 40) == 1
    assert c.parse([A, PLUS]) is None
    assert c.parse([PLUS, A]) is None


def test_nullable(core) -> None:
    """Nullable nonterminals, which exercise the H set of the parser"""
    A, B, C = 1, 2, 3
    # S -> X Y Z; X -> a | 0; Y -> b | 0; Z -> c | 0
    spec = [[[nt(1), nt(2), nt(3)]], [[A], []], [[B], []], [[C], []]]
    c = core(spec)
    for tokens in ([A], [B], [C], [A, B], [A, C], [B, C], [A, B, C]):
        assert c.num_trees(tokens) == 1, tokens
    for tokens in ([B, A], [C, A], [C, B], [A, A], [A, B, C, A], [A, C, B]):
        assert c.parse(tokens) is None, tokens


def test_nullable_ambiguity(core) -> None:
    """Different ways of deriving nothing must yield different trees"""
    A, B, C = 1, 2, 3
    # S -> a M b; M -> 0 | c | N; N -> 0 | c c
    spec = [[[A, nt(1), B]], [[], [C], [nt(2)]], [[], [C, C]]]
    c = core(spec)
    assert c.num_trees([A, B]) == 2  # M -> 0 and M -> N -> 0
    assert c.num_trees([A, C, B]) == 1
    assert c.num_trees([A, C, C, B]) == 1
    assert c.parse([A, C, C, C, B]) is None


def test_nullable_chains(core) -> None:
    """Many nullable nonterminals completing in the same column, both
    before and after the nonterminals that refer to them are predicted"""
    N = 60
    T = N + 1  # A terminal that ends the sentence
    # S -> X1 X2 ... XN t; Xi -> xi | Yi; Yi -> 0
    spec: GrammarSpec = [[[nt(i) for i in range(1, N + 1)] + [T]]]
    for i in range(1, N + 1):
        spec.append([[i], [nt(N + i)]])
    for i in range(1, N + 1):
        spec.append([[]])
    c = core(spec)
    assert c.num_trees([T]) == 1
    assert c.num_trees(list(range(1, N + 1)) + [T]) == 1
    assert c.num_trees(list(range(1, N + 1, 3)) + [T]) == 1
    assert c.num_trees([N, T]) == 1
    assert c.parse([2, 1, T]) is None
    assert c.parse(list(range(1, N + 1))) is None


def test_nullable_tail(core) -> None:
    """A nullable suffix, and a nullable nonterminal used repeatedly"""
    A, B = 1, 2
    # S -> a O O O; O -> b | 0
    spec = [[[A, nt(1), nt(1), nt(1)]], [[B], []]]
    c = core(spec)
    assert c.num_trees([A]) == 1
    # One b can be derived by any one of the three O's, etc.
    assert c.num_trees([A, B]) == 3
    assert c.num_trees([A, B, B]) == 3
    assert c.num_trees([A, B, B, B]) == 1
    assert c.parse([A, B, B, B, B]) is None


def test_error_token(core) -> None:
    """The core reports where the parse fails: the index of the first
    Earley column that ends up empty, i.e. the number of tokens that
    could be consumed plus one - or the number of tokens, if all of them
    were consumed without arriving at a complete sentence"""
    A, B, C = 1, 2, 3
    # S -> a L c; L -> L b | b
    spec = [[[A, nt(1), C]], [[nt(1), B], [B]]]
    c = core(spec)
    assert c.num_trees([A, B, B, B, C]) == 1
    for tokens, err in (
        # No state survives in the first column: reported as index 0
        ([B], 0),
        ([A, C], 2),
        ([A, B, A, C], 3),
        ([A, B, B, B, B, A], 6),
        # Input ends prematurely: the error is at the end
        ([A, B, B], 3),
        # Extra input after a complete sentence
        ([A, B, C, C], 4),
    ):
        assert c.parse(tokens) is None
        assert c.error_token == err, tokens
    # S -> a b c | a b L: here, a state can be stopped by a terminal
    # that does not match the next token
    spec = [[[A, B, C], [A, B, nt(1)]], [[nt(1), B], [B]]]
    c = core(spec)
    assert c.num_trees([A, B, C]) == 1
    assert c.num_trees([A, B, B]) == 1
    for lookahead in (True, False):
        # The lookahead filter does not change where errors are reported
        c.set_lookahead(lookahead)
        for tokens, err in (
            ([A, C], 1),
            ([A, A, B], 1),
            ([A], 1),
            ([A, B], 2),
            ([A, B, A], 3),
            ([A, B, C, A], 4),
            ([A, B, B, C], 4),
        ):
            assert c.parse(tokens) is None
            assert c.error_token == err, (lookahead, tokens)


@pytest.mark.parametrize("left", [True, False])
def test_long_input(core, left: bool) -> None:
    """A long input, i.e. a parse with many Earley columns,
    using a left recursive or a right recursive list grammar"""
    A, SEP = 1, 2
    # L -> L , a | a   or   L -> a , L | a
    spec = [[[nt(0), SEP, A] if left else [A, SEP, nt(0)], [A]]]
    c = core(spec)
    n = 1500
    tokens = [A] + [SEP, A] * (n - 1)
    assert c.num_trees(tokens) == 1
    assert c.parse(tokens + [SEP]) is None
    assert c.error_token == len(tokens) + 1
    # Insert an extra element after the separator at index 999,
    # so that the two elements at indices 1000 and 1001 are adjacent
    assert c.parse(tokens[:1000] + [A] + tokens[1000:]) is None
    assert c.error_token == 1002


def test_many_states(core) -> None:
    """Columns with thousands of states, i.e. several times more than
    there are hash bins in a column, where a large part of the states
    is completed, and where all nonterminals are nullable"""
    N = 700
    A, B = 1, 2
    # S -> X1 | X2 | ... | XN
    # Xi -> a Yi | Zi a | 0;  Yi -> b | 0;  Zi -> b | 0
    spec: GrammarSpec = [[[nt(i)] for i in range(1, N + 1)]]
    for i in range(1, N + 1):
        spec.append([[A, nt(N + i)], [nt(2 * N + i), A], []])
    for i in range(1, 2 * N + 1):
        spec.append([[B], []])
    c = core(spec)
    forest = c.parse([A])
    assert forest is not None
    # For each Xi: a followed by an empty Yi, or an empty Zi followed by a
    assert forest.num_trees == 2 * N
    assert c.num_trees([A, B]) == N
    assert c.num_trees([B, A]) == N
    assert c.parse([B]) is None
    assert c.parse([A, B, B]) is None


def test_many_advanced_states(core) -> None:
    """A column with thousands of states that are not predictions, and
    thus go through the detection of duplicate states: enough of them
    to make the table of states grow several times"""
    N = 5000
    A = 1
    # S -> X1 | X2 | ... | XN;  Xi -> a
    spec: GrammarSpec = [[[nt(i)] for i in range(1, N + 1)]]
    for i in range(1, N + 1):
        spec.append([[A]])
    c = core(spec)
    assert c.num_trees([A]) == N
    assert c.parse([A, A]) is None
    assert c.error_token == 2
    # The same, where each Xi has two (identical) productions: Xi -> a | a
    # Both complete Xi, and each completion advances the state S -> . Xi
    # to the same state S -> Xi . with the same tree node; the second
    # one is a duplicate, which must be detected and dropped.
    for i in range(1, N + 1):
        spec[i] = [[A], [A]]
    c = core(spec)
    # Each Xi has two derivations
    assert c.num_trees([A]) == 2 * N


def test_recursive_root(core) -> None:
    """The root nonterminal occurs within its own productions, so it is
    at the dot of states in the first column. Its productions are in that
    column from the start and must not be predicted again."""
    A, B = 1, 2
    # S -> S a | a
    c = core([[[nt(0), A], [A]]])
    for n in range(1, 8):
        assert c.num_trees([A] * n) == 1
    # S -> a S | b
    c = core([[[A, nt(0)], [B]]])
    for n in range(0, 8):
        assert c.num_trees([A] * n + [B]) == 1
    assert c.parse([A, A]) is None
    # S -> S S | a | b S
    c = core([[[nt(0), nt(0)], [A], [B, nt(0)]]])
    spec: GrammarSpec = [[[nt(0), nt(0)], [A], [B, nt(0)]]]
    for tokens in ([A], [B, A], [A, A, A], [B, A, A], [A, B, A, A], [B, B, A, A, A]):
        assert c.num_trees(tokens) == count_trees(spec, tokens), tokens


def random_grammar(rnd: random.Random) -> GrammarSpec:
    """Create a pseudo-random grammar without epsilon productions
    and without cyclic unit productions"""
    num_nt = rnd.randint(1, 6)
    num_t = rnd.randint(1, 3)
    spec: GrammarSpec = []
    for n in range(num_nt):
        prods: List[Production] = []
        for _ in range(rnd.randint(1, 4)):
            length = rnd.choice((1, 1, 2, 2, 2, 3, 4))
            if length == 1:
                # A terminal, or a unit production that refers to a nonterminal
                # with a higher index (so unit productions can't be cyclic)
                if n + 1 < num_nt and rnd.random() < 0.4:
                    p = [nt(rnd.randint(n + 1, num_nt - 1))]
                else:
                    p = [rnd.randint(1, num_t)]
            else:
                p = [
                    nt(rnd.randrange(num_nt))
                    if rnd.random() < 0.55
                    else rnd.randint(1, num_t)
                    for _ in range(length)
                ]
            if p not in prods:
                prods.append(p)
        spec.append(prods)
    # Make sure that all terminals occur in the grammar
    spec[-1].extend([t] for t in range(1, num_t + 1) if [t] not in spec[-1])
    return spec


def test_random_grammars(core) -> None:
    """Compare the core with the reference tree counter, for
    a set of pseudo-random grammars and token sequences"""
    rnd = random.Random(20261109)
    num_parsed = 0
    num_ambiguous = 0
    for _ in range(150):
        spec = random_grammar(rnd)
        num_t = num_terminals(spec)
        c = core(spec)
        for _ in range(25):
            tokens = [rnd.randint(1, num_t) for _ in range(rnd.randint(1, 9))]
            expected = count_trees(spec, tokens)
            assert c.num_trees(tokens) == expected, (spec, tokens)
            num_parsed += expected > 0
            num_ambiguous += expected > 1
        # Release the memory right away, rather than at the end of the test
        c.close()
    # Make sure that the test is not vacuous
    assert num_parsed > 500
    assert num_ambiguous > 200


def random_nullable_grammar(rnd: random.Random) -> GrammarSpec:
    """Create a pseudo-random grammar with empty productions, where
    nonterminals can also derive themselves in various ways"""
    num_nt = rnd.randint(2, 7)
    num_t = rnd.randint(1, 4)
    spec: GrammarSpec = []
    for n in range(num_nt):
        prods: List[Production] = []
        for _ in range(rnd.randint(1, 4)):
            length = rnd.choice((0, 0, 1, 1, 2, 2, 3, 4))
            p = [
                nt(rnd.randrange(num_nt))
                if rnd.random() < 0.6
                else rnd.randint(1, num_t)
                for _ in range(length)
            ]
            if p not in prods:
                prods.append(p)
        spec.append(prods)
    spec[-1].extend([t] for t in range(1, num_t + 1) if [t] not in spec[-1])
    return spec


def test_lookahead(core) -> None:
    """The lookahead filter of the parser, which keeps states that can't
    advance on the current token out of the Earley columns, must not
    change anything that can be seen from the outside: neither the
    content of the forest, nor whether there is a parse, nor the token
    at which a failed parse is reported to fail"""
    rnd = random.Random(20261110)
    num_parsed = num_failed = 0
    error_tokens = set()
    for count in range(300):
        nullable = count % 2 == 1
        spec = random_nullable_grammar(rnd) if nullable else random_grammar(rnd)
        num_t = num_terminals(spec)
        c = core(spec)
        for _ in range(25):
            tokens = [rnd.randint(1, num_t) for _ in range(rnd.randint(1, 8))]
            c.set_lookahead(True)
            forest = c.parse(tokens)
            error = c.error_token
            c.set_lookahead(False)
            other = c.parse(tokens)
            assert c.error_token == error, (spec, tokens)
            if forest is None:
                assert other is None, (spec, tokens)
                num_failed += 1
                error_tokens.add((len(tokens), error))
            else:
                assert other is not None, (spec, tokens)
                assert forest.content() == other.content(), (spec, tokens)
                if not nullable:
                    assert forest.num_trees == count_trees(spec, tokens)
                num_parsed += 1
        c.close()
    # Make sure that the test is not vacuous
    assert num_parsed > 1500
    assert num_failed > 1500
    # Failures at the first token, in the middle and at the end
    assert any(error == 0 for _, error in error_tokens)
    assert any(error == n for n, error in error_tokens)
    assert any(0 < error < n for n, error in error_tokens)


def test_lookahead_saves_work(tmp_path, capfd) -> None:
    """With the lookahead filter, the parser creates fewer states"""
    with allocation_report(capfd) as before:
        pass
    if "States" not in before:
        pytest.skip("Unable to capture the allocation report")
    # S -> X S | X;  X -> A1 | ... | AN;  Ai -> ti Bi | ti;  Bi -> ti ti
    # Each X is predicted in N ways, of which only one fits the token
    N = 40
    spec: GrammarSpec = [[[nt(1), nt(0)], [nt(1)]], [[nt(1 + i)] for i in range(1, N + 1)]]
    for i in range(1, N + 1):
        spec.append([[i, nt(1 + N + i)], [i]])
    for i in range(1, N + 1):
        spec.append([[i, i]])
    tokens = [3, 3, 3, 7, 11, 11, 11, 40, 1]
    c = Core(spec, tmp_path / "grammar.bin")
    c.set_lookahead(False)
    num = c.num_trees(tokens)
    assert num == count_trees(spec, tokens) > 0
    with allocation_report(capfd) as without:
        pass
    c.set_lookahead(True)
    assert c.num_trees(tokens) == num
    with allocation_report(capfd) as with_lookahead:
        pass
    c.close()
    states_without = without["States"][1] - before["States"][1]
    states_with = with_lookahead["States"][1] - without["States"][1]
    assert 0 < states_with < states_without // 3


def test_determinism(core) -> None:
    """Repeated parses of the same input, by the same parser and by
    different parser instances, must yield identical forests, down to
    the order of families of children within each node"""
    PLUS, TIMES, LPAR, RPAR, A = 1, 2, 3, 4, 5
    E, OP = 0, 1
    # E -> E OP E | ( E ) | a | E E;  OP -> + | * | 0
    spec = [
        [[nt(E), nt(OP), nt(E)], [LPAR, nt(E), RPAR], [A], [nt(E), nt(E)]],
        [[PLUS], [TIMES], []],
    ]
    tokens = [A, PLUS, A, A, TIMES, LPAR, A, A, PLUS, A, RPAR, A, A, TIMES, A]
    c1 = core(spec)
    f1 = c1.parse(tokens)
    assert f1 is not None
    assert f1.num_trees > 1000
    dump = f1.dump()
    # Some nodes are ambiguous, i.e. have more than one family
    assert any(len(node[-1]) > 1 for node in dump)
    for _ in range(3):
        f = c1.parse(tokens)
        assert f is not None and f.dump() == dump
    # Parse something else in between, then parse again
    assert c1.parse([A, A, A]) is not None
    f = c1.parse(tokens)
    assert f is not None and f.dump() == dump
    c2 = core(spec)
    f2 = c2.parse(tokens)
    assert f2 is not None and f2.dump() == dump


@contextmanager
def allocation_report(capfd) -> Iterator[Dict[str, Tuple[int, int]]]:
    """Context manager yielding a dict that, upon exit, is filled with
    the (balance, number of allocations) pairs from the allocation report
    of the C++ core, or stays empty if the report could not be captured"""
    result: Dict[str, Tuple[int, int]] = dict()
    yield result
    capfd.readouterr()
    eparser.printAllocationReport()
    out = capfd.readouterr().out
    for m in re.finditer(r"^(\w[\w .]*?)\s*:\s+(-?\d+)\s+(\d+)\s*$", out, re.M):
        result[m.group(1)] = (int(m.group(2)), int(m.group(3)))
    for m in re.finditer(r"^(\w[\w .]*?)\s*:\s+(\d+)\s*$", out, re.M):
        result[m.group(1)] = (0, int(m.group(2)))


def test_allocation_counters(tmp_path, capfd) -> None:
    """All working memory of a parse is released when it completes, and
    the forest is released when it is deleted. Also checks the internal
    consistency of the (batched) statistics counters of the core."""
    with allocation_report(capfd) as before:
        pass
    if "States" not in before:
        pytest.skip("Unable to capture the allocation report")
    # S -> S S | a X;  X -> b | 0
    spec = [[[nt(0), nt(0)], [1, nt(1)]], [[2], []]]
    c = Core(spec, tmp_path / "grammar.bin")
    with allocation_report(capfd) as during:
        assert c.num_trees([1] * 12) == catalan(11)
        assert c.parse([1, 2, 2]) is None
    with allocation_report(capfd) as after:
        c.close()

    def delta(a: Dict[str, Tuple[int, int]], key: str) -> Tuple[int, int]:
        return (a[key][0] - before[key][0], a[key][1] - before[key][1])

    # Working memory: everything is released at the end of each parse
    for key in ("States", "StateChunks", "Columns", "HNodes"):
        balance, allocs = delta(during, key)
        assert balance == 0, key
        assert allocs > 0, key
    # 12 + 3 tokens, plus a sentinel column for each parse
    assert delta(during, "Columns")[1] == 17
    assert delta(during, "NodeDict lookups")[1] > 0
    assert delta(during, "Matching calls")[1] > 0
    # The forest of the successful parse is alive until deleted
    assert delta(during, "Nodes")[0] > 0
    assert delta(during, "Grammars") == (1, 1)
    assert delta(during, "Nonterminals") == (2, 2)
    assert delta(during, "Productions") == (4, 4)
    for key in ("Nodes", "Grammars", "Nonterminals", "Productions", "States"):
        assert delta(after, key)[0] == 0, key
