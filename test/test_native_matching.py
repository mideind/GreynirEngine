"""

    test_native_matching.py

    Tests for the native (C++) token/terminal matching fast path
    (build_matching_table()/encode_token_matching_data() in binparser.py
    and evalMatch() in eparser.cpp). Verifies that the fast path is
    enabled by default, produces results identical to Python matching,
    reports zero discrepancies in parity mode, and is automatically
    disabled for parser subclasses that override token wrapping.

"""

import os

from reynir import Greynir
from reynir.binparser import BIN_Token
from reynir.fastparser import Fast_Parser

# A corpus exercising a variety of token and terminal kinds:
# regular words, literal terminals, abbreviations, numbers, amounts,
# dates, person names, entities, unknown words and punctuation
SENTENCES = [
    "Ása sá sól.",
    "Konan sem kom í heimsókn í gær ætlar að kaupa nýja íbúð í miðbænum.",
    "Hr. Jón Jónsson býr á Laugavegi 26 og á 3,4 milljónir króna í banka.",
    "Verðbólgan hefur aukist verulega, þ.e.a.s. um 5,6%, á síðustu mánuðum.",
    "Xylofonn og Kwerty eru ekki íslensk orð.",
    "Hinn 17. júní 2011 var lýðveldið Ísland 67 ára gamalt.",
    "Þórunn Ólafsdóttir varð sér úti um brimsalta poka af poppi.",
    "Það rignir sjaldan í Reykjavík í júlí en þó gerist það stundum.",
    "Bandaríkin og Evrópusambandið gerðu með sér nýjan viðskiptasamning.",
    "Kötturinn, sem heitir Brandur, veiddi þrjár mýs í nótt.",
]


def _parse_results(disable_native: bool):
    """Parse the corpus with a fresh parser, native matching on or off.
    Returns, per sentence, the number of parse tree combinations in the
    forest (or None if the sentence did not parse). Note that we compare
    forest sizes rather than reduced trees, since the reducer may break
    exact score ties differently between runs; the forest itself is
    fully determined by the token/terminal match results."""
    key = "GREYNIR_DISABLE_CPP_MATCHING"
    old = os.environ.get(key)
    try:
        if disable_native:
            os.environ[key] = "1"
        else:
            os.environ.pop(key, None)
        # Discard the cached parser so that a fresh one is constructed
        # under the current environment settings
        Greynir.cleanup()
        g = Greynir()
        results = []
        for s in SENTENCES:
            r = g.parse_single(s)
            results.append(None if r.tree is None else r.combinations)
        assert g.parser.uses_native_matching == (not disable_native)
        return results
    finally:
        if old is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = old
        Greynir.cleanup()


def test_native_matching_enabled_by_default():
    fp = Fast_Parser()
    try:
        assert fp.uses_native_matching
    finally:
        fp.cleanup()


def test_native_python_equivalence():
    """The native fast path must produce exactly the same parse forests
    as Python matching"""
    native = _parse_results(disable_native=False)
    python = _parse_results(disable_native=True)
    assert native == python
    # Sanity check: most of the corpus should actually parse
    assert sum(1 for r in native if r is not None) >= len(SENTENCES) - 1


def test_parity_mode():
    """In parity mode, every native match evaluation is compared with
    the Python matcher; there must be no discrepancies"""
    key = "GREYNIR_MATCHING_PARITY"
    old = os.environ.get(key)
    try:
        os.environ[key] = "1"
        Greynir.cleanup()
        g = Greynir()
        for s in SENTENCES:
            g.parse_single(s)
        fp = g.parser
        assert fp.uses_native_matching
        assert fp.parity_mismatches == 0
    finally:
        if old is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = old
        Greynir.cleanup()


def test_gate_subclass_wrap_token():
    """A parser subclass that overrides token wrapping (as e.g.
    GreynirCorrect does) must automatically fall back to Python matching"""

    class TokenWrappingParser(Fast_Parser):
        @staticmethod
        def wrap_token(t, ix):
            return BIN_Token(t, ix)

    fp = TokenWrappingParser()
    try:
        assert not fp.uses_native_matching
    finally:
        fp.cleanup()


def test_gate_class_flag():
    """Setting _USE_CPP_MATCHING = False must disable the fast path"""

    class PythonMatchingParser(Fast_Parser):
        _USE_CPP_MATCHING = False

    fp = PythonMatchingParser()
    try:
        assert not fp.uses_native_matching
    finally:
        fp.cleanup()
