# type: ignore
"""

    test_no_multiply_numbers.py

    Tests for Greynir no_multiply_numbers flag functionality

    Copyright © 2023 by Miðeind ehf.

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

import pytest

from reynir import Greynir

# Import tests from other files directly into namespace
# (they get run again with the new Greynir instance from the r function below)
# in order to see if flag affects other functionality than just written numbers
from test_cases import test_addresses, test_cases, test_noun_phrases
from test_matcher import test_matcher
from test_original import test_original

# Too many to comfortably write, instead we
# overwrite the only affected tests and the function r
from test_parse import *
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
    assert t.lemma == lemma
    if category == "töl":
        # Ignore variants for undeclinable number words; also,
        # allow "no" for the category since some number words have
        # both "no" and "töl" categories in BÍN
        assert t.category == "no" or t.category == "töl"
    elif category == "to":
        # Allow "no" for the category since declinable number words have
        # both "no" and "to" categories in BÍN
        assert t.category == "no" or t.category == "to"
        assert set(t.variants) == set(variants)
    else:
        assert t.category == category
        assert set(t.variants) == set(variants)


# Overwrite tests from test_parse which use numbers and assume flag is not set
test_amounts = test_terminals = test_single = lambda r: None


def test_no_multiply_numbers(r: Greynir):
    """Test no_multiply_numbers flag"""

    s = r.parse_single("Tjónið nam 10 milljörðum króna.")
    assert s is not None
    t: List[Terminal] = s.terminals or []
    assert len(t) == 6
    check_terminal(
        t[2],
        text="10",
        lemma="10",
        category="tala",
        variants=["þgf", "kk", "ft"],
    )
    check_terminal(
        t[3],
        text="milljörðum",
        lemma="milljarður",
        category="no",
        variants=["þgf", "kk", "ft"],
    )
    check_terminal(
        t[4],
        text="króna",
        lemma="króna",
        category="no",
        variants=["ef", "kvk", "ft"],
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
        variants=[],
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
        variants=[],
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
        variants=[],
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
        category="to",
        variants=["ft", "kk", "nf"],
    )

    s = r.parse_single("Tjónið nam tólf hundruðum punda.")
    assert s is not None
    t = s.terminals or []
    assert len(t) == 6
    check_terminal(
        t[2],
        text="tólf",
        lemma="tólf",
        category="töl",
        variants=[],
    )
    check_terminal(
        t[3],
        text="hundruðum",
        lemma="hundrað",
        category="no",
        variants=["ft", "þgf", "hk"],
    )
    check_terminal(
        t[4],
        text="punda",
        lemma="pund",
        category="no",
        variants=["ft", "ef", "hk"],
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
        category="no",  # "no",  # The choice between töl and no seems a bit random
        variants=["ft", "nf", "hk"],
    )

    s = r.parse_single("7 milljón borðtenniskúlur.")
    assert s is not None
    t = s.terminals or []
    assert len(t) == 4
    check_terminal(
        t[0],
        text="7",
        lemma="7",
        category="tala",
        variants=["kvk", "ft", "nf"],
    )
    check_terminal(
        t[1],
        text="milljón",
        lemma="milljón",
        category="töl",
        variants=[],  # ["kvk", "ft", "nf"]
    )

    s = r.parse_single("Árið áttatíu þúsund sextíu og tvö er í framtíðinni.")
    assert s is not None
    t = s.terminals or []
    assert len(t) == 10
    check_terminal(
        t[1],
        text="áttatíu",
        lemma="áttatíu",
        category="töl",
        variants=["ft", "nf", "hk"],
    )
    check_terminal(
        t[2],
        text="þúsund",
        lemma="þúsund",
        category="töl",
        variants=["ft", "nf", "hk"],
    )
    check_terminal(
        t[3],
        text="sextíu",
        lemma="sextíu",
        category="töl",
        variants=["ft", "nf", "hk"],
    )
    check_terminal(
        t[5],
        text="tvö",
        lemma="tveir",
        category="to",
        variants=["ft", "nf", "hk"],
    )

    s = r.parse_single("Árið átján hundruð níutíu og þrjú er í fortíðinni.")
    assert s is not None
    t = s.terminals or []
    assert len(t) == 10
    check_terminal(
        t[1],
        text="átján",
        lemma="átján",
        category="töl",
        variants=["ft", "nf", "hk"],
    )
    check_terminal(
        t[2],
        text="hundruð",
        lemma="hundrað",
        category="no",
        variants=["ft", "nf", "hk"],
    )
    check_terminal(
        t[3],
        text="níutíu",
        lemma="níutíu",
        category="töl",
        variants=["ft", "nf", "hk"],
    )
    check_terminal(
        t[5],
        text="þrjú",
        lemma="þrír",
        category="to",
        variants=["ft", "nf", "hk"],
    )

    s = r.parse_single("Tvö hundruð þúsund og þrír leikmenn mættu á blakmótið.")
    assert s is not None
    t = s.terminals or []
    assert len(t) == 10
    check_terminal(
        t[0],
        text="Tvö",
        lemma="tveir",
        category="to",
        variants=["ft", "hk", "nf"],
    )
    check_terminal(
        t[1],
        text="hundruð",
        lemma="hundrað",
        category="to",
        variants=["ft", "hk", "nf"],
    )
    check_terminal(
        t[2],
        text="þúsund",
        lemma="þúsund",
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
        category="to",
        variants=["ft", "kk", "nf"],
    )

    s = r.parse_single("Þúsundir mættu á blakmótið.")
    assert s is not None
    t = s.terminals or []
    assert len(t) == 5
    check_terminal(
        t[0],
        text="Þúsundir",
        lemma="þúsund",
        category="no",
        variants=["ft", "kvk", "nf"],
    )
