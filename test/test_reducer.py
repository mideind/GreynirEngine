"""

    test_reducer.py

    Tests for the C++ parse forest reducer

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

    The C++ reducer (ereducer.cpp) counts the trees in a parse forest,
    reduces the forest to its highest-scoring tree and hands that tree to
    Python, replicating what Node.from_c_node(), Fast_Parser.num_combinations()
    and the classes of reducer.py do in Python. The Python implementations
    are the reference: the tests here verify that the two give the same
    results, down to the scores of individual nodes.

    The first part of the tests drives both implementations with
    pseudo-random grammars, where nonterminals have random tags, score
    adjustments and priorities, terminals have random categories, tokens
    match more than one terminal, and the scores of token/terminal matches
    and the verb/preposition and verb/particle bonuses are pseudo-random
    as well. This exercises the parts of the algorithm that are rarely or
    never seen with the real grammar: nonterminals tagged no_reduce, nodes
    that are scored in several verb contexts, exact ties between families,
    and so on.

    The second part uses the real grammar and real sentences.

"""

from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import random
import struct

import pytest

from reynir import Greynir
from reynir._eparser import lib as eparser, ffi  # type: ignore
from reynir.fastparser import Fast_Parser, Node, ParseJob
from reynir.reducer import ParseForestReducer, Reducer, same_forest

SIGNATURE = b"Greynir00.00.01\n"

# The tags that the reducer acts on
TAGS = (
    "enable_prep_bonus",
    "begin_prep_scope",
    "verb_particle",
    "apply_particle_bonus",
    "apply_length_bonus",
    "apply_prep_bonus",
    "pick_up_verb",
    "purge_verb",
    "no_reduce",
)


# The probabilities of tags in grammars that are rich in verb contexts
VERB_TAGS = {
    "enable_prep_bonus": 0.4,
    "pick_up_verb": 0.5,
    "apply_particle_bonus": 0.3,
    "verb_particle": 0.3,
    "apply_prep_bonus": 0.3,
    "begin_prep_scope": 0.08,
    "purge_verb": 0.08,
    "no_reduce": 0.25,
}

# Stand-ins for the grammar objects that the reducers work with


class FakeNonterminal:
    def __init__(self, index: int, tags: Set[str], noun_phrase: bool) -> None:
        self.index = index  # Negative
        self._tags = tags
        self.is_noun_phrase = noun_phrase
        self.no_reduce = "no_reduce" in tags

    def has_tag(self, tag: str) -> bool:
        return tag in self._tags

    def has_any_tag(self, tagset: Iterable[str]) -> bool:
        return not self._tags.isdisjoint(tagset)

    def __repr__(self) -> str:
        return "NT{0}".format(-self.index)


class FakeTerminal:
    def __init__(self, index: int, cat: str, literal: bool) -> None:
        self.index = index  # Positive
        self._cat = cat
        self.is_literal = literal

    def matches_category(self, cat: str) -> bool:
        return self._cat == cat

    def __repr__(self) -> str:
        return "t{0}".format(self.index)


class FakeProduction:
    def __init__(self, index: int, priority: int, items: List[int]) -> None:
        self.index = index
        self.priority = priority
        self.items = items


class FakeToken:

    """A token that matches a given set of terminals"""

    def __init__(self, index: int, terminals: Set[int]) -> None:
        self.index = index
        self._terminals = frozenset(terminals)
        # Distinct tokens may have the same text
        self.lower = "w{0}".format(min(terminals))

    @property
    def key(self) -> Tuple[Any, ...]:
        return tuple(sorted(self._terminals))

    def matches(self, terminal: FakeTerminal) -> bool:
        return terminal.index in self._terminals

    def __repr__(self) -> str:
        return "tok{0}".format(self.index)


class FakeGrammar:

    """A pseudo-random grammar. Nonterminal number n (0-based) has the
    index -1-n; nonterminal 0 is the root."""

    def __init__(
        self, rnd: random.Random, cyclic: bool = False, verbs: bool = False
    ) -> None:
        """If verbs is True, the grammar is rich in the tags and terminal
        categories that make the reducer track verbs and prepositions"""
        num_nt = rnd.randint(2, 6)
        num_t = rnd.randint(2, 5)
        self.num_nonterminals = num_nt
        self.num_terminals = num_t
        self.nonterminals_by_ix: Dict[int, FakeNonterminal] = {}
        self.terminals_by_ix: Dict[int, FakeTerminal] = {}
        self.productions_by_ix: Dict[int, FakeProduction] = {}
        self._nt_scores: Dict[FakeNonterminal, int] = {}
        for n in range(num_nt):
            if verbs:
                tags = set(tag for tag in TAGS if rnd.random() < VERB_TAGS.get(tag, 0.1))
            else:
                tags = set(tag for tag in TAGS if rnd.random() < 0.18)
            fnt = FakeNonterminal(-1 - n, tags, rnd.random() < 0.15)
            self.nonterminals_by_ix[-1 - n] = fnt
            if rnd.random() < 0.5:
                self._nt_scores[fnt] = rnd.randint(-4, 4)
        for t in range(1, num_t + 1):
            if verbs:
                cat = rnd.choice(("ao", "ao", "fs", "fs", "so", "so", "so"))
            else:
                cat = rnd.choice(("ao", "ao", "fs", "fs", "so", "so", "no", "lo"))
            self.terminals_by_ix[t] = FakeTerminal(t, cat, rnd.random() < 0.8)
        # The productions of each nonterminal. Unit productions only
        # refer to nonterminals with a higher number, and all other
        # productions contain a terminal, so that the grammar can't
        # derive a nonterminal from itself (unless cyclic is True).
        self.spec: List[List[FakeProduction]] = []
        prod_id = 0
        for n in range(num_nt):
            seen: List[List[int]] = []
            prods: List[FakeProduction] = []
            for _ in range(rnd.randint(1, 5)):
                length = rnd.choice((0, 1, 1, 2, 2, 2, 3, 3, 4))
                if length == 1:
                    if cyclic and rnd.random() < 0.3:
                        items = [-1 - rnd.randrange(num_nt)]
                    elif n + 1 < num_nt and rnd.random() < 0.4:
                        items = [-1 - rnd.randint(n + 1, num_nt - 1)]
                    else:
                        items = [rnd.randint(1, num_t)]
                else:
                    items = [
                        -1 - rnd.randrange(num_nt)
                        if rnd.random() < 0.6
                        else rnd.randint(1, num_t)
                        for _ in range(length)
                    ]
                    if length and all(item < 0 for item in items) and not cyclic:
                        items[rnd.randrange(length)] = rnd.randint(1, num_t)
                if items in seen:
                    continue
                seen.append(items)
                # Productions have priorities 0, 1 and (rarely) 2
                prio = rnd.choice((0, 0, 0, 0, 1, 1, 2))
                prods.append(FakeProduction(prod_id, prio, items))
                prod_id += 1
            if not any(len(p.items) == 1 and p.items[0] > 0 for p in prods):
                # Make sure that every nonterminal can derive a single token
                items = [rnd.randint(1, num_t)]
                prods.append(FakeProduction(prod_id, 0, items))
                prod_id += 1
            self.spec.append(prods)
        for prods in self.spec:
            for p in prods:
                self.productions_by_ix[p.index] = p

    def lookup_nonterminal(self, index: int) -> Optional[FakeNonterminal]:
        return self.nonterminals_by_ix.get(index)

    def lookup_terminal(self, index: int) -> Optional[FakeTerminal]:
        return self.terminals_by_ix.get(index)

    def binary(self) -> bytes:
        """The grammar in the binary format read by newGrammar()
        (see Grammar._write_binary() in grammar.py)"""
        buf = [
            SIGNATURE,
            struct.pack("<IIi", self.num_terminals, self.num_nonterminals, -1),
        ]
        for prods in self.spec:
            buf.append(struct.pack("<I", len(prods)))
            for p in prods:
                buf.append(struct.pack("<III", p.index, p.priority, len(p.items)))
                buf.append(struct.pack("<{0}i".format(len(p.items)), *p.items))
        return b"".join(buf)

    def derive(self, rnd: random.Random, max_len: int) -> List[int]:
        """Return a pseudo-random sequence of terminals
        that the root nonterminal derives"""

        def expand(n: int, budget: int) -> List[int]:
            prods = self.spec[n]
            if budget <= 1:
                # Out of budget: derive a single token
                p = next(p for p in prods if len(p.items) == 1 and p.items[0] > 0)
            else:
                p = rnd.choice(prods)
            result: List[int] = []
            for item in p.items:
                if item > 0:
                    result.append(item)
                else:
                    result.extend(expand(-1 - item, budget // max(len(p.items), 2)))
            return result

        for _ in range(100):
            tokens = expand(0, max_len)
            if 0 < len(tokens) <= max_len:
                return tokens
        return []


def mix(*numbers: int) -> int:
    """A deterministic pseudo-random function of some integers"""
    h = 17
    for n in numbers:
        h = (h * 31 + n) % 1000003
    return h


class FakeForestReducer(ParseForestReducer):

    """A forest reducer where the bonuses that depend on the
    vocabulary are pseudo-random functions of their arguments"""

    def verb_prep_bonus(
        self, prep_terminal: Any, prep_token: Any, verb_terminal: Any, verb_token: Any
    ) -> int:
        h = mix(
            prep_terminal.index,
            int(prep_token[1:]),
            verb_terminal.index,
            verb_token.index,
        )
        return (7, -2, 3, 0, 5, -1, 1)[h % 7]

    def verb_particle_bonus(self, particle: str, verbs: Any) -> int:
        if not verbs:
            return -6
        h = mix(int(particle[1:]), *(n for t, tok in verbs for n in (t.index, tok.index)))
        return (7, -6, 2)[h % 3]


class FakeReducer(Reducer):

    """A reducer where the scores of token/terminal matches are
    a pseudo-random function of the token and the terminal"""

    _forest_reducer_class = FakeForestReducer

    def _score_options(self, finals: Any, tokens: Any, start: int, end: int) -> Any:
        return {
            i: {t: mix(i, t.index) % 7 - 3 for t in finals[i]}
            for i in range(start, end)
        }


class FakeParser:

    """A C++ parser instance for a FakeGrammar"""

    def __init__(self, grammar: FakeGrammar, path: Any) -> None:
        path.write_bytes(grammar.binary())
        self.grammar = grammar
        self._c_grammar = eparser.newGrammar(str(path).encode("utf-8"))
        assert self._c_grammar != ffi.NULL
        self._c_parser = eparser.newParser(
            self._c_grammar, eparser.matching_func, eparser.alloc_func
        )
        assert self._c_parser != ffi.NULL
        self._cache: Dict[Any, Any] = dict()
        # Set if the Python implementation could not handle the last forest
        self.python_failed = False
        self.reducer = FakeReducer(grammar)  # type: ignore
        assert Reducer._install_native_tables(self)  # type: ignore

    def close(self) -> None:
        eparser.deleteParser(self._c_parser)
        eparser.deleteGrammar(self._c_grammar)

    def reduce_both_ways(
        self, tokens: Sequence[FakeToken]
    ) -> Tuple[Optional[Tuple[Node, int, int]], Optional[Tuple[Node, int, int]]]:
        """Parse the tokens and reduce the forest, first with the C++
        reducer and then in Python. Returns the two results: tuples of
        tree, number of trees and score; or None from a reducer that
        could not handle the forest (the C++ one declines to; the Python
        one fails, and self.python_failed is set). If there is no parse,
        two Nones are returned."""
        self.python_failed = False
        err = ffi.new("unsigned int*")
        grammar: Any = self.grammar
        toks: Any = list(tokens)
        terminals: Any = grammar.terminals_by_ix
        with ParseJob.make(grammar, toks, terminals, self._cache) as job:
            job.c_parser = self._c_parser
            c_forest = eparser.earleyParse(
                self._c_parser, len(toks), 0, job.handle, err
            )
            if c_forest == ffi.NULL:
                return None, None
            try:
                native = self.reducer._native_reduce(job, c_forest)
                forest = Node.from_c_node(job, c_forest)
                assert forest is not None
            finally:
                eparser.deleteForest(c_forest)
        try:
            return native, self.reducer._python_reduce(forest)
        except (AssertionError, RecursionError):
            # The Python implementation gives up on forests with cycles
            self.python_failed = True
            return native, None


@pytest.fixture
def fake_parser(tmp_path):
    """Fixture yielding a factory of FakeParser instances
    that are properly cleaned up after the test"""
    parsers: List[FakeParser] = []

    def make(grammar: FakeGrammar) -> FakeParser:
        p = FakeParser(grammar, tmp_path / "grammar{0}.bin".format(len(parsers)))
        parsers.append(p)
        return p

    yield make
    for p in parsers:
        p.close()


def random_tokens(
    rnd: random.Random, grammar: FakeGrammar, max_len: int
) -> List[FakeToken]:
    """Return a pseudo-random sentence of the grammar,
    where some tokens match more than one terminal"""
    tokens: List[FakeToken] = []
    for ix, t in enumerate(grammar.derive(rnd, max_len)):
        terminals = {t}
        while rnd.random() < 0.3:
            terminals.add(rnd.randint(1, grammar.num_terminals))
        tokens.append(FakeToken(ix, terminals))
    return tokens


def test_random_grammars(fake_parser) -> None:
    """Compare the C++ reducer with the Python one on sentences
    of pseudo-random grammars"""
    rnd = random.Random(31337)
    num_parsed = num_ambiguous = num_reduced = num_no_reduce = 0
    for count in range(600):
        # Two out of three grammars are rich in verb contexts
        grammar = FakeGrammar(rnd, verbs=count % 3 != 0)
        parser = fake_parser(grammar)
        for _ in range(16):
            tokens = random_tokens(rnd, grammar, rnd.choice((4, 6, 9, 14, 20)))
            if not tokens:
                continue
            native, python = parser.reduce_both_ways(tokens)
            # The sentence was derived from the root, so it parses
            assert python is not None
            assert native is not None, "The C++ reducer should handle this forest"
            tree, num, score = native
            py_tree, py_num, py_score = python
            assert num == py_num
            assert score == py_score
            assert same_forest(tree, py_tree)
            num_parsed += 1
            if num > 1:
                num_ambiguous += 1
                # Was something actually reduced, and did
                # any node keep more than one family?
                if Fast_Parser.num_combinations(tree) < num:
                    num_reduced += 1
                if Fast_Parser.num_combinations(tree) > 1:
                    num_no_reduce += 1
    # Check that the test tests what it is meant to test
    assert num_parsed > 1500
    assert num_ambiguous > 500
    assert num_reduced > 500
    assert num_no_reduce > 50


def test_cyclic_grammars(fake_parser) -> None:
    """The C++ reducer declines to handle forests with cycles,
    and agrees with the Python one about all others"""
    rnd = random.Random(4711)
    num_declined = num_handled = 0
    for _ in range(60):
        grammar = FakeGrammar(rnd, cyclic=True)
        parser = fake_parser(grammar)
        for _ in range(8):
            tokens = random_tokens(rnd, grammar, 6)
            if not tokens:
                continue
            native, python = parser.reduce_both_ways(tokens)
            if parser.python_failed:
                # A forest with a cycle
                assert native is None
                num_declined += 1
                continue
            assert native is not None and python is not None
            assert native[1:] == python[1:]
            assert same_forest(native[0], python[0])
            num_handled += 1
    assert num_handled > 100
    assert num_declined > 20


def explicit_grammar(
    nonterminals: List[Tuple[Set[str], List[List[int]]]], categories: List[str]
) -> FakeGrammar:
    """Return a grammar with the given nonterminals, each of which is a
    set of tags and a list of productions, and with terminals of the
    given categories (terminal 1 first)"""
    grammar = FakeGrammar(random.Random(0))
    grammar.num_nonterminals = len(nonterminals)
    grammar.num_terminals = len(categories)
    grammar.nonterminals_by_ix = {
        -1 - n: FakeNonterminal(-1 - n, tags, False)
        for n, (tags, _) in enumerate(nonterminals)
    }
    grammar.terminals_by_ix = {
        t + 1: FakeTerminal(t + 1, cat, False) for t, cat in enumerate(categories)
    }
    grammar.spec = []
    grammar.productions_by_ix = {}
    for _, productions in nonterminals:
        prods: List[FakeProduction] = []
        for items in productions:
            p = FakeProduction(len(grammar.productions_by_ix), 0, items)
            grammar.productions_by_ix[p.index] = p
            prods.append(p)
        grammar.spec.append(prods)
    grammar._nt_scores = {}
    return grammar


def simple_grammar(productions: List[List[int]]) -> FakeGrammar:
    """Return a grammar with a single nonterminal, without tags"""
    num_terminals = max(item for p in productions for item in p)
    return explicit_grammar([(set(), productions)], ["no"] * num_terminals)


def test_shared_node_in_two_contexts(fake_parser) -> None:
    """A node that is shared between two verb contexts, with a different
    winning family in each, is reduced the way that the first context
    to reach it in the resulting forest wants"""

    class ForestReducer(ParseForestReducer):
        def verb_prep_bonus(self, prep_terminal: Any, *args: Any) -> int:
            # In the context of a verb, prefer terminal 4 to terminal 3
            return 7 if prep_terminal.index == 4 else -2

    class ZeroReducer(Reducer):
        _forest_reducer_class = ForestReducer

        def _score_options(self, finals: Any, tokens: Any, start: int, end: int) -> Any:
            return {i: {t: 0 for t in finals[i]} for i in range(start, end)}

    grammar = explicit_grammar(
        [
            # R -> A X | B X, where both families are kept
            ({"no_reduce"}, [[-2, -4], [-3, -4]]),
            # A -> verb, which becomes the current verb
            ({"pick_up_verb"}, [[1]]),
            # B -> noun
            (set(), [[2]]),
            # X -> preposition | preposition, scored in the context of
            # the current verb, if there is one; if not, it is a tie
            ({"enable_prep_bonus"}, [[3], [4]]),
        ],
        ["so", "no", "fs", "fs"],
    )
    parser = fake_parser(grammar)
    parser.reducer = ZeroReducer(grammar)  # type: ignore
    native, python = parser.reduce_both_ways([FakeToken(0, {1, 2}), FakeToken(1, {3, 4})])
    assert native is not None and python is not None
    assert native[1] == python[1] == 4
    assert native[2] == python[2]
    assert same_forest(native[0], python[0])
    # Both families of the root are there, sharing the X node, which
    # has been reduced to a single family
    families = list(python[0].enum_children())
    assert len(families) == 2
    x = families[0][1][1]
    assert x is families[1][1][1]
    assert x is not None and x.num_families == 1


def catalan(n: int) -> int:
    c = 1
    for i in range(n):
        c = c * 2 * (2 * i + 1) // (i + 2)
    return c


def test_huge_number_of_trees(fake_parser) -> None:
    """S -> S S | a has Catalan(n-1) parse trees for n tokens, which
    is much more than fits in 64 bits for the lengths tested here"""
    parser = fake_parser(simple_grammar([[-1, -1], [1]]))
    for n in (2, 3, 10, 34, 35, 36, 60, 75):
        native, python = parser.reduce_both_ways([FakeToken(i, {1}) for i in range(n)])
        assert native is not None and python is not None
        assert native[1] == python[1] == catalan(n - 1)
        assert native[2] == python[2]
        assert same_forest(native[0], python[0])
    assert catalan(74) > 2 ** 128


def test_deep_forest(fake_parser) -> None:
    """The C++ reducer declines to handle a forest
    that is deeper than its limit on recursion"""
    # S -> a S | a
    parser = fake_parser(simple_grammar([[1, -1], [1]]))
    err = ffi.new("unsigned int*")
    grammar: Any = parser.grammar
    terminals: Any = grammar.terminals_by_ix
    for n, handled in ((900, True), (1100, False)):
        toks: Any = [FakeToken(i, {1}) for i in range(n)]
        with ParseJob.make(grammar, toks, terminals, parser._cache) as job:
            job.c_parser = parser._c_parser
            c_forest = eparser.earleyParse(parser._c_parser, n, 0, job.handle, err)
            assert c_forest != ffi.NULL
            try:
                native = parser.reducer._native_reduce(job, c_forest)
            finally:
                eparser.deleteForest(c_forest)
        if handled:
            assert native is not None
            assert native[1] == 1
            # The tree has a node for each token, and one for each S
            depth = 0
            node: Optional[Node] = native[0]
            while node is not None and not node.is_token:
                depth += 1
                node = list(node.enum_child_nodes())[-1]
            assert depth == n
        else:
            assert native is None


# Tests with the real grammar

SENTENCES = [
    "Ása sá sól.",
    "Konan sem kom í heimsókn í gær ætlar að kaupa nýja íbúð í miðbænum.",
    "Hann bjó til stóran snjókarl handa börnunum og þau tóku vel í það.",
    "Ríkisstjórnin ákvað á fundi sínum í morgun að leggja fram frumvarp "
    "um breytingar á lögum um tekjuskatt.",
    "Mig langar að fara til Frakklands í sumar ef veðrið verður gott.",
    "Jón gaf Guðrúnu bókina sem hann keypti í gær.",
    "Þeir sem mættu á fundinn voru sammála um að málið væri flókið.",
    "Lögreglan handtók manninn eftir að hann hafði brotist inn í húsið.",
    "Verðbólgan hefur aukist um 5,6% á síðustu tólf mánuðum.",
    "Hún sagði að þau hefðu ekki tekið eftir neinu óvenjulegu.",
    "Páli þykir þetta vera tóm vitleysa.",
    "Hvað heitir höfuðborg Frakklands?",
    "Stjórnin lagði til að félagið greiddi hluthöfum arð.",
    "Skipið sigldi út úr höfninni og hvarf í þokuna.",
    "Bókin, sem kom út í fyrra, hefur selst í tíu þúsund eintökum.",
    "Hesturinn.",
    "Þetta er setning sem þáttast ekki vegna þess að hún er er rugl rugl.",
]


@pytest.fixture(scope="module")
def r():
    """Provide a module-scoped Greynir instance as a test fixture"""
    r = Greynir()
    yield r
    # Do teardown here
    r.__class__.cleanup()


def parse_all(r: Greynir) -> List[Tuple[Any, ...]]:
    """Parse the test sentences and return what is known about each one"""
    result: List[Tuple[Any, ...]] = []
    for text in SENTENCES:
        s = r.parse_single(text)
        assert s is not None
        result.append(
            (
                s.combinations,
                s.score,
                None if s.tree is None else s.tree.flat,
                # A text representation of the tree, with the score of each node
                repr(s.deep_tree),
            )
        )
    return result


def count_native(monkeypatch) -> Dict[str, int]:
    """Count the calls to Reducer._native_reduce() and the
    number of those where the forest was handled"""
    count = dict(calls=0, handled=0)
    original = Reducer._native_reduce

    def native_reduce(self: Reducer, job: Any, c_forest: Any) -> Any:
        count["calls"] += 1
        result = original(self, job, c_forest)
        if result is not None:
            count["handled"] += 1
        return result

    monkeypatch.setattr(Reducer, "_native_reduce", native_reduce)
    return count


def test_native_by_default(r: Greynir, monkeypatch) -> None:
    """Sentences are reduced by the C++ reducer, unless it is turned off;
    the results are the same either way"""
    monkeypatch.delenv("GREYNIR_DISABLE_CPP_REDUCER", raising=False)
    monkeypatch.delenv("GREYNIR_REDUCER_PARITY", raising=False)
    count = count_native(monkeypatch)
    native = parse_all(r)
    num_parsed = sum(1 for res in native if res[2] is not None)
    assert num_parsed >= len(SENTENCES) - 1
    assert count["calls"] == count["handled"] == num_parsed
    # The same in Python
    monkeypatch.setenv("GREYNIR_DISABLE_CPP_REDUCER", "1")
    python = parse_all(r)
    assert count["calls"] == num_parsed  # No more calls
    assert native == python


def test_parity_mode(r: Greynir, monkeypatch) -> None:
    """In parity mode, both reducers are run and compared"""
    monkeypatch.delenv("GREYNIR_DISABLE_CPP_REDUCER", raising=False)
    monkeypatch.setenv("GREYNIR_REDUCER_PARITY", "1")
    count = count_native(monkeypatch)
    before = Reducer.parity_mismatches
    results = parse_all(r)
    assert count["calls"] == count["handled"] > 0
    assert Reducer.parity_mismatches == before
    assert sum(1 for res in results if res[0] and res[0] > 1) > 10


def test_parity_mode_detects_differences(r: Greynir, monkeypatch) -> None:
    """A difference between the two reducers is counted in parity mode"""
    monkeypatch.setenv("GREYNIR_REDUCER_PARITY", "1")
    original = Reducer._native_reduce

    def native_reduce(self: Reducer, job: Any, c_forest: Any) -> Any:
        result = original(self, job, c_forest)
        assert result is not None
        tree, num, score = result
        # Sabotage the score of some node at the bottom of the tree
        node = tree
        while not node.is_token:
            node = next(ch for ch in node.enum_child_nodes() if ch is not None)
        node.score += 1
        return tree, num, score

    monkeypatch.setattr(Reducer, "_native_reduce", native_reduce)
    before = Reducer.parity_mismatches
    try:
        s = r.parse_single(SENTENCES[1])
        assert s is not None and s.tree is not None
        assert Reducer.parity_mismatches == before + 1
    finally:
        Reducer.parity_mismatches = before


def test_overrides_turn_native_off(r: Greynir, monkeypatch) -> None:
    """A reducer or a parser that overrides what the C++ reducer
    replicates is left to do its work in Python"""
    monkeypatch.delenv("GREYNIR_DISABLE_CPP_REDUCER", raising=False)
    parser = r.parser
    grammar = parser.grammar
    assert Reducer(grammar)._native_allowed(parser)

    class MyReducer(Reducer):
        def _reduce(self, w: Node, scores: Any) -> Any:
            return super()._reduce(w, scores)

    assert not MyReducer(grammar)._native_allowed(parser)

    class MyForestReducer(ParseForestReducer):
        pass

    class MyOtherReducer(Reducer):
        _forest_reducer_class = MyForestReducer

    assert not MyOtherReducer(grammar)._native_allowed(parser)

    class OptOutReducer(Reducer):
        _USE_CPP_REDUCER = False

    assert not OptOutReducer(grammar)._native_allowed(parser)

    class MyParser(Fast_Parser):
        def go(self, tokens: Any, **kwargs: Any) -> Node:
            return super().go(tokens, **kwargs)

    monkeypatch.setattr(parser, "__class__", MyParser)
    assert not Reducer(grammar)._native_allowed(parser)
    monkeypatch.undo()
    assert Reducer(grammar)._native_allowed(parser)
    monkeypatch.setenv("GREYNIR_DISABLE_CPP_REDUCER", "1")
    assert not Reducer(grammar)._native_allowed(parser)


def test_exception_in_callback(r: Greynir, monkeypatch) -> None:
    """An exception raised in Python code that the C++ reducer
    calls is passed on to the caller of the reducer"""
    monkeypatch.delenv("GREYNIR_DISABLE_CPP_REDUCER", raising=False)
    monkeypatch.delenv("GREYNIR_REDUCER_PARITY", raising=False)

    class Boom(Exception):
        pass

    def verb_prep_bonus(self: Any, *args: Any) -> int:
        raise Boom()

    monkeypatch.setattr(ParseForestReducer, "verb_prep_bonus", verb_prep_bonus)
    with pytest.raises(Boom):
        r.parse_single("Konan kom í heimsókn til mín í gær.")
    monkeypatch.undo()
    s = r.parse_single("Konan kom í heimsókn til mín í gær.")
    assert s is not None and s.tree is not None


def test_same_forest(r: Greynir) -> None:
    """The comparison function used in parity mode tells forests apart"""
    parser = r.parser
    tokens = list(r.tokenize(SENTENCES[1]))
    # Convert the same forest twice (nodes are compared by the
    # identity of the grammar objects and tokens that they refer to)
    with parser.parse_forest(tokens) as (job, c_forest):
        a = Node.from_c_node(job, c_forest)
        job.reset()
        b = Node.from_c_node(job, c_forest)
    assert a is not None and b is not None and a is not b
    assert same_forest(a, b)
    assert not same_forest(a, None)
    # Remove a family of children from an ambiguous node of one of them
    stack = [b]
    seen = set()
    while stack:
        node = stack.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        families = node._families or []
        if len(families) > 1:
            del families[-1]
            break
        stack.extend(ch for _, f in families for ch in f if ch is not None)
    else:
        assert False, "No ambiguous node found"
    assert not same_forest(a, b)
