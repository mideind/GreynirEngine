# type: ignore
"""

    test_original.py

    Tests for Greynir module

    Copyright (C) 2022 Miðeind ehf.
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
from reynir.bintokenizer import tokenize


@pytest.fixture(scope="module")
def r():
    """Provide a module-scoped Greynir instance as a test fixture"""
    r = Greynir()
    yield r
    # Do teardown here
    r.__class__.cleanup()


def test_original(r: Greynir) -> None:

    s = "Ég keypti     1000     EUR þann   23.   5. 2011 og græddi   10,5   %  ."
    tlist = list(tokenize(s))
    assert sum(len(t.original or "") for t in tlist) == len(s)

    s = "   Friðjón    Pálsson hitti Friðbert   \tJ.   Ástráðsson í gær."
    tlist = list(tokenize(s))
    assert sum(len(t.original or "") for t in tlist) == len(s)

    s = " \t Casey   Holdman  \n  og   Luke    Skywalker   fóru saman   á bar  ."
    tlist = list(tokenize(s))
    assert sum(len(t.original or "") for t in tlist) == len(s)

    s = "  Hver á    USD   5,75  sem ég fann í  grasinu með   5,558   prósent?"
    tlist = list(tokenize(s))
    assert sum(len(t.original or "") for t in tlist) == len(s)

    s = "  Virkjunin var  \t 600    MW  og var á Reynimel  40C  í Reykjavík  ."
    tlist = list(tokenize(s))
    assert sum(len(t.original or "") for t in tlist) == len(s)

    s = "  Katrín   Júlíusdóttir   var   iðnaðar-  \n\t  og \t\t  viðskiptaráðherra"
    tlist = list(tokenize(s))
    assert sum(len(t.original or "") for t in tlist) == len(s)

    s = "  Friðbert  Marsillíus   Jónsson  keypti hlutabréf  í   Eimskip   hf.  fyrir    100    milljónir   í gær"
    tlist = list(tokenize(s))
    assert sum(len(t.original or "") for t in tlist) == len(s)

    s = "  Jens \tStoltenberg   keypti hlutabréf  nú   síðdegis  fyrir   100   milljónir  króna  kl. 12:30 30.   júlí 2002  og Jens   er stoltur   af því."
    tlist = list(tokenize(s))
    assert sum(len(t.original or "") for t in tlist) == len(s)

    s = "Gengi  danskrar  krónu  féll um   2.000    EUR  kl.   14:00   30.  desember  ."
    tlist = list(tokenize(s))
    assert sum(len(t.original or "") for t in tlist) == len(s)

    s = "Dómsmála-  ,    iðnaðar-   og  viðskiptaráðherra gerði víðreist um landið"
    tlist = list(tokenize(s))
    assert sum(len(t.original or "") for t in tlist) == len(s)

    s = "  Dagur   Bergþóruson   Eggertsson    hefur verið  farsæll borgarstjóri ."
    tlist = list(tokenize(s))
    assert sum(len(t.original or "") for t in tlist) == len(s)

    s = "  Formaður framkvæmdastjórnarinnar er Ursula  \t\t   van  der    Leyen  ."
    tlist = list(tokenize(s))
    assert sum(len(t.original or "") for t in tlist) == len(s)

    s = "  Angela   Merkel   hefur   lengi   vel  verið kanslari   V-Þýskalands ."
    tlist = list(tokenize(s))
    assert sum(len(t.original or "") for t in tlist) == len(s)


if __name__ == "__main__":
    # When invoked as a main module, do a verbose test
    from reynir import Greynir

    greynir = Greynir()
    test_original(greynir)
    greynir.__class__.cleanup()
