# type: ignore
"""

    test_no_multiply_numbers.py

    Tests for Greynir module

    Copyright(C) 2021 by Miðeind ehf.
    Original author: Vilhjálmur Þorsteinsson

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

"""

import pytest  # type: ignore

from reynir import Greynir

# Import tests from other files directly into namespace (they get run again with the new Greynir instance from r() function below)
# in order to see if flag affects other functionality than just written numbers
from test_cases import test_addresses, test_cases, test_noun_phrases
from test_matcher import test_matcher
from test_original import test_original
from test_parse import *  # Too many to comfortably write, instead we overwrite the only affected test (test_amounts)
from test_reynir import (
    test_augment_terminal,
    test_auto_uppercase,
    test_compounds,
    test_compounds_with_numbers,
    test_lemmas,
    test_names,
    test_sentence_split,
)
from test_serializers import test_annotree, test_serializers


@pytest.fixture(scope="module")
def r():
    """Provide module-scoped Greynir instance (which doesn't multiply numbers) as test fixture"""
    r = Greynir(no_multiply_numbers=True)
    yield r
    # Do teardown here
    r.__class__.cleanup()


def check_terminal(t, text, lemma, category, variants):
    assert t.text == text
    assert t.lemma == lemma or lemma == "*"
    assert t.category == category or category == "*"
    assert set(t.variants) == set(variants) or variants == ["*"]


def test_amounts(r: Greynir):
    # Just to overwrite test_amounts from test_parse
    pass


def test_no_multiply_numbers(r: Greynir):
    """Test no_multiply_numbers flag"""

    s = r.parse_single("Tjónið nam 10 milljörðum króna.")
    assert s is not None
    t: List[Terminal] = s.terminals or []
    assert len(t) == 4
    check_terminal(
        t[2],
        text="10 milljörðum króna",
        lemma="10 milljörðum króna",
        category="no",
        variants=["ft", "þgf", "kk"],
    )

    s = r.parse_single("Tjónið þann 22. maí nam einum milljarði króna.")
    assert s is not None
    t = s.terminals or []
    assert len(t) == 8
    check_terminal(
        t[4],
        text="einum",
        lemma="einn",
        category="to",
        variants=["et", "þgf", "kk"],
    )
    check_terminal(
        t[5],
        text="milljarði",
        lemma="milljarður",
        category="no",
        variants=["et", "þgf", "kk"],
    )
    check_terminal(
        t[6],
        text="króna",
        lemma="króna",
        category="no",
        variants=["ft", "ef", "kvk"],
    )

    s = r.parse_single("Tjónið nam tuttugu og einum milljarði króna.")
    assert s is not None
    t = s.terminals or []
    assert len(t) == 8
    check_terminal(
        t[2],
        text="tuttugu",
        lemma="tuttugu",
        category="töl",
        variants=["ft", "kk", "þgf"],
    )
    check_terminal(
        t[4],
        text="einum",
        lemma="einn",
        category="to",
        variants=["et", "þgf", "kk"],
    )
    check_terminal(
        t[5],
        text="milljarði",
        lemma="milljarður",
        category="no",
        variants=["et", "þgf", "kk"],
    )
    check_terminal(
        t[6],
        text="króna",
        lemma="króna",
        category="no",
        variants=["ft", "ef", "kvk"],
    )

    s = r.parse_single("Fjöldi stjarna í Vetrarbrautinni skiptir hundruðum milljarða.")
    assert s is not None
    t = s.terminals or []
    assert len(t) == 8
    check_terminal(
        t[5],
        text="hundruðum",
        lemma="hundrað",
        category="no",
        variants=["ft", "þgf", "hk"],
    )
    check_terminal(
        t[6],
        text="milljarða",
        lemma="milljarður",
        category="no",
        variants=["ft", "ef", "kk"],
    )

    s = r.parse_single("Sex hundruð áttatíu og þrír leikmenn mættu á blakmótið.")
    assert s is not None
    t = s.terminals or []
    assert len(t) == 10
    check_terminal(
        t[0],
        text="Sex",
        lemma="sex",
        category="töl",
        variants=["ft", "hk", "nf"],
    )
    check_terminal(
        t[1],
        text="hundruð",
        lemma="hundrað",
        category="no",
        variants=["ft", "hk", "nf"],
    )
    check_terminal(
        t[2],
        text="áttatíu",
        lemma="áttatíu",
        category="töl",
        variants=["ft", "hk", "nf"],
    )
    check_terminal(
        t[3],
        text="og",
        lemma="og",
        category="st",
        variants=[],
    )
    check_terminal(
        t[4],
        text="þrír",
        lemma="þrír",
        category="töl",
        variants=["ft", "kk", "þf"],
    )

    s = r.parse_single("Tjónið nam tólf hundruð pundum.")
    assert s is not None
    t = s.terminals or []
    assert len(t) == 6
    check_terminal(
        t[2],
        text="tólf",
        lemma="tólf",
        category="töl",
        variants=["ft", "þgf", "hk"],
    )
    check_terminal(
        t[3],
        text="hundruð",
        lemma="hundrað",
        category="no",
        variants=["ft", "þgf", "hk"],
    )

    s = r.parse_single("Sjötíu þúsund manns söfnuðust fyrir á torginu.")
    assert s is not None
    t = s.terminals or []
    assert len(t) == 8
    check_terminal(
        t[0],
        text="Sjötíu",
        lemma="sjötíu",
        category="töl",
        variants=["ft", "nf", "hk"],
    )
    check_terminal(
        t[1],
        text="þúsund",
        lemma="þúsund",
        category="no",
        variants=["ft", "nf", "hk"],
    )
    check_terminal(
        t[2],
        text="tólf hundruð pundum",
        lemma="tólf hundruð pundum",
        category="no",
        variants=["ft", "þgf", "hk"],
    )
    check_terminal(t[3], text=".", lemma=".", category="", variants=[])

    s = r.parse_single("Árið áttatíu þúsund sextíu og tvö er í framtíðinni.")
    assert s is not None
    t = s.terminals or []
    assert len(t) == 4
    check_terminal(
        t[0],
        text="Tjónið",
        lemma="tjón",
        category="no",
        variants=["et", "nf", "hk", "gr"],
    )
    check_terminal(
        t[1],
        text="nam",
        lemma="nema",
        category="so",
        variants=["1", "þgf", "et", "p3", "gm", "þt", "fh"],
    )
    check_terminal(
        t[2],
        text="tólf hundruð pundum",
        lemma="tólf hundruð pundum",
        category="no",
        variants=["ft", "þgf", "hk"],
    )
    check_terminal(t[3], text=".", lemma=".", category="", variants=[])

    s = r.parse_single("Árið átján hundruð níutíu og þrjú er í fortíðinni.")
    assert s is not None
    t = s.terminals or []
    assert len(t) == 4
    check_terminal(
        t[0],
        text="Tjónið",
        lemma="tjón",
        category="no",
        variants=["et", "nf", "hk", "gr"],
    )
    check_terminal(
        t[1],
        text="nam",
        lemma="nema",
        category="so",
        variants=["1", "þgf", "et", "p3", "gm", "þt", "fh"],
    )
    check_terminal(
        t[2],
        text="tólf hundruð pundum",
        lemma="tólf hundruð pundum",
        category="no",
        variants=["ft", "þgf", "hk"],
    )
    check_terminal(t[3], text=".", lemma=".", category="", variants=[])
