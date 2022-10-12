# type: ignore
"""

    test_matcher.py

    Tests for the SimpleTree matching functionality in matcher.py

    Copyright(C) 2022 by Miðeind ehf.
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

from typing import List, cast

from collections import defaultdict

import pytest

from tokenizer.definitions import AmountTuple, DateTimeTuple

from reynir import Greynir
from reynir.reynir import Terminal


@pytest.fixture(scope="module")
def r():
    """Provide a module-scoped Greynir instance as a test fixture"""
    r = Greynir()
    yield r
    # Do teardown here
    r.__class__.cleanup()


def test_matcher(r: Greynir, verbose: bool = False) -> None:

    s = r.parse_single("Hún á heiðurinn að þessu.")
    m = list(
        s.tree.all_matches(
            "( "
            "VP > [ .* VP > { ( 'eiga'|'fá'|'hljóta' ) } .* NP-OBJ > { 'heiður' PP > { 'að' } } ] "
            "| "
            "VP > [ .* VP > { ( 'eiga'|'fá'|'hljóta' ) } .* NP-OBJ > { 'heiður' } PP > { 'að' } ] "
            ") "
        )
    )
    assert len(m) == 1

    # Simple condition, correct sentence (vh in both subtrees)
    s = r.parse_single("Ég hefði farið út ef Jón hefði hegðað sér vel.")
    m = list(
        s.tree.all_matches(
            "VP > { VP > { so_vh } CP-ADV-COND > { IP > { VP >> so_fh }}}"
        )
    )
    assert len(m) == 0

    # Simple condition, incorrect sentence (fh in conditional subtree)
    s = r.parse_single("Ég hefði farið út ef Jón hafði hegðað sér vel.")
    m = list(
        s.tree.all_matches(
            "VP > { VP > { so_vh } CP-ADV-COND > { IP > { VP >> so_fh }}}"
        )
    )
    assert len(m) == 1

    # Complex condition, incorrect sentence (fh in complex subsentence, fh in conditional subtree)
    s = r.parse_single(
        "Ég hefði farið út ef Jón, sem Anna elskaði heitt, hafði hegðað sér vel."
    )
    # There are two potential attachments of the CP-ADV-COND subtree
    m = list(
        s.tree.all_matches(
            "VP > { VP > { so_vh } CP-ADV-COND > { IP > { VP >> so_fh }}}"
        )
    ) + list(
        s.tree.all_matches(
            " IP > { VP > { VP > { so_vh } } CP-ADV-COND > { IP > { VP >> so_fh }}}"
        )
    )
    assert len(m) == 1

    # Complex condition, incorrect sentence (vh in complex subsentence, fh in conditional subtree)
    s = r.parse_single(
        "Ég hefði farið út ef Jón, sem Anna hefði elskað heitt, hafði hegðað sér vel."
    )
    # There are two potential attachments of the CP-ADV-COND subtree
    m = list(
        s.tree.all_matches(
            "VP > { VP > { so_vh } CP-ADV-COND > { IP > { VP >> so_fh }}}"
        )
    ) + list(
        s.tree.all_matches(
            "IP > { VP > { VP > { so_vh } } CP-ADV-COND > { IP > { VP >> so_fh }}}"
        )
    )
    assert len(m) == 1

    # Complex condition, correct sentence (fh in complex subsentence, vh in conditional subtree)
    s = r.parse_single(
        "Ég hefði farið út ef Jón, sem Anna elskaði heitt, hefði hegðað sér vel."
    )
    # There are two potential attachments of the CP-ADV-COND subtree
    m = list(
        s.tree.all_matches(
            "VP > { VP > { so_vh } CP-ADV-COND > { IP > { VP >> so_fh }}}"
        )
    ) + list(
        s.tree.all_matches(
            "IP > { VP > { VP > { so_vh } } CP-ADV-COND > { IP > { VP >> so_fh }}}"
        )
    )
    assert len(m) == 0

    # Complex condition, correct sentence (vh in complex subsentence, vh in conditional subtree)
    s = r.parse_single(
        "Ég hefði farið út ef Jón, sem Anna hefði elskað heitt, hefði hegðað sér vel."
    )
    # There are two potential attachments of the CP-ADV-COND subtree
    m = list(
        s.tree.all_matches(
            "VP > { VP > { so_vh } CP-ADV-COND > { IP > { VP >> so_fh }}}"
        )
    ) + list(
        s.tree.all_matches(
            "IP > { VP > { VP > { so_vh } } CP-ADV-COND > { IP > { VP >> so_fh }}}"
        )
    )
    assert len(m) == 0
